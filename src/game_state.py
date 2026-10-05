"""Main game loop and state management (section 12).

Part 1  GameState / StateMachine - which screen we are on, and the allowed moves between them
Part 2  GameEngine               - the rules of one match; knows nothing about cameras or hands
Part 3  Game                     - screens, buttons, input handling (one frame at a time)
Part 4  run()                    - the real loop: camera -> hands -> Game -> window
"""
import argparse
import time
from enum import Enum, auto

import cv2

from . import config as cfg
from .board import Board
from .config import t
from .game_rules import RoundResult, evaluate, is_valid_move
from .gesture_detector import CellMapper, GestureDetector, MouseInput, Rect, SelectionManager
from .renderer import ERROR_COLOR, Renderer
from .score_manager import ScoreManager
from .turn_manager import TurnManager


class GameState(Enum):
    MENU = auto()
    INSTRUCTIONS = auto()
    SETTINGS = auto()
    CAMERA_ERROR = auto()
    SETUP = auto()
    PLAYING = auto()
    CHECK_RESULT = auto()
    ROUND_RESULT = auto()


S = GameState
ALLOWED = {
    S.MENU: {S.SETUP, S.INSTRUCTIONS, S.SETTINGS, S.CAMERA_ERROR},
    S.INSTRUCTIONS: {S.MENU},
    S.SETTINGS: {S.MENU},
    S.CAMERA_ERROR: {S.MENU, S.SETUP},
    S.SETUP: {S.PLAYING, S.MENU, S.CAMERA_ERROR},
    S.PLAYING: {S.PLAYING, S.CHECK_RESULT, S.MENU, S.CAMERA_ERROR},   # PLAYING->PLAYING = invalid move / restart
    S.CHECK_RESULT: {S.ROUND_RESULT, S.PLAYING},
    S.ROUND_RESULT: {S.PLAYING, S.MENU},
}


class InvalidTransition(Exception):
    pass


class StateMachine:
    def __init__(self, initial=GameState.MENU):
        self.state = initial

    def can_go(self, new) -> bool:
        return new in ALLOWED[self.state]

    def go(self, new):
        if not self.can_go(new):
            raise InvalidTransition(f"{self.state.name} -> {new.name} is not allowed")
        self.state = new


class MoveOutcome(Enum):
    REJECTED_STATE = auto()   # not in PLAYING
    INVALID_CELL = auto()     # occupied or out of range
    PLACED = auto()           # valid, game continues
    WIN = auto()
    DRAW = auto()


class GameEngine:
    def __init__(self, settings):
        self.settings = settings
        self.board = Board()
        self.turns = TurnManager(settings.player_names, settings.first_player)
        self.scores = ScoreManager()
        self.fsm = StateMachine()
        self._clear_round()

    # -- convenience ---------------------------------------------------------
    @property
    def state(self):
        return self.fsm.state

    def go(self, new_state):
        self.fsm.go(new_state)

    def sync_settings(self):
        self.turns.set_names(self.settings.player_names)

    def _clear_round(self):
        self.board.reset()
        self.turns.reset(self.settings.first_player)
        self.result = RoundResult.ONGOING
        self.winner_index = None
        self.winning_line = None
        self.last_move = None

    # -- match / round control (FR-12) ---------------------------------------
    def begin_match(self):
        """SETUP -> PLAYING with fresh scores."""
        self.sync_settings()
        self.scores.reset()
        self._clear_round()
        self.fsm.go(GameState.PLAYING)

    def new_round(self, keep_score=True):
        self.sync_settings()
        if not keep_score:
            self.scores.reset()
        self._clear_round()
        self.fsm.go(GameState.PLAYING)

    def reset_scores(self):
        self.scores.reset()

    # -- the one game action -------------------------------------------------
    def play(self, row, col) -> MoveOutcome:
        if self.state != GameState.PLAYING:
            return MoveOutcome.REJECTED_STATE
        if not is_valid_move(self.board, row, col):
            return MoveOutcome.INVALID_CELL

        player = self.turns.current
        self.board.place(row, col, player.symbol)
        self.last_move = (row, col)
        self.fsm.go(GameState.CHECK_RESULT)

        result, symbol, line = evaluate(self.board)
        self.result = result
        if result == RoundResult.WIN:
            self.winner_index = self.turns.index_of(symbol)
            self.winning_line = line
            self.scores.record_win(self.winner_index)
            self.fsm.go(GameState.ROUND_RESULT)
            return MoveOutcome.WIN
        if result == RoundResult.DRAW:
            self.scores.record_draw()
            self.fsm.go(GameState.ROUND_RESULT)
            return MoveOutcome.DRAW

        self.turns.switch()                  # only after a valid move (FR-11)
        self.fsm.go(GameState.PLAYING)
        return MoveOutcome.PLACED


# =====================================================================
# Part 3: Game  (screens, buttons, input handling)
# =====================================================================
ST = GameState


class Game:
    """Everything except the physical camera, so tests can drive it with fake fingertips."""

    def __init__(self, settings=None):
        self.settings = settings or cfg.Settings()
        self.engine = GameEngine(self.settings)
        self.mapper = CellMapper(Rect(cfg.BOARD_X, cfg.BOARD_Y, cfg.BOARD_SIZE, cfg.BOARD_SIZE))
        self.selector = SelectionManager()
        self.renderer = Renderer(self.settings)
        self.running = True
        self.pointers, self.sel, self.active_pointer = [], None, None
        self.toast = None                          # (text, colour, until)
        self.cell_times, self.result_time = {}, 0.0
        self.editing = None                        # 0/1 while typing a player name
        self.camera_ok, self.mouse_mode, self.error_detail = True, False, ""
        self.setup_since, self.countdown_end = None, None
        self.setup_seen, self.setup_needed = 0, 1
        self.retry_camera = False                  # set by key R on the error screen

    # ---- helpers ---------------------------------------------------
    def say(self, msg, now):
        self.toast = (msg, ERROR_COLOR, now + cfg.TOAST_S)

    def goto(self, state):
        self.engine.go(state)
        self.selector.reset(lock=True)

    def pick_pointer(self):
        if not self.pointers:
            return None
        if self.engine.state == ST.PLAYING and self.settings.use_player_zones:
            idx = self.engine.turns.current_index          # only the active player's zone counts
            return next((p for p in self.pointers if p.owner == idx), None)
        return self.pointers[0]

    # ---- buttons for the current screen -----------------------------
    @staticmethod
    def _stack(items, x, y, w, h, gap):
        return {bid: (Rect(x, y + i * (h + gap), w, h), label) for i, (bid, label) in enumerate(items)}

    def buttons(self):
        s, st, names = self.settings, self.engine.state, self.settings.player_names
        if st == ST.MENU:
            return self._stack([("btn:start", t("start")), ("btn:instructions", t("instructions")),
                                ("btn:settings", t("settings")), ("btn:exit", t("exit"))], 430, 235, 420, 76, 18)
        if st in (ST.INSTRUCTIONS, ST.SETUP):
            return {"btn:menu": (Rect(540, 630, 200, 60), t("back"))}
        if st == ST.PLAYING:
            return {"btn:restart": (Rect(400, 645, 230, 60), t("restart")),
                    "btn:menu": (Rect(650, 645, 230, 60), t("menu"))}
        if st == ST.ROUND_RESULT:
            return {"btn:next": (Rect(250, 645, 240, 60), t("next_round")),
                    "btn:reset": (Rect(520, 645, 240, 60), t("reset_scores")),
                    "btn:menu": (Rect(790, 645, 240, 60), t("menu"))}
        if st == ST.SETTINGS:
            cursor = "_" if self.editing is not None else ""

            def name(i):
                return f"P{i + 1} name: {names[i]}{cursor if self.editing == i else ''}"
            items = [("btn:dwell", f"Dwell time: {s.dwell_time:.1f} s"),
                     ("btn:mode", "Select by: " + ("Dwell" if s.selection_mode == "dwell" else "Pinch")),
                     ("btn:zones", "Player zones: " + ("ON" if s.use_player_zones else "OFF")),
                     ("btn:first", f"First player: {names[s.first_player]}"),
                     ("btn:name0", name(0)), ("btn:name1", name(1)),
                     ("btn:debug", "Debug landmarks: " + ("ON" if s.debug_landmarks else "OFF"))]
            out = {bid: (Rect(190 + (i % 2) * 480, 150 + (i // 2) * 100, 420, 80), label)
                   for i, (bid, label) in enumerate(items)}
            out["btn:menu"] = (Rect(440, 580, 400, 76), t("back"))
            return out
        return {}

    # ---- what happens when something is selected ---------------------
    def activate(self, target, now):
        eng, s = self.engine, self.settings
        if target.startswith("cell:"):
            row, col = divmod(int(target.split(":")[1]), 3)
            outcome = eng.play(row, col)
            if outcome == MoveOutcome.INVALID_CELL:              # FR-06: clear invalid-move message
                self.say(t("taken"), now)
            elif outcome in (MoveOutcome.PLACED, MoveOutcome.WIN, MoveOutcome.DRAW):
                self.cell_times[(row, col)] = now
                self.selector.reset(lock=True)                   # finger must leave before re-triggering
                self.toast = None
                if outcome != MoveOutcome.PLACED:
                    self.result_time = now
            return

        if target == "btn:start":
            if not self.mouse_mode and not self.camera_ok:
                self.goto(ST.CAMERA_ERROR)
            else:
                self.setup_since = self.countdown_end = None
                self.goto(ST.SETUP)
        elif target == "btn:instructions":
            self.goto(ST.INSTRUCTIONS)
        elif target == "btn:settings":
            self.goto(ST.SETTINGS)
        elif target == "btn:exit":
            self.running = False
        elif target == "btn:menu":
            self.editing = None
            self.goto(ST.MENU)
        elif target in ("btn:restart", "btn:next"):
            self.cell_times.clear()
            eng.new_round(keep_score=s.keep_score_on_new_round)
            self.selector.reset(lock=True)
        elif target == "btn:reset":
            self.cell_times.clear()
            eng.new_round(keep_score=False)
            self.selector.reset(lock=True)
        elif target == "btn:dwell":
            c = cfg.DWELL_CHOICES
            s.dwell_time = c[(c.index(s.dwell_time) + 1) % len(c)] if s.dwell_time in c else c[0]
        elif target == "btn:mode":
            s.selection_mode = "pinch" if s.selection_mode == "dwell" else "dwell"
        elif target == "btn:zones":
            s.use_player_zones = not s.use_player_zones
        elif target == "btn:first":
            s.first_player = 1 - s.first_player
        elif target == "btn:debug":
            s.debug_landmarks = not s.debug_landmarks
        elif target in ("btn:name0", "btn:name1"):
            self.editing = int(target[-1])
            s.player_names[self.editing] = ""
        if target != "btn:menu":
            self.selector.reset(lock=True)

    # ---- one frame ----------------------------------------------------
    def update(self, now):
        eng = self.engine
        self.selector.dwell_time = self.settings.dwell_time
        self.selector.mode = self.settings.selection_mode
        self.active_pointer = self.pick_pointer()

        if eng.state == ST.CAMERA_ERROR:
            self.sel = None
            return
        if eng.state == ST.SETUP:
            self.update_setup(now)

        targets = {bid: rect for bid, (rect, _) in self.buttons().items()}
        if eng.state == ST.PLAYING:
            targets.update(self.mapper.all_rects())

        p = self.active_pointer
        usable = p is not None and not p.ambiguous                   # ambiguous gesture = ignored
        self.sel = self.selector.update((p.x, p.y) if usable else None, targets, now,
                                        p.pinching if usable else False)
        if self.sel.selected and self.editing is None:
            self.activate(self.sel.selected, now)

    def update_setup(self, now):
        """SETUP: wait until the hand(s) are visible, then count down 3-2-1."""
        needed = 2 if self.settings.use_player_zones and not self.mouse_mode else 1
        owners = {p.owner for p in self.pointers if p.owner is not None}
        seen = len(owners) if needed == 2 else len(self.pointers)
        if seen < needed:
            self.setup_since = self.countdown_end = None
        elif self.setup_since is None:
            self.setup_since = now
        elif self.countdown_end is None and now - self.setup_since >= cfg.SETUP_READY_S:
            self.countdown_end = now + cfg.COUNTDOWN_S
        if self.countdown_end is not None and now >= self.countdown_end:
            self.cell_times.clear()
            self.engine.begin_match()
            self.selector.reset(lock=True)
            self.setup_since = self.countdown_end = None
        self.setup_seen, self.setup_needed = seen, needed

    def draw(self, frame, now):
        r, eng, st = self.renderer, self.engine, self.engine.state
        img = r.background(frame)
        if st == ST.CAMERA_ERROR:
            r.camera_error(img, self.error_detail)
            return img
        if st == ST.MENU:
            note = None if (self.camera_ok or self.mouse_mode) else "No camera detected - press Start to see options"
            r.menu(img, note, "hint_pinch" if self.settings.selection_mode == "pinch" else "hint_dwell")
        elif st == ST.INSTRUCTIONS:
            r.instructions(img)
        elif st == ST.SETTINGS:
            r.settings_screen(img, self.editing)
        elif st == ST.SETUP:
            left = None if self.countdown_end is None else max(1, int(self.countdown_end - now) + 1)
            r.setup(img, self.setup_needed, self.setup_seen, left)
        else:
            r.game(img, eng, self.mapper, self.sel, now, self.cell_times, self.result_time, self.toast)
        r.buttons(img, self.buttons(), self.sel)
        r.pointers(img, self.pointers, self.active_pointer, self.sel, self.settings.debug_landmarks)
        return img

    def step(self, frame, pointers, now):
        """Run one frame of the whole game and return the image to show."""
        self.pointers = pointers
        self.update(now)
        return self.draw(frame, now)

    # ---- keyboard -----------------------------------------------------
    def on_key(self, key):
        if key == 255 or key < 0:
            return
        st = self.engine.state
        if self.editing is not None:                                  # typing a player name
            names = self.settings.player_names
            if key in (13, 10):
                if not names[self.editing].strip():
                    names[self.editing] = f"Player {self.editing + 1}"
                self.editing = None
                self.engine.sync_settings()
            elif key == 27:
                names[self.editing] = f"Player {self.editing + 1}"
                self.editing = None
            elif key in (8, 127):
                names[self.editing] = names[self.editing][:-1]
            elif 32 <= key <= 126 and len(names[self.editing]) < cfg.MAX_NAME_LEN:
                names[self.editing] += chr(key)
            return
        ch = chr(key).lower() if 0 <= key < 128 else ""
        if ch == "q":
            self.running = False
        elif ch == "h":
            self.settings.debug_landmarks = not self.settings.debug_landmarks
        elif key == 27:
            if st == ST.MENU:
                self.running = False
            else:
                self.goto(ST.MENU)
        elif st == ST.CAMERA_ERROR and ch == "r":
            self.retry_camera = True
        elif st == ST.CAMERA_ERROR and ch == "m":
            self.mouse_mode = True
            self.goto(ST.MENU)
        elif ch == "r" and st in (ST.PLAYING, ST.ROUND_RESULT):
            self.activate("btn:restart", time.monotonic())
        elif ch == "n" and st == ST.ROUND_RESULT:
            self.activate("btn:next", time.monotonic())


# =====================================================================
# Part 4: run()  (the real loop: camera -> hands -> Game -> window)
# =====================================================================
def parse_args():
    p = argparse.ArgumentParser(description="Gesture Tic-Tac-Toe")
    p.add_argument("--camera", type=int, default=cfg.CAMERA_INDEX, help="camera index (default 0)")
    p.add_argument("--mouse", action="store_true", help="use the mouse instead of a camera")
    p.add_argument("--debug", action="store_true", help="show hand landmarks and FPS")
    return p.parse_args()


def run(args):
    from .hand_tracker import Camera, HandTracker

    settings = cfg.Settings(debug_landmarks=args.debug)
    game = Game(settings)
    game.mouse_mode = args.mouse
    camera, tracker, detector, mouse = None, None, GestureDetector(settings), MouseInput()

    def open_camera():
        """FR-01: check the camera (and the hand model) before a game can start."""
        nonlocal camera, tracker
        game.error_detail = ""
        camera = Camera(args.camera)
        game.camera_ok = camera.open()
        if not game.camera_ok:
            game.error_detail = f"camera index {args.camera} could not be opened"
            return
        try:
            tracker = tracker or HandTracker()
        except Exception as exc:
            game.camera_ok = False
            game.error_detail = str(exc).splitlines()[0]
            print("Hand tracker problem:\n", exc)

    if not args.mouse:
        open_camera()

    cv2.namedWindow(cfg.WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(cfg.WINDOW_NAME, cfg.WINDOW_W, cfg.WINDOW_H)
    cv2.setMouseCallback(cfg.WINDOW_NAME, mouse.on_mouse)

    lost_since, last_time, fps = None, time.monotonic(), 0.0
    try:
        while game.running:
            now = time.monotonic()
            frame = None
            if game.retry_camera:
                game.retry_camera = False
                open_camera()
                if game.camera_ok:
                    game.goto(ST.MENU)
            if not game.mouse_mode and camera is not None and camera.is_open:
                frame = camera.read()
                if frame is None:                                     # FR-14: lost camera feed
                    lost_since = lost_since or now
                    if now - lost_since > 2.0 and game.engine.state in (ST.SETUP, ST.PLAYING):
                        game.camera_ok = False
                        game.error_detail = "the camera stopped sending frames"
                        game.goto(ST.CAMERA_ERROR)
                else:
                    lost_since = None

            if game.mouse_mode:
                pointers = mouse.update()
            elif frame is not None and tracker is not None:
                tracker.set_max_hands(2 if settings.use_player_zones else 1)
                pointers = detector.update(tracker.process(frame))   # no hands -> []  (no crash)
            else:
                pointers = []

            img = game.step(frame, pointers, now)
            if settings.debug_landmarks:
                fps = 0.9 * fps + 0.1 / max(now - last_time, 1e-6)
                cv2.putText(img, f"{fps:4.0f} FPS", (cfg.WINDOW_W - 130, cfg.WINDOW_H - 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1, cv2.LINE_AA)
            last_time = now
            cv2.imshow(cfg.WINDOW_NAME, img)
            game.on_key(cv2.waitKey(1) & 0xFF)
            if cv2.getWindowProperty(cfg.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:                                                          # FR-14: safe exit
        if camera is not None:
            camera.release()
        if tracker is not None:
            tracker.close()
        cv2.destroyAllWindows()
