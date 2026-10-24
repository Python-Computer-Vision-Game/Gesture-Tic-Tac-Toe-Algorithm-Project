
from __future__ import annotations
import sys
from pathlib import Path
from . import config as cfg

SOUND_DIR = cfg.ROOT_DIR / "assets" / "sounds"
FILES = {
    "target": "click.wav",
    "click": "click.wav",
    "confirm": "place_x.wav",
    "place_x": "place_x.wav",
    "place_o": "place_o.wav",
    "select": "place_x.wav",
    "invalid": "invalid.wav",
    "win": "win.wav",
    "draw": "draw.wav",
}

MUSIC_FILE = "background_music.wav"


class AudioManager:
    def __init__(self, settings, enabled=True, sound_dir=SOUND_DIR):
        self.settings = settings
        self.backend = None
        self.paths = {}
        self._pygame = None
        self._winsound = None
        self._music_path = None
        self.music_on = True

        if not enabled:
            print("Sound: off")
            return

        sound_dir = Path(sound_dir)
        for name, filename in FILES.items():
            path = sound_dir / filename
            if path.is_file():
                self.paths[name] = path

        music = sound_dir / MUSIC_FILE
        if music.is_file():
            self._music_path = music

        try:
            import pygame
            pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
            self._pygame = pygame
            self.backend = "pygame"
        except Exception:
            pass

        if self.backend is None and sys.platform.startswith("win"):
            try:
                import winsound
                self._winsound = winsound
                self.backend = "winsound"
            except ImportError:
                pass

        print(f"Sound: {self.backend or 'off'} (audio pack)")

        if self.backend and getattr(settings, "sound", True):
            self.start_music()

    def play(self, name: str) -> None:
        if self.backend is None:
            return
        if not getattr(self.settings, "sound", True):
            return
        path = self.paths.get(name)
        if path is None:
            return
        try:
            if self.backend == "pygame":
                sound = self._pygame.mixer.Sound(str(path))
                sound.set_volume(0.7)
                sound.play()
            else:
                self._winsound.PlaySound(
                    str(path),
                    self._winsound.SND_FILENAME
                    | self._winsound.SND_ASYNC
                    | self._winsound.SND_NODEFAULT,
                )
        except Exception as e:
            print("Sound play error:", e)

    def start_music(self) -> None:
        if not self._music_path or not self.backend:
            return
        if not getattr(self.settings, "sound", True):
            return
        self.music_on = True
        try:
            if self.backend == "pygame":
                self._pygame.mixer.music.load(str(self._music_path))
                self._pygame.mixer.music.set_volume(0.25)
                self._pygame.mixer.music.play(-1)
                print("Music: started (loop)")
            else:
                self._winsound.PlaySound(
                    str(self._music_path),
                    self._winsound.SND_FILENAME
                    | self._winsound.SND_ASYNC
                    | self._winsound.SND_NODEFAULT,
                )
                print("Music: started (once)")
        except Exception as e:
            print("Music start error:", e)

    def stop_music(self) -> None:
        self.music_on = False
        if self.backend == "pygame" and self._pygame:
            self._pygame.mixer.music.stop()
        print("Music: stopped")

    def toggle_music(self) -> None:
        if self.music_on:
            self.stop_music()
        else:
            self.start_music()
