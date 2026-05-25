"""Player-facing runtime preferences.

These settings are intentionally separate from the authored .pvnm project.
They represent accessibility/player preferences and are stored through the
runtime storage layer so desktop, Web, and Android share the same API.
"""
from __future__ import annotations

import hashlib
import os
from typing import Any

from engine import storage as _storage


TEXT_SIZE_OPTIONS = (16, 17, 18, 19, 20, 21, 22, 23, 24)
_PREFS_FILE = "player_prefs.json"
_TEXT_SIZE_KEY = "text_size_override"
_ENDING_COLLECTION_KEY = "ending_collection"


def _path() -> str:
    return _storage.runtime_data_path(_PREFS_FILE, per_app=False)


def _load() -> dict[str, Any]:
    data = _storage.read_json(_path(), default={})
    return data if isinstance(data, dict) else {}


def _save(data: dict[str, Any]) -> bool:
    return _storage.write_json(_path(), data)


def normalize_text_size(size: int | None) -> int | None:
    """Return a valid player text size, or None for game default."""
    if size is None:
        return None
    try:
        n = int(size)
    except Exception:
        return None
    if n <= 0:
        return None
    return min(TEXT_SIZE_OPTIONS, key=lambda value: abs(value - n))


def load_text_size_override() -> int | None:
    return normalize_text_size(_load().get(_TEXT_SIZE_KEY))


def save_text_size_override(size: int | None) -> bool:
    data = _load()
    n = normalize_text_size(size)
    if n is None:
        data.pop(_TEXT_SIZE_KEY, None)
    else:
        data[_TEXT_SIZE_KEY] = n
    return _save(data)


def project_key(source: str | None = None) -> str:
    """Return a stable key for per-game runtime progress."""
    text = str(source or "").strip() or _storage.app_id()
    path_like = (
        os.path.isabs(text)
        or text.startswith("~")
        or os.sep in text
        or (os.altsep is not None and os.altsep in text)
        or text.lower().endswith(".pvnm")
    )
    if text and path_like:
        try:
            text = os.path.abspath(os.path.expanduser(text))
        except Exception:
            text = str(text)
    digest = hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()[:16]
    label = os.path.basename(text.rstrip(os.sep)) if path_like else text
    label = label or _storage.app_id()
    return f"{label}:{digest}"


def _clean_ending_name(name: str | None) -> str:
    return str(name or "").strip()


def _clean_ending_names(names) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for name in names or []:
        text = _clean_ending_name(name)
        if text and text not in seen:
            cleaned.append(text)
            seen.add(text)
    return cleaned


def load_collected_endings(project: str) -> set[str]:
    data = _load()
    collection = data.get(_ENDING_COLLECTION_KEY, {})
    if not isinstance(collection, dict):
        return set()
    names = collection.get(project, [])
    if not isinstance(names, list):
        return set()
    return set(_clean_ending_names(names))


def migrate_collected_endings_by_label(label: str, target_project: str) -> bool:
    """Merge legacy progress keys that share a display label into target_project.

    Older pyxapp+assets builds accidentally hashed the random ``pyxel play``
    extraction directory for exported games. Those keys still start with the
    stable app label, so they can be folded into the corrected key.
    """
    label = str(label or "").strip()
    if not label or not target_project:
        return False
    data = _load()
    collection = data.get(_ENDING_COLLECTION_KEY, {})
    if not isinstance(collection, dict):
        return False

    prefix = f"{label}:"
    merged = _clean_ending_names(collection.get(target_project, []))
    before = list(merged)
    for key, names in list(collection.items()):
        if key == target_project or not str(key).startswith(prefix):
            continue
        for name in _clean_ending_names(names):
            if name not in merged:
                merged.append(name)

    if merged == before:
        return False
    collection[target_project] = merged
    data[_ENDING_COLLECTION_KEY] = collection
    return _save(data)


def mark_ending_collected(project: str, ending_name: str) -> bool:
    """Persist that one ending has been reached naturally."""
    name = _clean_ending_name(ending_name)
    if not project or not name:
        return False
    data = _load()
    collection = data.get(_ENDING_COLLECTION_KEY, {})
    if not isinstance(collection, dict):
        collection = {}
    names = _clean_ending_names(collection.get(project, []))
    if name in names:
        return True
    names.append(name)
    collection[project] = names
    data[_ENDING_COLLECTION_KEY] = collection
    return _save(data)


def all_endings_collected(project: str, ending_names) -> bool:
    """Return True only when every authored ending has been collected."""
    names = _clean_ending_names(ending_names)
    if not names:
        return False
    collected = load_collected_endings(project)
    return all(name in collected for name in names)
