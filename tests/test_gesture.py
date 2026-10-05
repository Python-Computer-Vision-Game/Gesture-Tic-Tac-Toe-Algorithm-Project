import unittest
from src.config import Settings
from src.gesture_detector import (CellMapper, GestureDetector, Rect, SelectionManager,
                                  is_pointing, pinch_ratio)
from src.hand_tracker import Hand

BOARD = Rect(400, 150, 480, 480)          # each cell is 160 x 160


def fake_hand(wrist_x=0.5, index_up=True, pinch=False):
    """21 synthetic landmarks (normalised). Wrist low, fingers above it."""
    pts = [(wrist_x, 0.9)] * 21
    pts[9] = (wrist_x, 0.70)                                  # middle knuckle -> hand size 0.2
    pts[6], pts[8] = (wrist_x, 0.62), (wrist_x, 0.30 if index_up else 0.75)
    for pip, tip in ((10, 12), (14, 16), (18, 20)):            # other fingers curled
        pts[pip], pts[tip] = (wrist_x, 0.66), (wrist_x, 0.78)
    pts[4] = (wrist_x + (0.01 if pinch else 0.15), 0.30 if pinch else 0.60)
    return Hand(pts)


class TestMapping(unittest.TestCase):                          # Cell Mapping Test
    def test_all_nine_cells(self):
        m = CellMapper(BOARD)
        for row in range(3):
            for col in range(3):
                x = 400 + col * 160 + 80
                y = 150 + row * 160 + 80
                self.assertEqual(m.cell_at(x, y), (row, col))

    def test_outside_board_selects_nothing(self):
        m = CellMapper(BOARD)
        for p in [(399, 300), (880, 300), (600, 149), (600, 630), (0, 0)]:
            self.assertIsNone(m.cell_at(*p))

    def test_edges_belong_to_correct_cell(self):
        m = CellMapper(BOARD)
        self.assertEqual(m.cell_at(400, 150), (0, 0))
        self.assertEqual(m.cell_at(879, 629), (2, 2))


class TestDwell(unittest.TestCase):                            # Dwell Test
    def setUp(self):
        self.targets = CellMapper(BOARD).all_rects()
        self.sel = SelectionManager(dwell_time=1.0)
        self.centre = (640, 390)                               # cell 4

    def run_for(self, point, start, end, step=0.05):
        t, last = start, None
        while t <= end + 1e-9:
            last = self.sel.update(point, self.targets, t)
            if last.selected:
                return last, t
            t += step
        return last, None

    def test_confirms_after_dwell_time(self):
        res, t = self.run_for(self.centre, 0.0, 1.5)
        self.assertEqual(res.selected, "cell:4")
        self.assertAlmostEqual(t, 1.0, delta=0.06)

    def test_does_not_confirm_early(self):
        res, t = self.run_for(self.centre, 0.0, 0.9)
        self.assertIsNone(t)
        self.assertGreater(res.progress, 0.8)

    def test_fires_once_then_locks_until_pointer_leaves(self):
        res, t = self.run_for(self.centre, 0.0, 1.2)
        res2, t2 = self.run_for(self.centre, t + 0.05, t + 3.0)
        self.assertIsNone(t2)                                  # no repeat while finger stays
        self.sel.update((100, 100), self.targets, t + 3.1)     # leave
        res3, t3 = self.run_for(self.centre, t + 3.2, t + 5.0)
        self.assertEqual(res3.selected, "cell:4")              # works again after leaving

    def test_moving_between_cells_restarts_dwell(self):
        self.run_for(self.centre, 0.0, 0.8)
        res = self.sel.update((470, 390), self.targets, 0.85)  # clearly inside cell 3
        self.assertEqual(res.hover, "cell:3")
        self.assertLess(res.progress, 0.1)

    def test_small_jitter_across_border_keeps_target(self):
        edge = 400 + 160                                        # border between cell 3 and 4
        self.sel.update((edge - 30, 390), self.targets, 0.0)   # in cell 3
        res = self.sel.update((edge + 8, 390), self.targets, 0.1)   # 8 px over, inside hysteresis
        self.assertEqual(res.hover, "cell:3")
        res = self.sel.update((edge + 60, 390), self.targets, 0.2)  # clearly in cell 4
        self.assertEqual(res.hover, "cell:4")

    def test_short_hand_loss_keeps_progress_long_loss_cancels(self):   # Recovery Test
        self.run_for(self.centre, 0.0, 0.5)
        self.sel.update(None, self.targets, 0.55)               # hand lost
        res = self.sel.update(self.centre, self.targets, 0.75)  # back after 0.2 s
        self.assertEqual(res.hover, "cell:4")
        self.assertGreater(res.progress, 0.4)
        self.sel.update(None, self.targets, 1.0)
        self.sel.update(None, self.targets, 1.6)                # lost > grace
        res = self.sel.update(self.centre, self.targets, 1.65)
        self.assertLess(res.progress, 0.1)

    def test_reset_with_lock_ignores_finger_until_it_moves(self):
        self.sel.reset(lock=True)
        res, t = self.run_for(self.centre, 0.0, 3.0)
        self.assertIsNone(t)
        self.sel.update((100, 100), self.targets, 3.1)
        res, t = self.run_for(self.centre, 3.2, 5.0)
        self.assertIsNotNone(t)


class TestPinchMode(unittest.TestCase):
    def test_pinch_selects_on_rising_edge_only(self):
        targets = CellMapper(BOARD).all_rects()
        sel = SelectionManager(mode="pinch")
        c = (640, 390)
        self.assertIsNone(sel.update(c, targets, 0.0, pinching=False).selected)
        self.assertEqual(sel.update(c, targets, 0.1, pinching=True).selected, "cell:4")
        self.assertIsNone(sel.update(c, targets, 0.2, pinching=True).selected)   # held, no repeat


class TestHandGestures(unittest.TestCase):
    def test_pointing_pose(self):
        pts = [(x * 1280, y * 720) for x, y in fake_hand().landmarks]
        self.assertTrue(is_pointing(pts))

    def test_pinch_ratio(self):
        far = [(x * 1280, y * 720) for x, y in fake_hand(pinch=False).landmarks]
        near = [(x * 1280, y * 720) for x, y in fake_hand(pinch=True).landmarks]
        self.assertGreater(pinch_ratio(far), 0.45)
        self.assertLess(pinch_ratio(near), 0.30)

    def test_fingertip_becomes_pixel_pointer(self):
        d = GestureDetector(Settings())
        (p,) = d.update([fake_hand()])
        self.assertAlmostEqual(p.x, 640, delta=1)
        self.assertAlmostEqual(p.y, 0.30 * 720, delta=1)

    def test_player_zones_assign_left_and_right(self):
        d = GestureDetector(Settings(use_player_zones=True))
        ps = d.update([fake_hand(0.75), fake_hand(0.25)])
        self.assertEqual(sorted(p.owner for p in ps), [0, 1])
        left = [p for p in ps if p.owner == 0][0]
        self.assertLess(left.x, 640)

    def test_no_hands_gives_no_pointers(self):                 # Recovery Test
        self.assertEqual(GestureDetector(Settings()).update([]), [])


if __name__ == "__main__":
    unittest.main()
