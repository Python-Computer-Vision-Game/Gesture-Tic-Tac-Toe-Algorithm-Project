import unittest
from src.board import Board, X, O, EMPTY, index_to_rc, rc_to_index


class TestBoard(unittest.TestCase):
    def test_starts_empty(self):
        b = Board()
        self.assertTrue(all(c == EMPTY for row in b.grid for c in row))

    def test_place_and_read(self):
        b = Board()
        self.assertTrue(b.place(1, 1, X))
        self.assertEqual(b.get(1, 1), X)

    def test_cannot_overwrite_occupied_cell(self):          # Invalid Move Test
        b = Board()
        b.place(0, 0, X)
        self.assertFalse(b.place(0, 0, O))
        self.assertEqual(b.get(0, 0), X)

    def test_rejects_bad_input(self):
        b = Board()
        self.assertFalse(b.place(3, 0, X))
        self.assertFalse(b.place(0, -1, X))
        self.assertFalse(b.place(0, 0, "Z"))

    def test_full_and_reset(self):
        b = Board()
        for r in range(3):
            for c in range(3):
                b.place(r, c, X)
        self.assertTrue(b.is_full())
        b.reset()                                            # Reset Test
        self.assertFalse(b.is_full())
        self.assertTrue(b.is_empty(2, 2))

    def test_index_conversion(self):
        for i in range(9):
            self.assertEqual(rc_to_index(*index_to_rc(i)), i)
        self.assertEqual(index_to_rc(5), (1, 2))


if __name__ == "__main__":
    unittest.main()
