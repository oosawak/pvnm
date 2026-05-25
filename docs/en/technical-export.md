# Export Design

Japanese version: [エクスポート設計](../ja/technical-export.md)

This page explains PVNM's export pipeline from a developer perspective. For user-facing export steps, see [Export Overview](export.md) and the per-format pages.

The main implementation files are:

| File | Role |
| --- | --- |
| `engine/export.py` | Central implementation for all export formats |
| `engine/export_worker.py` | Runs full exports in a separate Python process |
| `engine/export_prebuild_worker.py` | Runs image cache prebuild in a separate Python process |
| `engine/image_cache.py` | Loads exported `.npy` cache files and `image_manifest.json` |
| `engine/standalone_app.py` | Entry point for exported runtimes |
| `resources/pvnm/web/` | Web/Android JavaScript bridges and Pyxel Web runtime assets |
| `tools/build_windows_exe.py` | Windows CI/local build helper |

## Export Format Families

PVNM supports multiple export formats, but they share the same core step: build a runtime tree, then package it differently.

| Menu | Main internal flow |
| --- | --- |
| `[PYXAPP]` | Runtime tree -> `pyxel package` |
| `[PYXAPP + ASSETS]` | Runtime tree -> move image cache/audio to external assets -> `pyxel package` |
| `[macOS APP]` | Runtime tree -> PyInstaller onedir `.app` |
| `[WINDOWS EXE]` | Runtime tree -> PyInstaller onedir -> zip |
| `[WEB HTML]` | Runtime tree -> `pyxel package` -> `pyxel app2html` -> inject bridges/assets |
| `[ANDROID PROJECT]` | Web bundle -> Capacitor project |
| `[ANDROID APK DEBUG/RELEASE]` | Capacitor project -> Gradle build -> copy APK |

The shared core is `_write_runtime_tree()`.

## Runtime Tree Generation

`_write_runtime_tree()` builds a standalone runtime directory in a temporary folder.

High-level order:

```text
Build script data from EditorState
  ↓
Write compact story.json
  ↓
Normalize and write settings/endings/title/gallery/extra_text
  ↓
Collect referenced assets
  ↓
Copy assets as needed
  ↓
Prebuild image cache
  ↓
Copy runtime assets such as fonts and the master palette
  ↓
Copy required engine/ and ui/ runtime files
  ↓
Write generated main.py and README.md
  ↓
Include PVNM runtime license notices
```

The generated `main.py` is intentionally minimal:

```python
from engine.standalone_app import App

App(title="...", storage_app_id="...")
```

Playback behavior stays in `engine.standalone_app.App` and the player modules instead of being duplicated into export-specific launchers.

## Asset Collection

PVNM gathers asset references from the scenario, endings, title screen, and gallery.

| Source | Assets |
| --- | --- |
| Scenes | Backgrounds, sprites, flipbooks, palette files, fonts, BGM, SE |
| Endings | BGM and slide images |
| Title | Background image and BGM |
| Gallery | CG images |

Images are not always bundled as source files. With `bundle_original_images=False`, PVNM leans on `.npy` cache files plus the manifest. Audio may be copied into format-specific external asset folders for Web, Android, or portable external-assets exports.

## Why Workers Exist

PVNM is a Pyxel GUI app. Running long Pillow/NumPy work, PyInstaller, Gradle, or `pyxel package` inside the live GUI process can interfere with the UI loop and Pyxel state.

For normal saved-project exports, PVNM sends the full export to `engine.export_worker`:

```text
GUI process
  ↓ input json
engine.export_worker
  ↓ reload EditorState
run inline exporter
  ↓ result json / PVNM_PROGRESS
GUI process receives result
```

Image cache prebuild is then separated further into `engine.export_prebuild_worker`:

```text
export_worker or GUI process
  ↓ image_prebuild_input.json
engine.export_prebuild_worker
  ↓ _prebuild_image_manifest()
image_manifest.json / pvnm_cache/*.npy / diagnostics
```

Benefits:

| Benefit | Detail |
| --- | --- |
| GUI stability | Heavy image work is not done inside the active Pyxel UI process |
| Reproducibility | Saved `.pvnm` is reloaded from disk |
| Progress reporting | Worker stdout lines prefixed with `PVNM_PROGRESS\t` are forwarded |
| Failure diagnosis | Worker tail logs and result JSON are captured |
| Environment control | `PYTHONPATH` and `PVNM_EXPORT_INLINE_FULL` can be set explicitly |

`PVNM_EXPORT_INLINE_FULL=1` and `PVNM_EXPORT_INLINE_PREBUILD=1` are development switches for running without the worker boundary.

## Image Cache Prebuild

The densest part of the export design is image cache prebuild.

It has two goals:

1. **Avoid heavy work during playback**
   Opening images, resizing, quantizing, and building Pyxel index arrays are done during export.

2. **Allow playback without source images**
   Web and external-assets formats can play from `image_manifest.json` and `.npy` files.

Prebuild mirrors the player's persistence rules. If a scene does not set a new background, the previous one remains. If a sprite is not hidden or replaced, it remains. The exporter resolves this state just like the player.

Then it builds the scene palette and generates cache entries at the actual display sizes.

| Target | Size rule |
| --- | --- |
| Normal background | Fit within the screen; fullscreen uses screen fit |
| Background above dialogue | Fit within the non-dialogue height |
| Character sprite | Configured `w/h`, or screen-fit if unspecified |
| Ending image | Fit within 720x480 |
| Gallery detail | Fit within 720x480 |
| Gallery thumbnail | Fit within the gallery slot |
| Title background | Fit within 720x480 |

## image_manifest.json

`image_manifest.json` tells the runtime what to load when source images are absent.

Conceptual structure:

```json
{
  "version": 1,
  "cache_dir": "pvnm_cache",
  "images": {
    "assets/images/bg.png": {
      "<palette-and-options-hash>": {
        "original_size": [1280, 720],
        "sizes": {
          "720x405": {
            "cache": "v2_....npy",
            "width": 720,
            "height": 405,
            "palette_hash": "...",
            "auto_colkey": 123
          }
        }
      }
    }
  },
  "palettes": {
    "<manifest-palette-key>": {
      "hash": "...",
      "paths": ["..."],
      "colors": ["1e1e1e", "..."]
    }
  },
  "prebuild": {
    "report": "image_prebuild_report.json",
    "trace": "image_prebuild_trace.jsonl",
    "mode": "direct_export_cache"
  }
}
```

`images` maps path, palette/options hash, and display size to cache files. `palettes` lets exported runtimes reconstruct scene palettes when source PNG/JPG files are not bundled.

At runtime, `ImageCache.get_prebuilt_palette()` builds the same manifest key from image paths and reserved colors. If a palette entry is found, it returns the stored 256 colors. If not, and source images exist, callers can fall back to `build_scene_palette()`.

## Prebuild Diagnostics

Image prebuild can be slow, so PVNM writes diagnostics.

| File | Contents |
| --- | --- |
| `image_prebuild_report.json` | Final statistics, timings, slow scenes/images |
| `image_prebuild_report.partial.json` | In-progress report |
| `image_prebuild_trace.jsonl` | Checkpoint event log |
| `.pvnm_export_logs/image_prebuild_report.latest.json` | Latest project-side report |
| `.pvnm_export_logs/export_pipeline.latest.jsonl` | Stage log for the export pipeline |

Stats include `requests`, `unique`, `generated`, `duplicate`, and `failed`. A high `duplicate` count is not necessarily bad; it often means several scenes requested the same path, size, and palette.

## `.pyxapp`

The standard `.pyxapp` export builds a runtime tree and calls `pyxel package`:

```text
_write_runtime_tree()
  ↓
python -m pyxel package <app_dir> <app_dir>/main.py
  ↓
<name>.pyxapp
```

`bundle_original_images` controls whether source images are included or the build relies mostly on prebuilt cache. Cache-based builds are lighter, but depend on a correct manifest and cache set.

## `.pyxapp + assets`

`[PYXAPP + ASSETS]` writes a small `.pyxapp` plus a sibling assets folder.

| Item | Behavior |
| --- | --- |
| Images | Move `image_manifest.json` and `pvnm_cache/*.npy` to the external assets folder |
| Audio | Copy to the external assets folder |
| Marker | Write `external_assets.json` inside the `.pyxapp` runtime |
| Runtime | Keep the assets folder next to the `.pyxapp`, or set `PVNM_ASSET_ROOT` |

This is useful on portable or test environments where unpacking a large `.pyxapp` is inconvenient.

## Web HTML

Web HTML has the longest pipeline:

```text
_write_runtime_tree()
  ↓
Externalize image cache to Web assets/image_cache
  ↓
pyxel package
  ↓
pyxel app2html
  ↓
Prepare audio assets
  ↓
Inject viewport / screen container / loading overlay
  ↓
Inject WebAudio bridge
  ↓
Inject storage bridge
  ↓
Inject startup timing bridge
  ↓
Inject input bridge
  ↓
Externalize pyxapp payload to assets/app
  ↓
Localize Pyxel Web runtime
  ↓
Copy HTML, assets, and pyxel/ to destination
```

Embedding everything into one base64-heavy HTML would make the file huge. PVNM moves heavy content into external assets.

| Externalized item | Location |
| --- | --- |
| Image cache `.npy` | `<name>_assets/image_cache/` |
| `.pyxapp` payload | `<name>_assets/app/` |
| Audio | `<name>_assets/audio/` |
| Loading image | `<name>_assets/ui/loading.png` |
| Pyxel/Pyodide runtime | `pyxel/` |

`image_manifest.json` remains inside the package because Python needs it early. The manifest records `external_cache.base_url` so image cache files can be fetched from same-origin assets.

## Web Bridges

PVNM injects several JavaScript bridges into the `pyxel app2html` output:

| Bridge | Purpose |
| --- | --- |
| `pvnm_audio_bridge.js` | Play audio assets through WebAudio |
| `pvnm_storage_bridge.js` | Save data for Web/Capacitor |
| `pvnm_input_bridge.js` | Touch, gamepad, and browser input support |
| `pvnm_startup_bridge.js` | Startup timing and loading overlay control |
| `pvnm_webview_compat.js` | WebView compatibility checks |

These are injected rather than patched into Pyxel itself, keeping PVNM-specific behavior separated from the upstream runtime.

## Android / Capacitor

Android builds are based on the Web build:

```text
export_web_bundle(..., output_dir/www)
  ↓
write package.json / capacitor.config.json / build scripts
  ↓
write Android diagnostics and checklists
  ↓
optionally run Gradle APK build
  ↓
copy APK to requested output path
```

`[ANDROID PROJECT]` only creates the intermediate project. `[ANDROID APK DEBUG]` and `[ANDROID APK RELEASE]` create/update that project, run `build_android.sh`, and copy Gradle's APK output.

Release APK exports also write a `.sha256` file next to the APK for distribution verification.

## Windows EXE and macOS APP

Windows and macOS use PyInstaller.

Shared flow:

```text
_write_runtime_tree()
  ↓
PyInstaller onedir
  ↓
Copy output folder or .app bundle
  ↓
Include license notices
  ↓
Zip Windows output if requested
```

Windows EXE export runs only on Windows. On macOS, Windows builds are expected to use GitHub Actions or another Windows runner, typically through `tools/build_windows_exe.py`.

macOS `.app` export runs only on macOS. If an icon is available, PVNM generates an `.icns`; if AVFoundation modules are installed, it adds them as PyInstaller hidden imports.

## License Notices

Exported builds include PVNM runtime and third-party notice files:

| File | Contents |
| --- | --- |
| `PVNM_LICENSE.txt` | License for PVNM runtime code included in the build |
| `PVNM_THIRD_PARTY_NOTICES.md` | Fonts, Pyxel, Pyodide, and other third-party components |
| `PVNM_EXPORT_LICENSE_README.txt` | Explains that these are not the game content license |

These files do not define the license for your scenario, images, music, characters, or other original game content. Game creators should provide their own rights and credits.

## Speed Design

| Strategy | Detail |
| --- | --- |
| Build in temporary runtime trees | Move/copy only final artifacts after success |
| Prebuild images as `.npy` | Avoid Pillow quantization in the target runtime |
| Compact `story.json` | Reduce whitespace-heavy writes for large scripts |
| Worker separation | Keep heavy work out of the GUI process |
| Pipeline logs | Identify slow stages |
| Externalize heavy Web assets | Avoid huge HTML and heavy startup unpacking |
| Derive gallery thumbnails | Reuse detail cache data where possible |

## Common Failure Points

| Symptom | Check |
| --- | --- |
| Image missing | Does `image_manifest.json` contain the path/size/palette? Does `pvnm_cache` contain the `.npy`? |
| Image missing only on Web | Does `external_cache.base_url` match the deployed assets layout? |
| Audio missing | WebAudio bridge asset map and `<name>_assets/audio/` |
| Export slow or stuck | `.pvnm_export_logs/export_pipeline.latest.jsonl` and `image_prebuild_report.latest.json` |
| Windows EXE cannot build | Windows host and `requirements-build.txt` / PyInstaller |
| Android APK cannot build | `build_android.sh`, Gradle, Android SDK, signing config |
| Speaker colors changed | Runtime `settings.json` includes `dialog_role_indices` and `speaker_colors` |

## Benefits

The current export design keeps format-specific differences mostly in the packaging layer. Scene interpretation, palette construction, image cache generation, audio abstraction, and settings loading are shared as much as possible.

This reduces "works on desktop but not Web" class bugs inside PVNM itself. Browser and WebView constraints still exist, but story interpretation and image cache generation are common.

## Tradeoffs

| Tradeoff | Reason |
| --- | --- |
| Export can take time | Image cache is built ahead of playback |
| Output structure can be complex | Web/Android split HTML, assets, and runtime files |
| Cache mismatches need diagnosis | Path, size, or palette hash differences produce different cache identities |
| Worker debugging is less direct | Need stdout, result JSON, and log files |
| External tool dependencies | PyInstaller, Gradle, and host OS constraints vary by format |

PVNM intentionally shifts work toward export time so playback is lighter and distribution builds are more stable.
