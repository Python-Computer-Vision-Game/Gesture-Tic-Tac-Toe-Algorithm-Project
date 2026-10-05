# Gesture Tic-Tac-Toe

Two-player Tic-Tac-Toe controlled by hand gestures in front of a webcam.
Python + OpenCV + MediaPipe. No touchscreen, no controller.

## Install

```
python -m venv venv
source venv/Scripts/activate        # Git Bash on Windows
python -m pip install -r requirements.txt
```

The first camera run downloads the MediaPipe hand model (~7 MB) into `assets/models/`.
If your network blocks it, download
https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
and save it as `assets/models/hand_landmarker.task`.

## Run

```
python main.py              # webcam
python main.py --mouse      # no camera: hover = point
python main.py --debug      # hand landmarks + FPS
python main.py --camera 1   # another camera
```

## The rules

1. Player 1 is **X** and goes first; Player 2 is **O**. (First player can be changed in Settings.)
2. Players take turns. Only the player whose turn it is can place a mark.
3. Point your index finger at an **empty** cell and hold still until the ring fills.
4. A taken cell is rejected with a message, and the turn does not change.
5. Three in a row (row, column or diagonal) wins the round and scores 1 point.
6. A full board with no line is a draw. Nobody scores.
7. After a round: Next Round (keeps score), Reset Scores, or Main Menu.

Keys: `Esc` back/menu, `Q` quit, `H` landmarks, `R` restart round, `N` next round.

## Project structure

```
main.py                 entry point
src/config.py           settings, colours, constants, UI text
src/board.py            3x3 board + win/draw detection
src/game_rules.py       move validation + result checking
src/turn_manager.py     whose turn it is
src/score_manager.py    match scores
src/hand_tracker.py     camera (threaded) + MediaPipe hand tracking
src/gesture_detector.py landmarks -> pointer, cell mapping, Point & Dwell selection
src/renderer.py         drawing: camera, board, menus, overlays
src/game_state.py       state machine, game engine, screens, main loop
tests/                  unit + end-to-end tests (no camera needed)
```

## Tests

```
python -m unittest discover -s tests -t . -v
```
