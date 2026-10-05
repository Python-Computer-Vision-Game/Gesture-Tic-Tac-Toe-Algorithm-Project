"""Turn management (FR-02, FR-11). Player 1 is always X, Player 2 is always O."""
from dataclasses import dataclass

from .board import X, O


@dataclass
class Player:
    name: str
    symbol: str


class TurnManager:
    def __init__(self, names=("Player 1", "Player 2"), first=0):
        self.players = [Player(names[0], X), Player(names[1], O)]
        self.current_index = first

    @property
    def current(self) -> Player:
        return self.players[self.current_index]

    @property
    def other(self) -> Player:
        return self.players[1 - self.current_index]

    def switch(self):
        self.current_index = 1 - self.current_index

    def reset(self, first=0):
        self.current_index = first

    def set_names(self, names):
        for player, name in zip(self.players, names):
            player.name = name

    def index_of(self, symbol) -> int:
        return 0 if symbol == X else 1
