# Colors and Tools

This page explains UI colors, speaker colors, and VN Palette Tool.

Japanese version: [色とツール](../ja/colors-and-tools.md)

For the internal design of quantization, scene palettes, and image cache, see [Palette, Quantization, and Image Cache Design](technical-palette.md). For a detailed breakdown of every VN Palette Tool setting, see [VN Palette Tool Detailed Design](technical-vn-palette-tool.md).

## COLOR CONFIG

`SETTINGS > COLOR CONFIG` configures game UI colors such as the message window, borders, buttons, and text.

`COLOR CONFIG` assigns colors from the 256-color master palette to named roles. The screen shows a preview on the left, `ROLES` / `PRESET` on the right, and `MASTER PALETTE` at the bottom.

Basic flow:

1. Select a role from `ROLES`.
2. Click a color in `MASTER PALETTE (click to assign)`.
3. Check the `EDITOR UI` / `PLAY UI` preview.
4. Save with `SAVE`.

| Button | Action |
| --- | --- |
| `SAVE` | Save current color settings |
| `REVERT` | Restore settings from when editing started |
| `DEFAULT` | Restore default role colors |
| `CANCEL` / `ESC` | Close without saving. Unsaved changes show a discard confirmation |

### EDITOR UI Roles

`EDITOR UI` colors are used by PVNM's editor and do not directly affect exported game play screens.

| Role | Purpose |
| --- | --- |
| `EDIT_BG` | Editor background |
| `EDIT_PANEL` | Panel background |
| `EDIT_BTN_BG` | Button background |
| `EDIT_PREVIEW_BG` | Main view and flowchart background |
| `EDIT_BORDER` | Borders |
| `EDIT_TEXT_DIM` | Dim text |
| `EDIT_TEXT` | Normal text |
| `EDIT_BTN_HOVER` | Button hover color |
| `EDIT_ACCENT` | Accent and active state |
| `EDIT_HIGHLIGHT` | Selection highlight |
| `EDIT_TITLE_BG` | Title bar background |

### PLAY UI Roles

`PLAY UI` colors are used while the game is running.

| Role | Purpose |
| --- | --- |
| `PLAY_BG` | Play screen background |
| `PLAY_DIALOG_BG` | Dialogue box background |
| `PLAY_BORDER` | Borders |
| `PLAY_TEXT_DIM` | Dim text |
| `PLAY_TEXT` | Main text color |
| `PLAY_ACCENT` | Accent and active state |
| `PLAY_HIGHLIGHT` | Highlight band |
| `PLAY_SPEAKER_FG` | Default speaker badge text |
| `PLAY_SPEAKER_BG` | Default speaker badge background |
| `PLAY_CHOICE_BG` | Choice button background |
| `PLAY_CHOICE_HOVER` | Choice hover color |

`PRESET` can apply editor presets such as `DARK`, `LIGHT`, `SOFT`, `NOIR`, and play presets such as `DARK`, `LIGHT`, `CINEMA`, `WARM`. Presets only update the current unsaved settings, so press `SAVE` to keep them.

## SPEAKER COLORS

`SPEAKER COLORS` sets name and body text colors per speaker. This makes dialogue easier to read when multiple characters speak.

Select a speaker from `SPEAKERS`, select a slot in the center, then click a color in `MASTER PALETTE`. A play-screen dialogue preview appears at the bottom.

| Target | Configurable colors |
| --- | --- |
| `[Narration]` | `TEXT` |
| Registered speaker | `NAME COLOR`, `NAME BG COLOR`, `TEXT COLOR` |

Use `ADD` to add a speaker name. Select a speaker and press `DEL` to delete it. `[Narration]` cannot be deleted.

`RESET SLOT (use default)` clears the selected slot. Cleared slots use the standard colors from `COLOR CONFIG`.

| Button | Action |
| --- | --- |
| `SAVE & CLOSE` | Save and close |
| `REVERT` | Restore settings from when editing started |
| `CANCEL` / `ESC` | Close without saving. Unsaved changes show a discard confirmation |

Speaker colors affect runtime body text and speaker badges. They are also reserved during image palette reduction, like `COLOR CONFIG` colors.

## VN Palette Tool

Open VN Palette Tool from `SETTINGS > TOOLS > VN PALETTE TOOL`. It helps convert images into a PVNM-friendly palette and preview reduced-color results.

VN Palette Tool runs as a separate process, so you can keep editing in PVNM while converting images.

| Tab | Purpose |
| --- | --- |
| `CONVERT` | Resize, correct, reduce, and save one image |
| `BATCH` | Process all images in a folder |
| `RENAME` | Copy source images to sequential file names without modifying originals |

Top buttons select the image, input folder, and output folder. Bottom buttons such as `SAVE CURRENT`, `BATCH CONVERT`, `RENAME COPY`, and `CONVERT + RENAME` run each operation.

Main `CONVERT` settings:

| Item | Purpose |
| --- | --- |
| Output size | Size such as `480x320` |
| Keep aspect | Fit with `contain` / `cover` while preserving aspect ratio |
| Scale resize | Resize by a multiplier |
| Resampling | `nearest`, `lanczos`, `bicubic`, and others |
| Correction preset | `AUTO`, `VIVID`, `SOFT`, `DARK CINEMA`, and others |
| Color distance | Pillow default, `RGB`, `Weighted RGB`, `YCbCr`, `Lab` |
| Dithering | None, `Floyd-Steinberg`, `Ordered 2x2`, `Ordered 4x4` |
| Noise reduction, post noise, skin correction, pixelation, edge enhancement, speck removal | 0-10 effect strength |
| Make selected color transparent | Useful for removing white backgrounds. Set color and tolerance |
| Trim transparent margin | Remove transparent padding |
| Fixed canvas | Place the image on a fixed-size canvas |

For palette settings, `PVNM AUTO` is usually the best starting point. Use `CUSTOM .pyxpal` only when you need a custom palette.

| Item | Purpose |
| --- | --- |
| Image colors | Choose all 256 colors or exclude UI reserved colors |
| UI preset | Choose how reserved colors are handled |
| Color count | Number of colors extracted for a custom palette |
| Create custom palette from image | Generate a `.pyxpal` from the current image |

If `BATCH` output is empty, results are saved to `_pvnm_batch` inside the input folder. If `RENAME` output is empty, results are saved to `_renamed`. Original images are not modified.

Always check the final result in the editor preview and in the exported target environment, especially for Windows, Web, and Android.

For implementation details such as what `Noise reduction 0-10` or `Speck removal 0-10` changes internally, see [VN Palette Tool Detailed Design](technical-vn-palette-tool.md).
