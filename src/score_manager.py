"""Match scoring across rounds (FR-10)."""


class ScoreManager:
    def __init__(self):
        self.reset()

    def reset(self):
        self.wins = [0, 0]
        self.draws = 0
        self.rounds_played = 0

    def record_win(self, player_index: int):
        self.wins[player_index] += 1
        self.rounds_played += 1

    def record_draw(self):
        self.draws += 1               # a draw never changes either player's score
        self.rounds_played += 1
