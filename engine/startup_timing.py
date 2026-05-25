"""Startup timing markers shared by PVNM desktop and Web runtimes."""
from __future__ import annotations

import json
import sys
import time
from typing import Any


_T0 = time.perf_counter()
_MARKS: list[dict[str, Any]] = []


def mark(label: str, detail: dict[str, Any] | None = None) -> None:
    """Record a startup milestone and mirror it to the Web bridge if present."""
    now = time.perf_counter()
    elapsed_ms = (now - _T0) * 1000.0
    previous = _MARKS[-1]["ms"] if _MARKS else 0.0
    entry = {
        "label": str(label or "event"),
        "ms": round(elapsed_ms, 1),
        "delta_ms": round(elapsed_ms - float(previous), 1),
        "detail": detail or {},
    }
    _MARKS.append(entry)
    if len(_MARKS) > 240:
        del _MARKS[:-240]
    _mark_js(entry["label"], entry["detail"])


def summary() -> dict[str, Any]:
    """Return a compact startup timing summary for the debug HUD."""
    js_summary = _summary_js()
    if js_summary:
        return js_summary
    last = _MARKS[-1] if _MARKS else None
    return {
        "elapsedMs": round((time.perf_counter() - _T0) * 1000.0, 1),
        "count": len(_MARKS),
        "lastLabel": str(last["label"]) if last else "-",
        "lastMs": float(last["ms"]) if last else 0.0,
        "lastDeltaMs": float(last["delta_ms"]) if last else 0.0,
    }


def marks() -> list[dict[str, Any]]:
    return list(_MARKS)


def _mark_js(label: str, detail: dict[str, Any]) -> None:
    if sys.platform != "emscripten":
        return
    try:
        from js import window  # type: ignore

        api = getattr(window, "PVNM_STARTUP", None)
        fn = getattr(api, "mark", None) if api is not None else None
        if callable(fn):
            fn(str(label), json.dumps(detail or {}, ensure_ascii=False))
    except Exception:
        pass


def _summary_js() -> dict[str, Any] | None:
    if sys.platform != "emscripten":
        return None
    try:
        from js import window  # type: ignore

        api = getattr(window, "PVNM_STARTUP", None)
        fn = getattr(api, "getSummary", None) if api is not None else None
        if not callable(fn):
            return None
        data = json.loads(str(fn() or "{}"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None
