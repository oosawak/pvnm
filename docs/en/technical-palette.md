# Palette, Quantization, and Image Cache Design

Japanese version: [減色・パレット・画像キャッシュ設計](../ja/technical-palette.md)

This page explains PVNM's image quantization, scene palette generation, image cache, and VN Palette Tool integration from a developer perspective.

The main implementation files are:

| File | Role |
| --- | --- |
| `engine/palette.py` | Generate/load `MasterColor.pyxpal`; build scene palettes |
| `engine/image_cache.py` | Fixed-palette quantization, `.npy` cache, manifest loading, transparent colkey handling |
| `engine/player.py` | Scene palette application and image prewarming |
| `engine/ending_player.py` | Ending slide palettes |
| `engine/gallery_palette.py` | Sepia palette for CG gallery thumbnails |
| `vn_palette_tool.py` | Standalone image conversion tool for PVNM-friendly assets |

For the detailed behavior and formulas of VN Palette Tool UI settings, see [VN Palette Tool Detailed Design](technical-vn-palette-tool.md).

## Quantization Algorithms In Context

Image quantization approximates a full-color image with a smaller set of colors. Common approaches include:

| Method | Summary | Strengths | Weaknesses |
| --- | --- | --- | --- |
| Uniform quantization | Split RGB space into evenly sized boxes | Simple and fast | Wastes slots on colors not present in the image |
| Popularity | Keep the most frequent colors | Good for flat art and pixel art | Gradients can crowd out rare accent colors |
| Median Cut | Recursively split the color distribution and choose representatives | Covers color range well for illustrations/photos | Still needs a mapping step to final palette colors |
| Octree | Insert colors into a tree and merge leaves | Can be incremental | Quality depends heavily on implementation |
| k-means | Cluster colors and use cluster centroids | Can produce high quality | Iterative, slower, sensitive to initialization |
| Fixed-palette nearest color | Map pixels into an already chosen palette | Matches runtime palette indices | Bad palettes cannot be rescued |
| Dithering | Distribute or pattern quantization error | Simulates gradients with fewer colors | Can add visible noise or shimmer |

PVNM separates two stages:

1. **Palette construction**
   Build representative colors from the images visible in a scene. PVNM uses Pillow's Adaptive Palette, which is Median Cut-like in practice.

2. **Fixed-palette mapping**
   Map each pixel to an index in the chosen 256-color palette. PVNM uses Pillow's C-implemented `quantize(palette=...)` for the runtime image cache path.

This separation matters. Simply running `convert("P", palette=ADAPTIVE)` per image would not preserve Pyxel palette indices, reserved UI colors, speaker colors, transparent colkeys, or export manifest compatibility.

## Master Palette Layout

PVNM's baseline palette is `assets/images/MasterColor.pyxpal`. If it is missing, or if `MasterColor.png` is newer, `engine/palette.py` regenerates it.

The index layout is:

| Index range | Purpose |
| --- | --- |
| `0..15` | Safe editor UI area: backgrounds, panels, buttons, text, accents |
| `16..255` | Colors extracted from `MasterColor.png` |

Indices `0..15` are kept fixed when PVNM builds a scene palette. PVNM changes palettes per scene and sometimes per image context, but changing fundamental UI colors during playback would break message windows and editor previews.

Indices referenced by `settings.json` `dialog_role_indices` and `speaker_colors` are also reserved. For example, if speaker A's text color uses index 50, index 50 keeps the master RGB value even when the scene images need many other colors.

## Scene Palette Generation

Scene palettes are built by `engine.palette.build_scene_palette(image_paths, reserved, base_dir)`.

The input is the set of images that may be visible in the current resolved scene state:

| Image type | Collected images |
| --- | --- |
| Background | Current background, or inherited background from previous scenes |
| Background animation | `bg_anim.flipbook_files` |
| Character sprites | Current `char_l`, `char_c`, `char_r` images |
| Character animation | Each character's `anim.flipbook_files` |
| Endings | One palette per slide image |
| Title | Title background, plus reserved title button colors |
| Gallery | Detail image palettes and sepia thumbnail palette |

Implementation flow:

```text
Resolve image_paths against base_dir
  ↓
Keep existing files with their mtimes
  ↓
Build a cache key from reserved colors and file mtimes
  ↓
Load each image as RGB
  ↓
Composite transparent pixels over reserved index 0 RGB
  ↓
Downscale each image to max side 256 px
  ↓
Stack all images into one vertical canvas
  ↓
Extract extra candidate colors with Pillow Adaptive Palette
  ↓
Remove colors already present in reserved RGBs
  ↓
Fill free palette slots in order
  ↓
Fill remaining slots with black
```

Transparent pixels are composited using the RGB value of reserved index 0 so that transparent areas do not consume their own palette slots. Since that fill color duplicates a reserved color, it is removed during reserved-color filtering, leaving more free slots for real image colors.

## Why Median Cut-like Adaptive Palette

PVNM assets are not only pixel art. They can include antialiased character sprites, gradient backgrounds, and photo-like images. A pure popularity strategy can fail there.

For example, a skin gradient may contain many slightly different high-frequency colors. Popularity extraction can spend most slots on those midtones, dropping small but important accents such as eye color, ribbons, or highlights.

Median Cut-like adaptive palette extraction partitions color space according to the distribution. It tends to cover the overall color range instead of only the most frequent colors, which is a better fit for VN-style illustrations.

PVNM also stacks the visible images into one canvas before extraction, so the background and all visible sprites share one scene palette.

## Fixed-Palette Quantization

After the scene palette is chosen, each image pixel is mapped into that palette. `engine.image_cache._quantize()` handles this.

The essential code shape is:

```python
pal_image = Image.new("P", (1, 1))
pal_image.putpalette(flat_256_rgb)
quantized = img_rgb.quantize(palette=pal_image, dither=Image.Dither.NONE)
arr = np.array(quantized, dtype=np.uint8)
```

PVNM delegates the mapping to Pillow's fixed-palette `quantize()`. Pillow performs the heavy work in C and uses a search structure suitable for fixed palette lookup.

A naive Python/NumPy implementation conceptually compares every pixel `P` against every palette color `K`:

```text
P pixels × K colors × 3 RGB components
```

For a 720x480 image and 256 colors, that is roughly 88 million component differences. NumPy can vectorize this, but it can still create large temporary arrays and heavy memory bandwidth pressure.

The Pillow path is fast because:

| Reason | Detail |
| --- | --- |
| C implementation | Pixel scan and nearest-color search do not run in Python loops |
| Search structure | It avoids simple all-colors brute force for each pixel |
| Fewer Python-side arrays | PVNM does not create a huge `P x K x 3` diff array |
| Cacheable result | The output is a palette-index array that can be saved as `.npy` |
| Direct Pyxel path | The index array can be copied into `pyxel.Image.data_ptr()` |

Exact timings are environment-dependent, but the design point is stable: move expensive nearest-color mapping out of Python and into Pillow's optimized implementation.

## Why Runtime Dithering Is Disabled

The runtime image cache path uses `Image.Dither.NONE`. This is intentional.

| Concern | Benefit of no dithering |
| --- | --- |
| Speed | No error diffusion work |
| Reproducibility | Same input and palette produce a stable index array |
| UI compatibility | Less noise around text, borders, and transparent sprite edges |
| Cache clarity | `.npy` stores the exact final index image |
| VN visuals | Static VN images can make dithering grain very visible |

Smooth gradients can band without dithering. For that reason, VN Palette Tool offers Floyd-Steinberg and ordered dithering as authoring-time options. Runtime prioritizes stability and speed; the conversion tool prioritizes art direction.

## allowed_indices and Reserved Color Protection

Some contexts need to prevent image pixels from using certain indices. PVNM passes `allowed_indices` for that.

Pillow's `quantize(palette=...)` chooses from the full fixed palette. If a pixel maps to a reserved UI index, `_remap_disallowed_indices()` remaps it to the nearest allowed color.

The remapper caches results by RGB value, so if many pixels share the same source color, the nearest-allowed search is computed once for that RGB.

## Transparency and colkey

Pyxel `blt` uses a color index, the colkey, as transparent. PNG alpha is not stored directly inside Pyxel images, so PVNM converts alpha into a safe colkey index.

`engine.image_cache._apply_alpha_colkey()` works as follows:

1. Treat alpha below 128 as transparent.
2. Find a palette index unused by opaque pixels.
3. If such an index exists, use it as the transparent colkey.
4. If all indices are used, choose a colkey and remap opaque pixels that collide with it to nearby allowed colors.
5. Set transparent pixels to the chosen colkey index.

This lets PVNM preserve transparent PNG sprites without asking the user to manually choose a transparent color index.

During export, the auto-derived colkey is recorded in `image_manifest.json` cache records. Exports without source PNGs can still use the same colkey.

## Image Cache

`ImageCache.get()` converts or loads an image as a `pyxel.Image` at a particular size and palette.

The cache identity conceptually includes:

```text
normalized path
display width
display height
palette hash
allowed_indices
alpha_colkey flag
```

On disk, cache names look like `v2_<filehash>_<w>x<h>_<palettehash>.npy`. The content is a 2D `uint8` array where each value is a Pyxel palette index.

Load paths depend on context:

| Context | Path |
| --- | --- |
| Editor/runtime with source image present | Use fresh `.npy` if newer than source; otherwise generate |
| Exported runtime without source image | Use `.npy` referenced by `image_manifest.json` |
| Web/Android with externalized cache | Fetch from `external_cache.base_url` or prefetched bytes |

`.npy` is used because the image has already been resized and quantized into Pyxel indices. Runtime only needs to load the array and copy it into `pyxel.Image`.

## Scene Palette Cache

`engine.palette.build_scene_palette()` caches by reserved colors and image file mtimes:

```text
cache_key = (sorted(reserved.items()), sorted((resolved_path, mtime)))
```

VN projects often reuse the same background and character combinations across multiple scenes, so this avoids rebuilding identical palettes.

## Prewarming

`engine/player.py` analyzes likely successor scenes and queues image cache prewarming.

It considers next scenes, choice destinations, and `goto` targets. It simulates the same persistent background/character inheritance rules as normal playback, builds the palette for that future state, and queues the required background and sprite cache entries.

Prewarming is delayed while text is typing or confirm input is held. Synchronous image loading during text advance would make dialogue feel less smooth.

## Export-Time Prebuild

During export, `engine.export._prebuild_image_manifest()` generates image cache entries ahead of time.

It follows the same scene inheritance rules as the player and prebuilds:

| Target | Generated data |
| --- | --- |
| Backgrounds | Indexed arrays at display size |
| Background flipbooks | Same display size as the background |
| Character sprites | Configured `w/h` or screen-fit size |
| Character flipbooks | Same size as the main sprite |
| Ending slides | Screen-fit slide images |
| Title background | Palette also reserving title button colors |
| Gallery detail images | Screen-fit images |
| Gallery thumbnails | Small images using the sepia palette |

This lets lightweight exports play back from `image_manifest.json` and `.npy` files without bundling the original images.

## Benefits

| Benefit | Detail |
| --- | --- |
| Whole-screen coherence | Backgrounds, sprites, UI, and text share one Pyxel palette safely |
| Speed | Heavy quantization goes through Pillow C code and `.npy` cache |
| Export compatibility | Builds without source images can still render via manifest and cache |
| Reserved color protection | UI and speaker colors are less likely to be stolen by images |
| Transparent PNG support | Auto colkey reduces manual setup |
| Authoring control | VN Palette Tool lets creators tune assets before import |

## Tradeoffs

| Tradeoff | Reason |
| --- | --- |
| Color tone can change between scenes | Each scene image set can build a different palette |
| Not perfectly optimal per image | Backgrounds and multiple sprites share one palette |
| More reserved colors means fewer image colors | UI/speaker protection competes with image fidelity |
| Gradients can band without runtime dithering | Runtime prioritizes stability and speed |
| Cache count can grow | Same image under different palettes creates different `.npy` files |
| Adaptive Palette depends on Pillow | PVNM is not implementing the palette extraction algorithm from scratch |

## Possible Improvements

| Idea | Expected effect | Caution |
| --- | --- | --- |
| Share palettes across scene groups | Reduce tone shifts and cache count | Requires whole-project analysis |
| Weight important regions | Preserve faces or key character colors better | Needs UI or metadata |
| Allocate extraction ratios by image type | Avoid background overpowering sprites or vice versa | Hard to infer automatically |
| Runtime Lab-space mapping | More perceptual nearest colors | Likely slower than Pillow fixed-palette path |
| Optional dithered cache | Improve gradients | More grain, more cache variants, more QA |
| Palette generation visualization | Easier debugging | Requires UI/logging work |

The current design balances quality, speed, maintainability, and export size for a VN authoring tool. The key practical choice is to rely on Pillow's optimized quantization and then cache the resulting index arrays.
