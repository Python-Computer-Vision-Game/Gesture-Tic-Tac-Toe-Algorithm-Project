"""Gesture Tic-Tac-Toe - entry point.

    python main.py             play with the webcam
    python main.py --mouse     no camera? hover with the mouse instead
    python main.py --debug     show hand landmarks and FPS
    python main.py --camera 1  use another camera
"""
from src.game_state import parse_args, run

if __name__ == "__main__":
    run(parse_args())
