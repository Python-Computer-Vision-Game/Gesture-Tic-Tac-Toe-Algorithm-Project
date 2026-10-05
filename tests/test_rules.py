import unittest
from src.board import Board, X, O
from src.game_rules import WIN_LINES, check_winner, is_draw, evaluate, RoundResult


def board_from(rows):
    b = Board()
    for r in range(3):
        for c in range(3):
            if rows[r][c]:
                b.place(r, c, rows[r][c])
    return b


class TestRules(unittest.TestCase):
    def test_there_are_eight_lines(self):
        self.assertEqual(len(WIN_LINES), 8)

    def test_every_line_wins_for_both_symbols(self):        # rows + columns + diagonals
        for line in WIN_LINES:
            for sym in (X, O):
                b = Board()
                for r, c in line:
                    b.place(r, c, sym)
                winner, found = check_winner(b)
                self.assertEqual(winner, sym)
                self.assertEqual(found, line)

    def test_two_in_a_row_is_not_a_win(self):
        b = board_from([[X, X, ""], ["", "", ""], ["", "", ""]])
        self.assertEqual(check_winner(b), (None, None))
        self.assertEqual(evaluate(b)[0], RoundResult.ONGOING)

    def test_draw(self):                                     # Draw Test
        b = board_from([[X, O, X], [X, O, O], [O, X, X]])
        self.assertTrue(is_draw(b))
        self.assertEqual(evaluate(b)[0], RoundResult.DRAW)

    def test_full_board_with_winner_is_not_a_draw(self):
        b = board_from([[X, X, X], [O, O, X], [O, X, O]])
        self.assertFalse(is_draw(b))
        self.assertEqual(evaluate(b)[0], RoundResult.WIN)


if __name__ == "__main__":
    unittest.main()
