
import math
from dataclasses import dataclass
from typing import Optional

from . import config as cfg
from .hand_tracker import MIDDLE_MCP, THUMB_TIP, INDEX_TIP, WRIST, Hand


@dataclass
class Pointer:
    x: float
    y: float
    owner: Optional[int] = None      # 0 / 1 when player zones are on, else None
    pinching: bool = False
    pointing: bool = True
    ambiguous: bool = False          # unclear gesture -> shown but ignored
    hand: Optional[Hand] = None


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _extended(pts, tip, pip, factor):
    return _dist(pts[tip], pts[WRIST]) > _dist(pts[pip], pts[WRIST]) * factor


def is_pointing(pts) -> bool:
    # Index tip farther from wrist than the knuckle (finger is extended)
    index_up = _extended(pts, 8, 6, 1.08)
    return index_up


def pinch_ratio(pts) -> float:
    size = _dist(pts[WRIST], pts[MIDDLE_MCP]) or 1e-6
    return _dist(pts[THUMB_TIP], pts[INDEX_TIP]) / size
class PointSmoother:
    def __init__(self, alpha=cfg.SMOOTHING_ALPHA):
        self.alpha, self.value = alpha, None

    def update(self, x, y):
        if self.value is None:
            self.value = (x, y)
        else:
            a = self.alpha
            self.value = (a * x + (1 - a) * self.value[0], a * y + (1 - a) * self.value[1])
        return self.value


class GestureDetector:
    def __init__(self, settings, width=cfg.WINDOW_W, height=cfg.WINDOW_H):
        self.settings, self.w, self.h = settings, width, height
        self._smooth = {}
        self._pinch = {}

    def update(self, hands):
        zones = self.settings.use_player_zones
        pinch_mode = self.settings.selection_mode == "pinch"
        pointers, seen, used_owners = [], set(), set()

        for rank, hand in enumerate(sorted(hands, key=lambda h: h.landmarks[0][0])):
            pts = [(x * self.w, y * self.h) for x, y in hand.landmarks]
            owner = None
            if zones:                                   # left half = P1, right half = P2
                owner = 0 if hand.landmarks[WRIST][0] < 0.5 else 1
                if owner in used_owners:
                    continue
                used_owners.add(owner)
            key = owner if zones else rank
            seen.add(key)

            ratio = pinch_ratio(pts)
            was = self._pinch.get(key, False)
            pinching = ratio < (cfg.PINCH_OFF if was else cfg.PINCH_ON)
            self._pinch[key] = pinching

            # Always drive the cursor from the INDEX FINGERTIP (landmark 8)
            if pinch_mode:
                raw = ((pts[THUMB_TIP][0] + pts[INDEX_TIP][0]) / 2,
                       (pts[THUMB_TIP][1] + pts[INDEX_TIP][1]) / 2)
            else:
                raw = pts[INDEX_TIP]
            x, y = self._smooth.setdefault(key, PointSmoother()).update(*raw)

            pointing = is_pointing(pts)
            # Only mark ambiguous if config requires a pointing pose
            ambiguous = cfg.REQUIRE_POINTING_POSE and not pinch_mode and not pointing
            pointers.append(Pointer(min(max(x, 0), self.w - 1), min(max(y, 0), self.h - 1),
                                    owner, pinching, pointing, ambiguous, hand))

        for store in (self._smooth, self._pinch):
            for key in [k for k in store if k not in seen]:
                del store[key]
        return pointers


class MouseInput:

    def __init__(self):
        self.pos, self.down = None, False

    def on_mouse(self, event, x, y, flags, param):
        import cv2
        self.pos = (x, y)
        if event == cv2.EVENT_LBUTTONDOWN:
            self.down = True
        elif event == cv2.EVENT_LBUTTONUP:
            self.down = False

    def update(self):
        if self.pos is None:
            return []
        return [Pointer(self.pos[0], self.pos[1], None, self.down)]


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def center(self):
        return (self.x + self.w // 2, self.y + self.h // 2)

    def contains(self, px, py, pad=0):
        return (self.x - pad <= px <= self.x + self.w + pad and
                self.y - pad <= py <= self.y + self.h + pad)


class CellMapper:
    def __init__(self, board_rect: Rect):
        self.rect = board_rect
        self.cell = board_rect.w // 3

    def cell_rect(self, row, col) -> Rect:
        r = self.rect
        c = self.cell
        return Rect(r.x + col * c, r.y + row * c, c, c)

    def all_rects(self):
        return {f"cell:{row * 3 + col}": self.cell_rect(row, col)
                for row in range(3) for col in range(3)}


@dataclass
class Selection:
    hover: Optional[str] = None
    progress: float = 0.0
    selected: Optional[str] = None


class SelectionManager:
    def __init__(self, dwell_time=1.0, mode="dwell",
                 hysteresis=cfg.SELECT_HYSTERESIS_PX, lost_grace=cfg.LOST_GRACE_S):
        self.dwell_time, self.mode = dwell_time, mode
        self.hysteresis, self.lost_grace = hysteresis, lost_grace
        self.reset()

    def reset(self, lock=False):
        self.hover = None
        self.start = 0.0
        self.locked = False
        self._pending_lock = lock
        self._lost_since = None
        self._pinch_prev = False
        self._progress = 0.0
        self._smooth_progress = 0.0
        self._lock_point = None

    def _find(self, point, targets):
        x, y = point
        current = targets.get(self.hover)
        # Stay on current target while inside it + hysteresis padding (anti-jitter)
        if current is not None and current.contains(x, y, pad=self.hysteresis):
            return self.hover
        for tid, rect in targets.items():
            if rect.contains(x, y):
                return tid
        return None

    def update(self, point, targets, now, pinching=False) -> Selection:
        # --- pointer missing: pause, then cancel after grace ----------------
        if point is None:
            if self._lost_since is None:
                self._lost_since = now
            if now - self._lost_since > self.lost_grace:
                self.reset()
                return Selection()
            # Keep showing last progress while hand is briefly lost
            return Selection(self.hover, self._smooth_progress, None)

        if self._lost_since is not None:
            # Shift start so elapsed dwell time is preserved
            self.start += now - self._lost_since
            self._lost_since = None

        hover = self._find(point, targets)

        # Unlock after a selection if the user moved away enough
        if self.locked and self._lock_point is not None:
            if _dist(point, self._lock_point) > 50:
                self.locked = False
                self._lock_point = None

        if hover != self.hover:
            self.hover, self.start, self.locked = hover, now, False
            self._smooth_progress = 0.0
            self._lock_point = None

        if self._pending_lock:
            self._pending_lock = False
            self.locked = hover is not None
            if self.locked and point is not None:
                self._lock_point = point

        if hover is None:
            self._progress = 0.0
            self._smooth_progress = 0.0
            self._pinch_prev = pinching
            return Selection()

        # --- Mode B: pinch --------------------------------------------------
        if self.mode == "pinch":
            rising = pinching and not self._pinch_prev
            self._pinch_prev = pinching
            self._progress = 1.0 if pinching else 0.0
            self._smooth_progress = self._progress
            if rising and not self.locked:
                self.locked = True
                self._lock_point = point
                return Selection(hover, 1.0, hover)
            return Selection(hover, self._smooth_progress, None)

        # --- Mode A: dwell (smooth ring) ------------------------------------
        if self.locked:
            self._progress = 0.0
            self._smooth_progress = 0.0
            return Selection(hover, 0.0, None)

        raw = min(1.0, (now - self.start) / max(self.dwell_time, 0.05))
        self._progress = raw
        # Smooth the visible ring so it does not jump
        a = 0.35
        self._smooth_progress = a * raw + (1 - a) * self._smooth_progress
        # Catch up near the end so confirm is not delayed by smoothing
        if raw >= 1.0:
            self._smooth_progress = 1.0
            self.locked = True
            self._lock_point = point
            return Selection(hover, 1.0, hover)
        return Selection(hover, self._smooth_progress, None)
