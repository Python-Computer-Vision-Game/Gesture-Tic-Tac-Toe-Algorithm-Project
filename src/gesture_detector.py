"""Gesture detector (FR-04, FR-05, section 6): hand landmarks -> Point & Dwell selection.

GestureDetector  - landmarks -> pointers (fingertip, pinch, pose, player zone)
MouseInput       - mouse stand-in for a hand (testing / no camera)
CellMapper       - pixel -> (row, col) on the 3x3 board
SelectionManager - dwell (or pinch) confirmation with anti-jitter protection
"""
import math
from dataclasses import dataclass
from typing import Optional

from . import config as cfg
from .hand_tracker import MIDDLE_MCP, THUMB_TIP, INDEX_TIP, WRIST, Hand


@dataclass
class Pointer:
    """Where a player is pointing, in window pixels."""
    x: float
    y: float
    owner: Optional[int] = None      # 0 / 1 when player zones are on, else None
    pinching: bool = False
    pointing: bool = True
    ambiguous: bool = False          # unclear gesture -> shown but ignored (FR-14)
    hand: Optional[Hand] = None


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _extended(pts, tip, pip, factor):
    return _dist(pts[tip], pts[WRIST]) > _dist(pts[pip], pts[WRIST]) * factor


def is_pointing(pts) -> bool:
    """Index finger straight, middle/ring/pinky curled."""
    index_up = _extended(pts, 8, 6, 1.15)
    others_curled = not any(_extended(pts, tip, pip, 1.05)
                            for tip, pip in ((12, 10), (16, 14), (20, 18)))
    return index_up and others_curled


def pinch_ratio(pts) -> float:
    """Thumb-tip to index-tip gap, relative to hand size (wrist to middle knuckle)."""
    size = _dist(pts[WRIST], pts[MIDDLE_MCP]) or 1e-6
    return _dist(pts[THUMB_TIP], pts[INDEX_TIP]) / size


class PointSmoother:
    """Exponential moving average to reduce hand jitter (risk table, section 21)."""

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

            ratio = pinch_ratio(pts)                    # hysteresis stops flicker
            was = self._pinch.get(key, False)
            pinching = ratio < (cfg.PINCH_OFF if was else cfg.PINCH_ON)
            self._pinch[key] = pinching

            # pinch mode: use the midpoint so closing the fingers doesn't move the cursor
            if pinch_mode:
                raw = ((pts[THUMB_TIP][0] + pts[INDEX_TIP][0]) / 2,
                       (pts[THUMB_TIP][1] + pts[INDEX_TIP][1]) / 2)
            else:
                raw = pts[INDEX_TIP]
            x, y = self._smooth.setdefault(key, PointSmoother()).update(*raw)

            pointing = is_pointing(pts)
            ambiguous = cfg.REQUIRE_POINTING_POSE and not pinch_mode and not pointing
            pointers.append(Pointer(min(max(x, 0), self.w - 1), min(max(y, 0), self.h - 1),
                                    owner, pinching, pointing, ambiguous, hand))

        for store in (self._smooth, self._pinch):       # forget hands that left the frame
            for key in [k for k in store if k not in seen]:
                del store[key]
        return pointers


class MouseInput:
    """Mouse stand-in for a hand: hover = point, left button = pinch. For testing / no camera."""

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


# ======================================================================
# Cell mapping and selection (Point & Dwell)
# ======================================================================

@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    def contains(self, px, py, pad=0) -> bool:
        return (self.x - pad <= px < self.x + self.w + pad and
                self.y - pad <= py < self.y + self.h + pad)

    @property
    def center(self):
        return (self.x + self.w // 2, self.y + self.h // 2)

    def __iter__(self):                      # lets drawing code do: x, y, w, h = rect
        return iter((self.x, self.y, self.w, self.h))


class CellMapper:
    """Divide a board rectangle into 3 columns x 3 rows (section 6)."""

    def __init__(self, region: Rect):
        self.region = region

    def cell_at(self, x, y):
        """(row, col) under the point, or None if outside the board region."""
        r = self.region
        if not r.contains(x, y):
            return None
        col = min(2, int((x - r.x) * 3 / r.w))
        row = min(2, int((y - r.y) * 3 / r.h))
        return row, col

    def cell_rect(self, row, col) -> Rect:
        r = self.region
        cw, ch = r.w // 3, r.h // 3
        return Rect(r.x + col * cw, r.y + row * ch, cw, ch)

    def all_rects(self):
        return {f"cell:{row * 3 + col}": self.cell_rect(row, col)
                for row in range(3) for col in range(3)}


@dataclass
class Selection:
    hover: Optional[str] = None       # id of the target under the pointer
    progress: float = 0.0             # 0..1 dwell progress
    selected: Optional[str] = None    # set for exactly one frame when confirmed


class SelectionManager:
    """Turns a moving pointer into "select" events.

    Anti-accidental-selection features:
      * dwell time: the pointer must stay on one target for dwell_time seconds
      * hysteresis: moving to a neighbouring target needs a few pixels of overshoot
      * lock: after a selection fires, the pointer must leave the target first
      * grace period: a brief hand-detection loss pauses (not cancels) progress
    """

    def __init__(self, dwell_time=1.0, mode="dwell",
                 hysteresis=cfg.SELECT_HYSTERESIS_PX, lost_grace=cfg.LOST_GRACE_S):
        self.dwell_time, self.mode = dwell_time, mode
        self.hysteresis, self.lost_grace = hysteresis, lost_grace
        self.reset()

    def reset(self, lock=False):
        """Forget the current target. lock=True: ignore whatever the pointer is
        on right now until it moves to something else."""
        self.hover = None
        self.start = 0.0
        self.locked = False
        self._pending_lock = lock
        self._lost_since = None
        self._pinch_prev = False
        self._progress = 0.0

    def _find(self, point, targets):
        x, y = point
        current = targets.get(self.hover)
        if current is not None and current.contains(x, y, pad=self.hysteresis):
            return self.hover                                   # sticky
        for tid, rect in targets.items():
            if rect.contains(x, y):
                return tid
        return None

    def update(self, point, targets, now, pinching=False) -> Selection:
        # --- pointer missing: pause, then cancel after the grace period ------
        if point is None:
            if self._lost_since is None:
                self._lost_since = now
            if now - self._lost_since > self.lost_grace:
                self.reset()
                return Selection()
            return Selection(self.hover, self._progress, None)
        if self._lost_since is not None:                        # came back in time
            self.start += now - self._lost_since
            self._lost_since = None

        # --- which target is under the pointer? ------------------------------
        hover = self._find(point, targets)
        if hover != self.hover:
            self.hover, self.start, self.locked = hover, now, False
        if self._pending_lock:
            self._pending_lock = False
            self.locked = hover is not None

        if hover is None:
            self._progress = 0.0
            self._pinch_prev = pinching
            return Selection()

        # --- Mode B: pinch confirms ------------------------------------------
        if self.mode == "pinch":
            rising = pinching and not self._pinch_prev
            self._pinch_prev = pinching
            self._progress = 1.0 if pinching else 0.0
            if rising and not self.locked:
                return Selection(hover, 1.0, hover)
            return Selection(hover, self._progress, None)

        # --- Mode A: dwell confirms ------------------------------------------
        if self.locked:
            self._progress = 0.0
            return Selection(hover, 0.0, None)
        progress = min(1.0, (now - self.start) / max(self.dwell_time, 0.05))
        self._progress = progress
        if progress >= 1.0:
            self.locked = True
            return Selection(hover, 1.0, hover)
        return Selection(hover, progress, None)
