"""Project-wide constants, user-adjustable settings and UI labels.

Covers FR-02 (player names), FR-03 (camera resolution / mirror),
FR-05 (dwell time) and FR-11 (configurable first player).
"""
from dataclasses import dataclass, field
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT_DIR / "assets" / "models"

# ---- window / camera -------------------------------------------------------
WINDOW_NAME = "Gesture Tic-Tac-Toe"
WINDOW_W, WINDOW_H = 1280, 720
CAMERA_INDEX = 0
CAMERA_W, CAMERA_H = 1280, 720
MIRROR_CAMERA = True
TRACK_WIDTH = 480            # frames are shrunk to this width before hand tracking (speed)

# ---- board region in window pixels (section 6) -----------------------------
BOARD_SIZE = 480
BOARD_X = (WINDOW_W - BOARD_SIZE) // 2
BOARD_Y = 150

# ---- selection tuning ------------------------------------------------------
DWELL_CHOICES = (0.8, 1.0, 1.2, 1.5)   # seconds, section 5 Mode A
SELECT_HYSTERESIS_PX = 20              # must move this far past a border to change target
LOST_GRACE_S = 0.35                    # hand may vanish this long without losing progress
SMOOTHING_ALPHA = 0.45                 # 0..1, higher = more responsive, lower = smoother
PINCH_ON = 0.30                        # thumb-index gap / hand size to start a pinch
PINCH_OFF = 0.45                       # ... and to release it (hysteresis)
REQUIRE_POINTING_POSE = False          # True = ignore hands that are not pointing

# ---- game flow -------------------------------------------------------------
SETUP_READY_S = 1.0          # hand(s) must be visible this long before the countdown
COUNTDOWN_S = 3
TOAST_S = 1.6
MAX_NAME_LEN = 12


@dataclass
class Settings:
    """Options the player can change from the Settings screen."""
    player_names: list = field(default_factory=lambda: ["Player 1", "Player 2"])
    first_player: int = 0            # 0 = Player 1 (X), 1 = Player 2 (O)
    dwell_time: float = 1.0
    selection_mode: str = "dwell"    # "dwell" (Mode A) or "pinch" (Mode B)
    use_player_zones: bool = False   # left half of camera = P1, right half = P2
    debug_landmarks: bool = False
    keep_score_on_new_round: bool = True


# ---- UI text (section 13: English now, Khmer can be added as another dict) --
LANGUAGE = "en"
LABELS = {
    "en": {
        "title": "GESTURE TIC-TAC-TOE",
        "subtitle": "Computer Vision  -  2 Players  -  No touching",
        "start": "Start Game",
        "instructions": "Instructions",
        "settings": "Settings",
        "exit": "Exit",
        "back": "Back",
        "restart": "Restart Round",
        "menu": "Main Menu",
        "next_round": "Next Round",
        "reset_scores": "Reset Scores",
        "your_turn": "YOUR TURN",
        "wins": "wins!",
        "draw": "It's a draw!",
        "taken": "That cell is already taken!",
        "score": "Score",
        "draws": "Draws",
        "round": "Round",
        "hint_dwell": "Point at a button and hold still to select it",
        "hint_pinch": "Point at a button and pinch thumb + index to select it",
    },
}


def t(key: str) -> str:
    return LABELS[LANGUAGE].get(key, key)
