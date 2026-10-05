import unittest
from src.config import Settings
from src.game_state import GameEngine, GameState, MoveOutcome, InvalidTransition


def started(first=0):
    e = GameEngine(Settings(first_player=first))
    e.go(GameState.SETUP)
    e.begin_match()
    return e


class TestEngine(unittest.TestCase):
    def test_cannot_play_before_game_starts(self):
        e = GameEngine(Settings())
        self.assertEqual(e.play(0, 0), MoveOutcome.REJECTED_STATE)

    def test_turns_alternate_only_after_valid_move(self):    # Turn Test
        e = started()
        self.assertEqual(e.turns.current.symbol, "X")
        self.assertEqual(e.play(0, 0), MoveOutcome.PLACED)
        self.assertEqual(e.turns.current.symbol, "O")
        self.assertEqual(e.play(0, 0), MoveOutcome.INVALID_CELL)   # occupied
        self.assertEqual(e.turns.current.symbol, "O")               # turn did NOT switch
        self.assertEqual(e.board.get(0, 0), "X")                    # not overwritten

    def test_configurable_first_player(self):
        e = started(first=1)
        self.assertEqual(e.turns.current.symbol, "O")

    def test_win_updates_score_and_stops_play(self):          # Win + Score Test
        e = started()
        for move in [(0, 0), (1, 0), (0, 1), (1, 1)]:
            e.play(*move)
        self.assertEqual(e.play(0, 2), MoveOutcome.WIN)
        self.assertEqual(e.state, GameState.ROUND_RESULT)
        self.assertEqual(e.scores.wins, [1, 0])
        self.assertEqual(e.winning_line, ((0, 0), (0, 1), (0, 2)))
        self.assertEqual(e.play(2, 2), MoveOutcome.REJECTED_STATE)  # gameplay stopped

    def test_draw_gives_nobody_a_point(self):                 # Draw Test
        e = started()
        # X O X / X O O / O X X  (no line)
        for move in [(0, 0), (0, 1), (0, 2), (1, 1), (1, 0), (1, 2), (2, 1), (2, 0)]:
            self.assertEqual(e.play(*move), MoveOutcome.PLACED)
        self.assertEqual(e.play(2, 2), MoveOutcome.DRAW)
        self.assertEqual(e.scores.wins, [0, 0])
        self.assertEqual(e.scores.draws, 1)

    def test_new_round_clears_board_keeps_score(self):        # Reset Test
        e = started()
        for move in [(0, 0), (1, 0), (0, 1), (1, 1), (0, 2)]:
            e.play(*move)
        e.new_round(keep_score=True)
        self.assertEqual(e.state, GameState.PLAYING)
        self.assertTrue(all(c == "" for row in e.board.grid for c in row))
        self.assertEqual(e.scores.wins, [1, 0])
        e.reset_scores()
        self.assertEqual(e.scores.wins, [0, 0])

    def test_illegal_state_jump_is_blocked(self):
        e = GameEngine(Settings())
        with self.assertRaises(InvalidTransition):
            e.go(GameState.ROUND_RESULT)


if __name__ == "__main__":
    unittest.main()
