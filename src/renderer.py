"""Renderer (FR-07, section 13, section 14): everything drawn on screen, with OpenCV."""
import math

import cv2
import numpy as np

from . import config as cfg
from .board import EMPTY, X
from .config import t
from .gesture_detector import Rect
from .hand_tracker import HAND_CONNECTIONS

WHITE, GRAY = (255, 255, 255), (175, 175, 175)
PANEL, PANEL_HOVER = (60, 52, 48), (95, 82, 72)
X_COLOR, O_COLOR = (95, 95, 255), (255, 195, 70)      # BGR: red-ish X, blue-ish O
ACCENT, WIN_COLOR, BAD = (0, 215, 255), (110, 230, 110), (70, 70, 240)
PLAYER_COLORS = (X_COLOR, O_COLOR)
ERROR_COLOR = BAD
FONT = cv2.FONT_HERSHEY_DUPLEX
AA = cv2.LINE_AA
W, H = cfg.WINDOW_W, cfg.WINDOW_H


# ---- drawing helpers -------------------------------------------------------
_TEXT_CACHE = {}


def _text_sprite(s, scale, color, thick):
    """Pre-render text + black shadow once. Blitting it later is ~10x faster than putText."""
    key = (s, scale, color, thick)
    sprite = _TEXT_CACHE.get(key)
    if sprite is None:
        if len(_TEXT_CACHE) > 400:
            _TEXT_CACHE.clear()
        (tw, th), base = cv2.getTextSize(s, FONT, scale, thick)
        pad = thick + 4
        w, h = tw + 2 * pad, th + base + 2 * pad
        shadow, fill = np.zeros((h, w), np.uint8), np.zeros((h, w), np.uint8)
        cv2.putText(shadow, s, (pad, pad + th), FONT, scale, 255, thick + 3, AA)
        cv2.putText(fill, s, (pad, pad + th), FONT, scale, 255, thick, AA)
        a_s, a_f = shadow.astype(np.float32) / 255, fill.astype(np.float32) / 255
        keep = ((1 - a_s) * (1 - a_f))[..., None]                  # how much background survives
        add = a_f[..., None] * np.array(color, np.float32)         # how much text colour is added
        sprite = (keep, add, pad, th)
        _TEXT_CACHE[key] = sprite
    return sprite


def text(img, s, pos, scale=1.0, color=WHITE, thick=2, anchor="center"):
    keep, add, pad, th = _text_sprite(s, scale, tuple(color), thick)
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


def rounded_rect(img, rect, radius, color, thickness=-1):
    x, y, w, h = rect
    r = max(0, min(radius, w // 2, h // 2))
    if thickness < 0:
        cv2.rectangle(img, (x + r, y), (x + w - r, y + h), color, -1)
        cv2.rectangle(img, (x, y + r), (x + w, y + h - r), color, -1)
        for cx, cy in ((x + r, y + r), (x + w - r, y + r), (x + r, y + h - r), (x + w - r, y + h - r)):
            cv2.circle(img, (cx, cy), r, color, -1, AA)
        return
    for p1, p2 in (((x + r, y), (x + w - r, y)), ((x + r, y + h), (x + w - r, y + h)),
                   ((x, y + r), (x, y + h - r)), ((x + w, y + r), (x + w, y + h - r))):
        cv2.line(img, p1, p2, color, thickness, AA)
    for (cx, cy), a in (((x + r, y + r), 180), ((x + w - r, y + r), 270),
                        ((x + w - r, y + h - r), 0), ((x + r, y + h - r), 90)):
        cv2.ellipse(img, (cx, cy), (r, r), 0, a, a + 90, color, thickness, AA)


def panel(img, rect, color, alpha=0.6, radius=18):
    """Semi-transparent rounded rectangle (only blends the small region it covers)."""
    x, y, w, h = rect
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    roi = img[y0:y1, x0:x1]
    overlay = roi.copy()
    rounded_rect(overlay, (x - x0, y - y0, w, h), radius, color, -1)
    cv2.addWeighted(overlay, alpha, roi, 1 - alpha, 0, roi)


def draw_symbol(img, rect, symbol, progress=1.0, color=None, thick=14):
    """X and O that 'draw themselves' while progress goes 0 -> 1."""
    cx, cy = rect.center
    s = int(rect.w * 0.28)
    if symbol == X:
        color = color or X_COLOR
        p1, p2 = min(1, progress * 2), max(0, progress * 2 - 1)
        a, b = (cx - s, cy - s), (cx + s, cy + s)
        cv2.line(img, a, (int(a[0] + (b[0] - a[0]) * p1), int(a[1] + (b[1] - a[1]) * p1)), color, thick, AA)
        if p2 > 0:
            c, d = (cx + s, cy - s), (cx - s, cy + s)
            cv2.line(img, c, (int(c[0] + (d[0] - c[0]) * p2), int(c[1] + (d[1] - c[1]) * p2)), color, thick, AA)
    else:
        color = color or O_COLOR
        if progress > 0:
            cv2.ellipse(img, (cx, cy), (s, s), -90, 0, 360 * min(1, progress), color, thick, AA)


class Renderer:
    def __init__(self, settings):
        self.settings = settings

    # ---- backgrounds ------------------------------------------------------
    def background(self, frame):
        if frame is None:
            canvas = np.empty((H, W, 3), np.uint8)
            canvas[:] = (48, 38, 32)
            return canvas
        return cv2.convertScaleAbs(cv2.resize(frame, (W, H)), alpha=0.45)   # dimmed camera feed

    # ---- generic widgets --------------------------------------------------
    def buttons(self, img, buttons, sel):
        for bid, (rect, label) in buttons.items():
            hovered = sel is not None and sel.hover == bid
            panel(img, rect, PANEL_HOVER if hovered else PANEL, 0.85)
            if hovered and sel.progress > 0:                                # dwell progress fill
                panel(img, Rect(rect.x, rect.y, max(2, int(rect.w * sel.progress)), rect.h), ACCENT, 0.45)
            rounded_rect(img, tuple(rect), 18, ACCENT if hovered else GRAY, 3 if hovered else 2)
            text(img, label, rect.center, 0.9 if rect.h >= 70 else 0.7)

    def pointers(self, img, pointers, active, sel, debug):
        for p in pointers:
            if debug and p.hand is not None:
                pts = [(int(x * W), int(y * H)) for x, y in p.hand.landmarks]
                for a, b in HAND_CONNECTIONS:
                    cv2.line(img, pts[a], pts[b], (120, 255, 120), 2, AA)
                for pt in pts:
                    cv2.circle(img, pt, 4, (0, 140, 255), -1, AA)
            is_active = p is active and not p.ambiguous
            color = GRAY if not is_active else (PLAYER_COLORS[p.owner] if p.owner is not None else ACCENT)
            c = (int(p.x), int(p.y))
            cv2.circle(img, c, 13, color, -1, AA)
            cv2.circle(img, c, 13, WHITE, 2, AA)
            if is_active and sel is not None and sel.progress > 0:
                cv2.ellipse(img, c, (30, 30), -90, 0, 360 * sel.progress, ACCENT, 6, AA)

    # ---- screens ----------------------------------------------------------
    def menu(self, img, note=None, hint_key="hint_dwell"):
        text(img, t("title"), (W // 2, 120), 2.0, WHITE, 4)
        text(img, t("subtitle"), (W // 2, 185), 0.8, GRAY, 1)
        text(img, t(hint_key), (W // 2, 668), 0.7, GRAY, 1)
        if note:
            text(img, note, (W // 2, 700), 0.65, BAD, 1)

    def instructions(self, img):
        sections = [
            ("1. Pointing", ["Raise one hand in front of the camera and point your index finger.",
                             "The cell under your fingertip lights up - that is your target."]),
            ("2. Confirming a move", ["Hold your fingertip still: a ring fills up, then your symbol is placed.",
                                      "(Pinch mode: touch thumb and index finger together instead.)"]),
            ("3. Winning", ["Make 3 of your symbols in a row: horizontal, vertical or diagonal.",
                            "All 9 cells full with no line = draw. Occupied cells cannot be used."]),
            ("4. Hand position", ["Stand 50-80 cm from the camera in good light. Keep your hand in view.",
                                  "Players take turns. With 'Player zones' on: Player 1 = left, Player 2 = right."]),
        ]
        panel(img, Rect(110, 40, 1060, 560), (30, 26, 24), 0.78)
        text(img, "HOW TO PLAY", (W // 2, 85), 1.3, ACCENT, 3)
        y = 150
        for heading, lines in sections:
            text(img, heading, (150, y), 0.95, WHITE, 2, "left")
            for i, line in enumerate(lines):
                text(img, line, (170, y + 38 + i * 32), 0.68, GRAY, 1, "left")
            y += 112

    def settings_screen(self, img, editing):
        text(img, "SETTINGS", (W // 2, 80), 1.5, WHITE, 3)
        if editing is not None:
            text(img, "Type the name on the keyboard, then press Enter", (W // 2, 120), 0.7, ACCENT, 1)

    def setup(self, img, hands_needed, hands_seen, countdown):
        text(img, "GET READY", (W // 2, 140), 1.6, WHITE, 3)
        if countdown is not None:
            text(img, str(countdown), (W // 2, 340), 6.0, ACCENT, 10)
            text(img, "Keep your hand in view", (W // 2, 500), 0.9, GRAY, 1)
        else:
            msg = ("Show both hands to the camera (one on each side)" if hands_needed == 2
                   else "Show your hand to the camera")
            text(img, msg, (W // 2, 300), 1.0, WHITE, 2)
            text(img, f"Hands detected: {hands_seen}", (W // 2, 360), 0.9,
                 WIN_COLOR if hands_seen >= hands_needed else BAD, 2)

    def camera_error(self, img, detail):
        panel(img, Rect(190, 150, 900, 400), (30, 26, 24), 0.85)
        text(img, "Camera problem", (W // 2, 210), 1.5, BAD, 3)
        lines = ["We could not get video from your camera.", "",
                 "- Is a webcam plugged in or enabled?",
                 "- Is another app (Zoom, Teams, browser) using it?", "",
                 "R = try again      M = play with the mouse      Esc = back"]
        for i, line in enumerate(lines):
            text(img, line, (W // 2, 275 + i * 36), 0.8, WHITE if i != 0 else GRAY, 1)
        if detail:
            text(img, detail[:90], (W // 2, 520), 0.55, GRAY, 1)

    # ---- the game screen --------------------------------------------------
    def game(self, img, engine, mapper, sel, now, cell_times, result_time, toast):
        state = engine.state
        playing = state.name == "PLAYING"
        names = [p.name for p in engine.turns.players]

        if self.settings.use_player_zones and playing:              # tint the two hand zones
            panel(img, Rect(0, 0, W // 2, H), X_COLOR, 0.07, 0)
            panel(img, Rect(W // 2, 0, W // 2, H), O_COLOR, 0.07, 0)

        text(img, t("title"), (W // 2, 40), 0.9, GRAY, 1)

        # banner: toast > result > whose turn
        if toast and now < toast[2]:
            banner, color = toast[0], toast[1]
        elif state.name == "ROUND_RESULT":
            if engine.winner_index is not None:
                pl = engine.turns.players[engine.winner_index]
                banner, color = f"{pl.name} ({pl.symbol}) {t('wins')}", WIN_COLOR
            else:
                banner, color = t("draw"), ACCENT
        else:
            pl = engine.turns.current
            banner, color = f"{pl.name} ({pl.symbol})  -  {t('your_turn')}", PLAYER_COLORS[engine.turns.current_index]
        pulse = 1.0 + (0.04 * math.sin((now - result_time) * 8) if state.name == "ROUND_RESULT" else 0)
        text(img, banner, (W // 2, 105), 1.15 * pulse, color, 3)

        # player panels
        for i, rect in enumerate((Rect(40, 170, 320, 210), Rect(920, 170, 320, 210))):
            active = playing and engine.turns.current_index == i
            panel(img, rect, (30, 26, 24), 0.65)
            rounded_rect(img, tuple(rect), 18, PLAYER_COLORS[i] if active else GRAY, 5 if active else 2)
            text(img, names[i], (rect.x + rect.w // 2, rect.y + 35), 0.95)
            draw_symbol(img, Rect(rect.x + rect.w // 2 - 45, rect.y + 55, 90, 90),
                        engine.turns.players[i].symbol, 1.0, thick=9)
            text(img, f"{t('score')}: {engine.scores.wins[i]}", (rect.x + rect.w // 2, rect.y + 175), 1.0, WHITE, 2)
            if active:
                text(img, t("your_turn"), (rect.x + rect.w // 2, rect.y - 18), 0.65, PLAYER_COLORS[i], 2)
        text(img, f"{t('draws')}: {engine.scores.draws}", (200, 415), 0.8, GRAY, 1)
        text(img, f"{t('round')}: {engine.scores.rounds_played + (1 if playing else 0)}", (1080, 415), 0.8, GRAY, 1)

        # board
        rg = mapper.region
        panel(img, Rect(rg.x - 14, rg.y - 14, rg.w + 28, rg.h + 28), (30, 26, 24), 0.62, 24)
        if state.name == "ROUND_RESULT" and engine.winning_line is None:      # draw: pulsing border
            glow = 3 + int(3 * (1 + math.sin((now - result_time) * 6)))
            rounded_rect(img, (rg.x - 14, rg.y - 14, rg.w + 28, rg.h + 28), 24, ACCENT, glow)

        if sel is not None and playing and sel.hover and sel.hover.startswith("cell:"):   # target highlight
            row, col = divmod(int(sel.hover.split(":")[1]), 3)
            occupied = engine.board.get(row, col) != EMPTY
            color = BAD if occupied else PLAYER_COLORS[engine.turns.current_index]
            r = mapper.cell_rect(row, col)
            panel(img, Rect(r.x + 6, r.y + 6, r.w - 12, r.h - 12), color, 0.18 + 0.40 * sel.progress, 14)

        if engine.winning_line:                                                           # winning cells
            for row, col in engine.winning_line:
                r = mapper.cell_rect(row, col)
                panel(img, Rect(r.x + 6, r.y + 6, r.w - 12, r.h - 12), WIN_COLOR,
                      0.25 + 0.15 * math.sin((now - result_time) * 8), 14)

        cw = rg.w // 3
        for i in (1, 2):
            cv2.line(img, (rg.x + i * cw, rg.y + 12), (rg.x + i * cw, rg.y + rg.h - 12), WHITE, 5, AA)
            cv2.line(img, (rg.x + 12, rg.y + i * cw), (rg.x + rg.w - 12, rg.y + i * cw), WHITE, 5, AA)

        for row in range(3):
            for col in range(3):
                symbol = engine.board.get(row, col)
                if symbol != EMPTY:
                    p = min(1.0, (now - cell_times.get((row, col), -9)) / 0.30)
                    draw_symbol(img, mapper.cell_rect(row, col), symbol, p)

        if engine.winning_line:                                                           # winning line
            a = mapper.cell_rect(*engine.winning_line[0]).center
            b = mapper.cell_rect(*engine.winning_line[2]).center
            g = min(1.0, (now - result_time) / 0.40)
            end = (int(a[0] + (b[0] - a[0]) * g), int(a[1] + (b[1] - a[1]) * g))
            cv2.line(img, a, end, WIN_COLOR, int(12 + 4 * math.sin((now - result_time) * 8)), AA)
