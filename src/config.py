
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
TRACK_WIDTH = 480          

# ---- board region in window pixels (section 6) -----------------------------
BOARD_SIZE = 480
BOARD_X = (WINDOW_W - BOARD_SIZE) // 2
BOARD_Y = 150

# ---- selection tuning ------------------------------------------------------
DWELL_CHOICES = (0.6, 0.8, 1.0, 1.2, 1.5) 
SELECT_HYSTERESIS_PX = 28            
LOST_GRACE_S = 0.55               
SMOOTHING_ALPHA = 0.35                 
PINCH_ON = 0.30
PINCH_OFF = 0.45
REQUIRE_POINTING_POSE = False       

# ---- game flow -------------------------------------------------------------
SETUP_READY_S = 1.0         
COUNTDOWN_S = 3
TOAST_S = 1.6
MAX_NAME_LEN = 12


@dataclass
class Settings:
    """Options the player can change from the Settings screen."""
    player_names: list = field(default_factory=lambda: ["Player 1", "Player 2"])
    first_player: int = 0            
    dwell_time: float = 1.0
    selection_mode: str = "dwell"    
    use_player_zones: bool = False   
    debug_landmarks: bool = False
    sound: bool = True
    keep_score_on_new_round: bool = True


# ---- UI text (section 13: English now, Khmer can be added as another dict) --
LANGUAGE = "en"
LABELS = {
    "en": {
        "title": "GESTURE TIC-TAC-TOE",
        "subtitle": "Computer Vision  ·  2 Players  ·  No touching",
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