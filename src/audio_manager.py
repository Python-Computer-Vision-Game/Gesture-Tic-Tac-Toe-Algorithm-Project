"""Lovable-style synth: SFX + looping background music.

Port of the TypeScript Web Audio version:
  sfx: click, place, invalid, win, draw, target
  music: soft looping melody (MELODY array, 300ms steps)
"""
from __future__ import annotations

import sys
import threading
import time
import wave
from pathlib import Path

import numpy as np

from . import config as cfg

SAMPLE_RATE = 44100
SOUND_DIR = cfg.ROOT_DIR / "assets" / "sounds"

# Same melody as Lovable TS
MELODY = [262, 330, 392, 330, 294, 349, 440, 349, 262, 330, 392, 523, 494, 392, 330, 294]


def _osc(freq: float, n: int, wave_type: str) -> np.ndarray:
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    phase = 2 * np.pi * freq * t
    if wave_type == "square":
        return np.sign(np.sin(phase)).astype(np.float32)
    if wave_type == "triangle":
        return (2 / np.pi * np.arcsin(np.sin(phase))).astype(np.float32)
    if wave_type == "sawtooth":
        return (2 * (t * freq - np.floor(t * freq + 0.5))).astype(np.float32)
    return np.sin(phase).astype(np.float32)


def _tone(freq: float, dur: float, wave_type: str = "sine", vol: float = 0.15) -> np.ndarray:
    n = max(1, int(SAMPLE_RATE * dur))
    wave_ = _osc(freq, n, wave_type)
    attack = max(1, int(SAMPLE_RATE * 0.008))
    env = np.ones(n, dtype=np.float32)
    env[:attack] = np.linspace(0.0, 1.0, attack, dtype=np.float32)
    rest = n - attack
    if rest > 0:
        env[attack:] = np.exp(-np.linspace(0, 5.5, rest, dtype=np.float32))
    return (wave_ * env * vol).astype(np.float32)


def _place_buffer(f1: float, f2: float) -> np.ndarray:
    total = int(SAMPLE_RATE * 0.28)
    buf = np.zeros(total, dtype=np.float32)
    a = _tone(f1, 0.12, "triangle", 0.14)
    b = _tone(f2, 0.15, "triangle", 0.12)
    buf[: len(a)] += a
    start = int(SAMPLE_RATE * 0.06)
    buf[start: start + len(b)] += b
    return np.clip(buf, -1.0, 1.0).astype(np.float32)


def _arpeggio(freqs, note_dur, gap, wave_type, vol) -> np.ndarray:
    total = int(SAMPLE_RATE * (gap * (len(freqs) - 1) + note_dur + 0.05))
    buf = np.zeros(max(total, 1), dtype=np.float32)
    for i, f in enumerate(freqs):
        note = _tone(f, note_dur, wave_type, vol)
        start = int(SAMPLE_RATE * gap * i)
        end = start + len(note)
        if end > len(buf):
            buf = np.pad(buf, (0, end - len(buf)))
        buf[start:end] += note
    return np.clip(buf, -1.0, 1.0).astype(np.float32)


def _click():
    return _tone(660, 0.08, "square", 0.07)


def _confirm():
    return _place_buffer(520, 780)


def _invalid():
    return _tone(140, 0.25, "sawtooth", 0.09)

def _win():
    return _arpeggio([523, 659, 784, 1046], 0.30, 0.12, "triangle", 0.15)
def _draw():
    return _arpeggio([440, 392, 349], 0.30, 0.15, "sine", 0.13)

def _target():
    return _tone(880, 0.05, "sine", 0.10)

RECIPES = {
    "click": _click,
    "confirm": _confirm,
    "select": _confirm,
    "place": _confirm,
    "invalid": _invalid,
    "win": _win,
    "draw": _draw,
    "target": _target,
}


def write_wav(path: Path, samples: np.ndarray) -> None:
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(pcm.tobytes())


class AudioManager:
    """SFX via play(name) + soft looping background music."""

    def __init__(self, settings, enabled: bool = True, sound_dir=SOUND_DIR):
        self.settings = settings
        self.backend = None
        self.paths = {}
        self._data = {}
        self._music_stop = threading.Event()
        self._music_thread = None
        self.music_on = True  # background music enabled by default

        if not enabled:
            print("Sound: off")
            return

        try:
            sound_dir = Path(sound_dir)
            sound_dir.mkdir(parents=True, exist_ok=True)
            for name, make in RECIPES.items():
                path = sound_dir / f"{name}.wav"
                write_wav(path, make())
                self.paths[name] = path
        except Exception as exc:
            print("Sound disabled:", exc)
            return

        if sys.platform.startswith("win"):
            try:
                import winsound
                self._winsound = winsound
                self.backend = "winsound"
            except ImportError:
                pass

        if self.backend is None:
            try:
                import sounddevice as sd
                sd.query_devices(kind="output")
                self._sd = sd
                self._data = {n: self._load(p) for n, p in self.paths.items()}
                self.backend = "sounddevice"
            except Exception:
                self.backend = None

        print(f"Sound: {self.backend or 'off'} (Lovable synth + music)")

        # Start background music automatically
        if self.backend is not None and getattr(settings, "sound", True):
            self.start_music()

    @staticmethod
    def _load(path: Path):
        with wave.open(str(path), "rb") as f:
            rate = f.getframerate()
            data = np.frombuffer(f.readframes(f.getnframes()), np.int16).astype(np.float32) / 32768.0
        return data, rate

    def play(self, name: str) -> None:
        if self.backend is None:
            return
        if not getattr(self.settings, "sound", True):
            return
        if name not in self.paths:
            return
        try:
            self._emit_file(self.paths[name], name)
        except Exception:
            self.backend = None

    def _emit_file(self, path: Path, name: str | None = None) -> None:
        if self.backend == "winsound":
            ws = self._winsound
            ws.PlaySound(
                str(path),
                ws.SND_FILENAME | ws.SND_ASYNC | ws.SND_NODEFAULT,
            )
        else:
            key = name if name and name in self._data else None
            if key:
                data, rate = self._data[key]
            else:
                data, rate = self._load(path)
            self._sd.play(data, rate)

    def _emit_samples(self, samples: np.ndarray) -> None:
        """Play raw samples (used by music loop)."""
        if self.backend == "sounddevice":
            try:
                self._sd.play(samples, SAMPLE_RATE)
            except Exception:
                pass
        elif self.backend == "winsound":
            try:
                tmp = SOUND_DIR / "_music_tick.wav"
                write_wav(tmp, samples)
                self._winsound.PlaySound(
                    str(tmp),
                    self._winsound.SND_FILENAME | self._winsound.SND_ASYNC | self._winsound.SND_NODEFAULT,
                )
            except Exception:
                pass

    # ---- background music (Lovable MELODY loop) ---------------------------
    def start_music(self) -> None:
        if self.backend is None:
            return
        if self._music_thread and self._music_thread.is_alive():
            return
        self.music_on = True
        self._music_stop.clear()
        self._music_thread = threading.Thread(target=self._music_loop, daemon=True)
        self._music_thread.start()
        print("Music: started")

    def stop_music(self) -> None:
        self.music_on = False
        self._music_stop.set()
        print("Music: stopped")

    def toggle_music(self) -> None:
        if self.music_on and self._music_thread and self._music_thread.is_alive():
            self.stop_music()
        else:
            self.start_music()

    def _music_loop(self) -> None:
        """Same idea as TS: every 300ms play next melody note, bass every 4th."""
        i = 0
        while not self._music_stop.is_set():
            if not self.music_on or not getattr(self.settings, "sound", True):
                # wait until sound/music turned back on
                self._music_stop.wait(0.3)
                continue

            freq = float(MELODY[i % len(MELODY)])
            # Main soft sine note (vol 0.035 like Lovable)
            note = _tone(freq, 0.28, "sine", 0.045)
            if i % 4 == 0:
                # Bass triangle an octave below (vol 0.03)
                bass = _tone(freq / 2.0, 0.55, "triangle", 0.035)
                # mix bass under the note
                n = max(len(note), len(bass))
                mix = np.zeros(n, dtype=np.float32)
                mix[: len(note)] += note
                mix[: len(bass)] += bass
                note = np.clip(mix, -1.0, 1.0)

            self._emit_samples(note)
            i += 1
            # 300ms step like setInterval(..., 300)
            self._music_stop.wait(0.30)
