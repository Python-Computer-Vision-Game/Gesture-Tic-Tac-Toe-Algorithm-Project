import unittest
from src.score_manager import ScoreManager


class TestScore(unittest.TestCase):
    def test_win_adds_point_to_winner_only(self):
        s = ScoreManager()
        s.record_win(1)
        self.assertEqual(s.wins, [0, 1])

    def test_draw_changes_no_score(self):
        s = ScoreManager()
        s.record_draw()
        self.assertEqual(s.wins, [0, 0])
        self.assertEqual(s.draws, 1)
        self.assertEqual(s.rounds_played, 1)

    def test_multiple_rounds_and_reset(self):
        s = ScoreManager()
        s.record_win(0); s.record_win(0); s.record_win(1); s.record_draw()
        self.assertEqual((s.wins, s.draws, s.rounds_played), ([2, 1], 1, 4))
        s.reset()
        self.assertEqual((s.wins, s.draws, s.rounds_played), ([0, 0], 0, 0))


if __name__ == "__main__":
    unittest.main()
