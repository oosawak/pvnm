"""Worker process for full PVNM export jobs."""
from __future__ import annotations

import json
import os
import sys
import time
import traceback


def _progress(message: str) -> None:
    print("PVNM_PROGRESS\t" + str(message), flush=True)


def _write_result(path: str, data: dict) -> None:
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python -m engine.export_worker input.json", file=sys.stderr)
        return 2

    result_path = ""
    started = time.perf_counter()
    try:
        with open(argv[0], encoding="utf-8") as f:
            payload = json.load(f)

        result_path = str(payload.get("result_path") or "")
        project_path = os.path.abspath(str(payload.get("project_path") or ""))
        if not project_path or not os.path.isfile(project_path):
            raise FileNotFoundError(f"project file not found: {project_path}")

        project_dir = os.path.dirname(project_path)
        if project_dir:
            os.chdir(project_dir)

        from editor_state import EditorState
        from engine.export import (
            _export_android_apk_inline,
            _export_capacitor_project_inline,
            _export_macos_app_inline,
            _export_pyxapp_external_assets_inline,
            _export_pyxapp_inline,
            _export_windows_exe_inline,
        )

        state = EditorState()
        if not state.load(project_path):
            raise RuntimeError(f"failed to load project: {project_path}")

        kind = str(payload.get("kind") or "pyxapp_external")
        if kind == "pyxapp":
            _progress(".pyxapp export worker loaded project")
            ok, message = _export_pyxapp_inline(
                state,
                str(payload.get("output_path") or ""),
                settings=payload.get("settings") or {},
                title=str(payload.get("title") or "My Visual Novel"),
                progress=_progress,
                bundle_original_images=bool(
                    payload.get("bundle_original_images", False)),
            )
        elif kind == "capacitor_project":
            _progress("Capacitor export worker loaded project")
            ok, message = _export_capacitor_project_inline(
                state,
                str(payload.get("output_path") or ""),
                settings=payload.get("settings") or {},
                title=str(payload.get("title") or "My Visual Novel"),
                progress=_progress,
                bundle_original_images=bool(
                    payload.get("bundle_original_images", False)),
                embed_audio=bool(payload.get("embed_audio", False)),
                app_id=payload.get("app_id") or None,
            )
        elif kind == "android_apk":
            variant = "release" if payload.get("variant") == "release" else "debug"
            _progress(f"Android {variant} APK export worker loaded project")
            ok, message = _export_android_apk_inline(
                state,
                str(payload.get("output_path") or ""),
                variant=variant,
                project_dir=payload.get("project_dir") or None,
                settings=payload.get("settings") or {},
                title=str(payload.get("title") or "My Visual Novel"),
                progress=_progress,
            )
        elif kind == "macos_app":
            _progress("macOS app export worker loaded project")
            ok, message = _export_macos_app_inline(
                state,
                str(payload.get("output_path") or ""),
                settings=payload.get("settings") or {},
                title=str(payload.get("title") or "My Visual Novel"),
                progress=_progress,
                bundle_original_images=bool(
                    payload.get("bundle_original_images", True)),
            )
        elif kind == "windows_exe":
            _progress("Windows EXE export worker loaded project")
            ok, message = _export_windows_exe_inline(
                state,
                str(payload.get("output_path") or ""),
                settings=payload.get("settings") or {},
                title=str(payload.get("title") or "My Visual Novel"),
                progress=_progress,
                bundle_original_images=bool(
                    payload.get("bundle_original_images", False)),
                make_zip=bool(payload.get("make_zip", True)),
            )
        else:
            _progress("Portable export worker loaded project")
            ok, message = _export_pyxapp_external_assets_inline(
                state,
                str(payload.get("output_path") or ""),
                settings=payload.get("settings") or {},
                title=str(payload.get("title") or "My Visual Novel"),
                progress=_progress,
                asset_dir_name=payload.get("asset_dir_name") or None,
            )
        elapsed = time.perf_counter() - started
        _write_result(result_path, {
            "ok": bool(ok),
            "message": str(message),
            "elapsed_sec": round(elapsed, 4),
        })
        return 0 if ok else 1
    except Exception as exc:
        traceback.print_exc()
        _write_result(result_path, {
            "ok": False,
            "message": str(exc),
            "elapsed_sec": round(time.perf_counter() - started, 4),
        })
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
