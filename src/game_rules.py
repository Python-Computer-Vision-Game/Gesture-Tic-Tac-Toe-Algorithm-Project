"""Move validation + result checking (FR-06, FR-08, FR-09)."""
from enum import Enum

from .board import WIN_LINES  # noqa: F401  (re-exported for convenience)


class RoundResult(Enum):
    ONGOING = "ongoing"
    WIN = "win"
    DRAW = "draw"


def is_valid_move(board, row, col) -> bool:
    return board.is_empty(row, col)


def check_winner(board):
    return board.find_winner()


def is_draw(board) -> bool:
    return board.is_draw()


def evaluate(board):
    """Return (RoundResult, winning_symbol, winning_line)."""
    symbol, line = board.find_winner()
    if symbol:
        return RoundResult.WIN, symbol, line
    if board.is_full():
        return RoundResult.DRAW, None, None
    return RoundResult.ONGOING, None, None
