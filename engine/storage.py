"""Small persistence layer for runtime player data.

Desktop builds keep using normal JSON files. Pyodide/Web builds can provide
``window.PVNM_STORAGE`` from JavaScript; PVNM then stores small player data such
as save slots and controller mapping in browser/WebView storage.
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any


class StorageBackend:
    name = "none"

    def read_text(self, key: str) -> str | None:
        return None

    def write_text(self, key: str, text: str) -> bool:
        return False

    def remove(self, key: str) -> bool:
        return False


class FileStorageBackend(StorageBackend):
    name = "file"

    def read_text(self, key: str) -> str | None:
        if not key or not os.path.exists(key):
            return None
        with open(key, "r", encoding="utf-8") as f:
            return f.read()

    def write_text(self, key: str, text: str) -> bool:
        if not key:
            return False
        parent = os.path.dirname(os.path.abspath(key))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(key, "w", encoding="utf-8") as f:
            f.write(text)
        return True

    def remove(self, key: str) -> bool:
        if key and os.path.exists(key):
            os.remove(key)
        return True


class WebStorageBackend(StorageBackend):
    name = "web"

    def __init__(self, api: Any) -> None:
        self._api = api

    def read_text(self, key: str) -> str | None:
        fn = getattr(self._api, "getItem", None)
        if not callable(fn):
            return None
        value = fn(_normalize_web_key(key))
        if value is None:
            return None
        return str(value)

    def write_text(self, key: str, text: str) -> bool:
        fn = getattr(self._api, "setItem", None)
        if not callable(fn):
            return False
        return bool(fn(_normalize_web_key(key), str(text)))

    def remove(self, key: str) -> bool:
        fn = getattr(self._api, "removeItem", None)
        if not callable(fn):
            return False
        return bool(fn(_normalize_web_key(key)))


_backend: StorageBackend | None = None
_app_id = "pvnm-game"


def set_app_id(app_id: str) -> None:
    """Set the current exported game's storage id for file-backed runtime data."""
    global _app_id
    slug = _slugify(app_id)
    if slug:
        _app_id = slug


def app_id() -> str:
    return _app_id


def runtime_data_dir(per_app: bool = True) -> str:
    """Return the file-backed runtime data directory.

    Web/Pyodide callers should keep using storage keys. For desktop/Linux file
    backends this centralizes player-created data under ``~/.pvnm``. The base
    can be overridden with ``PVNM_USER_DATA_DIR`` for unusual handheld setups.
    """
    base = os.environ.get("PVNM_USER_DATA_DIR", "").strip()
    if not base:
        home = os.path.expanduser("~")
        if not home or home == "~":
            home = os.getcwd()
        base = os.path.join(home, ".pvnm")
    base = os.path.abspath(os.path.expanduser(base))
    path = os.path.join(base, _app_id) if per_app else base
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass
    return path


def runtime_data_path(filename: str, per_app: bool = True) -> str:
    """Return a storage key on Web, or an absolute file path on desktop/Linux."""
    name = _safe_rel_path(filename)
    if is_web_storage():
        return name
    return os.path.join(runtime_data_dir(per_app=per_app), name)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(value or "").strip())
    slug = re.sub(r"-{2,}", "-", slug).strip("._-")
    return slug[:80] or "pvnm-game"


def _safe_rel_path(value: str) -> str:
    text = str(value or "pvnm_data.json").replace("\\", "/").lstrip("/")
    parts = [p for p in text.split("/") if p and p not in (".", "..")]
    return "/".join(parts) or "pvnm_data.json"


def _normalize_web_key(key: str) -> str:
    value = str(key or "").replace("\\", "/")
    value = value.replace("//", "/")
    return value.lstrip("/") or "pvnm_data.json"


def init_storage() -> StorageBackend:
    global _backend
    if _backend is not None:
        return _backend
    if sys.platform == "emscripten":
        try:
            from js import window  # type: ignore
            api = getattr(window, "PVNM_STORAGE", None)
            if api is not None:
                _backend = WebStorageBackend(api)
                print("[storage] using Web storage backend")
                return _backend
        except Exception as e:
            print(f"[storage] Web storage unavailable: {e}")
    _backend = FileStorageBackend()
    return _backend


def backend_name() -> str:
    return init_storage().name


def is_web_storage() -> bool:
    return backend_name() == "web"


def read_text(key: str) -> str | None:
    try:
        return init_storage().read_text(key)
    except Exception as e:
        print(f"[storage] read failed ({key}): {e}")
        return None


def write_text(key: str, text: str) -> bool:
    try:
        return init_storage().write_text(key, text)
    except Exception as e:
        print(f"[storage] write failed ({key}): {e}")
        return False


def read_json(key: str, default: Any = None) -> Any:
    text = read_text(key)
    if text is None:
        return default
    try:
        return json.loads(text)
    except Exception as e:
        print(f"[storage] json read failed ({key}): {e}")
        return default


def write_json(key: str, data: Any) -> bool:
    try:
        text = json.dumps(data, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[storage] json encode failed ({key}): {e}")
        return False
    return write_text(key, text)


def remove(key: str) -> bool:
    try:
        return init_storage().remove(key)
    except Exception as e:
        print(f"[storage] remove failed ({key}): {e}")
        return False
