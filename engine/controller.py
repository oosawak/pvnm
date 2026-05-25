"""Gamepad input mapping for the runtime player.

Pyxel exposes gamepad buttons as constants such as GAMEPAD1_BUTTON_A. Some
handhelds swap the physical ABXY layout, so PVNM stores logical actions against
the actual Pyxel button name the player pressed.
"""
from __future__ import annotations

import os
import pyxel
from engine import storage as _storage


ACTION_DEFS = [
    ("confirm", "A / NEXT", "Choice OK / next page", "GAMEPAD1_BUTTON_A"),
    ("back", "B / BACK", "Previous scene / close menu", "GAMEPAD1_BUTTON_B"),
    ("auto", "X / AUTO", "Cycle autoplay speed", "GAMEPAD1_BUTTON_X"),
    ("opt", "Y / OPT", "Open options", "GAMEPAD1_BUTTON_Y"),
]

FIXED_ACTION_DEFS = [
    ("save", "START / SAVE", "Open save screen", "GAMEPAD1_BUTTON_START"),
    ("log", "L1 / LOG", "Open conversation log", "GAMEPAD1_BUTTON_LEFTSHOULDER"),
    ("skip_hold", "R1 / SKIP", "Hold to skip", "GAMEPAD1_BUTTON_RIGHTSHOULDER"),
    ("hide_dialog", "BACK / HIDE", "Show or hide dialog", "GAMEPAD1_BUTTON_BACK"),
    ("back_button", "BACK", "Quit combo: BACK + START", "GAMEPAD1_BUTTON_BACK"),
    ("start_button", "START", "Quit combo: BACK + START", "GAMEPAD1_BUTTON_START"),
]

_ALL_ACTION_DEFS = ACTION_DEFS + FIXED_ACTION_DEFS
ACTION_LABELS = {key: label for key, label, _desc, _default in _ALL_ACTION_DEFS}
ACTION_DESCRIPTIONS = {key: desc for key, _label, desc, _default in _ALL_ACTION_DEFS}
DEFAULT_MAPPING = {key: default for key, _label, _desc, default in _ALL_ACTION_DEFS}

_BUTTON_SUFFIXES = (
    "A", "B", "X", "Y",
    "BACK", "START", "GUIDE",
    "LEFTSHOULDER", "RIGHTSHOULDER",
    "LEFTSTICK", "RIGHTSTICK",
    "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT",
)

_AXIS_SUFFIXES = (
    "LEFTX", "LEFTY", "RIGHTX", "RIGHTY",
)

_AXIS_THRESHOLD = 16000
_AXIS_FIRST_REPEAT = 15
_AXIS_REPEAT = 5


def _button_names() -> list[str]:
    names: list[str] = []
    for pad in range(1, 5):
        for suffix in _BUTTON_SUFFIXES:
            name = f"GAMEPAD{pad}_BUTTON_{suffix}"
            if hasattr(pyxel, name):
                names.append(name)
    return names


def _const(name: str) -> int | None:
    value = getattr(pyxel, name, None)
    return value if isinstance(value, int) else None


def _config_path() -> str:
    if _storage.is_web_storage():
        return "controller_map.json"
    return _storage.runtime_data_path("controller_map.json", per_app=False)


class GamepadControls:
    """Logical gamepad actions with runtime remapping."""

    def __init__(self, settings: dict | None = None):
        self.mapping = dict(DEFAULT_MAPPING)
        self._axis_repeat: dict[str, tuple[bool, int]] = {}
        if isinstance(settings, dict):
            cfg = settings.get("controller_mapping")
            if isinstance(cfg, dict):
                self._merge_mapping(cfg)
        self.load_user_mapping()

    def _merge_mapping(self, cfg: dict) -> None:
        for key in DEFAULT_MAPPING:
            name = cfg.get(key)
            if isinstance(name, str) and _const(name) is not None:
                self.mapping[key] = name

    def load_user_mapping(self) -> None:
        try:
            data = _storage.read_json(_config_path())
            if isinstance(data, dict):
                self._merge_mapping(data)
        except Exception:
            pass

    def save_user_mapping(self) -> None:
        path = _config_path()
        try:
            if not _storage.write_json(path, self.mapping):
                raise RuntimeError("storage backend returned false")
        except Exception as e:
            print(f"[controller] save mapping failed: {e}")

    def reset_defaults(self) -> None:
        self.mapping = dict(DEFAULT_MAPPING)
        self.save_user_mapping()

    def set_action(self, action: str, button_name: str) -> None:
        if action in DEFAULT_MAPPING and _const(button_name) is not None:
            self.mapping[action] = button_name
            self.save_user_mapping()

    def button_label(self, action: str) -> str:
        return self.mapping.get(action, DEFAULT_MAPPING.get(action, "")).replace(
            "GAMEPAD1_BUTTON_", ""
        ).replace("GAMEPAD2_BUTTON_", "P2 ").replace(
            "GAMEPAD3_BUTTON_", "P3 "
        ).replace("GAMEPAD4_BUTTON_", "P4 ")

    def pressed(self, action: str) -> bool:
        code = _const(self.mapping.get(action, ""))
        return bool(code is not None and pyxel.btnp(code))

    def held(self, action: str) -> bool:
        code = _const(self.mapping.get(action, ""))
        return bool(code is not None and pyxel.btn(code))

    def quit_combo_pressed(self) -> bool:
        return ((self.held("back_button") and self.pressed("start_button"))
                or (self.held("start_button") and self.pressed("back_button")))

    def any_pressed_button(self) -> str | None:
        for name in _button_names():
            code = _const(name)
            if code is not None and pyxel.btnp(code):
                return name
        return None

    def any_pressed_face_button(self) -> str | None:
        for pad in range(1, 5):
            for suffix in ("A", "B", "X", "Y"):
                name = f"GAMEPAD{pad}_BUTTON_{suffix}"
                code = _const(name)
                if code is not None and pyxel.btnp(code):
                    return name
        return None

    def nav_up(self) -> bool:
        return (
            _pressed_any("GAMEPAD1_BUTTON_DPAD_UP", "GAMEPAD2_BUTTON_DPAD_UP")
            or self._axis_nav("up", "Y", -1)
        )

    def nav_down(self) -> bool:
        return (
            _pressed_any("GAMEPAD1_BUTTON_DPAD_DOWN", "GAMEPAD2_BUTTON_DPAD_DOWN")
            or self._axis_nav("down", "Y", 1)
        )

    def nav_left(self) -> bool:
        return (
            _pressed_any("GAMEPAD1_BUTTON_DPAD_LEFT", "GAMEPAD2_BUTTON_DPAD_LEFT")
            or self._axis_nav("left", "X", -1)
        )

    def nav_right(self) -> bool:
        return (
            _pressed_any("GAMEPAD1_BUTTON_DPAD_RIGHT", "GAMEPAD2_BUTTON_DPAD_RIGHT")
            or self._axis_nav("right", "X", 1)
        )

    def _axis_nav(self, key: str, axis: str, direction: int) -> bool:
        active = False
        for pad in range(1, 5):
            for stick in ("LEFT", "RIGHT"):
                name = f"GAMEPAD{pad}_AXIS_{stick}{axis}"
                code = _const(name)
                if code is None:
                    continue
                try:
                    value = int(pyxel.btnv(code))
                except Exception:
                    value = 0
                if direction < 0 and value <= -_AXIS_THRESHOLD:
                    active = True
                    break
                if direction > 0 and value >= _AXIS_THRESHOLD:
                    active = True
                    break
            if active:
                break

        if not active:
            self._axis_repeat[key] = (False, 0)
            return False

        frame = int(getattr(pyxel, "frame_count", 0))
        was_active, next_frame = self._axis_repeat.get(key, (False, 0))
        if not was_active or frame >= next_frame:
            delay = _AXIS_REPEAT if was_active else _AXIS_FIRST_REPEAT
            self._axis_repeat[key] = (True, frame + delay)
            return True

        self._axis_repeat[key] = (True, next_frame)
        return False


def _pressed_any(*names: str) -> bool:
    for name in names:
        code = _const(name)
        if code is not None and pyxel.btnp(code, hold=15, repeat=5):
            return True
    return False
