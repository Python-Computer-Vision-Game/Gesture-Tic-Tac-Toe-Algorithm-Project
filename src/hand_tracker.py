"""Camera capture + MediaPipe hand tracking (FR-03, FR-04).

Camera       - reads the webcam on a background thread (always the newest frame)
HandTracker  - MediaPipe hand landmarks -> list of Hand objects

MediaPipe 1.x removed the old `mp.solutions.hands` API, so HandTracker uses the
Tasks API (HandLandmarker) first and falls back to the legacy API only if the
Tasks API is unavailable (older MediaPipe 0.10.x installs).
"""
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass

import cv2

from . import config as cfg

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/1/hand_landmarker.task")
MODEL_PATH = cfg.MODEL_DIR / "hand_landmarker.task"

# Landmark index pairs drawn as the hand "skeleton" in debug mode.
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10),
    (10, 11), (11, 12), (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (17, 18),
    (18, 19), (19, 20), (0, 17),
]
WRIST, THUMB_TIP, INDEX_PIP, INDEX_TIP, MIDDLE_MCP = 0, 4, 6, 8, 9


# =============================================================== camera
class Camera:
    """Webcam reader. A background thread keeps grabbing frames so the game loop
    never waits on the camera and always gets the newest picture (lower latency)."""

    def __init__(self, index=cfg.CAMERA_INDEX, width=cfg.CAMERA_W, height=cfg.CAMERA_H,
                 mirror=cfg.MIRROR_CAMERA):
        self.index, self.width, self.height, self.mirror = index, width, height, mirror
        self.cap = None
        self._frame = None
        self._lock = threading.Lock()
        self._new_frame = threading.Event()
        self._running = False
        self._thread = None

    @property
    def is_open(self) -> bool:
        return self.cap is not None and self._running

    def open(self) -> bool:
        """Try to open the camera. Returns False (never raises) if unavailable."""
        self.release()
        backends = []
        if isinstance(self.index, int) and sys.platform.startswith("win"):
            backends.append(cv2.CAP_DSHOW)            # fastest/most reliable on Windows
        backends.append(cv2.CAP_ANY)
        for backend in backends:
            try:
                cap = cv2.VideoCapture(self.index, backend)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    ok, frame = cap.read()
                    if ok and frame is not None:
                        self.cap = cap
                        self._store(frame)
                        self._running = True
                        self._thread = threading.Thread(target=self._loop, daemon=True)
                        self._thread.start()
                        return True
                cap.release()
            except Exception:
                pass
        return False

    def _store(self, frame):
        if self.mirror:
            frame = cv2.flip(frame, 1)
        with self._lock:
            self._frame = frame
        self._new_frame.set()

    def _loop(self):
        while self._running:
            ok, frame = self.cap.read()
            if ok and frame is not None:
                self._store(frame)
            else:
                time.sleep(0.01)                      # camera hiccup: read() will return None

    def read(self):
        """Newest BGR frame (mirrored), or None if no new frame arrived within 100 ms."""
        if not self._new_frame.wait(0.1):
            return None
        self._new_frame.clear()
        with self._lock:
            return self._frame

    def release(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self._new_frame.clear()


# =============================================================== hand tracking
@dataclass
class Hand:
    landmarks: list          # 21 (x, y) pairs, normalised 0..1 in the (mirrored) frame


def ensure_model():
    """Download the hand model once (about 7 MB) if it is not already on disk."""
    if MODEL_PATH.exists() and MODEL_PATH.stat().st_size > 1_000_000:
        return MODEL_PATH
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading hand model to {MODEL_PATH} ...")
    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    except Exception as exc:
        raise RuntimeError(
            "Could not download the hand model.\n"
            f"Download it manually from:\n  {MODEL_URL}\n"
            f"and save it as:\n  {MODEL_PATH}\n({exc})") from exc
    return MODEL_PATH


class HandTracker:
    def __init__(self, max_hands=1, detect_conf=0.6, track_conf=0.5):
        import mediapipe as mp
        self._mp = mp
        self.detect_conf, self.track_conf = detect_conf, track_conf
        self.max_hands = max_hands
        self.backend = None
        self._last_ts = 0
        self._build()

    def _build(self):
        try:
            self._init_tasks()
        except Exception as tasks_error:
            if not self._init_legacy():
                raise tasks_error

    def _init_tasks(self):
        from mediapipe.tasks.python import BaseOptions, vision
        options = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_buffer=ensure_model().read_bytes()),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=self.max_hands,
            min_hand_detection_confidence=self.detect_conf,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=self.track_conf)
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self.backend = "tasks"

    def _init_legacy(self) -> bool:
        try:
            self._hands = self._mp.solutions.hands.Hands(
                static_image_mode=False, max_num_hands=self.max_hands, model_complexity=0,
                min_detection_confidence=self.detect_conf, min_tracking_confidence=self.track_conf)
            self.backend = "legacy"
            return True
        except Exception:
            return False

    def set_max_hands(self, n):
        """1 hand is faster; 2 hands are only needed when player zones are on."""
        if n != self.max_hands:
            self.close()
            self.max_hands = n
            self._build()

    def process(self, frame_bgr):
        """Return a list of Hand (possibly empty). Never raises on a bad frame."""
        if frame_bgr is None:
            return []
        try:
            h, w = frame_bgr.shape[:2]
            if w > cfg.TRACK_WIDTH:
                frame_bgr = cv2.resize(frame_bgr, (cfg.TRACK_WIDTH, int(h * cfg.TRACK_WIDTH / w)),
                                       interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            if self.backend == "tasks":
                image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
                ts = max(int(time.monotonic() * 1000), self._last_ts + 1)   # must increase
                self._last_ts = ts
                result = self._landmarker.detect_for_video(image, ts)
                return [Hand([(p.x, p.y) for p in hand]) for hand in result.hand_landmarks]
            result = self._hands.process(rgb)
            return [Hand([(p.x, p.y) for p in hand.landmark])
                    for hand in (result.multi_hand_landmarks or [])]
        except Exception:
            return []           # temporary detection failure = "no hands" (FR-14)

    def close(self):
        try:
            if self.backend == "tasks":
                self._landmarker.close()
            elif self.backend == "legacy":
                self._hands.close()
        except Exception:
            pass
