# VN Palette Tool Detailed Design

Japanese version: [VN Palette Tool詳細設計](../ja/technical-vn-palette-tool.md)

This page explains what each `vn_palette_tool.py` setting does internally.

For the user-facing overview, see [Colors and Tools](colors-and-tools.md). For PVNM runtime scene palettes, image cache, and export prebuild, see [Palette, Quantization, and Image Cache Design](technical-palette.md).

## Role

VN Palette Tool is a separate image conversion tool launched outside the main PVNM process. Its role is different from runtime scene palette generation.

| Process | Purpose |
| --- | --- |
| PVNM scene palette | Fit background, sprites, and UI colors into one active Pyxel palette |
| Export image cache prebuild | Generate `.npy` index arrays ahead of playback |
| VN Palette Tool | Resize, correct, reduce, and save source image files for authoring |

PNG files saved by VN Palette Tool can be imported into PVNM as normal image assets. The tool is best understood as an asset-preparation step.

## Conversion Pipeline

`convert_image()` runs in this order:

```text
Convert input to RGBA
  ↓
Normalize transparent RGB to white and create alpha mask from source alpha
  ↓
Resize or scale-resize
  ↓
Apply selected-color transparency to alpha mask
  ↓
Apply correction preset to RGB
  ↓
Restore alpha mask
  ↓
If palette reduction is disabled, return here
  ↓
Pixelize
  ↓
Noise reduction
  ↓
Skin correction
  ↓
Edge enhancement
  ↓
Choose PVNM AUTO or CUSTOM .pyxpal palette
  ↓
Map to fixed palette with selected color distance and dithering
  ↓
Post noise reduction
  ↓
Restore alpha mask
  ↓
Remove isolated pixels
  ↓
Restore alpha mask
  ↓
Trim transparent margins
  ↓
Place on fixed canvas
  ↓
Output PNG
```

Selected-color transparency runs after resizing and before color correction. It does not try to remove colors after dithering, so original transparent margins are less likely to be damaged.

## Input and Output

| Item | Internal behavior |
| --- | --- |
| `Select image` | Load with `Image.open(path).convert("RGBA")`, then normalize transparent RGB to white |
| `Select output folder` | Candidate destination for single save, palette creation, BATCH, and RENAME |
| `SAVE CURRENT` | Convert current image and save as `pal_<source>.png` |
| `BATCH CONVERT` | Process target images under the input folder |
| `RENAME COPY` | Copy source images to sequential names without conversion |
| `CONVERT + RENAME` | Convert images and save results with sequential names |

Single-image save never overwrites existing files. If `pal_image.png` exists, the tool writes names such as `pal_image_001.png`.

## Output Size

`Output size` uses a string such as `480x320`. `parse_size()` splits on `x` and converts width and height to integers.

When `Scale resize` is off, this is the normal conversion target size.

| Keep aspect | Fit mode | Behavior |
| --- | --- | --- |
| OFF | ignored | Resize directly to the target size; aspect ratio may change |
| ON | `contain` | Fit inside target size and place on a transparent canvas |
| ON | `cover` | Fill the target size and crop overflow around center |

The alpha mask is always resized with `NEAREST`. The final alpha is binary: values `>= 128` become opaque and lower values become transparent.

## Scale Resize

When `Scale resize` is on, the tool ignores `Output size` and computes the new size from the source size and selected scale.

Internal formula:

```text
scale = max(0.01, 1.0 + percent / 100)
```

Examples:

| Setting | Internal scale | Result |
| --- | --- | --- |
| `-200%` | `0.01` | 1% size floor |
| `-50%` | `0.50` | Half size |
| `0%` | `1.00` | Original size |
| `+100%` | `2.00` | Double size |
| `+200%` | `3.00` | Triple size |

Use normal output size for fixed-size assets. Use scale resize when you want to keep the source proportion and make a relative adjustment.

## Resampling

`Resampling` selects a Pillow `Image.Resampling` mode.

| Mode | Internal value | Character |
| --- | --- | --- |
| `nearest` | `NEAREST` | Hardest. Best for pixel art |
| `lanczos` | `LANCZOS` | High-quality downscale; can add ringing around thin lines |
| `bicubic` | `BICUBIC` | Smooth and slightly soft; often good for character art |
| `bilinear` | `BILINEAR` | Softer; averages fine noise |
| `box` | `BOX` | Strong averaging when downscaling; suppresses rough noise |
| `hamming` | `HAMMING` | Middle ground between Lanczos and Bilinear |

Resampling happens before palette reduction, so it strongly affects palette extraction and nearest-color mapping.

## Correction Preset

Correction presets run after resizing and before palette reduction. Alpha is preserved; RGB is modified.

| Preset | Internal processing |
| --- | --- |
| `NONE` | No correction |
| `AUTO` | `autocontrast(cutoff=1)`, Contrast `1.06`, Color `1.08` |
| `VIVID` | Color `1.28`, Contrast `1.12`, Sharpness `1.05` |
| `VIVID WARM` | Color `1.24`, Contrast `1.10`, R `1.06`, G `1.01`, B `0.94`, R offset `+3` |
| `VIVID COOL` | Color `1.22`, Contrast `1.10`, R `0.96`, G `1.01`, B `1.08`, B offset `+3` |
| `SOFT` | Color `0.92`, Contrast `0.94`, Brightness `1.04`, Sharpness `0.90` |
| `DARK CINEMA` | Brightness `0.88`, Contrast `1.20`, Color `0.90`, B `1.04` |

Palette reduction tends to merge subtle low-contrast differences. `VIVID` spreads differences, `SOFT` compresses them, and `DARK CINEMA` creates a darker high-contrast look.

## Color Distance

Color distance decides which palette color each pixel maps to.

| Mode | Behavior |
| --- | --- |
| `Pillow default` | Use Pillow fixed-palette `quantize(palette=...)` |
| `RGB` | Nearest color by squared RGB distance |
| `Weighted RGB` | Squared RGB distance multiplied by R/G/B weights |
| `YCbCr` | Convert to Y/Cb/Cr and use weights `[1.25, 0.85, 0.85]` |
| `Lab` | Convert RGB to Lab-like space and use squared Lab distance |

All modes except `Pillow default` use `custom_palette_map_fast()`. It extracts unique RGB values from opaque pixels, maps only those unique colors, and expands the result back through `inverse`.

```text
Opaque pixels
  ↓
unique RGB + inverse
  ↓
Convert unique RGBs into selected color space
  ↓
Compute distances to palette colors in chunks
  ↓
Choose nearest colors
  ↓
Expand through inverse
```

`Lab` uses chunk size `4096`; the other custom modes use `8192`.

## R/G/B Weights

`R weight`, `G weight`, and `B weight` affect only `Weighted RGB`.

Conceptual distance:

```text
distance =
  (dr * dr) * R weight
+ (dg * dg) * G weight
+ (db * db) * B weight
```

A larger weight makes differences in that channel more expensive. Increasing `R weight` preserves red-channel similarity more strongly, which can help warm skin or sunset colors, but high values can distort balance.

These fields do not affect `RGB`, `YCbCr`, `Lab`, or `Pillow default`.

## Dithering

Dithering simulates gradients with fewer colors.

| Mode | Internal behavior |
| --- | --- |
| `None` | Direct palette mapping |
| `Floyd-Steinberg` | Only used in `Pillow default`, via `Image.Dither.FLOYDSTEINBERG` |
| `Ordered 2x2` | Add a 2x2 brightness offset to RGB before mapping |
| `Ordered 4x4` | Add a 4x4 brightness offset to RGB before mapping |

Ordered 2x2 matrix:

```text
0 2
3 1
```

Ordered 4x4 matrix:

```text
0  8  2 10
12 4 14  6
3 11  1  9
15 7 13  5
```

Offset formula:

```text
2x2: offset = (matrix[y % 2][x % 2] - 1.5) * 8
4x4: offset = (matrix[y % 4][x % 4] - 7.5) * 7
```

For `RGB`, `Weighted RGB`, `YCbCr`, and `Lab`, Floyd-Steinberg is not applied. Ordered dithering is the only dither path in those modes.

## Palette Mode

### PVNM AUTO

`PVNM AUTO` builds a 256-color palette from the current image.

Flow:

```text
Load MasterColor.pyxpal
  ↓
Determine reserved indices from UI preset
  ↓
Fix reserved index RGBs
  ↓
Composite transparent pixels over reserved index 0 color
  ↓
Downscale to max side 256 px
  ↓
Extract candidates with Pillow Adaptive Palette
  ↓
Optionally remove candidates that duplicate reserved RGBs
  ↓
Fill free slots
```

This is close in spirit to PVNM's runtime scene palette generation, but the tool is centered on a single image.

### CUSTOM .pyxpal

`CUSTOM .pyxpal` uses colors from a selected `.pyxpal`. The loader accepts basic `RRGGBB` lines and tolerates some `#`, `;`, `//`, and `key=value` forms.

If fewer than 256 colors are loaded, the rest are filled with black. If more than 256 are present, only the first 256 are used.

## Image Colors

`Image colors` controls whether image pixels may use UI-reserved indices.

| Setting | Behavior |
| --- | --- |
| `All 256 colors` | Image pixels may use reserved UI indices |
| `Exclude UI reserved colors` | Reserved UI indices are removed from the pixel candidate set |

When UI reserved colors are excluded, `allowed_indices` is the set of `0..255` minus reserved indices. If Pillow maps a pixel to a disallowed index, the tool remaps it to the nearest allowed index.

PVNM AUTO may duplicate reserved RGB values into free slots. This lets an image visually use that color while avoiding the actual reserved index.

## UI Preset

UI preset decides which indices are reserved.

| Setting | Reserved indices |
| --- | --- |
| `MASTER 0-15` | Indices `0..15` |
| `CURRENT SETTINGS` | `settings.json` `dialog_role_indices` |
| `EDIT DARK/LIGHT/SOFT/NOIR` | Role indices used by that editor UI preset |
| `PLAY DARK/LIGHT/CINEMA/WARM` | Role indices used by that play UI preset |

Reserved indices are fixed to master RGB values in PVNM AUTO. With CUSTOM `.pyxpal`, presets other than `MASTER 0-15` overwrite those indices with master palette RGBs.

## Create Custom Palette From Image

`Create custom palette from image` writes a `.pyxpal` extracted from the current image.

| Item | Behavior |
| --- | --- |
| `Color count` | `16`, `32`, `64`, `128`, or `256` |
| `Include #FFFFFF` | Reserve white at the beginning and reduce extraction count by one |
| `Sort` | `None`, `Brightness`, or `Hue` |
| `Use this palette after creation` | Immediately select the saved `.pyxpal` as CUSTOM |

Extraction composites the image over white, converts to RGB, and uses Pillow Adaptive Palette. If white is included, duplicate white from extracted colors is removed.

Sort behavior:

| Sort | Key |
| --- | --- |
| `None` | Pillow output order |
| `Brightness` | `0.299R + 0.587G + 0.114B`, then RGB |
| `Hue` | Convert RGB to HSV and sort by `H, S, V` |

## Make Selected Color Transparent

This option makes pixels near a selected RGB transparent in addition to source alpha. It is mainly for removing white backgrounds.

It runs after resizing:

```text
target = selected RGB
tolerance = selected value
dist2 = (r-target_r)^2 + (g-target_g)^2 + (b-target_b)^2
if dist2 <= tolerance^2:
    alpha = 0
```

The UI offers `0..10` and `15, 20, 25, ... 80`. The helper clamps internally to `0..441`, but the UI max is 80.

| Value | Meaning |
| --- | --- |
| `0` | Exact match only |
| `1..10` | Very close colors |
| `15..25` | Useful for JPEG noise or slight white-background variation |
| `30..50` | Stronger removal; may hit white clothing or highlights |
| `55..80` | Very broad; special cases only |

Alpha is binary in the final output. This is not a semi-transparent matting operation.

## Noise Reduction 0-10

`Noise reduction` smooths small color variation before palette reduction. Implementation: `reduce_noise_10level()`.

Formula:

```text
strength = level / 10
median_size = 3 if level <= 6 else 5
median = MedianFilter(median_size)
blur_radius = 0.05 + strength * 0.75
blurred = GaussianBlur(blur_radius)
alpha = min(0.85, 0.20 + strength * 0.65)
out = blend(original, blurred, alpha)
```

| level | strength | median | blur radius | blend alpha | Effect |
| --- | --- | --- | --- | --- | --- |
| 0 | - | - | - | - | No operation |
| 1 | 0.1 | 3 | 0.125 | 0.265 | Very light roughness suppression |
| 2 | 0.2 | 3 | 0.200 | 0.330 | Light noise suppression |
| 3 | 0.3 | 3 | 0.275 | 0.395 | Useful for character art |
| 4 | 0.4 | 3 | 0.350 | 0.460 | Slightly groups background detail |
| 5 | 0.5 | 3 | 0.425 | 0.525 | Helps gradients and photo-like noise |
| 6 | 0.6 | 3 | 0.500 | 0.590 | Quite smooth |
| 7 | 0.7 | 5 | 0.575 | 0.655 | Wider median; details drop more easily |
| 8 | 0.8 | 5 | 0.650 | 0.720 | Strong smoothing |
| 9 | 0.9 | 5 | 0.725 | 0.785 | Very strong |
| 10 | 1.0 | 5 | 0.800 | 0.850 | Maximum; lines and details can become sleepy |

This runs before palette selection/mapping, so it changes both extracted palette colors and final mapping.

## Post Noise 0-10

`Post noise` smooths speckling after palette reduction. Implementation: `post_dither_noise_reduce_10level()`.

Formula:

```text
strength = level / 10
median = MedianFilter(3)
if level >= 7:
    median = GaussianBlur(0.15 + 0.25 * strength)
alpha = min(0.85, 0.15 + 0.60 * strength)
out = blend(quantized, median, alpha)
```

| level | strength | blur | blend alpha | Effect |
| --- | --- | --- | --- | --- |
| 0 | - | - | - | No operation |
| 1 | 0.1 | none | 0.210 | Suppress tiny specks |
| 2 | 0.2 | none | 0.270 | Slightly rounds dither grain |
| 3 | 0.3 | none | 0.330 | Good low setting for sprites |
| 4 | 0.4 | none | 0.390 | Smoother |
| 5 | 0.5 | none | 0.450 | Reduces background grain |
| 6 | 0.6 | none | 0.510 | Strong median pull |
| 7 | 0.7 | radius 0.325 | 0.570 | Adds blur |
| 8 | 0.8 | radius 0.350 | 0.630 | Strong postprocess |
| 9 | 0.9 | radius 0.375 | 0.690 | Color edges soften |
| 10 | 1.0 | radius 0.400 | 0.750 | Maximum; can look blurred |

Because this blends colors after reduction, it can increase the number of RGB colors in the output. Keep it low if you need a strict palette-like result.

## Skin Correction 0-10

`Skin correction` detects skin-like pixels in HSV and adjusts RGB slightly.

Skin-like condition:

```text
5 <= hue_deg <= 55
0.08 <= saturation <= 0.65
0.35 <= value <= 1.0
r >= g >= b * 0.75
alpha > 0
```

Adjustment:

```text
strength = level / 10
r += 10 * strength
g -=  3 * strength
b +=  5 * strength
```

| level | R | G | B | Tendency |
| --- | --- | --- | --- | --- |
| 0 | 0 | 0 | 0 | No operation |
| 1 | +1.0 | -0.3 | +0.5 | Almost imperceptible |
| 2 | +2.0 | -0.6 | +1.0 | Slightly healthier skin |
| 3 | +3.0 | -0.9 | +1.5 | Often useful for character sprites |
| 4 | +4.0 | -1.2 | +2.0 | Warmer |
| 5 | +5.0 | -1.5 | +2.5 | Stronger |
| 6 | +6.0 | -1.8 | +3.0 | Skin stands out |
| 7 | +7.0 | -2.1 | +3.5 | Warm tone becomes strong |
| 8 | +8.0 | -2.4 | +4.0 | Very strong |
| 9 | +9.0 | -2.7 | +4.5 | Color can shift noticeably |
| 10 | +10.0 | -3.0 | +5.0 | Maximum |

Values are clamped to 0-255. Wood, sunset backgrounds, and some hair colors can match the skin condition, so backgrounds usually use 0.

## Pixelize 0-10

`Pixelize` downscales before reduction, then returns to original size with nearest-neighbor.

```text
factor = 1.0 + (level / 10.0) * 4.0
small_w = int(width / factor)
small_h = int(height / factor)
small = resize(BILINEAR)
out = small.resize(original_size, NEAREST)
```

| level | factor | Downscale ratio | Look |
| --- | --- | --- | --- |
| 0 | - | - | No operation |
| 1 | 1.4 | about 71% | Very slight blockiness |
| 2 | 1.8 | about 56% | Mild pixel feel |
| 3 | 2.2 | about 45% | Simplified edges |
| 4 | 2.6 | about 38% | Clear blockiness |
| 5 | 3.0 | about 33% | Strong |
| 6 | 3.4 | about 29% | Much detail lost |
| 7 | 3.8 | about 26% | Very coarse |
| 8 | 4.2 | about 24% | Strong pixel-art feel |
| 9 | 4.6 | about 22% | Highly abstracted |
| 10 | 5.0 | 20% | Maximum |

Use low values for normal sprites. Raise it when intentionally pushing toward a pixel-art look.

## Edge Enhancement 0-10

`Edge enhancement` applies Unsharp Mask before reduction. Implementation: `sharpen_edges_10level()`.

```text
strength = level / 10
radius = 1.0 + strength * 1.2
percent = int(60 + strength * 220)
threshold = max(0, int(6 - strength * 5))
blend_alpha = min(1.0, 0.25 + strength * 0.75)
sharp = UnsharpMask(radius, percent, threshold)
out = blend(original, sharp, blend_alpha)
```

| level | radius | percent | threshold | blend | Tendency |
| --- | --- | --- | --- | --- | --- |
| 0 | - | - | - | - | No operation |
| 1 | 1.12 | 82 | 5 | 0.325 | Light line clarity |
| 2 | 1.24 | 104 | 5 | 0.400 | Slightly sharper |
| 3 | 1.36 | 126 | 4 | 0.475 | Useful for character art |
| 4 | 1.48 | 148 | 4 | 0.550 | Lines stand out |
| 5 | 1.60 | 170 | 3 | 0.625 | Stronger |
| 6 | 1.72 | 192 | 3 | 0.700 | Very clear contours |
| 7 | 1.84 | 214 | 2 | 0.775 | Highlights also emphasized |
| 8 | 1.96 | 236 | 2 | 0.850 | Can pick up noise |
| 9 | 2.08 | 258 | 1 | 0.925 | Strong |
| 10 | 2.20 | 280 | 1 | 1.000 | Maximum |

This can prevent lines from dissolving during palette reduction. Too much can create extra colors around edges.

## Speck Removal 0-10

`Speck removal` replaces isolated post-reduction pixels with the majority color in their neighborhood.

It uses a 3x3 neighborhood:

```text
strength = level / 10
threshold = max(2, round(8 - strength * 6))
repeat = 1 if level <= 5 else 2

Look at center pixel and 8 neighbors
Ignore transparent neighbors
If most common neighbor color count >= threshold and differs from center:
    replace center with that color
```

| level | threshold | repeat | Replacement condition |
| --- | --- | --- | --- |
| 0 | - | - | No operation |
| 1 | 7 | 1 | 7 of 8 neighbors share a color |
| 2 | 7 | 1 | 7 of 8 neighbors share a color |
| 3 | 6 | 1 | 6 of 8 neighbors share a color |
| 4 | 6 | 1 | 6 of 8 neighbors share a color |
| 5 | 5 | 1 | 5 of 8 neighbors share a color |
| 6 | 4 | 2 | Looser threshold, two passes |
| 7 | 4 | 2 | Strong |
| 8 | 3 | 2 | Small patterns can disappear |
| 9 | 3 | 2 | Very strong |
| 10 | 2 | 2 | Maximum; can erase fine details |

This is effective for dot noise after reduction. It can also remove eye highlights, accessories, or tiny patterns, so start around 1-3 for character art.

## Trim Transparent Margin

`Trim transparent margin` crops both image and alpha mask to the alpha bounding box:

```text
bbox = alpha.getbbox()
if bbox:
    img = img.crop(bbox)
    alpha = alpha.crop(bbox)
```

It removes fully transparent padding. Be careful with sprites whose placement assumes a fixed canvas origin.

## Fixed Canvas

`Fixed canvas` places the converted image on a transparent canvas of the specified size.

| Anchor | x | y |
| --- | --- | --- |
| `Left bottom` | `0` | `canvas_h - image_h` |
| `Center bottom` | `(canvas_w - image_w) // 2` | `canvas_h - image_h` |
| `Right bottom` | `canvas_w - image_w` | `canvas_h - image_h` |
| `Center` | `(canvas_w - image_w) // 2` | `(canvas_h - image_h) // 2` |

Use bottom anchors when aligning character sprites by feet. If the image is larger than the canvas, behavior depends on Pillow compositing bounds; this is not a dedicated crop feature.

## Preview Scale

`Original scale` and `Converted scale` affect preview display only. They do not change the saved image size.

The preview uses `NEAREST` scaling and composites over a checkerboard background, making pixels and transparent areas easier to inspect.

## Used Color Count

The status text's `used colors` count is the number of unique RGB values among non-transparent pixels:

```text
img.convert("RGBA").getcolors(maxcolors=999999)
add c[:3] to set only when alpha > 0
```

This is an RGB count, not a palette-index count. Post noise blending can increase it.

## BATCH

BATCH recursively processes images under the selected input folder. Target extensions:

```text
.png .jpg .jpeg .webp .bmp
```

Output is PNG. If no output folder is selected, results go into `_pvnm_batch` inside the input folder. `_pvnm_batch`, `_renamed`, and the selected output folder are excluded from scanning.

| Item | Behavior |
| --- | --- |
| `Size` | `720x480`, `360x240`, or `180x120` |
| `Reduce colors too` | ON uses CONVERT palette settings; OFF skips palette reduction |
| `Do not upscale smaller images` | ON prevents images smaller than target from being enlarged |
| `Run batch` | Convert and save to `_pvnm_batch` or output folder |
| `Convert + rename` | Save converted PNGs using RENAME naming rules |

BATCH uses the BATCH tab's `Size`, not the normal CONVERT `Output size`. It keeps aspect ratio and fits inside the target size.

When `Reduce colors too` is OFF, processing still includes resize, correction preset, and transparency handling. It skips palette application and later palette-dependent steps.

## Per-Image Batch Settings

The BATCH file list supports multiple selection. Changing a setting while files are selected records only that field as a per-image override.

Internal structure:

```text
global_settings: default settings
per_file_settings[path].values: per-image values
per_file_settings[path].touched: field names explicitly changed for that image
```

The list shows `[*]` for images with custom settings and `[ ]` for images without them.

During BATCH processing, PVNM starts from global settings and only overwrites fields listed in `touched`. This lets a creator adjust transparency tolerance or color distance for specific files.

## RENAME

RENAME copies original files to sequential names without conversion.

| Item | Behavior |
| --- | --- |
| `Base name` | Output prefix. Control chars and invalid filename chars such as `<`, `>`, `:`, `"`, `/`, backslash, vertical bar, `?`, `*` become `_` |
| `Start` | Starting number. Must be 0 or higher |
| `Digits` | `4`, `5`, or `6`; implementation requires at least 4 |
| `Order` | Filename order or modification-time order |
| `Target` | Whole list or selected files |
| `Preview` | Show source -> destination names |
| `Copy` | Copy original files to sequential names |

Example:

```text
Base name image
Start 1
Digits 4

image_0001.png
image_0002.png
image_0003.png
```

If a destination file already exists, the operation stops before copying. It does not overwrite.

## CONVERT + RENAME

`CONVERT + RENAME` combines BATCH conversion with RENAME naming.

| Settings source | Used for |
| --- | --- |
| CONVERT | Correction, color distance, dithering, transparency, palette |
| BATCH | Size, reduce on/off, do-not-upscale |
| RENAME | Base name, start number, digits, order, target |

Output is always PNG. Source files are not modified. Existing destination conflicts stop the operation before writing.

## Recommended Starting Points

| Use case | Starting point |
| --- | --- |
| Character sprites | Color distance `Lab`, Ordered 4x4, Noise `1..3`, Skin `2..5`, Edge `0..2`, Post noise `1..3`, Speck `1..3` |
| Backgrounds | `Pillow default` or `Lab`, Floyd-Steinberg or Ordered 4x4, Noise `3..6`, Skin `0`, Edge `0..1`, Post noise `2..5`, Speck `2..4` |
| Pixel art | `nearest`, Pixelize low or 0, no dithering, weak postprocess |
| White-background sprite cutout | Selected-color transparency ON, tolerance around `10..25` |

Strong processing can make images cleaner but lose source detail. Start low and raise only the settings that solve a visible problem.

## Caveats

| Caveat | Reason |
| --- | --- |
| Strong post noise can increase used color count | It blends already-quantized colors |
| Strong speck removal can erase tiny highlights | It replaces pixels with neighborhood majority colors |
| Skin correction can affect backgrounds | Wood, sunset, or warm hair can match the HSV condition |
| Excluding UI colors reduces available image colors | Reserved indices are removed from image candidates |
| CUSTOM `.pyxpal` gives consistency but less per-image optimization | The palette is fixed |
| Per-image BATCH overrides persist by touched field | A changed setting may remain on a specific image |
