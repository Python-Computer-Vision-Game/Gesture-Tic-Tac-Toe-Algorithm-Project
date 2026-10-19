"""Main entry point and execution loop for Gesture Tic-Tac-Toe."""
import sys
import time
import argparse
import cv2

from src import config as cfg
from src.audio_manager import AudioManager
from src.game_state import Game, GameState as ST
from src.gesture_detector import GestureDetector, MouseInput
from src.hand_tracker import Camera, HandTracker


def parse_args():
    p = argparse.ArgumentParser(description="Gesture Tic-Tac-Toe")
    p.add_argument("--camera", type=int, default=cfg.CAMERA_INDEX, help="Camera device index (default 0)")
    p.add_argument("--mouse", action="store_true", help="Enable mouse control mode (no webcam required)")
    p.add_argument("--debug", action="store_true", help="Show landmarks and FPS overlay")
    p.add_argument("--no-sound", action="store_true", help="Disable audio effects")
    return p.parse_args()


def run(args):
    settings = cfg.Settings(debug_landmarks=args.debug, sound=not args.no_sound)
    game = Game(settings, AudioManager(settings, enabled=not args.no_sound))
    game.mouse_mode = args.mouse

    camera, tracker, detector, mouse = None, None, GestureDetector(settings), MouseInput()

    def open_camera():
        nonlocal camera, tracker
        game.error_detail = ""
        camera = Camera(args.camera)
        game.camera_ok = camera.open()
        if not game.camera_ok:
            game.error_detail = f"Camera index {args.camera} could not be opened"
            return
        try:
            tracker = tracker or HandTracker()
        except Exception as exc:
            game.camera_ok = False
            game.error_detail = str(exc).splitlines()[0]
            print("Hand tracker initialization error:\n", exc)

    if not args.mouse:
        open_camera()

    # Window creation
    cv2.namedWindow(cfg.WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(cfg.WINDOW_NAME, cfg.WINDOW_W, cfg.WINDOW_H)
    cv2.setMouseCallback(cfg.WINDOW_NAME, mouse.on_mouse)

    lost_since, last_time, fps = None, time.monotonic(), 0.0

    try:
        while game.running:
            now = time.monotonic()
            frame = None

            # Retry camera reconnection if requested
            if game.retry_camera:
                game.retry_camera = False
                open_camera()
                if game.camera_ok:
                    game.goto(ST.MENU)

            # Read webcam frame
            if not game.mouse_mode and camera is not None and camera.is_open:
                frame = camera.read()
                if frame is None:
                    lost_since = lost_since or now
                    if now - lost_since > 2.0 and game.engine.state in (ST.SETUP, ST.PLAYING):
                        game.camera_ok = False
                        game.error_detail = "The camera feed disconnected or stopped sending frames"
                        game.goto(ST.CAMERA_ERROR)
                else:
                    lost_since = None

            # Determine input pointers
            if game.mouse_mode:
                pointers = mouse.update()
            elif frame is not None and tracker is not None:
                tracker.set_max_hands(2 if settings.use_player_zones else 1)
                pointers = detector.update(tracker.process(frame))
            else:
                pointers = []

            # Step game logic and render frame
            img = game.step(frame, pointers, now)

            # FPS counter overlay
            if settings.debug_landmarks:
                fps = 0.9 * fps + 0.1 / max(now - last_time, 1e-6)
                cv2.putText(
                    img,
                    f"{fps:4.0f} FPS",
                    (cfg.WINDOW_W - 130, cfg.WINDOW_H - 15),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (200, 200, 200),
                    1,
                    cv2.LINE_AA,
                )

            last_time = now

            # Display window
            cv2.imshow(cfg.WINDOW_NAME, img)
            game.on_key(cv2.waitKey(1) & 0xFF)

            # Detect window close button (X button)
            if cv2.getWindowProperty(cfg.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break

    finally:
        # Resource cleanup
        if camera is not None:
            camera.release()
        if tracker is not None:
            tracker.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    run(parse_args())