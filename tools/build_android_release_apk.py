#!/usr/bin/env python3
"""Build a signed Android release APK for a saved PVNM project."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from editor_state import EditorState  # noqa: E402
from engine.export import export_android_apk, _load_project_settings  # noqa: E402


def _progress(message: str) -> None:
    print(f"[PVNM] {message}", flush=True)


def _safe_app_name(raw: str) -> str:
    safe = "".join(
        ch if ch.isalnum() or ch in ("-", "_", ".") else "_"
        for ch in str(raw or "")
    ).strip("._")
    return safe or "PVNMGame"


def build_android_release_apk(project_path: Path, output_path: Path,
                              name: str = "",
                              project_dir: Path | None = None) -> Path:
    project_path = project_path.resolve()
    output_path = output_path.resolve()
    app_name = _safe_app_name(name or project_path.stem)
    if not project_path.is_file():
        raise FileNotFoundError(f"project file not found: {project_path}")

    state = EditorState()
    if not state.load(str(project_path)):
        raise RuntimeError(f"failed to load project: {project_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_project_dir = project_dir.resolve() if project_dir else None
    _progress(f"Loading project: {project_path}")
    ok, message = export_android_apk(
        state,
        str(output_path),
        variant="release",
        project_dir=str(resolved_project_dir) if resolved_project_dir else None,
        settings=_load_project_settings(str(project_path.parent)),
        title=app_name,
        progress=_progress,
    )
    if not ok:
        raise RuntimeError(message)
    apk = Path(message)
    _progress(f"Release APK: {apk}")
    sha256 = Path(str(apk) + ".sha256")
    if sha256.is_file():
        _progress(f"SHA-256: {sha256}")
    return apk


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a signed Android release APK for GitHub Releases.")
    parser.add_argument("--project", required=True,
                        help="Path to the .pvnm project file.")
    parser.add_argument("--output", default="",
                        help=("Output APK path. Defaults to "
                              "export/android/<project>-release.apk."))
    parser.add_argument("--name", default="",
                        help="Application name. Defaults to project stem.")
    parser.add_argument("--project-dir", default="",
                        help="Optional intermediate Capacitor project folder.")
    args = parser.parse_args(argv)

    project = Path(args.project)
    if not project.is_absolute():
        project = ROOT / project
    output = Path(args.output or f"export/android/{project.stem}-release.apk")
    if not output.is_absolute():
        output = ROOT / output
    project_dir = Path(args.project_dir) if args.project_dir else None
    if project_dir is not None and not project_dir.is_absolute():
        project_dir = ROOT / project_dir

    try:
        build_android_release_apk(
            project,
            output,
            name=args.name or project.stem,
            project_dir=project_dir,
        )
    except Exception as exc:
        print(f"[PVNM] Android release APK build failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
