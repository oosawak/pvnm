"""Optional runtime HUD for Web/Android exports.

The HUD is intentionally disabled by default. In Web/Capacitor exports, open
the game with ``?pvnm_debug=1`` (or ``#pvnm_debug=1``) to draw a small overlay
with the runtime state that tends to matter on Android devices.
"""
from __future__ import annotations

import sys
import json

import pyxel

from engine import audio as _audio
from engine import platform_input as _platform_input
from engine import storage as _storage
from engine import startup_timing as _startup_timing
from ui.widgets import draw_unicode, text_px_w


_active: bool | None = None
_last_snapshot_frame = -9999


def active() -> bool:
    global _active
    if _active is not None:
        return _active
    _active = False
    if sys.platform != "emscripten":
        return False
    try:
        from js import window  # type: ignore

        search = str(getattr(window.location, "search", "") or "")
        hash_value = str(getattr(window.location, "hash", "") or "")
        _active = _has_debug_flag(search) or _has_debug_flag(hash_value)
    except Exception:
        _active = False
    return _active


def draw_hud() -> None:
    if not active():
        return

    audio = _audio_status()
    startup = _startup_status()
    pointer = _pointer_status()
    storage_name = _safe_storage_name()
    lines = [
        "PVNM DEBUG",
        f"start:{startup['elapsedMs']:.0f}ms last:{_short_debug(startup['lastLabel'], 28)}",
        f"stage:{startup['lastMs']:.0f}ms +{startup['lastDeltaMs']:.0f}ms marks:{startup['count']}",
        f"audio:{audio['backend']} unlock:{audio['unlocked']} pending:{audio['pending']}",
        f"bgm:{audio['time']:.2f}s playing:{audio['playing']} ctx:{audio['context']}",
        f"req:{audio['last_status']} {audio['last_name']}",
        f"back:{_platform_input.pending_back_count()}/{_platform_input.total_back_count()}",
        pointer,
        f"storage:{storage_name} frame:{pyxel.frame_count}",
    ]
    _record_hud_snapshot(lines)

    size = 10
    line_h = 11
    width = min(
        pyxel.width - 8,
        max(text_px_w(line, size) for line in lines) + 10,
    )
    height = len(lines) * line_h + 7
    x, y = 4, 4
    pyxel.rect(x, y, width, height, 0)
    pyxel.rectb(x, y, width, height, 13)
    for i, line in enumerate(lines):
        col = 10 if i == 0 else 7
        draw_unicode(x + 5, y + 4 + i * line_h, line[:64], col, size=size)


def _has_debug_flag(value: str) -> bool:
    text = value.lstrip("?#")
    if not text:
        return False
    for part in text.replace(";", "&").split("&"):
        if not part:
            continue
        key, sep, raw_val = part.partition("=")
        if key != "pvnm_debug":
            continue
        if not sep:
            return True
        return raw_val.lower() not in ("0", "false", "off", "no")
    return False


def _record_hud_snapshot(lines: list[str]) -> None:
    global _last_snapshot_frame
    frame = int(pyxel.frame_count)
    if frame - _last_snapshot_frame < 30:
        return
    _last_snapshot_frame = frame
    api = _js_api("PVNM_DEBUG_LOG")
    add = getattr(api, "add", None) if api is not None else None
    if not callable(add):
        return
    try:
        add("hud", json.dumps({
            "frame": frame,
            "lines": lines,
        }, ensure_ascii=False))
    except Exception:
        pass


def _audio_status() -> dict[str, object]:
    api = _js_api("PVNM_AUDIO")
    backend = _audio_backend_name(api)
    unlocked = _js_bool(api, "isUnlocked", default=False)
    pending = _js_bool(api, "hasPendingBgm", default=False)
    context = _js_str(api, "getAudioContextState", default="-")
    return {
        "backend": backend,
        "unlocked": "yes" if unlocked else "no",
        "pending": "yes" if pending else "no",
        "context": context,
        "time": _audio.get_bgm_pos_sec(),
        "playing": "yes" if _audio.is_bgm_playing() else "no",
        **_last_bgm_status(api),
    }


def _startup_status() -> dict[str, object]:
    try:
        data = _startup_timing.summary()
        return {
            "elapsedMs": float(data.get("elapsedMs", 0) or 0),
            "count": int(data.get("count", 0) or 0),
            "lastLabel": str(data.get("lastLabel", "-") or "-"),
            "lastMs": float(data.get("lastMs", 0) or 0),
            "lastDeltaMs": float(data.get("lastDeltaMs", 0) or 0),
        }
    except Exception:
        return {
            "elapsedMs": 0.0,
            "count": 0,
            "lastLabel": "?",
            "lastMs": 0.0,
            "lastDeltaMs": 0.0,
        }


def _last_bgm_status(api) -> dict[str, str]:
    raw = _js_str(api, "getLastBgmInfo", "")
    if not raw:
        return {"last_status": "-", "last_name": "-"}
    try:
        info = json.loads(raw)
        if not isinstance(info, dict):
            return {"last_status": "?", "last_name": "?"}
    except Exception:
        return {"last_status": "?", "last_name": "?"}
    status = str(info.get("status") or "-")
    error = str(info.get("error") or "")
    web_error = str(info.get("webError") or "")
    path = str(info.get("path") or info.get("url") or "")
    name = path.replace("\\", "/").rstrip("/").split("/")[-1] or "-"
    if error:
        if web_error and web_error != error:
            error = f"{error} web:{web_error}"
        return {"last_status": "err", "last_name": _short_debug(error, 42)}
    return {"last_status": _short_debug(status, 16),
            "last_name": _short_debug(name, 42)}


def _short_debug(text: str, limit: int) -> str:
    value = str(text or "")
    if len(value) <= limit:
        return value
    if limit <= 3:
        return value[:limit]
    return value[:limit - 3] + "..."


def _pointer_status() -> str:
    pointer, touch, click = _platform_input.pointer_event_counts()
    event = _platform_input.last_pointer_event()
    if not event:
        return f"ptr:none p:{pointer} t:{touch} c:{click}"
    kind = str(event.get("kind", "?"))
    x = _safe_int(event.get("x", 0))
    y = _safe_int(event.get("y", 0))
    pointer_type = str(event.get("pointerType") or "-")
    return f"ptr:{kind} {x},{y} {pointer_type} p:{pointer} t:{touch} c:{click}"


def _safe_storage_name() -> str:
    try:
        return _storage.backend_name()
    except Exception:
        return "?"


def _js_api(name: str):
    if sys.platform != "emscripten":
        return None
    try:
        from js import window  # type: ignore

        return getattr(window, name, None)
    except Exception:
        return None


def _js_call(api, name: str, default=None):
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


def _js_bool(api, name: str, default: bool = False) -> bool:
    return bool(_js_call(api, name, default))


def _js_str(api, name: str, default: str = "") -> str:
    return str(_js_call(api, name, default) or default)


def _audio_backend_name(api) -> str:
    value = _js_str(api, "getBackendName", "")
    if value:
        return value
    return str(getattr(_audio, "_backend", "none"))


def _safe_int(value) -> int:
    try:
        return int(value)
    except Exception:
        return 0
