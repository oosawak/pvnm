"""Runtime input bridge for platform-specific controls.

Desktop builds keep using Pyxel keyboard/gamepad input. Web/Android builds can
provide ``window.PVNM_INPUT`` from JavaScript; PVNM then consumes platform
events such as the Android hardware Back button without exiting the WebView.
"""
from __future__ import annotations

import json
import sys
from typing import Any


_api: Any | None = None
_initialized = False


def _get_api() -> Any | None:
    global _api, _initialized
    if _initialized:
        return _api
    _initialized = True
    if sys.platform != "emscripten":
        return None
    try:
        from js import window  # type: ignore

        api = getattr(window, "PVNM_INPUT", None)
        if api is not None:
            _api = api
            print("[input] using Web input backend")
    except Exception as e:
        print(f"[input] Web input unavailable: {e}")
    return _api


def consume_back_pressed() -> bool:
    """Return and clear one pending platform Back event, if available."""
    api = _get_api()
    if api is None:
        return False
    fn = getattr(api, "consumeBackPressed", None)
    if not callable(fn):
        return False
    try:
        return bool(fn())
    except Exception as e:
        print(f"[input] consume back failed: {e}")
        return False


def pending_back_count() -> int:
    api = _get_api()
    if api is None:
        return 0
    fn = getattr(api, "getPendingBackCount", None)
    if not callable(fn):
        return 0
    try:
        return int(fn())
    except Exception:
        return 0


def total_back_count() -> int:
    api = _get_api()
    if api is None:
        return 0
    fn = getattr(api, "getTotalBackCount", None)
    if not callable(fn):
        return 0
    try:
        return int(fn())
    except Exception:
        return 0


def _call(name: str, default: Any = None) -> Any:
    api = _get_api()
    if api is None:
        return default
    fn = getattr(api, name, None)
    if not callable(fn):
        return default
    try:
        value = fn()
        return default if value is None else value
    except Exception:
        return default


def pointer_event_counts() -> tuple[int, int, int]:
    """Return pointer/touch/click counts recorded by the Web input bridge."""
    try:
        pointer = int(_call("getPointerEventCount", 0) or 0)
        touch = int(_call("getTouchEventCount", 0) or 0)
        click = int(_call("getClickEventCount", 0) or 0)
        return pointer, touch, click
    except Exception:
        return 0, 0, 0


def last_pointer_event() -> dict[str, Any] | None:
    """Return the last pointer/touch/click event recorded before/after Pyxel start."""
    raw = _call("getLastPointerEvent", "")
    if not raw:
        return None
    try:
        value = json.loads(str(raw))
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def backend_name() -> str:
    return "web" if _get_api() is not None else "pyxel"


def request_exit_app() -> bool:
    """Ask the host shell to close the app, if a platform bridge exists."""
    api = _get_api()
    if api is None:
        return False
    fn = getattr(api, "requestExitApp", None)
    if not callable(fn):
        return False
    try:
        return bool(fn())
    except Exception as e:
        print(f"[input] request exit failed: {e}")
        return False
