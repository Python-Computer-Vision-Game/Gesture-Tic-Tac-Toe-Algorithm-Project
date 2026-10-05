"""3x3 board + win/draw detection (FR-07, FR-08, FR-09, section 8)."""
EMPTY, X, O = "", "X", "O"

# The 8 winning lines as (row, col) cells: 3 rows, 3 columns, 2 diagonals.
WIN_LINES = (
    ((0, 0), (0, 1), (0, 2)), ((1, 0), (1, 1), (1, 2)), ((2, 0), (2, 1), (2, 2)),
    ((0, 0), (1, 0), (2, 0)), ((0, 1), (1, 1), (2, 1)), ((0, 2), (1, 2), (2, 2)),
    ((0, 0), (1, 1), (2, 2)), ((0, 2), (1, 1), (2, 0)),
)


def index_to_rc(index: int):
    return divmod(index, 3)          # cell index = row * 3 + column


def rc_to_index(row: int, col: int) -> int:
    return row * 3 + col


class Board:
    SIZE = 3

    def __init__(self):
        self.reset()

    def reset(self):
        self.grid = [[EMPTY] * self.SIZE for _ in range(self.SIZE)]

    def in_bounds(self, row, col) -> bool:
        return 0 <= row < self.SIZE and 0 <= col < self.SIZE

    def get(self, row, col):
        return self.grid[row][col]

    def is_empty(self, row, col) -> bool:
        return self.in_bounds(row, col) and self.grid[row][col] == EMPTY

    def place(self, row, col, symbol) -> bool:
        """Put a symbol on an empty cell. Never overwrites (FR-07, FR-14)."""
        if symbol not in (X, O) or not self.is_empty(row, col):
            return False
        self.grid[row][col] = symbol
        return True

    def is_full(self) -> bool:
        return all(cell != EMPTY for row in self.grid for cell in row)

    def find_winner(self):
        """Return (symbol, line) for the first complete line, else (None, None)."""
        for line in WIN_LINES:
            a, b, c = (self.grid[r][col] for r, col in line)
            if a != EMPTY and a == b == c:
                return a, line
        return None, None

    def is_draw(self) -> bool:
        return self.is_full() and self.find_winner()[0] is None

    def to_list(self):
        return [row[:] for row in self.grid]
