"""BGM & SE audio engine with swappable backends.

PVNM uses pygame.mixer on desktop when available because Pyxel's built-in PCM
playback is fixed at 22050 Hz. Standalone macOS app builds can use
AVFoundation, and pyxapp/portable builds can fall back to Pyxel PCM.

The public module API is intentionally kept stable:
  - init_audio()
  - play_bgm(path, vol, loop, start)
  - fadeout_bgm(frames)
  - update()
  - stop_bgm()
  - get_bgm_pos_sec()
  - is_bgm_playing()
  - play_se(path, vol, repeat)
  - stop_all_se()
  - set_mute(bgm=, se=)
  - cleanup()

Future Web/Android builds can provide ``window.PVNM_AUDIO`` from JavaScript.
When running under Pyodide/Emscripten, ``WebAudioBackend`` will use that bridge
and expose the music ``currentTime`` as the parent clock for timeline sync.
"""
from __future__ import annotations

import os
import sys
from typing import Any

try:
    import pygame as _pygame
    _pygame_imported = True
except ImportError:
    _pygame = None
    _pygame_imported = False


_available: bool = False
_backend: str = "none"
_mute_bgm: bool = False
_mute_se: bool = False
_bgm_gain: float = 0.7
_bgm_fade: "dict[str, float] | None" = None


def _vol_to_unit(volume: int) -> float:
    """Convert PVNM user volume (1-10) to backend gain (0.0-1.0)."""
    v = max(1, min(10, int(volume)))
    return v / 10.0


class AudioBackend:
    """Small interface shared by all audio backends."""

    name = "none"

    def __init__(self) -> None:
        self.available = False

    def init(self) -> bool:
        return False

    def play_bgm(self, abs_path: str, volume: int, loop: bool,
                 start: float) -> bool:
        return False

    def stop_bgm(self) -> None:
        pass

    def set_bgm_volume(self, volume_unit: float) -> None:
        pass

    def get_bgm_pos_sec(self) -> float:
        return 0.0

    def is_bgm_playing(self) -> bool:
        return False

    def play_se(self, abs_path: str, volume: int, repeat: int) -> bool:
        return False

    def stop_all_se(self) -> None:
        pass

    def cleanup(self) -> None:
        self.stop_bgm()
        self.stop_all_se()
        self.available = False


class NullAudioBackend(AudioBackend):
    name = "none"


class PygameAudioBackend(AudioBackend):
    """44.1 kHz desktop backend powered by pygame.mixer."""

    name = "pygame"

    def __init__(self, pygame_mod: Any) -> None:
        super().__init__()
        self._pygame = pygame_mod
        self._current_bgm_path = ""
        self._current_bgm_vol = 0.7
        self._bgm_start_offset = 0.0
        self._se_cache: dict[str, Any] = {}

    def init(self) -> bool:
        try:
            # Direct mixer.init is more reliable than pre_init + init on some
            # handheld Linux builds. Keep this before pyxel.init in pyxapp.
            self._pygame.mixer.init(frequency=44100, size=-16,
                                    channels=2, buffer=8192)
            self._pygame.mixer.set_num_channels(8)
            self.available = True
            return True
        except Exception as e:
            print(f"[audio] pygame.mixer init failed: {e}")
            self.available = False
            return False

    def play_bgm(self, abs_path: str, volume: int, loop: bool,
                 start: float) -> bool:
        self._current_bgm_vol = _vol_to_unit(volume)
        try:
            if (abs_path == self._current_bgm_path
                    and self._pygame.mixer.music.get_busy()
                    and float(start) <= 0.0):
                self._pygame.mixer.music.set_volume(self._current_bgm_vol)
                return True
            self._current_bgm_path = abs_path
            self._bgm_start_offset = max(0.0, float(start))
            if _mute_bgm:
                return True
            self._pygame.mixer.music.load(abs_path)
            self._pygame.mixer.music.set_volume(self._current_bgm_vol)
            self._pygame.mixer.music.play(loops=-1 if loop else 0,
                                          start=self._bgm_start_offset)
            return True
        except Exception as e:
            print(f"[audio] BGM play failed: {e}")
            return False

    def stop_bgm(self) -> None:
        self._current_bgm_path = ""
        self._bgm_start_offset = 0.0
        try:
            self._pygame.mixer.music.stop()
        except Exception:
            pass

    def set_bgm_volume(self, volume_unit: float) -> None:
        self._current_bgm_vol = max(0.0, min(1.0, float(volume_unit)))
        try:
            self._pygame.mixer.music.set_volume(
                0.0 if _mute_bgm else self._current_bgm_vol)
        except Exception:
            pass

    def get_bgm_pos_sec(self) -> float:
        try:
            ms = self._pygame.mixer.music.get_pos()
            if ms < 0:
                return 0.0
            return self._bgm_start_offset + ms / 1000.0
        except Exception:
            return 0.0

    def is_bgm_playing(self) -> bool:
        try:
            return bool(self._pygame.mixer.music.get_busy())
        except Exception:
            return False

    def _get_or_load_sound(self, abs_path: str):
        snd = self._se_cache.get(abs_path)
        if snd is not None:
            return snd
        try:
            snd = self._pygame.mixer.Sound(abs_path)
            self._se_cache[abs_path] = snd
            return snd
        except Exception as e:
            print(f"[audio] SE load failed ({abs_path}): {e}")
            return None

    def play_se(self, abs_path: str, volume: int, repeat: int) -> bool:
        snd = self._get_or_load_sound(abs_path)
        if snd is None:
            return False
        try:
            snd.set_volume(_vol_to_unit(volume))
            snd.play(loops=-1 if repeat > 0 else 0)
            return True
        except Exception as e:
            print(f"[audio] SE play failed: {e}")
            return False

    def stop_all_se(self) -> None:
        for snd in list(self._se_cache.values()):
            try:
                snd.stop()
            except Exception:
                pass

    def cleanup(self) -> None:
        self.stop_all_se()
        self.stop_bgm()
        self._se_cache.clear()
        try:
            self._pygame.mixer.quit()
        except Exception:
            pass
        self.available = False


class PyxelPcmBackend(AudioBackend):
    """Portable fallback using Pyxel PCM playback."""

    name = "pyxel"

    def __init__(self) -> None:
        super().__init__()
        self._current_bgm_path = ""
        self._current_bgm_vol = 0.7
        self._bgm_start_offset = 0.0
        self._se_cache: dict[str, int] = {}
        self._next_sound = 1
        self._next_channel = 1

    def init(self) -> bool:
        try:
            import pyxel
            pyxel.channels[0].gain = self._current_bgm_vol
            for ch in range(1, 4):
                pyxel.channels[ch].gain = 0.7
            self.available = True
            print("[audio] using pyxel PCM backend")
            return True
        except Exception as e:
            print(f"[audio] pyxel PCM backend unavailable: {e}")
            self.available = False
            return False

    def play_bgm(self, abs_path: str, volume: int, loop: bool,
                 start: float) -> bool:
        try:
            import pyxel
            self._current_bgm_vol = _vol_to_unit(volume)
            if (abs_path == self._current_bgm_path
                    and pyxel.play_pos(0) is not None
                    and float(start) <= 0.0):
                pyxel.channels[0].gain = (
                    0.0 if _mute_bgm else self._current_bgm_vol)
                return True
            self._current_bgm_path = abs_path
            self._bgm_start_offset = max(0.0, float(start))
            if _mute_bgm:
                return True
            pyxel.sounds[0].pcm(abs_path)
            pyxel.channels[0].gain = self._current_bgm_vol
            pyxel.play(0, 0, sec=self._bgm_start_offset, loop=loop)
            return True
        except Exception as e:
            print(f"[audio] Pyxel BGM play failed: {e}")
            return False

    def stop_bgm(self) -> None:
        self._current_bgm_path = ""
        self._bgm_start_offset = 0.0
        try:
            import pyxel
            pyxel.stop(0)
        except Exception:
            pass

    def set_bgm_volume(self, volume_unit: float) -> None:
        self._current_bgm_vol = max(0.0, min(1.0, float(volume_unit)))
        try:
            import pyxel
            pyxel.channels[0].gain = (
                0.0 if _mute_bgm else self._current_bgm_vol)
        except Exception:
            pass

    def get_bgm_pos_sec(self) -> float:
        try:
            import pyxel
            pos = pyxel.play_pos(0)
            return 0.0 if pos is None else float(pos[1])
        except Exception:
            return 0.0

    def is_bgm_playing(self) -> bool:
        try:
            import pyxel
            return pyxel.play_pos(0) is not None
        except Exception:
            return False

    def _sound_slot(self, abs_path: str) -> int:
        slot = self._se_cache.get(abs_path)
        if slot is not None:
            return slot
        import pyxel
        slot = self._next_sound
        self._next_sound += 1
        if self._next_sound >= 64:
            self._next_sound = 1
        pyxel.sounds[slot].pcm(abs_path)
        self._se_cache[abs_path] = slot
        return slot

    def play_se(self, abs_path: str, volume: int, repeat: int) -> bool:
        try:
            import pyxel
            slot = self._sound_slot(abs_path)
            ch = self._next_channel
            self._next_channel += 1
            if self._next_channel > 3:
                self._next_channel = 1
            pyxel.channels[ch].gain = _vol_to_unit(volume)
            pyxel.play(ch, slot, loop=(repeat > 0))
            return True
        except Exception as e:
            print(f"[audio] Pyxel SE play failed: {e}")
            return False

    def stop_all_se(self) -> None:
        try:
            import pyxel
            for ch in range(1, 4):
                pyxel.stop(ch)
        except Exception:
            pass

    def cleanup(self) -> None:
        try:
            import pyxel
            pyxel.stop()
        except Exception:
            pass
        self._current_bgm_path = ""
        self._bgm_start_offset = 0.0
        self._se_cache.clear()
        self.available = False


class AVFoundationBackend(AudioBackend):
    """macOS standalone app backend using PyObjC AVFoundation."""

    name = "avfoundation"

    def __init__(self) -> None:
        super().__init__()
        self._avf = None
        self._nsurl = None
        self._bgm_player = None
        self._se_players: list[Any] = []
        self._current_bgm_path = ""
        self._current_bgm_vol = 0.7
        self._bgm_start_offset = 0.0

    def init(self) -> bool:
        if sys.platform != "darwin":
            return False
        try:
            import AVFoundation
            from Foundation import NSURL
            self._avf = AVFoundation
            self._nsurl = NSURL
            self.available = True
            print("[audio] using AVFoundation backend")
            return True
        except Exception as e:
            print(f"[audio] AVFoundation backend unavailable: {e}")
            self.available = False
            return False

    def _new_player(self, abs_path: str):
        if self._avf is None or self._nsurl is None:
            return None
        try:
            url = self._nsurl.fileURLWithPath_(abs_path)
            result = self._avf.AVAudioPlayer.alloc().initWithContentsOfURL_error_(
                url, None)
            player = result[0] if isinstance(result, tuple) else result
            if player is None:
                return None
            try:
                player.prepareToPlay()
            except Exception:
                pass
            return player
        except Exception as e:
            print(f"[audio] AVFoundation load failed ({abs_path}): {e}")
            return None

    def play_bgm(self, abs_path: str, volume: int, loop: bool,
                 start: float) -> bool:
        self._current_bgm_vol = _vol_to_unit(volume)
        try:
            if (abs_path == self._current_bgm_path
                    and self._bgm_player is not None
                    and self._bgm_player.isPlaying()
                    and float(start) <= 0.0):
                self._bgm_player.setVolume_(
                    0.0 if _mute_bgm else self._current_bgm_vol)
                return True
        except Exception:
            pass
        self.stop_bgm()
        self._current_bgm_path = abs_path
        self._bgm_start_offset = max(0.0, float(start))
        if _mute_bgm:
            return True
        player = self._new_player(abs_path)
        if player is None:
            return False
        try:
            player.setNumberOfLoops_(-1 if loop else 0)
            player.setVolume_(self._current_bgm_vol)
            if self._bgm_start_offset > 0:
                player.setCurrentTime_(self._bgm_start_offset)
            player.play()
            self._bgm_player = player
            return True
        except Exception as e:
            print(f"[audio] AVFoundation BGM play failed: {e}")
            return False

    def stop_bgm(self) -> None:
        if self._bgm_player is not None:
            try:
                self._bgm_player.stop()
            except Exception:
                pass
        self._bgm_player = None
        self._current_bgm_path = ""
        self._bgm_start_offset = 0.0

    def set_bgm_volume(self, volume_unit: float) -> None:
        self._current_bgm_vol = max(0.0, min(1.0, float(volume_unit)))
        if self._bgm_player is None:
            return
        try:
            self._bgm_player.setVolume_(
                0.0 if _mute_bgm else self._current_bgm_vol)
        except Exception:
            pass

    def get_bgm_pos_sec(self) -> float:
        try:
            return (0.0 if self._bgm_player is None
                    else float(self._bgm_player.currentTime()))
        except Exception:
            return 0.0

    def is_bgm_playing(self) -> bool:
        try:
            return bool(self._bgm_player is not None
                        and self._bgm_player.isPlaying())
        except Exception:
            return False

    def _cleanup_se_players(self) -> None:
        try:
            self._se_players[:] = [
                p for p in self._se_players
                if p is not None and bool(p.isPlaying())
            ]
        except Exception:
            pass

    def play_se(self, abs_path: str, volume: int, repeat: int) -> bool:
        self._cleanup_se_players()
        player = self._new_player(abs_path)
        if player is None:
            return False
        try:
            player.setNumberOfLoops_(-1 if repeat > 0 else 0)
            player.setVolume_(_vol_to_unit(volume))
            player.play()
            self._se_players.append(player)
            return True
        except Exception as e:
            print(f"[audio] AVFoundation SE play failed: {e}")
            return False

    def stop_all_se(self) -> None:
        for player in list(self._se_players):
            try:
                player.stop()
            except Exception:
                pass
        self._se_players.clear()

    def cleanup(self) -> None:
        self.stop_bgm()
        self.stop_all_se()
        self.available = False


class WebAudioBackend(AudioBackend):
    """Pyodide/Emscripten bridge for future Web/Android exports."""

    name = "webaudio"

    def __init__(self) -> None:
        super().__init__()
        self._api = None

    def init(self) -> bool:
        if sys.platform != "emscripten":
            return False
        try:
            from js import window  # type: ignore
            api = getattr(window, "PVNM_AUDIO", None)
            if api is None:
                return False
            self._api = api
            self.available = True
            print("[audio] using WebAudio backend")
            return True
        except Exception as e:
            print(f"[audio] WebAudio backend unavailable: {e}")
            self.available = False
            return False

    def _call(self, names: tuple[str, ...], *args) -> bool:
        if self._api is None:
            return False
        for name in names:
            fn = getattr(self._api, name, None)
            if callable(fn):
                try:
                    fn(*args)
                    return True
                except Exception as e:
                    print(f"[audio] WebAudio {name} failed: {e}")
                    return False
        return False

    def _read_float(self, names: tuple[str, ...]) -> float:
        if self._api is None:
            return 0.0
        for name in names:
            value = getattr(self._api, name, None)
            try:
                if callable(value):
                    value = value()
                if value is not None:
                    return float(value)
            except Exception:
                return 0.0
        return 0.0

    def _read_bool(self, names: tuple[str, ...]) -> bool:
        if self._api is None:
            return False
        for name in names:
            value = getattr(self._api, name, None)
            try:
                if callable(value):
                    value = value()
                if value is not None:
                    return bool(value)
            except Exception:
                return False
        return False

    def _asset_key_path(self, abs_path: str) -> str:
        """Prefer portable asset keys when calling the JavaScript bridge."""
        path = str(abs_path or "").replace("\\", "/")
        marker = "/assets/"
        idx = path.find(marker)
        if idx >= 0:
            return path[idx + 1:]
        if path.startswith("./assets/"):
            return path[2:]
        if path.startswith("assets/"):
            return path
        return path

    def play_bgm(self, abs_path: str, volume: int, loop: bool,
                 start: float) -> bool:
        if _mute_bgm:
            return True
        web_path = self._asset_key_path(abs_path)
        return self._call(("playBgm", "play_bgm"),
                          web_path, _vol_to_unit(volume), bool(loop),
                          max(0.0, float(start)))

    def stop_bgm(self) -> None:
        self._call(("stopBgm", "stop_bgm"))

    def set_bgm_volume(self, volume_unit: float) -> None:
        self._call(("setBgmVolume", "set_bgm_volume"),
                   max(0.0, min(1.0, float(volume_unit))))

    def get_bgm_pos_sec(self) -> float:
        return self._read_float(("getBgmCurrentTime", "get_bgm_current_time",
                                 "currentTime", "current_time"))

    def is_bgm_playing(self) -> bool:
        return self._read_bool(("isBgmPlaying", "is_bgm_playing", "playing"))

    def play_se(self, abs_path: str, volume: int, repeat: int) -> bool:
        web_path = self._asset_key_path(abs_path)
        return self._call(("playSe", "play_se"),
                          web_path, _vol_to_unit(volume), int(repeat))

    def stop_all_se(self) -> None:
        self._call(("stopAllSe", "stop_all_se"))


_backend_obj: AudioBackend = NullAudioBackend()


def _set_backend(backend_obj: AudioBackend) -> None:
    global _backend_obj, _available, _backend
    _backend_obj = backend_obj
    _available = bool(backend_obj.available)
    _backend = backend_obj.name


def _backend_candidates() -> list[AudioBackend]:
    candidates: list[AudioBackend] = []
    if sys.platform == "emscripten":
        candidates.append(WebAudioBackend())
    if _pygame_imported and _pygame is not None:
        candidates.append(PygameAudioBackend(_pygame))
    candidates.append(AVFoundationBackend())
    candidates.append(PyxelPcmBackend())
    return candidates


def init_audio() -> None:
    """Initialize the best available audio backend."""
    if _available:
        return
    for candidate in _backend_candidates():
        if candidate.init():
            _set_backend(candidate)
            return
    _set_backend(NullAudioBackend())


def _switch_to_pyxel_backend() -> bool:
    """Switch to Pyxel PCM backend after another backend fails."""
    global _backend_obj
    pyxel_backend = PyxelPcmBackend()
    if not pyxel_backend.init():
        return False
    old_backend = _backend_obj
    if old_backend.name not in ("none", "pyxel"):
        try:
            old_backend.cleanup()
        except Exception:
            pass
    _set_backend(pyxel_backend)
    return True


# ── Public BGM API ───────────────────────────────────────────────


def play_bgm(path: str, volume: int = 7, loop: bool = True,
             start: float = 0.0) -> None:
    """Play BGM. Reuse the current stream when the same path is already playing."""
    global _bgm_gain, _bgm_fade
    if not _available:
        return
    _bgm_fade = None
    _bgm_gain = _vol_to_unit(user_vol_to_int(volume))
    abs_path = os.path.abspath(path)
    if _backend != "webaudio" and not os.path.exists(abs_path):
        return
    ok = _backend_obj.play_bgm(abs_path, user_vol_to_int(volume), loop, start)
    if not ok and _backend not in ("pyxel", "none"):
        if _switch_to_pyxel_backend():
            print("[audio] retrying BGM with Pyxel PCM backend")
            _backend_obj.play_bgm(abs_path, user_vol_to_int(volume),
                                  loop, start)


def stop_bgm() -> None:
    global _bgm_gain, _bgm_fade
    if not _available:
        return
    _bgm_fade = None
    _bgm_gain = 0.0
    _backend_obj.stop_bgm()


def fadeout_bgm(frames: int) -> None:
    """Fade the current BGM to silence over the given number of frames."""
    global _bgm_fade
    try:
        total = max(0, int(frames))
    except Exception:
        total = 0
    if not _available:
        return
    if total <= 0 or not _backend_obj.is_bgm_playing():
        stop_bgm()
        return
    _bgm_fade = {
        "frame": 0.0,
        "frames": float(total),
        "start_gain": max(0.0, min(1.0, float(_bgm_gain))),
    }


def update() -> None:
    """Advance frame-based audio fades. Call once per Pyxel frame."""
    global _bgm_gain, _bgm_fade
    if not _available or _bgm_fade is None:
        return
    frames = max(1.0, float(_bgm_fade.get("frames", 1.0)))
    frame = float(_bgm_fade.get("frame", 0.0)) + 1.0
    start_gain = max(0.0, min(1.0, float(_bgm_fade.get("start_gain", _bgm_gain))))
    t = min(1.0, frame / frames)
    gain = start_gain * (1.0 - t)
    _bgm_fade["frame"] = frame
    _bgm_gain = gain
    try:
        _backend_obj.set_bgm_volume(gain)
    except Exception:
        pass
    if frame >= frames:
        _bgm_fade = None
        stop_bgm()


def get_bgm_pos_sec() -> float:
    """Return current BGM position in seconds for timeline synchronization."""
    if not _available:
        return 0.0
    return _backend_obj.get_bgm_pos_sec()


def is_bgm_playing() -> bool:
    if not _available:
        return False
    return _backend_obj.is_bgm_playing()


# ── Public SE API ────────────────────────────────────────────────


def play_se(path: str, volume: int = 7, repeat: int = 0) -> None:
    if not _available or _mute_se:
        return
    abs_path = os.path.abspath(path)
    if _backend != "webaudio" and not os.path.exists(abs_path):
        return
    ok = _backend_obj.play_se(abs_path, user_vol_to_int(volume), repeat)
    if not ok and _backend not in ("pyxel", "none"):
        if _switch_to_pyxel_backend():
            print("[audio] retrying SE with Pyxel PCM backend")
            _backend_obj.play_se(abs_path, user_vol_to_int(volume), repeat)


def stop_all_se() -> None:
    if not _available:
        return
    _backend_obj.stop_all_se()


# ── Common API ───────────────────────────────────────────────────


def set_mute(bgm: bool | None = None, se: bool | None = None) -> None:
    """Set mute flags. Muting stops currently playing sounds."""
    global _mute_bgm, _mute_se
    if bgm is not None:
        _mute_bgm = bool(bgm)
        if _mute_bgm:
            stop_bgm()
    if se is not None:
        _mute_se = bool(se)
        if _mute_se:
            stop_all_se()


def user_vol_to_int(v: int) -> int:
    """Clamp PVNM user volume to 1-10."""
    return max(1, min(10, int(v)))


def cleanup() -> None:
    """Release backend resources on application shutdown."""
    try:
        _backend_obj.cleanup()
    except Exception:
        pass
    _set_backend(NullAudioBackend())
