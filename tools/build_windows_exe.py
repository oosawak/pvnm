#!/usr/bin/env python3
"""Build a Windows onedir executable for an exported PVNM project.

This script is intended to run on a Windows host, especially GitHub Actions.
It reuses PVNM's normal runtime export path, then packages that runtime with
PyInstaller. The output is a folder containing ``<name>.exe`` plus its runtime
files; a zip can be created for distribution.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.export import build_windows_exe_from_project  # noqa: E402


def _progress(message: str) -> None:
    print(f"[PVNM] {message}", flush=True)


def _safe_app_name(raw: str) -> str:
    safe = "".join(
        ch if ch.isalnum() or ch in ("-", "_", ".") else "_"
        for ch in str(raw or "")
    ).strip("._")
    return safe or "PVNMGame"


def build_windows_exe(project_path: Path, output_dir: Path, name: str,
                      make_zip: bool = False,
                      bundle_original_images: bool = False
                      ) -> tuple[Path, Path | None]:
    project_path = project_path.resolve()
    app_name = _safe_app_name(name or project_path.stem)
    output_dir = output_dir.resolve()
    _progress(f"Loading project: {project_path}")
    final_exe, zip_result = build_windows_exe_from_project(
        str(project_path),
        str(output_dir),
        name=app_name,
        make_zip=make_zip,
        bundle_original_images=bundle_original_images,
        progress=_progress,
    )
    final_exe = Path(final_exe)
    zip_path = Path(zip_result) if zip_result else None
    _progress(f"Executable: {final_exe}")
    if zip_path:
        _progress(f"Zip: {zip_path}")
    return final_exe, zip_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a Windows PVNM executable with PyInstaller.")
    parser.add_argument("--project", required=True,
                        help="Path to the .pvnm project file.")
    parser.add_argument("--output-dir", default="export/windows",
                        help="Folder for the Windows build output.")
    parser.add_argument("--name", default="",
                        help="Application/executable name. Defaults to project stem.")
    parser.add_argument("--zip", action="store_true",
                        help="Also create <name>-windows.zip.")
    parser.add_argument("--bundle-original-images", action="store_true",
                        help=("Copy original image assets as a fallback. "
                              "By default Windows builds use "
                              "image_manifest.json + pvnm_cache only."))
    args = parser.parse_args(argv)

    project = Path(args.project)
    if not project.is_absolute():
        project = ROOT / project
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    name = args.name or project.stem

    try:
        build_windows_exe(
            project,
            output_dir,
            name,
            make_zip=args.zip,
            bundle_original_images=args.bundle_original_images,
        )
    except Exception as exc:
        print(f"[PVNM] Windows build failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
