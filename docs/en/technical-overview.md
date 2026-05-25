# PVNM Technical Design Overview

Japanese version: [PVNM技術設計概要](../ja/technical-overview.md)

This page is an entry point for developers who want to modify PVNM, diagnose export issues, or understand the design behind image processing and runtime behavior.

This is not an operation guide. It explains what PVNM does internally. More detailed topics are split into these pages:

| Topic | Page |
| --- | --- |
| 256-color constraints, scene palettes, quantization, and image cache | [Palette, Quantization, and Image Cache Design](technical-palette.md) |
| VN Palette Tool settings, correction, dithering, and 0-10 parameters | [VN Palette Tool Detailed Design](technical-vn-palette-tool.md) |
| `.pyxapp`, Web, Android, Windows, and macOS export structure | [Export Design](technical-export.md) |

## Big Picture

PVNM has three major layers: the editor application, the player runtime, and the export pipeline.

| Layer | Responsibility | Representative files |
| --- | --- | --- |
| Editor application | Editing `.pvnm` projects, UI screens, asset picking, settings | `main.py`, `editor_state.py`, `ui/` |
| Player runtime | Scene playback, input, images, audio, saves, title screen, EXTRAS | `engine/player.py`, `engine/standalone_app.py`, `engine/audio.py` |
| Export pipeline | Runtime tree generation, image cache prebuild, format packaging | `engine/export.py`, `engine/export_worker.py`, `engine/export_prebuild_worker.py` |

Editor data is held as `EditorState`. During export, `engine.script.from_editor_state()` converts it into runtime story data, effectively the content written to `story.json`. Exported builds include the player code, settings JSON, fonts, the master palette, image cache files, audio, and Web/Android JavaScript bridges.

## Pyxel Constraints Shape the Design

PVNM's central constraint is Pyxel's global 256-color palette and indexed image model.

In a normal full-color image, each pixel stores RGB. In Pyxel image data, each pixel stores a color index from `0..255`, and the actual RGB value comes from `pyxel.colors[index]`. This creates several design problems:

| Problem | PVNM approach |
| --- | --- |
| A palette optimized for one image can change UI/text colors | Reserve UI, dialogue, and speaker color indices, then keep them fixed in scene palettes |
| Backgrounds and character sprites need different colors | Build a scene-level palette from the images that are actually visible together |
| Quantizing every image every frame is far too slow | Cache indexed arrays by image path, display size, and palette hash |
| Some exports do not bundle source PNG/JPG images | Prebuild required `.npy` cache files and record them in `image_manifest.json` |
| Web/Android local asset fetch can be expensive | Externalize image cache files into same-origin assets |

PVNM's quantization is therefore not just "turn an image into 256 colors." It is a runtime design for keeping UI colors, body text, speaker colors, backgrounds, character sprites, gallery images, and title images coherent under one active Pyxel palette.

## Runtime Image Display Pipeline

When the player displays a scene, the conceptual flow is:

```text
Resolve scene state
  ↓
Collect inherited background, character, and flipbook images
  ↓
Get a scene palette with reserved colors fixed
  ↓
Write the scene palette into pyxel.colors[0..255]
  ↓
Fetch image cache by image path + display size + palette hash
  ↓
Copy the indexed array directly into pyxel.Image
  ↓
Draw with pyxel.blt
```

In code, `engine/player.py` `_apply_scene_palette()` selects and applies the scene palette, while `engine/image_cache.py` `ImageCache.get()` converts or loads image data as a `pyxel.Image`.

The key detail is that the image cache identity includes the palette hash. The same `bg.png` can produce different indexed arrays under scene A's palette and scene B's palette, so PVNM treats them as separate cache entries.

## Data Files

PVNM uses these main files internally and in exports:

| File | Role |
| --- | --- |
| `.pvnm` | Editable project file: scenes, steps, asset references, and authoring data |
| `settings.json` | UI colors, speaker colors, font size, and app/runtime settings |
| `story.json` | Compact runtime scenario JSON written during export |
| `title_config.json` | Title screen settings |
| `gallery_config.json` | CG gallery settings |
| `extra_text_config.json` | EXTRA TEXT page settings |
| `endings.json` | Ending list and slide settings |
| `MasterColor.pyxpal` | PVNM's baseline 256-color palette |
| `image_manifest.json` | Index of prebuilt exported image cache entries |
| `pvnm_cache/*.npy` | NumPy-saved arrays of Pyxel palette indices |

`story.json` is written as compact JSON during export. Large projects can spend noticeable time writing whitespace-heavy JSON, and exported players only need fast `json.load()` compatibility. Editable `.pvnm` files remain oriented toward authoring and inspection.

## Design Separation

PVNM separates "choose colors", "cache images", and "package an export."

| Process | Representative function | Point |
| --- | --- | --- |
| Load master palette | `engine.palette.load()` | Apply 256 colors to `pyxel.colors` |
| Build scene palette | `engine.palette.build_scene_palette()` | Extract representative colors from visible images while preserving reserved colors |
| Quantize to fixed palette | `engine.image_cache._quantize()` | Use Pillow fixed-palette quantization |
| Fetch image cache | `ImageCache.get()` | Use memory, disk, manifest, or external cache |
| Export prebuild | `engine.export._prebuild_image_manifest()` | Generate runtime-required sizes and palettes ahead of time |
| Full export worker | `engine.export_worker` | Move heavy work out of the live Pyxel GUI process |
| Image prebuild worker | `engine.export_prebuild_worker` | Further isolate Pillow/NumPy image work |

This separation lets editor playback, `.pyxapp`, Web, Android, Windows, and macOS exports share the same runtime logic. Format-specific differences are mostly kept to file placement, wrapper tools, and Web/Android injection.

## Related Pages

Start with [Palette, Quantization, and Image Cache Design](technical-palette.md) if you want to understand PVNM's rendering quality and speed. Most of that comes from scene palette generation and fixed-palette quantization.

Read [VN Palette Tool Detailed Design](technical-vn-palette-tool.md) for the per-setting behavior of the standalone conversion tool.

Read [Export Design](technical-export.md) for export stages, `image_manifest.json`, Web/Android asset externalization, and worker separation.
