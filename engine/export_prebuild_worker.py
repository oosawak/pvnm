"""Worker process for PVNM export image-cache prebuild."""
from __future__ import annotations

import json
import os
import sys
import time
import traceback


def _progress(message: str) -> None:
    print("PVNM_PROGRESS\t" + str(message), flush=True)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python -m engine.export_prebuild_worker input.json [result.json]",
              file=sys.stderr)
        return 2
    input_path = argv[0]
    result_path = argv[1] if len(argv) >= 2 else ""
    try:
        with open(input_path, encoding="utf-8") as f:
            payload = json.load(f)
        src_base = os.path.abspath(str(payload.get("src_base") or "."))
        # MasterColor.pyxpal is project-relative in PVNM. Running from the
        # project root keeps palette loading identical to the editor/player.
        os.chdir(src_base)

        from engine.export import _prebuild_image_manifest

        started = time.perf_counter()
        manifest = _prebuild_image_manifest(
            payload.get("script") or {},
            payload.get("endings") or [],
            payload.get("settings") or {},
            src_base,
            os.path.abspath(str(payload.get("dst_dir") or ".")),
            dst_cache_name=str(payload.get("dst_cache_name") or "pvnm_cache"),
            gallery_config=payload.get("gallery_config") or {},
            title_config=payload.get("title_config") or {},
            progress=_progress,
        )
        elapsed = time.perf_counter() - started
        stats = ((manifest or {}).get("prebuild") or {}).get("stats") or {}
        if result_path:
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump({
                    "ok": True,
                    "elapsed_sec": round(elapsed, 4),
                    "unique": int(stats.get("unique", 0)),
                    "generated": int(stats.get("generated", 0)),
                    "reused": int(stats.get("reused", 0)),
                    "duplicate": int(stats.get("duplicate", 0)),
                }, f, ensure_ascii=False, indent=2)
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
