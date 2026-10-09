"""Renderer (FR-07, section 13, section 14): Neon Arcade visual interface.

Matches the neon cyan / pink look: dark brick background, glowing board,
neon X (pink) and O (cyan), soft glows on hover and win.
"""
import math

import cv2
import numpy as np

from . import config as cfg
from .board import EMPTY, X
from .config import t
from .gesture_detector import Rect
from .hand_tracker import HAND_CONNECTIONS

# ---- Neon palette (BGR) ----------------------------------------------------
BG_PURPLE = (28, 12, 18)
BRICK_LINE = (50, 22, 32)

NEON_CYAN = (255, 235, 0)        # board, O, accents
NEON_PINK = (180, 40, 255)       # X, errors, hearts
NEON_BLUE = (240, 120, 0)        # button outlines
GLOW_WHITE = (255, 255, 255)

WHITE = (255, 255, 255)
GRAY = (180, 160, 150)
DIM = (110, 100, 95)

# Names expected by the rest of the project
X_COLOR = NEON_PINK
O_COLOR = NEON_CYAN
ACCENT = NEON_CYAN
WIN_COLOR = (120, 255, 180)
BAD = NEON_PINK
ERROR_COLOR = NEON_PINK
PLAYER_COLORS = (NEON_PINK, NEON_CYAN)
PANEL = (36, 22, 30)
PANEL_HOVER = (55, 35, 48)

FONT = cv2.FONT_HERSHEY_DUPLEX
AA = cv2.LINE_AA
W, H = cfg.WINDOW_W, cfg.WINDOW_H

# ---- Brick background (cached) ---------------------------------------------
_BRICK_TEXTURE = None


def _get_brick_bg():
    global _BRICK_TEXTURE
    if _BRICK_TEXTURE is not None:
        return _BRICK_TEXTURE.copy()

    canvas = np.full((H, W, 3), BG_PURPLE, dtype=np.uint8)
    brick_h, brick_w = 32, 64
    for y in range(0, H, brick_h):
        cv2.line(canvas, (0, y), (W, y), BRICK_LINE, 1, AA)
        offset = (y // brick_h % 2) * (brick_w // 2)
        for x in range(offset, W, brick_w):
            cv2.line(canvas, (x, y), (x, y + brick_h), BRICK_LINE, 1, AA)

    _BRICK_TEXTURE = canvas
    return _BRICK_TEXTURE.copy()


# ---- Text engine -----------------------------------------------------------
_TEXT_CACHE = {}


def _text_sprite(s, scale, color, thick):
    key = (s, scale, color, thick)
    sprite = _TEXT_CACHE.get(key)
    if sprite is None:
        if len(_TEXT_CACHE) > 400:
            _TEXT_CACHE.clear()
        (tw, th), base = cv2.getTextSize(s, FONT, scale, thick)
        pad = thick + 6
        w, h = tw + 2 * pad, th + base + 2 * pad
        shadow = np.zeros((h, w), np.uint8)
        fill = np.zeros((h, w), np.uint8)
        cv2.putText(shadow, s, (pad + 2, pad + th + 2), FONT, scale, 100, thick + 2, AA)
        cv2.putText(fill, s, (pad, pad + th), FONT, scale, 255, thick, AA)
        a_s = shadow.astype(np.float32) / 255.0
        a_f = fill.astype(np.float32) / 255.0
        keep = ((1.0 - a_s) * (1.0 - a_f))[..., None]
        add = a_f[..., None] * np.array(color, np.float32)
        sprite = (keep, add, pad, th)
        _TEXT_CACHE[key] = sprite
    return sprite


def text(img, s, pos, scale=1.0, color=WHITE, thick=2, anchor="center"):
    keep, add, pad, th = _text_sprite(str(s), scale, tuple(color), thick)
    h, w = keep.shape[:2]
    x, y = pos
    left = int(x - (w - 2 * pad) / 2) - pad if anchor == "center" else int(x) - pad
    top = int(y - th / 2) - pad
    x0, y0, x1, y1 = max(0, left), max(0, top), min(W, left + w), min(H, top + h)
    if x1 <= x0 or y1 <= y0:
        return
    roi = img[y0:y1, x0:x1]
    k = keep[y0 - top:y1 - top, x0 - left:x1 - left]
    a = add[y0 - top:y1 - top, x0 - left:x1 - left]
    roi[:] = (roi * k + a).astype(np.uint8)


# ---- Glow helpers ----------------------------------------------------------
def draw_glow_line(img, pt1, pt2, color, thickness=3, glow_r=16):
    overlay = np.zeros_like(img)
    cv2.line(overlay, pt1, pt2, color, thickness + glow_r, AA)
    overlay = cv2.GaussianBlur(overlay, (25, 25), 0)
    cv2.addWeighted(img, 1.0, overlay, 0.85, 0, img)
    cv2.line(img, pt1, pt2, GLOW_WHITE, max(1, thickness - 1), AA)


def draw_glow_rounded_rect(img, rect, radius, color, thickness=3, glow_r=18):
    x, y, w, h = [int(v) for v in rect]
    r = max(4, min(radius, w // 2, h // 2))

    overlay = np.zeros_like(img)
    for p1, p2 in (((x + r, y), (x + w - r, y)),
                   ((x + r, y + h), (x + w - r, y + h)),
                   ((x, y + r), (x, y + h - r)),
                   ((x + w, y + r), (x + w, y + h - r))):
        cv2.line(overlay, p1, p2, color, thickness + glow_r, AA)
    for (cx, cy), a in (((x + r, y + r), 180), ((x + w - r, y + r), 270),
                        ((x + w - r, y + h - r), 0), ((x + r, y + h - r), 90)):
        cv2.ellipse(overlay, (cx, cy), (r, r), 0, a, a + 90, color, thickness + glow_r, AA)

    overlay = cv2.GaussianBlur(overlay, (25, 25), 0)
    cv2.addWeighted(img, 1.0, overlay, 0.80, 0, img)

    core = max(1, thickness - 2)
    for p1, p2 in (((x + r, y), (x + w - r, y)),
                   ((x + r, y + h), (x + w - r, y + h)),
                   ((x, y + r), (x, y + h - r)),
                   ((x + w, y + r), (x + w, y + h - r))):
        cv2.line(img, p1, p2, GLOW_WHITE, core, AA)
    for (cx, cy), a in (((x + r, y + r), 180), ((x + w - r, y + r), 270),
                        ((x + w - r, y + h - r), 0), ((x + r, y + h - r), 90)):
        cv2.ellipse(img, (cx, cy), (r, r), 0, a, a + 90, GLOW_WHITE, core, AA)


def draw_symbol(img, rect, symbol, progress=1.0, color=None, thick=14):
    """Glowing neon X / O. `thick` kept for API compatibility with older calls."""
    cx, cy = rect.center
    s = int(rect.w * 0.28)

    if symbol == X:
        color = color or NEON_PINK
        p1 = min(1.0, progress * 2)
        p2 = max(0.0, progress * 2 - 1.0)

        a, b = (cx - s, cy - s), (cx + s, cy + s)
        if p1 > 0:
            cur = (int(a[0] + (b[0] - a[0]) * p1), int(a[1] + (b[1] - a[1]) * p1))
            draw_glow_line(img, a, cur, color, thickness=5, glow_r=16)

        if p2 > 0:
            c, d = (cx + s, cy - s), (cx - s, cy + s)
            cur = (int(c[0] + (d[0] - c[0]) * p2), int(c[1] + (d[1] - c[1]) * p2))
            draw_glow_line(img, c, cur, color, thickness=5, glow_r=16)
    else:
        color = color or NEON_CYAN
        if progress > 0:
            overlay = np.zeros_like(img)
            cv2.ellipse(overlay, (cx, cy), (s, s), -90, 0, 360 * min(1.0, progress), color, 14, AA)
            overlay = cv2.GaussianBlur(overlay, (21, 21), 0)
            cv2.addWeighted(img, 1.0, overlay, 0.85, 0, img)
            cv2.ellipse(img, (cx, cy), (s, s), -90, 0, 360 * min(1.0, progress), GLOW_WHITE, 3, AA)


def _draw_heart(img, cx, cy, size, color):
    """Simple neon heart using two circles + triangle."""
    r = max(3, size // 3)
    cv2.circle(img, (cx - r, cy - r // 2), r, color, -1, AA)
    cv2.circle(img, (cx + r, cy - r // 2), r, color, -1, AA)
    pts = np.array([[cx - 2 * r, cy - r // 2],
                    [cx + 2 * r, cy - r // 2],
                    [cx, cy + 2 * r]], np.int32)
    cv2.fillConvexPoly(img, pts, color, AA)


class Renderer:
    def __init__(self, settings):
        self.settings = settings

    # ---- background --------------------------------------------------------
    def background(self, frame):
        bg = _get_brick_bg()
        if frame is not None:
            cam = cv2.resize(frame, (W, H))
            # Keep background dark; only a tiny hint of the camera
            cv2.addWeighted(bg, 0.95, cv2.convertScaleAbs(cam, alpha=0.12), 0.05, 0, bg)
        return bg

    # ---- widgets -----------------------------------------------------------
    def buttons(self, img, buttons, sel):
        for bid, (rect, label) in buttons.items():
            hovered = sel is not None and sel.hover == bid
            color = NEON_CYAN if hovered else NEON_BLUE
            glow = 14 if hovered else 8
            thick = 3 if hovered else 2

            draw_glow_rounded_rect(img, tuple(rect), 16, color, thickness=thick, glow_r=glow)

            if hovered and sel is not None and sel.progress > 0:
                fill_w = max(2, int(rect.w * sel.progress))
                x0, y0 = rect.x, rect.y
                x1, y1 = min(W, x0 + fill_w), min(H, y0 + rect.h)
                if x1 > x0 and y1 > y0:
                    roi = img[y0:y1, x0:x1]
                    overlay = roi.copy()
                    cv2.rectangle(overlay, (0, 0), (x1 - x0, y1 - y0), NEON_CYAN, -1)
                    cv2.addWeighted(overlay, 0.35, roi, 0.65, 0, roi)

            text(img, label, rect.center, 0.85 if rect.h >= 70 else 0.7,
                 color=WHITE if hovered else GRAY)

    def pointers(self, img, pointers, active, sel, debug):
        for p in pointers:
            if debug and p.hand is not None:
                pts = [(int(x * W), int(y * H)) for x, y in p.hand.landmarks]
                for a, b in HAND_CONNECTIONS:
                    cv2.line(img, pts[a], pts[b], NEON_BLUE, 2, AA)
                for pt in pts:
                    cv2.circle(img, pt, 4, NEON_CYAN, -1, AA)

            is_active = p is active and not p.ambiguous
            color = DIM if not is_active else (
                PLAYER_COLORS[p.owner] if p.owner is not None else NEON_CYAN
            )
            c = (int(p.x), int(p.y))

            if is_active:
                overlay = img.copy()
                cv2.circle(overlay, c, 26, color, -1, AA)
                cv2.addWeighted(overlay, 0.20, img, 0.80, 0, img)

            cv2.circle(img, c, 11, color, -1, AA)
            cv2.circle(img, c, 11, GLOW_WHITE, 2, AA)
            cv2.circle(img, c, 3, GLOW_WHITE, -1, AA)

            if is_active and sel is not None and sel.progress > 0:
                cv2.ellipse(img, c, (28, 28), -90, 0, 360 * sel.progress, NEON_CYAN, 5, AA)

    # ---- screens -----------------------------------------------------------
    def menu(self, img, note=None, hint_key="hint_dwell"):
        text(img, t("title"), (W // 2, 110), 2.1, GLOW_WHITE, 4)
        cv2.line(img, (W // 2 - 70, 152), (W // 2 + 70, 152), NEON_CYAN, 3, AA)
        text(img, t("subtitle"), (W // 2, 180), 0.82, NEON_CYAN, 1)
        text(img, t(hint_key), (W // 2, 668), 0.7, GRAY, 1)
        if note:
            text(img, note, (W // 2, 700), 0.65, NEON_PINK, 1)

    def instructions(self, img):
        sections = [
            ("1. Pointing", [
                "Raise one hand in front of the camera and point your index finger.",
                "The cell under your fingertip lights up - that is your target.",
            ]),
            ("2. Confirming a move", [
                "Hold your fingertip still: a ring fills up, then your symbol is placed.",
                "(Pinch mode: touch thumb and index finger together instead.)",
            ]),
            ("3. Winning", [
                "Make 3 of your symbols in a row: horizontal, vertical or diagonal.",
                "All 9 cells full with no line = draw. Occupied cells cannot be used.",
            ]),
            ("4. Hand position", [
                "Stand 50-80 cm from the camera in good light. Keep your hand in view.",
                "Players take turns. With 'Player zones' on: Player 1 = left, Player 2 = right.",
            ]),
        ]
        draw_glow_rounded_rect(img, (110, 40, 1060, 560), 22, NEON_CYAN, thickness=3, glow_r=16)
        text(img, "HOW TO PLAY", (W // 2, 85), 1.4, NEON_CYAN, 3)
        y = 150
        for heading, lines in sections:
            text(img, heading, (150, y), 0.95, WHITE, 2, "left")
            for i, line in enumerate(lines):
                text(img, line, (170, y + 38 + i * 32), 0.68, GRAY, 1, "left")
            y += 112

    def settings_screen(self, img, editing):
        text(img, "SETTINGS", (W // 2, 80), 1.6, WHITE, 3)
        if editing is not None:
            text(img, "Type name on keyboard, press Enter to finish",
                 (W // 2, 120), 0.75, NEON_CYAN, 1)

    def setup(self, img, hands_needed, hands_seen, countdown):
        text(img, "GET READY", (W // 2, 140), 1.6, WHITE, 3)
        if countdown is not None:
            cv2.circle(img, (W // 2, 340), 140, NEON_CYAN, 3, AA)
            text(img, str(countdown), (W // 2, 340), 6.5, NEON_CYAN, 10)
            text(img, "Keep your hand in view", (W // 2, 500), 0.9, GRAY, 1)
        else:
            msg = ("Show both hands to the camera (one on each side)"
                   if hands_needed == 2 else "Show your hand to the camera")
            text(img, msg, (W // 2, 300), 1.0, WHITE, 2)
            ok = hands_seen >= hands_needed
            text(img, f"Hands detected: {hands_seen}", (W // 2, 360), 0.9,
                 NEON_CYAN if ok else NEON_PINK, 2)

    def camera_error(self, img, detail):
        draw_glow_rounded_rect(img, (190, 150, 900, 400), 22, NEON_PINK, thickness=3, glow_r=20)
        text(img, "Camera Problem", (W // 2, 210), 1.5, NEON_PINK, 3)
        lines = [
            "We could not get video from your camera.", "",
            "- Is a webcam plugged in or enabled?",
            "- Is another app (Zoom, Teams, browser) using it?", "",
            "R = try again      M = play with the mouse      Esc = back",
        ]
        for i, line in enumerate(lines):
            text(img, line, (W // 2, 275 + i * 36), 0.8, WHITE if i else GRAY, 1)
        if detail:
            text(img, detail[:90], (W // 2, 520), 0.55, GRAY, 1)

    # ---- main game screen --------------------------------------------------
    def game(self, img, engine, mapper, sel, now, cell_times, result_time, toast):
        state = engine.state
        playing = state.name == "PLAYING"
        names = [p.name for p in engine.turns.players]

        # Top HUD
        total_score = engine.scores.wins[0] + engine.scores.wins[1]
        text(img, f"Score: {total_score}", (280, 48), 1.0, NEON_CYAN, 2)
        text(img, t("title"), (W // 2, 36), 0.75, DIM, 1)

        # Banner: toast > result > turn
        if toast and now < toast[2]:
            banner, color = toast[0], toast[1]
        elif state.name == "ROUND_RESULT":
            if engine.winner_index is not None:
                pl = engine.turns.players[engine.winner_index]
                banner, color = f"{pl.name} ({pl.symbol}) {t('wins')}", WIN_COLOR
            else:
                banner, color = t("draw"), NEON_CYAN
        else:
            pl = engine.turns.current
            banner, color = f"{pl.name} ({pl.symbol})  -  {t('your_turn')}", PLAYER_COLORS[engine.turns.current_index]

        pulse = 1.0 + (0.04 * math.sin((now - result_time) * 8) if state.name == "ROUND_RESULT" else 0)
        text(img, banner, (W // 2, 100), 1.1 * pulse, color, 3)

        # Left player labels
        p1_active = playing and engine.turns.current_index == 0
        p2_active = playing and engine.turns.current_index == 1

        text(img, names[0], (80, 270), 0.85, NEON_CYAN if p1_active else GRAY, 2, "left")
        draw_symbol(img, Rect(230, 245, 50, 50), engine.turns.players[0].symbol, 1.0)
        text(img, f"{t('score')}: {engine.scores.wins[0]}", (80, 310), 0.7,
             WHITE if p1_active else GRAY, 1, "left")

        text(img, names[1], (80, 370), 0.85, NEON_CYAN if p2_active else GRAY, 2, "left")
        draw_symbol(img, Rect(230, 345, 50, 50), engine.turns.players[1].symbol, 1.0)
        text(img, f"{t('score')}: {engine.scores.wins[1]}", (80, 410), 0.7,
             WHITE if p2_active else GRAY, 1, "left")

        # Right side info
        text(img, f"{t('round')}: {engine.scores.rounds_played + (1 if playing else 0)}",
             (980, 270), 0.85, NEON_CYAN, 2)
        text(img, f"{t('draws')}: {engine.scores.draws}", (980, 320), 0.75, GRAY, 1)

        # Neon hearts decoration
        for i in range(3):
            _draw_heart(img, 1000 + i * 45, 380, 22, NEON_PINK)

        # Board frame
        rg = mapper.region
        draw_glow_rounded_rect(
            img, (rg.x - 12, rg.y - 12, rg.w + 24, rg.h + 24),
            radius=28, color=NEON_CYAN, thickness=4, glow_r=22,
        )

        # Grid lines
        cw = rg.w // 3
        for i in (1, 2):
            draw_glow_line(img, (rg.x + i * cw, rg.y + 8),
                           (rg.x + i * cw, rg.y + rg.h - 8), NEON_CYAN, 3, 12)
            draw_glow_line(img, (rg.x + 8, rg.y + i * cw),
                           (rg.x + rg.w - 8, rg.y + i * cw), NEON_CYAN, 3, 12)

        # Target highlight
        if sel is not None and playing and sel.hover and sel.hover.startswith("cell:"):
            row, col = divmod(int(sel.hover.split(":")[1]), 3)
            occupied = engine.board.get(row, col) != EMPTY
            color = NEON_PINK if occupied else NEON_CYAN
            r = mapper.cell_rect(row, col)
            x0, y0 = r.x + 6, r.y + 6
            x1, y1 = r.x + r.w - 6, r.y + r.h - 6
            if x1 > x0 and y1 > y0:
                roi = img[y0:y1, x0:x1]
                overlay = roi.copy()
                cv2.rectangle(overlay, (0, 0), (x1 - x0, y1 - y0), color, -1)
                alpha = 0.18 + 0.35 * sel.progress
                cv2.addWeighted(overlay, alpha, roi, 1 - alpha, 0, roi)

        # Winning cells pulse
        if engine.winning_line:
            for row, col in engine.winning_line:
                r = mapper.cell_rect(row, col)
                x0, y0 = r.x + 6, r.y + 6
                x1, y1 = r.x + r.w - 6, r.y + r.h - 6
                if x1 > x0 and y1 > y0:
                    roi = img[y0:y1, x0:x1]
                    overlay = roi.copy()
                    cv2.rectangle(overlay, (0, 0), (x1 - x0, y1 - y0), WIN_COLOR, -1)
                    pulse_a = 0.22 + 0.15 * math.sin((now - result_time) * 8)
                    cv2.addWeighted(overlay, pulse_a, roi, 1 - pulse_a, 0, roi)

        # Symbols
        for row in range(3):
            for col in range(3):
                symbol = engine.board.get(row, col)
                if symbol != EMPTY:
                    p = min(1.0, (now - cell_times.get((row, col), -9)) / 0.30)
                    draw_symbol(img, mapper.cell_rect(row, col), symbol, p)

        # Winning line
        if engine.winning_line:
            a = mapper.cell_rect(*engine.winning_line[0]).center
            b = mapper.cell_rect(*engine.winning_line[2]).center
            g = min(1.0, (now - result_time) / 0.40)
            end = (int(a[0] + (b[0] - a[0]) * g), int(a[1] + (b[1] - a[1]) * g))
            draw_glow_line(img, a, end, NEON_PINK, thickness=8, glow_r=22)