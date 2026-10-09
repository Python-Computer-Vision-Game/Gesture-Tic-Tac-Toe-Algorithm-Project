"""Sound effects (section 14).

The five sounds are plain WAV files in assets/sounds/:
    target.wav   a cell is targeted        confirm.wav  a move / button is confirmed
    invalid.wav  rejected move             win.wav      round won        draw.wav  round drawn

If a file is missing it is generated automatically (simple beeps), and you can replace any
of them with your own .wav file. Playback:
    Windows        winsound (built into Python, no extra install)
    Mac / Linux    sounddevice (python -m pip install sounddevice)
If no sound output works, the game simply runs silently.
"""
import sys
import wave
from pathlib import Path

import numpy as np

from . import config as cfg

SAMPLE_RATE = 44100
SOUND_DIR = cfg.ROOT_DIR / "assets" / "sounds"


def _tone(freq, dur, vol=0.35):
    t = np.linspace(0, dur, int(SAMPLE_RATE * dur), endpoint=False)
    wave_ = np.sin(2 * np.pi * freq * t)
    fade = max(1, int(SAMPLE_RATE * 0.01))                    # 10 ms fade in/out avoids clicks
    env = np.ones_like(wave_)
    env[:fade], env[-fade:] = np.linspace(0, 1, fade), np.linspace(1, 0, fade)
    return wave_ * env * vol


def _seq(*notes):
    return np.concatenate([_tone(f, d) for f, d in notes])


RECIPES = {
    "target": lambda: _seq((880, 0.05)),
    "confirm": lambda: _seq((660, 0.07), (990, 0.12)),
    "invalid": lambda: _seq((190, 0.16), (140, 0.22)),
    "win": lambda: _seq((523, 0.12), (659, 0.12), (784, 0.12), (1047, 0.35)),
    "draw": lambda: _seq((440, 0.18), (370, 0.18), (330, 0.32)),
}


def write_wav(path, samples):
    """Save float samples (-1..1) as a 16-bit mono WAV."""
    pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(pcm.tobytes())


def read_wav(path):
    """Return (float32 samples, sample_rate) for a 16-bit WAV file."""
    with wave.open(str(path), "rb") as f:
        rate, channels = f.getframerate(), f.getnchannels()
        data = np.frombuffer(f.readframes(f.getnframes()), np.int16).astype(np.float32) / 32768
    return (data.reshape(-1, channels) if channels > 1 else data), rate


class AudioManager:
    def __init__(self, settings, enabled=True, sound_dir=SOUND_DIR):
        self.settings = settings
        self.backend = None                    # "winsound", "sounddevice" or None (silent)
        self.paths = {}
        self._data = {}
        if not enabled:
            return
        try:
            sound_dir = Path(sound_dir)
            sound_dir.mkdir(parents=True, exist_ok=True)
            for name, make in RECIPES.items():
                path = sound_dir / f"{name}.wav"
                if not path.exists():
                    write_wav(path, make())
                self.paths[name] = path
        except Exception as exc:
            print("Sound disabled (could not prepare sound files):", exc)
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
                sd.query_devices(kind="output")                    # raises if there is no speaker
                self._sd = sd
                self._data = {n: read_wav(p) for n, p in self.paths.items()}
                self.backend = "sounddevice"
            except Exception:
                self.backend = None
        print(f"Sound: {self.backend or 'off (no audio backend found)'}")

    def play(self, name):
        if self.backend is None or not self.settings.sound or name not in self.paths:
            return
        try:
            self._emit(name)
        except Exception:
            self.backend = None                                    # stop trying; stay silent

    def _emit(self, name):
        if self.backend == "winsound":
            ws = self._winsound
            ws.PlaySound(str(self.paths[name]), ws.SND_FILENAME | ws.SND_ASYNC | ws.SND_NODEFAULT)
        else:
            data, rate = self._data[name]
            self._sd.play(data, rate)                              # non-blocking