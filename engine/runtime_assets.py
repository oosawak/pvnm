"""Runtime asset-root discovery for exported PVNM players.

The normal .pyxapp route keeps assets inside the package. The Linux portable
route keeps the .pyxapp small and places heavy files beside it in
``<app_name>_assets`` so pyxel does not need to unpack them into /tmp.
"""
from __future__ import annotations

import json
import os
import sys
import unicodedata

_MARKER_FILE = "external_assets.json"
_ASSET_MARKERS = (
    "pvnm_external_assets.json",
    "asset_manifest.json",
    "image_manifest.json",
)


def find_asset_root(runtime_dir: str, launch_dir: str = "",
                    argv: list | tuple | None = None) -> str:
    """Return the directory that should be used for game assets.

    Priority:
      1. PVNM_ASSET_ROOT environment variable.
      2. A sibling asset folder next to the launched .pyxapp.
      3. A sibling/current-working-directory folder named by external_assets.json.
      4. runtime_dir itself for ordinary bundled exports.

    ``pyxel play`` extracts the .pyxapp into /tmp before running main.py. The
    exported app changes cwd to that extracted runtime directory, so callers
    should pass the original launch cwd captured before chdir().
    """
    runtime_dir = os.path.abspath(runtime_dir or ".")
    launch_dir = os.path.abspath(launch_dir or os.getcwd())
    cfg = _load_config(runtime_dir)
    expected_name = str(cfg.get("asset_dir_name") or "").strip()
    app_name = str(cfg.get("app_name") or "").strip()

    env_root = os.environ.get("PVNM_ASSET_ROOT", "").strip()
    if env_root:
        found = _valid_asset_root(env_root)
        if found:
            return found

    for pyxapp in _candidate_pyxapp_paths(app_name, launch_dir, argv):
        parent = os.path.dirname(os.path.abspath(pyxapp))
        for name in _candidate_asset_names(expected_name, app_name, pyxapp):
            found = _valid_asset_root(os.path.join(parent, name))
            if found:
                return found

    for base in (launch_dir, os.getcwd(), os.path.dirname(runtime_dir),
                 runtime_dir):
        for name in _candidate_asset_names(expected_name, app_name, ""):
            found = _valid_asset_root(os.path.join(base, name))
            if found:
                return found

    return runtime_dir


def resolve_asset_path(path: str, asset_root: str) -> str:
    """Resolve a story asset path against an external/bundled asset root."""
    if not path:
        return path
    if os.path.isabs(path):
        found = _existing_path_variant(path)
        if found:
            return found
    root = os.path.abspath(asset_root or ".")
    if not os.path.isabs(path):
        candidate = os.path.join(root, path)
        found = _existing_path_variant(candidate)
        if found:
            return found
    rel = _manifest_path_map(root).get(str(path))
    if rel:
        candidate = os.path.join(root, rel)
        found = _existing_path_variant(candidate)
        if found:
            return found
    if os.path.isabs(path):
        return path
    return os.path.join(root, path)


def _existing_path_variant(path: str) -> str:
    if not path:
        return ""
    path = str(path)
    if os.path.exists(path):
        return path
    for form in ("NFC", "NFD"):
        try:
            candidate = unicodedata.normalize(form, path)
        except Exception:
            continue
        if candidate != path and os.path.exists(candidate):
            return candidate
    return ""


def _manifest_path_map(asset_root: str) -> dict:
    data = _load_asset_manifest(asset_root)
    path_map = data.get("path_map") if isinstance(data, dict) else None
    return path_map if isinstance(path_map, dict) else {}


def _load_asset_manifest(asset_root: str) -> dict:
    for name in ("asset_manifest.json", "pvnm_external_assets.json"):
        path = os.path.join(asset_root, name)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def _load_config(runtime_dir: str) -> dict:
    path = os.path.join(runtime_dir, _MARKER_FILE)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _candidate_asset_names(expected_name: str, app_name: str,
                           pyxapp_path: str) -> list[str]:
    names: list[str] = []
    if expected_name:
        names.append(expected_name)
    if app_name:
        names.append(f"{app_name}_assets")
    if pyxapp_path:
        stem = os.path.splitext(os.path.basename(pyxapp_path))[0]
        if stem:
            names.append(f"{stem}_assets")
    result: list[str] = []
    for name in names:
        if name and name not in result:
            result.append(name)
    return result


def _candidate_pyxapp_paths(app_name: str, launch_dir: str = "",
                            argv: list | tuple | None = None) -> list[str]:
    paths: list[str] = []
    env_path = os.environ.get("PVNM_PYXAPP_PATH", "").strip()
    if env_path:
        paths.append(env_path)
    args = []
    if argv is not None:
        args.extend(list(argv))
    else:
        args.extend(list(sys.argv))
    # Python keeps the interpreter's original argv here. Some launchers mutate
    # sys.argv before the packaged script runs, so check both.
    args.extend(list(getattr(sys, "orig_argv", []) or []))
    for arg in args:
        text = str(arg or "")
        lower = text.lower()
        if lower.endswith(".pyxapp") or lower.endswith(".pyxapp/"):
            text = text.rstrip("/\\")
            paths.append(text)
    if app_name:
        paths.append(os.path.join(os.getcwd(), f"{app_name}.pyxapp"))
        if launch_dir:
            paths.append(os.path.join(launch_dir, f"{app_name}.pyxapp"))

    result: list[str] = []
    for path in paths:
        if not path:
            continue
        path = os.path.expanduser(path)
        if not os.path.isabs(path):
            base = launch_dir or os.getcwd()
            path = os.path.abspath(os.path.join(base, path))
        if path not in result:
            result.append(path)
    return result


def _valid_asset_root(path: str) -> str:
    if not path:
        return ""
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(path):
        return ""
    for marker in _ASSET_MARKERS:
        if os.path.exists(os.path.join(path, marker)):
            return path
    return ""
