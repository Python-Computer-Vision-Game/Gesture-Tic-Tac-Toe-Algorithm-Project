"""End-to-end test: drives the whole App with simulated fingertips (no camera needed)."""
import unittest

import numpy as np

from src.game_state import Game, GameState as ST
from src import config as cfg
from src.hand_tracker import Camera
from src.config import Settings
from src.gesture_detector import Pointer


def cell_center(index):
    row, col = divmod(index, 3)
    return cfg.BOARD_X + col * 160 + 80, cfg.BOARD_Y + row * 160 + 80


class Driver:
    def __init__(self, settings=None):
        self.app = Game(settings or Settings())
        self.t = 100.0
        self.frames = []

    def hold(self, point, seconds, owner=None, fps=30):
        for _ in range(int(seconds * fps)):
            self.t += 1 / fps
            ptrs = [] if point is None else [Pointer(point[0], point[1], owner)]
            self.frames.append(self.app.step(None, ptrs, self.t))

    def click(self, point, seconds=1.2, owner=None):
        self.hold(point, seconds, owner)

    def start_game(self):
        self.click((640, 273))                    # "Start Game" button
        assert self.app.engine.state == ST.SETUP, self.app.engine.state
        self.hold((100, 100), 5.0)                # hand visible: ready (1 s) + countdown (3 s)
        assert self.app.engine.state == ST.PLAYING, self.app.engine.state
        self.hold(None, 0.6)                      # let the selector forget the finger


class TestFlow(unittest.TestCase):
    def test_full_game_x_wins_and_score_updates(self):
        d = Driver()
        d.start_game()
        for cell in (0, 3, 1, 4, 2):              # X: 0,1,2 (top row)  O: 3,4
            d.click(cell_center(cell))
        e = d.app.engine
        self.assertEqual(e.state, ST.ROUND_RESULT)
        self.assertEqual(e.scores.wins, [1, 0])
        self.assertEqual(e.winning_line, ((0, 0), (0, 1), (0, 2)))

    def test_occupied_cell_rejected_with_message_and_turn_kept(self):
        d = Driver()
        d.start_game()
        d.click(cell_center(0))                   # X
        d.hold((100, 100), 0.3)                   # finger moves away ...
        d.click(cell_center(0))                   # ... O points at the occupied cell
        e = d.app.engine
        self.assertEqual(e.board.get(0, 0), "X")
        self.assertEqual(e.turns.current.symbol, "O")
        self.assertIsNotNone(d.app.toast)                         # "already taken" message shown

    def test_finger_resting_on_placed_cell_does_not_trigger_error(self):
        d = Driver()
        d.start_game()
        d.click(cell_center(4), seconds=4.0)      # keep finger there for 4 s
        self.assertIsNone(d.app.toast)                            # no error message appeared
        self.assertEqual(d.app.engine.board.get(1, 1), "X")

    def test_brief_hand_loss_does_not_crash_or_cancel(self):
        d = Driver()
        d.start_game()
        d.hold(cell_center(8), 0.5)
        d.hold(None, 0.2)                          # hand lost
        d.hold(cell_center(8), 0.7)
        self.assertEqual(d.app.engine.board.get(2, 2), "X")

    def test_long_hand_loss_resets_progress(self):
        d = Driver()
        d.start_game()
        d.hold(cell_center(8), 0.8)
        d.hold(None, 1.0)
        d.hold(cell_center(8), 0.4)
        self.assertEqual(d.app.engine.board.get(2, 2), "")

    def test_only_active_players_zone_can_move(self):      # Turn Test with zones
        d = Driver(Settings(use_player_zones=True))
        d.app.mouse_mode = False
        d.t += 0
        # Start: need both zones present
        for _ in range(int(0.1 * 30)):
            d.t += 1 / 30
            d.app.step(None, [Pointer(300, 100, 0), Pointer(900, 100, 1)], d.t)
        d.click((640, 273), owner=0)
        for _ in range(int(5 * 30)):
            d.t += 1 / 30
            d.app.step(None, [Pointer(300, 100, 0), Pointer(900, 100, 1)], d.t)
        self.assertEqual(d.app.engine.state, ST.PLAYING)
        d.hold(None, 0.6)
        d.hold(cell_center(4), 1.5, owner=1)       # Player 2 points during Player 1's turn
        self.assertEqual(d.app.engine.board.get(1, 1), "")
        d.hold(cell_center(4), 1.5, owner=0)       # Player 1 points
        self.assertEqual(d.app.engine.board.get(1, 1), "X")

    def test_next_round_button_and_menu(self):
        d = Driver()
        d.start_game()
        for cell in (0, 3, 1, 4, 2):
            d.click(cell_center(cell))
        d.click((370, 675))                        # "Next Round"
        e = d.app.engine
        self.assertEqual(e.state, ST.PLAYING)
        self.assertEqual(e.scores.wins, [1, 0])    # score preserved
        self.assertTrue(all(c == "" for r in e.board.grid for c in r))

    def test_start_without_camera_shows_error_screen(self):
        d = Driver()
        d.app.camera_ok = False
        d.click((640, 273))
        self.assertEqual(d.app.engine.state, ST.CAMERA_ERROR)
        d.app.on_key(27)
        self.assertEqual(d.app.engine.state, ST.MENU)

    def test_settings_screen_changes_options(self):
        d = Driver()
        d.click((640, 235 + 2 * 94 + 38))          # "Settings"
        self.assertEqual(d.app.engine.state, ST.SETTINGS)
        d.click((400, 190), seconds=1.2)           # dwell time button
        self.assertEqual(d.app.settings.dwell_time, 1.2)
        d.click((880, 190), seconds=1.4)           # select-by button -> pinch
        self.assertEqual(d.app.settings.selection_mode, "pinch")


class TestCameraMissing(unittest.TestCase):
    def test_camera_open_never_raises_when_missing(self):
        cam = Camera(index=97)                     # an index that does not exist
        self.assertFalse(cam.open())
        self.assertIsNone(cam.read())
        cam.release()


if __name__ == "__main__":
    unittest.main()


class TestThreadedCamera(unittest.TestCase):
    def test_reads_newest_frames_from_a_video_and_releases_cleanly(self):
        import os
        import tempfile
        import cv2
        path = os.path.join(tempfile.mkdtemp(), "fake_cam.avi")
        out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 30, (320, 180))
        for i in range(60):
            frame = np.zeros((180, 320, 3), np.uint8)
            frame[:, :20] = (0, 0, 255)                 # red bar on the LEFT edge
            out.write(frame)
        out.release()

        cam = Camera(index=path, width=320, height=180, mirror=True)
        self.assertTrue(cam.open())
        frame = cam.read()
        self.assertIsNotNone(frame)
        self.assertGreater(int(frame[90, 310, 2]), 150)  # mirrored: red bar is now on the RIGHT
        self.assertLess(int(frame[90, 5, 2]), 50)
        cam.release()
        self.assertFalse(cam.is_open)
