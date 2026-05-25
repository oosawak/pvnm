import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from collections import Counter
import shutil
from PIL import Image, ImageTk, ImageFilter, ImageOps, ImageEnhance
import colorsys
import json
import numpy as np

APP_TITLE = "VN Palette Tool"
AUTO_SAVE_PREFIX = "pal_"
AUTO_PALETTE_PREFIX = "auto_palette_"
BATCH_OUTPUT_DIR_NAME = "_pvnm_batch"
BATCH_RENAME_OUTPUT_DIR_NAME = "_renamed"
BATCH_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
BATCH_TARGET_SIZES = ("720x480", "360x240", "180x120")
BATCH_RENAME_ORDERS = ("ファイル名順", "更新日時順")
PALETTE_MODE_AUTO = "PVNM AUTO"
PALETTE_MODE_CUSTOM = "CUSTOM .pyxpal"
PALETTE_MODES = (PALETTE_MODE_AUTO, PALETTE_MODE_CUSTOM)
PALETTE_IMAGE_SCOPE_ALL = "全256色"
PALETTE_IMAGE_SCOPE_EXCLUDE_UI = "UI予約色を除外"
PALETTE_IMAGE_SCOPES = (
    PALETTE_IMAGE_SCOPE_ALL,
    PALETTE_IMAGE_SCOPE_EXCLUDE_UI,
)
UI_PALETTE_PRESET_MASTER = "MASTER 0-15"
UI_PALETTE_PRESET_CURRENT = "CURRENT SETTINGS"
UI_PALETTE_PRESET_OPTIONS = (
    UI_PALETTE_PRESET_MASTER,
    UI_PALETTE_PRESET_CURRENT,
    "EDIT DARK",
    "EDIT LIGHT",
    "EDIT SOFT",
    "EDIT NOIR",
    "PLAY DARK",
    "PLAY LIGHT",
    "PLAY CINEMA",
    "PLAY WARM",
)
COLOR_PRESETS = (
    "NONE",
    "AUTO",
    "VIVID",
    "VIVID WARM",
    "VIVID COOL",
    "SOFT",
    "DARK CINEMA",
)

RESERVED_UI_PALETTE = [
    (0x1E, 0x1E, 0x1E), (0x2D, 0x2D, 0x30),
    (0x3A, 0x3D, 0x41), (0x1E, 0x1E, 0x1E),
    (0x1E, 0x1E, 0x1E), (0x55, 0x55, 0x55),
    (0x99, 0x99, 0x99), (0xD4, 0xD4, 0xD4),
    (0x4A, 0x4F, 0x55), (0x00, 0x7A, 0xCC),
    (0xFF, 0xEC, 0x27), (0xFF, 0xFF, 0xFF),
    (0x5A, 0x88, 0x36), (0x1B, 0x1B, 0x1C),
    (0x3A, 0x3D, 0x41), (0x4A, 0x4F, 0x55),
]

_EDITOR_UI_PRESETS = {
    "DARK": {
        "EDIT_BG": 0, "EDIT_PANEL": 1, "EDIT_BTN_BG": 2,
        "EDIT_PREVIEW_BG": 0, "EDIT_BORDER": 5,
        "EDIT_TEXT_DIM": 8, "EDIT_TEXT": 119,
        "EDIT_BTN_HOVER": 115, "EDIT_ACCENT": 126,
        "EDIT_HIGHLIGHT": 36, "EDIT_TITLE_BG": 1,
    },
    "LIGHT": {
        "EDIT_BG": 119, "EDIT_PANEL": 71, "EDIT_BTN_BG": 52,
        "EDIT_PREVIEW_BG": 119, "EDIT_BORDER": 53,
        "EDIT_TEXT_DIM": 69, "EDIT_TEXT": 112,
        "EDIT_BTN_HOVER": 18, "EDIT_ACCENT": 126,
        "EDIT_HIGHLIGHT": 131, "EDIT_TITLE_BG": 71,
    },
    "SOFT": {
        "EDIT_BG": 22, "EDIT_PANEL": 23, "EDIT_BTN_BG": 54,
        "EDIT_PREVIEW_BG": 22, "EDIT_BORDER": 56,
        "EDIT_TEXT_DIM": 83, "EDIT_TEXT": 84,
        "EDIT_BTN_HOVER": 79, "EDIT_ACCENT": 40,
        "EDIT_HIGHLIGHT": 36, "EDIT_TITLE_BG": 55,
    },
    "NOIR": {
        "EDIT_BG": 112, "EDIT_PANEL": 147, "EDIT_BTN_BG": 111,
        "EDIT_PREVIEW_BG": 112, "EDIT_BORDER": 115,
        "EDIT_TEXT_DIM": 114, "EDIT_TEXT": 119,
        "EDIT_BTN_HOVER": 117, "EDIT_ACCENT": 113,
        "EDIT_HIGHLIGHT": 144, "EDIT_TITLE_BG": 123,
    },
}

_PLAY_UI_PRESETS = {
    "DARK": {
        "PLAY_BG": 0, "PLAY_DIALOG_BG": 1, "PLAY_BORDER": 5,
        "PLAY_TEXT_DIM": 8, "PLAY_TEXT": 119,
        "PLAY_ACCENT": 126, "PLAY_HIGHLIGHT": 36,
        "PLAY_SPEAKER_FG": 119, "PLAY_SPEAKER_BG": 111,
        "PLAY_CHOICE_BG": 2, "PLAY_CHOICE_HOVER": 115,
    },
    "LIGHT": {
        "PLAY_BG": 119, "PLAY_DIALOG_BG": 71, "PLAY_BORDER": 53,
        "PLAY_TEXT_DIM": 69, "PLAY_TEXT": 112,
        "PLAY_ACCENT": 126, "PLAY_HIGHLIGHT": 131,
        "PLAY_SPEAKER_FG": 119, "PLAY_SPEAKER_BG": 111,
        "PLAY_CHOICE_BG": 52, "PLAY_CHOICE_HOVER": 18,
    },
    "CINEMA": {
        "PLAY_BG": 112, "PLAY_DIALOG_BG": 147, "PLAY_BORDER": 115,
        "PLAY_TEXT_DIM": 114, "PLAY_TEXT": 119,
        "PLAY_ACCENT": 113, "PLAY_HIGHLIGHT": 144,
        "PLAY_SPEAKER_FG": 119, "PLAY_SPEAKER_BG": 123,
        "PLAY_CHOICE_BG": 111, "PLAY_CHOICE_HOVER": 117,
    },
    "WARM": {
        "PLAY_BG": 22, "PLAY_DIALOG_BG": 23, "PLAY_BORDER": 56,
        "PLAY_TEXT_DIM": 83, "PLAY_TEXT": 84,
        "PLAY_ACCENT": 40, "PLAY_HIGHLIGHT": 36,
        "PLAY_SPEAKER_FG": 22, "PLAY_SPEAKER_BG": 77,
        "PLAY_CHOICE_BG": 54, "PLAY_CHOICE_HOVER": 79,
    },
}

SETTING_VAR_NAMES = (
    "size_var",
    "keep_aspect_var",
    "fit_mode_var",
    "scale_resize_enabled_var",
    "scale_percent_var",
    "resize_var",
    "color_preset_var",
    "palette_mode_var",
    "palette_image_scope_var",
    "ui_palette_preset_var",
    "color_mode_var",
    "r_weight_var",
    "g_weight_var",
    "b_weight_var",
    "dither_var",
    "noise_level_var",
    "post_dither_noise_var",
    "skin_level_var",
    "pixelize_level_var",
    "edge_level_var",
    "isolated_level_var",
    "transparent_enabled_var",
    "transparent_color_var",
    "transparent_tolerance_var",
    "trim_var",
    "canvas_var",
    "canvas_size_var",
    "anchor_var",
    "batch_size_var",
    "batch_reduce_var",
    "batch_no_upscale_var",
)


def parse_size(text):
    text = text.lower().replace(" ", "")
    if "x" not in text:
        raise ValueError("サイズは 480x320 の形式で入力してください")
    w, h = text.split("x", 1)
    return int(w), int(h)


def hex_to_rgb(hex_text):
    s = hex_text.strip().replace("#", "")
    if len(s) != 6:
        raise ValueError("色は #FFFFFF の形式で指定してください")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return f"{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def clamp(v, min_v=0, max_v=255):
    return max(min_v, min(max_v, int(v)))


def load_pyxpal(path):
    colors = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("//") or line.startswith(";"):
                continue
            if "#" in line and not line.startswith("#"):
                line = line.split("#", 1)[0].strip()
            if "=" in line:
                line = line.split("=", 1)[1].strip()
            if line.startswith("#"):
                line = line[1:]
            line = line.replace(",", " ").split()[0]
            if len(line) == 6:
                try:
                    colors.append(hex_to_rgb(line))
                except Exception:
                    pass

    if not colors:
        raise ValueError("パレットから色を読み込めませんでした")

    return colors[:256]


def load_master_palette_for_tool():
    candidates = [
        Path("assets/images/MasterColor.pyxpal"),
        Path(__file__).resolve().parent / "assets/images/MasterColor.pyxpal",
    ]
    for path in candidates:
        try:
            if path.exists():
                colors = load_pyxpal(path)
                break
        except Exception:
            colors = []
    else:
        colors = []

    if not colors:
        colors = list(RESERVED_UI_PALETTE)
    if len(colors) < 256:
        colors = list(colors) + [(0, 0, 0)] * (256 - len(colors))
    return colors[:256]


def current_role_indices_from_settings():
    path = Path(__file__).resolve().parent / "settings.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    role = data.get("dialog_role_indices") if isinstance(data, dict) else {}
    if not isinstance(role, dict):
        return {}
    out = {}
    for key, value in role.items():
        if isinstance(value, int) and 0 <= value <= 255:
            out[str(key)] = value
    return out


def ui_preset_role_indices(preset_name):
    if preset_name == UI_PALETTE_PRESET_CURRENT:
        return current_role_indices_from_settings()
    if preset_name.startswith("EDIT "):
        name = preset_name.split(" ", 1)[1]
        return dict(_EDITOR_UI_PRESETS.get(name, {}))
    if preset_name.startswith("PLAY "):
        name = preset_name.split(" ", 1)[1]
        return dict(_PLAY_UI_PRESETS.get(name, {}))
    return {}


def ui_reserved_indices_for_preset(preset_name):
    indices = set(range(16))
    for idx in ui_preset_role_indices(preset_name).values():
        if isinstance(idx, int) and 0 <= idx <= 255:
            indices.add(idx)
    return indices


def ui_reserved_colors_for_preset(master, preset_name):
    reserved = {}
    for idx in ui_reserved_indices_for_preset(preset_name):
        if 0 <= idx < len(master):
            reserved[idx] = master[idx]
    return reserved


def adaptive_palette_from_image(img, target_colors, transparent_fill):
    src = img.convert("RGBA")
    bg = Image.new("RGB", src.size, transparent_fill)
    bg.paste(src, mask=src.getchannel("A"))

    w, h = bg.size
    if max(w, h) > 256:
        scale = 256 / max(w, h)
        bg = bg.resize(
            (max(1, int(w * scale)), max(1, int(h * scale))),
            Image.Resampling.LANCZOS,
        )

    n = max(1, min(256, int(target_colors)))
    paletted = bg.convert(
        "P",
        palette=Image.Palette.ADAPTIVE,
        colors=n,
        dither=Image.Dither.NONE,
    )
    raw = paletted.getpalette() or []
    colors = []
    seen = set()
    for i in range(n):
        if i * 3 + 2 >= len(raw):
            break
        rgb = (raw[i * 3], raw[i * 3 + 1], raw[i * 3 + 2])
        if rgb in seen:
            continue
        seen.add(rgb)
        colors.append(rgb)
    return colors


def build_pvnm_auto_palette(img, ui_preset_name=UI_PALETTE_PRESET_MASTER,
                            allow_reserved_rgb_in_free_slots=False):
    master = load_master_palette_for_tool()
    reserved = ui_reserved_colors_for_preset(master, ui_preset_name)
    free_slots = [i for i in range(256) if i not in reserved]
    transparent_fill = reserved.get(0, (0, 0, 0))
    extract_n = min(256, len(free_slots) + max(16, len(reserved)))
    candidates = adaptive_palette_from_image(img, extract_n, transparent_fill)
    reserved_rgbs = set(reserved.values())

    out = [(0, 0, 0)] * 256
    for idx, rgb in reserved.items():
        out[idx] = rgb

    picked = []
    for rgb in candidates:
        if not allow_reserved_rgb_in_free_slots and rgb in reserved_rgbs:
            continue
        picked.append(rgb)
        if len(picked) >= len(free_slots):
            break

    for slot, rgb in zip(free_slots, picked):
        out[slot] = rgb
    return out


def apply_ui_reserved_to_palette(colors, ui_preset_name):
    if ui_preset_name == UI_PALETTE_PRESET_MASTER:
        return colors
    master = load_master_palette_for_tool()
    out = list(colors[:256])
    if len(out) < 256:
        out.extend([(0, 0, 0)] * (256 - len(out)))
    for idx, rgb in ui_reserved_colors_for_preset(master, ui_preset_name).items():
        out[idx] = rgb
    return out[:256]


def image_allowed_indices_for_scope(scope, ui_preset_name=UI_PALETTE_PRESET_MASTER):
    if scope == PALETTE_IMAGE_SCOPE_EXCLUDE_UI:
        reserved = ui_reserved_indices_for_preset(ui_preset_name)
        return {idx for idx in range(256) if idx not in reserved}
    return None


def save_pyxpal(path, colors):
    with open(path, "w", encoding="utf-8") as f:
        for c in colors[:256]:
            f.write(rgb_to_hex(c) + "\n")


def make_auto_save_path(input_path, output_dir=None, prefix=AUTO_SAVE_PREFIX):
    input_file = Path(input_path)
    save_dir = Path(output_dir) if output_dir else input_file.parent
    save_dir.mkdir(parents=True, exist_ok=True)

    stem = input_file.stem
    output_path = save_dir / f"{prefix}{stem}.png"

    if not output_path.exists():
        return output_path

    index = 1
    while True:
        output_path = save_dir / f"{prefix}{stem}_{index:03d}.png"
        if not output_path.exists():
            return output_path
        index += 1


def make_auto_palette_save_path(input_path, output_dir=None, prefix=AUTO_PALETTE_PREFIX):
    input_file = Path(input_path)
    save_dir = Path(output_dir) if output_dir else input_file.parent
    save_dir.mkdir(parents=True, exist_ok=True)

    stem = input_file.stem
    output_path = save_dir / f"{prefix}{stem}.pyxpal"

    if not output_path.exists():
        return output_path

    index = 1
    while True:
        output_path = save_dir / f"{prefix}{stem}_{index:03d}.pyxpal"
        if not output_path.exists():
            return output_path
        index += 1


def make_unique_path(path):
    path = Path(path)
    if not path.exists():
        return path

    index = 1
    while True:
        candidate = path.with_name(f"{path.stem}_{index:03d}{path.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def is_relative_to_path(path, parent):
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
        return True
    except Exception:
        return False


def list_batch_image_files(input_dir, output_dir=None):
    root = Path(input_dir)
    if output_dir is None:
        excluded_dirs = []
    elif isinstance(output_dir, (str, Path)):
        excluded_dirs = [Path(output_dir).resolve()]
    else:
        excluded_dirs = [Path(p).resolve() for p in output_dir if p]
    files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in BATCH_IMAGE_EXTENSIONS:
            continue
        if any(is_relative_to_path(path, out) for out in excluded_dirs):
            continue
        files.append(path)
    return sorted(files)


def fit_inside_size(size, target_size, allow_upscale=False):
    w, h = size
    tw, th = target_size
    if w <= 0 or h <= 0 or tw <= 0 or th <= 0:
        return max(1, w), max(1, h)
    scale = min(tw / w, th / h)
    if not allow_upscale:
        scale = min(1.0, scale)
    return max(1, int(round(w * scale))), max(1, int(round(h * scale)))


def batch_output_path(input_file, input_dir, output_dir, target_size_text,
                      reduced=False):
    input_file = Path(input_file).resolve()
    input_dir = Path(input_dir).resolve()
    output_dir = Path(output_dir)
    rel_parent = input_file.parent.relative_to(input_dir)
    save_dir = output_dir / rel_parent
    save_dir.mkdir(parents=True, exist_ok=True)

    suffix = f"_{target_size_text}"
    if reduced:
        suffix += "_pal"
    return make_unique_path(save_dir / f"{input_file.stem}{suffix}.png")


def sanitize_rename_base_name(text):
    name = str(text or "").strip()
    cleaned = []
    for ch in name:
        if ord(ch) < 32 or ch in '<>:"/\\|?*':
            cleaned.append("_")
        else:
            cleaned.append(ch)
    name = "".join(cleaned).strip(" .")
    if not name:
        raise ValueError("ベース名を入力してください")
    return name


def sort_rename_files(files, order):
    paths = [Path(path) for path in files]
    if order == "更新日時順":
        return sorted(
            paths,
            key=lambda path: (
                path.stat().st_mtime if path.exists() else 0,
                str(path).lower(),
            ),
        )
    return sorted(paths, key=lambda path: str(path).lower())


def build_rename_copy_plan(files, output_dir, base_name, start_number=1, digits=4,
                           output_suffix=None):
    base_name = sanitize_rename_base_name(base_name)
    try:
        start_number = int(start_number)
    except Exception:
        raise ValueError("開始番号は整数で入力してください")
    try:
        digits = int(digits)
    except Exception:
        raise ValueError("桁数は整数で入力してください")

    if start_number < 0:
        raise ValueError("開始番号は0以上にしてください")
    if digits < 4:
        raise ValueError("桁数は4以上にしてください")

    output_dir = Path(output_dir)
    plan = []
    seen = set()
    for offset, src in enumerate(files):
        src = Path(src)
        suffix = src.suffix if output_suffix is None else str(output_suffix)
        if suffix and not suffix.startswith("."):
            suffix = "." + suffix
        dst = output_dir / f"{base_name}_{start_number + offset:0{digits}d}{suffix}"
        dst_key = str(dst.resolve())
        if dst_key in seen:
            raise ValueError(f"出力ファイル名が重複しています: {dst.name}")
        seen.add(dst_key)
        plan.append((src, dst))
    return plan


def default_assets_images_dir():
    return Path(__file__).resolve().parent / "assets" / "images"


def normalize_transparent_rgb(img, fill_rgb=(255, 255, 255)):
    img = img.convert("RGBA")
    bg = Image.new("RGBA", img.size, (*fill_rgb, 255))
    bg.alpha_composite(img)
    alpha = img.getchannel("A")
    bg.putalpha(alpha)
    return bg


def make_alpha_mask_from_source(img, transparent_enabled=False,
                                transparent_rgb=(255, 255, 255),
                                transparent_tolerance=0):
    img = img.convert("RGBA")
    arr = np.array(img, dtype=np.uint8)

    alpha = arr[..., 3].copy()

    if transparent_enabled:
        rgb = arr[..., :3].astype(np.int32)
        target = np.array(transparent_rgb, dtype=np.int32)
        tolerance = max(0, min(441, int(transparent_tolerance)))
        diff = rgb - target
        dist2 = np.sum(diff * diff, axis=2)
        color_mask = dist2 <= tolerance * tolerance
        alpha[color_mask] = 0

    return Image.fromarray(alpha, "L")


def apply_color_key_to_alpha_mask(img, alpha_mask, transparent_enabled=False,
                                  transparent_rgb=(255, 255, 255),
                                  transparent_tolerance=0):
    if not transparent_enabled:
        return alpha_mask

    img = img.convert("RGBA")
    alpha = alpha_mask.convert("L")
    if alpha.size != img.size:
        alpha = alpha.resize(img.size, Image.Resampling.NEAREST)

    rgb = np.array(img, dtype=np.uint8)[..., :3].astype(np.int32)
    target = np.array(transparent_rgb, dtype=np.int32)
    tolerance = max(0, min(441, int(transparent_tolerance)))
    diff = rgb - target
    dist2 = np.sum(diff * diff, axis=2)

    alpha_arr = np.array(alpha, dtype=np.uint8)
    alpha_arr[dist2 <= tolerance * tolerance] = 0
    return Image.fromarray(alpha_arr, "L")


def restore_alpha(img, alpha_mask):
    img = img.convert("RGBA")
    alpha = alpha_mask.convert("L")

    if alpha.size != img.size:
        alpha = alpha.resize(img.size, Image.Resampling.NEAREST)

    alpha = alpha.point(lambda v: 255 if v >= 128 else 0)
    img.putalpha(alpha)
    return img


def _adjust_rgb_channels(rgb_img, r_scale=1.0, g_scale=1.0, b_scale=1.0,
                         r_offset=0, g_offset=0, b_offset=0):
    arr = np.array(rgb_img.convert("RGB"), dtype=np.float32)
    arr[..., 0] = arr[..., 0] * r_scale + r_offset
    arr[..., 1] = arr[..., 1] * g_scale + g_offset
    arr[..., 2] = arr[..., 2] * b_scale + b_offset
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def apply_color_preset(img, preset):
    """Apply a non-destructive-looking color preset while preserving alpha."""
    preset = (preset or "NONE").upper()
    rgba = img.convert("RGBA")
    alpha = rgba.getchannel("A")
    rgb = rgba.convert("RGB")

    if preset == "NONE":
        out = rgb
    elif preset == "AUTO":
        out = ImageOps.autocontrast(rgb, cutoff=1)
        out = ImageEnhance.Contrast(out).enhance(1.06)
        out = ImageEnhance.Color(out).enhance(1.08)
    elif preset == "VIVID":
        out = ImageEnhance.Color(rgb).enhance(1.28)
        out = ImageEnhance.Contrast(out).enhance(1.12)
        out = ImageEnhance.Sharpness(out).enhance(1.05)
    elif preset == "VIVID WARM":
        out = ImageEnhance.Color(rgb).enhance(1.24)
        out = ImageEnhance.Contrast(out).enhance(1.10)
        out = _adjust_rgb_channels(out, r_scale=1.06, g_scale=1.01,
                                   b_scale=0.94, r_offset=3)
    elif preset == "VIVID COOL":
        out = ImageEnhance.Color(rgb).enhance(1.22)
        out = ImageEnhance.Contrast(out).enhance(1.10)
        out = _adjust_rgb_channels(out, r_scale=0.96, g_scale=1.01,
                                   b_scale=1.08, b_offset=3)
    elif preset == "SOFT":
        out = ImageEnhance.Color(rgb).enhance(0.92)
        out = ImageEnhance.Contrast(out).enhance(0.94)
        out = ImageEnhance.Brightness(out).enhance(1.04)
        out = ImageEnhance.Sharpness(out).enhance(0.90)
    elif preset == "DARK CINEMA":
        out = ImageEnhance.Brightness(rgb).enhance(0.88)
        out = ImageEnhance.Contrast(out).enhance(1.20)
        out = ImageEnhance.Color(out).enhance(0.90)
        out = _adjust_rgb_channels(out, r_scale=0.98, g_scale=1.00,
                                   b_scale=1.04)
    else:
        out = rgb

    rgba_out = out.convert("RGBA")
    rgba_out.putalpha(alpha)
    return rgba_out


def rgb_array_to_lab(rgb):
    rgb = rgb.astype(np.float32) / 255.0
    mask = rgb > 0.04045
    rgb = np.where(mask, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)

    r = rgb[..., 0]
    g = rgb[..., 1]
    b = rgb[..., 2]

    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) * 100.0
    y = (r * 0.2126 + g * 0.7152 + b * 0.0722) * 100.0
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) * 100.0

    x /= 95.047
    y /= 100.000
    z /= 108.883

    def f(t):
        return np.where(t > 0.008856, np.cbrt(t), (7.787 * t) + (16.0 / 116.0))

    fx = f(x)
    fy = f(y)
    fz = f(z)

    l = (116.0 * fy) - 16.0
    a = 500.0 * (fx - fy)
    bb = 200.0 * (fy - fz)

    return np.stack([l, a, bb], axis=-1).astype(np.float32)


def rgb_array_to_ycbcr(rgb):
    rgb = rgb.astype(np.float32)
    r = rgb[..., 0]
    g = rgb[..., 1]
    b = rgb[..., 2]

    y = 0.299 * r + 0.587 * g + 0.114 * b
    cb = 128 - 0.168736 * r - 0.331264 * g + 0.5 * b
    cr = 128 + 0.5 * r - 0.418688 * g - 0.081312 * b

    return np.stack([y, cb, cr], axis=-1).astype(np.float32)


def custom_palette_map_fast(img, palette, mode, weights, allowed_indices=None):
    img = img.convert("RGBA")
    arr = np.array(img, dtype=np.uint8)

    rgb = arr[..., :3]
    alpha = arr[..., 3]
    mask = alpha > 0

    if not np.any(mask):
        return img

    pixels = rgb[mask]
    unique_rgb, inverse = np.unique(pixels.reshape(-1, 3), axis=0, return_inverse=True)
    actual_len = max(1, min(256, len(palette)))
    full_palette = palette_array_256(palette)
    allowed = normalized_allowed_indices(allowed_indices, actual_len)
    palette_rgb = full_palette[allowed] if allowed else full_palette[:actual_len]

    if mode == "Lab":
        unique_space = rgb_array_to_lab(unique_rgb)
        palette_space = rgb_array_to_lab(palette_rgb)
        weight = None
        chunk_size = 4096
    elif mode == "YCbCr":
        unique_space = rgb_array_to_ycbcr(unique_rgb)
        palette_space = rgb_array_to_ycbcr(palette_rgb)
        weight = np.array([1.25, 0.85, 0.85], dtype=np.float32)
        chunk_size = 8192
    elif mode == "Weighted RGB":
        unique_space = unique_rgb.astype(np.float32)
        palette_space = palette_rgb.astype(np.float32)
        weight = np.array(weights, dtype=np.float32)
        chunk_size = 8192
    else:
        unique_space = unique_rgb.astype(np.float32)
        palette_space = palette_rgb.astype(np.float32)
        weight = None
        chunk_size = 8192

    mapped = np.empty_like(unique_rgb)

    for start in range(0, len(unique_space), chunk_size):
        end = start + chunk_size
        u = unique_space[start:end]

        diff = u[:, None, :] - palette_space[None, :, :]
        dist = diff * diff

        if weight is not None:
            dist = dist * weight

        dist = np.sum(dist, axis=2)
        nearest = np.argmin(dist, axis=1)
        mapped[start:end] = palette_rgb[nearest]

    new_pixels = mapped[inverse]

    out = arr.copy()
    out[..., :3][mask] = new_pixels
    out[..., :3][~mask] = (255, 255, 255)

    return Image.fromarray(out, "RGBA")


def normalized_allowed_indices(allowed_indices, palette_len=256):
    if not allowed_indices:
        return []
    allowed = sorted({
        int(idx) for idx in allowed_indices
        if isinstance(idx, int) and 0 <= int(idx) < palette_len
    })
    if not allowed or len(allowed) >= palette_len:
        return []
    return allowed


def remap_disallowed_indices(arr, img_rgb, palette, allowed_indices):
    actual_len = max(1, min(256, len(palette)))
    palette_rgb = palette_array_256(palette)
    allowed = normalized_allowed_indices(allowed_indices, actual_len)
    if not allowed:
        return arr

    allowed_mask = np.zeros(256, dtype=bool)
    allowed_mask[allowed] = True
    mask = ~allowed_mask[arr]
    if not np.any(mask):
        return arr

    rgb_arr = np.array(img_rgb.convert("RGB"), dtype=np.uint8)
    unique_rgb, inverse = np.unique(
        rgb_arr[mask].reshape(-1, 3),
        axis=0,
        return_inverse=True,
    )

    allowed_palette = palette_rgb[allowed].astype(np.float32)
    mapped = np.empty(len(unique_rgb), dtype=np.uint8)
    chunk_size = 8192
    unique_float = unique_rgb.astype(np.float32)

    for start in range(0, len(unique_float), chunk_size):
        end = start + chunk_size
        diff = unique_float[start:end, None, :] - allowed_palette[None, :, :]
        dist = np.sum(diff * diff, axis=2)
        nearest = np.argmin(dist, axis=1)
        mapped[start:end] = np.array(allowed, dtype=np.uint8)[nearest]

    out = arr.copy()
    out[mask] = mapped[inverse]
    return out


def indexed_array_to_rgba(arr, palette):
    palette_rgb = palette_array_256(palette)
    rgba = np.zeros((arr.shape[0], arr.shape[1], 4), dtype=np.uint8)
    rgba[..., :3] = palette_rgb[arr]
    rgba[..., 3] = 255
    return Image.fromarray(rgba, "RGBA")


def get_resample(method):
    methods = {
        "nearest": Image.Resampling.NEAREST,
        "lanczos": Image.Resampling.LANCZOS,
        "bicubic": Image.Resampling.BICUBIC,
        "bilinear": Image.Resampling.BILINEAR,
        "box": Image.Resampling.BOX,
        "hamming": Image.Resampling.HAMMING,
    }
    return methods.get(method, Image.Resampling.LANCZOS)


def resize_pair(img, alpha_mask, size, method, keep_aspect=False, fit_mode="contain"):
    resample = get_resample(method)

    if not keep_aspect:
        new_img = img.resize(size, resample)
        new_alpha = alpha_mask.resize(size, Image.Resampling.NEAREST)
        return new_img, new_alpha

    if fit_mode == "cover":
        new_img = ImageOps.fit(img, size, method=resample, centering=(0.5, 0.5))
        new_alpha = ImageOps.fit(alpha_mask, size, method=Image.Resampling.NEAREST, centering=(0.5, 0.5))
        return new_img, new_alpha

    result = ImageOps.contain(img, size, method=resample)
    result_alpha = ImageOps.contain(alpha_mask, size, method=Image.Resampling.NEAREST)

    canvas = Image.new("RGBA", size, (255, 255, 255, 0))
    alpha_canvas = Image.new("L", size, 0)

    x = (size[0] - result.width) // 2
    y = (size[1] - result.height) // 2

    canvas.alpha_composite(result.convert("RGBA"), (x, y))
    alpha_canvas.paste(result_alpha, (x, y))

    return canvas, alpha_canvas


def scale_pair_by_percent(img, alpha_mask, scale_adjust_percent, method):
    scale = max(0.01, 1.0 + (scale_adjust_percent / 100.0))

    new_w = max(1, int(round(img.width * scale)))
    new_h = max(1, int(round(img.height * scale)))

    resample = get_resample(method)

    new_img = img.resize((new_w, new_h), resample)
    new_alpha = alpha_mask.resize((new_w, new_h), Image.Resampling.NEAREST)

    return new_img, new_alpha


def pixelize_image_10level(img, level_text):
    level = int(level_text)
    if level <= 0:
        return img

    factor = 1.0 + (level / 10.0) * 4.0
    img = normalize_transparent_rgb(img, (255, 255, 255))

    w, h = img.size
    small_w = max(1, int(w / factor))
    small_h = max(1, int(h / factor))

    small = img.resize((small_w, small_h), Image.Resampling.BILINEAR)
    return small.resize((w, h), Image.Resampling.NEAREST)


def reduce_noise_10level(img, level_text):
    level = int(level_text)
    if level <= 0:
        return img

    strength = level / 10.0
    base = img.convert("RGBA")
    median_size = 3 if level <= 6 else 5

    median = base.filter(ImageFilter.MedianFilter(size=median_size))
    blur_radius = 0.05 + strength * 0.75
    blurred = median.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    alpha = min(0.85, 0.20 + strength * 0.65)
    return Image.blend(base, blurred, alpha)


def sharpen_edges_10level(img, level_text):
    level = int(level_text)
    if level <= 0:
        return img

    strength = level / 10.0
    sharp = img.filter(ImageFilter.UnsharpMask(
        radius=1.0 + strength * 1.2,
        percent=int(60 + strength * 220),
        threshold=max(0, int(6 - strength * 5)),
    ))

    return Image.blend(img.convert("RGBA"), sharp.convert("RGBA"), min(1.0, 0.25 + strength * 0.75))


def skin_tone_adjust_10level(img, level_text):
    level = int(level_text)
    if level <= 0:
        return img

    strength = level / 10.0
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size

    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue

            rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
            h_, s_, v_ = colorsys.rgb_to_hsv(rf, gf, bf)
            hue_deg = h_ * 360

            is_skin_like = (
                5 <= hue_deg <= 55 and
                0.08 <= s_ <= 0.65 and
                0.35 <= v_ <= 1.0 and
                r >= g >= b * 0.75
            )

            if is_skin_like:
                r = clamp(r + 10 * strength)
                g = clamp(g - 3 * strength)
                b = clamp(b + 5 * strength)

            px[x, y] = (r, g, b, a)

    return img


def make_pillow_palette(colors):
    palette = []

    for r, g, b in colors[:256]:
        palette.extend([r, g, b])

    while len(palette) < 768:
        palette.extend([0, 0, 0])

    pal_img = Image.new("P", (1, 1))
    pal_img.putpalette(palette)
    return pal_img


def palette_array_256(colors):
    arr = np.zeros((256, 3), dtype=np.uint8)
    for i, rgb in enumerate(colors[:256]):
        arr[i, 0] = int(rgb[0]) & 0xFF
        arr[i, 1] = int(rgb[1]) & 0xFF
        arr[i, 2] = int(rgb[2]) & 0xFF
    return arr


def ordered_dither(img, size=4, strength=8):
    img = img.convert("RGB")
    px = img.load()
    w, h = img.size

    if size == 2:
        matrix = [[0, 2], [3, 1]]
        base = 1.5
    else:
        matrix = [
            [0, 8, 2, 10],
            [12, 4, 14, 6],
            [3, 11, 1, 9],
            [15, 7, 13, 5],
        ]
        base = 7.5

    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            offset = (matrix[y % size][x % size] - base) * strength
            px[x, y] = (
                clamp(r + offset),
                clamp(g + offset),
                clamp(b + offset),
            )

    return img


def apply_palette(img, colors, dither_mode, color_mode, weights,
                  allowed_indices=None):
    img = normalize_transparent_rgb(img, (255, 255, 255))

    if color_mode != "Pillow標準":
        source = img

        if dither_mode == "Ordered 2x2":
            source = ordered_dither(img, size=2, strength=8).convert("RGBA")
        elif dither_mode == "Ordered 4x4":
            source = ordered_dither(img, size=4, strength=7).convert("RGBA")

        return custom_palette_map_fast(
            source, colors, color_mode, weights, allowed_indices)

    pal_img = make_pillow_palette(colors)

    if dither_mode == "Floyd-Steinberg":
        source = img.convert("RGB")
        dither = Image.Dither.FLOYDSTEINBERG
    elif dither_mode == "Ordered 2x2":
        source = ordered_dither(img, size=2, strength=8)
        dither = Image.Dither.NONE
    elif dither_mode == "Ordered 4x4":
        source = ordered_dither(img, size=4, strength=7)
        dither = Image.Dither.NONE
    else:
        source = img.convert("RGB")
        dither = Image.Dither.NONE

    indexed = source.quantize(palette=pal_img, dither=dither)
    arr = np.array(indexed, dtype=np.uint8)
    arr = remap_disallowed_indices(arr, source, colors, allowed_indices)
    if allowed_indices:
        return indexed_array_to_rgba(arr, colors)
    return indexed.convert("RGBA")


def post_dither_noise_reduce_10level(img, level_text):
    level = int(level_text)
    if level <= 0:
        return img

    strength = level / 10.0
    base = img.convert("RGBA")
    median = base.filter(ImageFilter.MedianFilter(size=3))

    if level >= 7:
        median = median.filter(ImageFilter.GaussianBlur(radius=0.15 + 0.25 * strength))

    return Image.blend(base, median, min(0.85, 0.15 + 0.60 * strength))


def remove_isolated_pixels_10level(img, level_text):
    level = int(level_text)
    if level <= 0:
        return img

    strength = level / 10.0
    threshold = max(2, int(round(8 - strength * 6)))

    src = img.convert("RGBA")
    dst = src.copy()

    sp = src.load()
    dp = dst.load()
    w, h = src.size

    repeat = 1 if level <= 5 else 2

    for _ in range(repeat):
        src = dst.copy()
        sp = src.load()
        dp = dst.load()

        for y in range(1, h - 1):
            for x in range(1, w - 1):
                center = sp[x, y]
                if center[3] == 0:
                    continue

                neighbors = []
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        c = sp[x + dx, y + dy]
                        if c[3] > 0:
                            neighbors.append(c)

                if not neighbors:
                    continue

                most_common_color, count = Counter(neighbors).most_common(1)[0]

                if center != most_common_color and count >= threshold:
                    dp[x, y] = most_common_color

    return dst


def trim_transparent_pair(img, alpha_mask):
    alpha = alpha_mask.convert("L")
    bbox = alpha.getbbox()

    if bbox:
        return img.crop(bbox), alpha.crop(bbox)

    return img, alpha_mask


def paste_on_canvas_pair(img, alpha_mask, canvas_size, anchor):
    img = img.convert("RGBA")
    alpha_mask = alpha_mask.convert("L")

    canvas = Image.new("RGBA", canvas_size, (255, 255, 255, 0))
    alpha_canvas = Image.new("L", canvas_size, 0)

    cw, ch = canvas_size
    iw, ih = img.size

    if anchor == "左下":
        x = 0
        y = ch - ih
    elif anchor == "中央下":
        x = (cw - iw) // 2
        y = ch - ih
    elif anchor == "右下":
        x = cw - iw
        y = ch - ih
    elif anchor == "中央":
        x = (cw - iw) // 2
        y = (ch - ih) // 2
    else:
        x = 0
        y = 0

    canvas.alpha_composite(img, (x, y))
    alpha_canvas.paste(alpha_mask, (x, y))

    return canvas, alpha_canvas


def count_used_colors(img):
    colors = img.convert("RGBA").getcolors(maxcolors=999999)
    if colors is None:
        return -1

    used = set()
    for _, c in colors:
        if c[3] > 0:
            used.add(c[:3])

    return len(used)


def make_checker_background(size):
    w, h = size
    checker = Image.new("RGBA", (w, h), (220, 220, 220, 255))
    pixels = checker.load()
    block = 8

    for y in range(h):
        for x in range(w):
            if ((x // block) + (y // block)) % 2 == 0:
                pixels[x, y] = (180, 180, 180, 255)

    return checker


def make_preview_image(img, scale_percent):
    img = img.convert("RGBA")
    scale = scale_percent / 100.0
    w = max(1, int(img.width * scale))
    h = max(1, int(img.height * scale))

    preview = img.resize((w, h), Image.Resampling.NEAREST)
    checker = make_checker_background((w, h))
    checker.alpha_composite(preview)
    return checker


def sort_palette_colors(colors, mode):
    if mode == "明るさ順":
        return sorted(colors, key=lambda c: (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2], c[0], c[1], c[2]))

    if mode == "色相順":
        def hue_key(c):
            r, g, b = c[0] / 255.0, c[1] / 255.0, c[2] / 255.0
            h, s, v = colorsys.rgb_to_hsv(r, g, b)
            return (h, s, v)
        return sorted(colors, key=hue_key)

    return colors


def extract_palette_from_image(img, color_count=256, include_white=True, sort_mode="なし"):
    img = img.convert("RGBA")

    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    bg.alpha_composite(img)
    rgb = bg.convert("RGB")

    reserve = 1 if include_white else 0
    extract_count = max(1, min(256 - reserve, color_count - reserve))

    paletted = rgb.convert(
        "P",
        palette=Image.Palette.ADAPTIVE,
        colors=extract_count,
        dither=Image.Dither.NONE,
    )

    raw_palette = paletted.getpalette()
    colors = []

    if raw_palette:
        for i in range(extract_count):
            r = raw_palette[i * 3 + 0]
            g = raw_palette[i * 3 + 1]
            b = raw_palette[i * 3 + 2]
            c = (r, g, b)
            if c not in colors:
                colors.append(c)

    if include_white:
        colors = [(255, 255, 255)] + [c for c in colors if c != (255, 255, 255)]

    colors = sort_palette_colors(colors, sort_mode)

    while len(colors) < color_count:
        colors.append(colors[-1] if colors else (0, 0, 0))

    return colors[:color_count]


HELP_TEXT = """
おすすめ設定

【キャラ立ち絵・肌色重視】
色距離: Lab
ディザリング: Ordered 4x4
ノイズ低減: 1〜3
肌色補正: 2〜5
輪郭強調: 0〜2
後ノイズ: 1〜3
孤立除去: 1〜3

【背景】
色距離: Pillow標準 または Lab
ディザリング: Floyd-Steinberg または Ordered 4x4
ノイズ低減: 3〜6
肌色補正: 0
輪郭強調: 0〜1
後ノイズ: 2〜5
孤立除去: 2〜4

【画像からパレット作成】
現在選択している画像から代表色を抽出し、.pyxpalとして保存します。
その画像に近い色味を再現しやすくなります。
ただし画像ごとにパレットを作ると、作品全体の統一感は下がる場合があります。

おすすめ:
キャラ用パレット
背景用パレット
イベントCG用パレット
のように用途別に作ると管理しやすいです。

通常はパレットを選ばず、PVNM AUTOのままで問題ありません。
PVNM AUTOはMasterColorのUI予約色を残し、残りのスロットを画像から自動抽出します。
これはPVNM本体のシーン用パレット生成に近い考え方です。

画像色:
全256色 = PVNM本体の通常プレイに近い設定です。
UI予約色も画像ピクセルに使えるため、表現に使える色が少し増えます。

UI予約色を除外 = 0〜15番を画像ピクセルに使わない設定です。
ビビッドなUI色が画像内に混ざって不自然に見える場合や、
UIと画像を同時に見せるサムネイル用途で安定します。
その代わり、画像に使える色はMASTER 0-15なら最大240色になります。
UIプリセットで追加予約indexを使う場合は、そのぶん画像用の最大色数は少し減ります。

UIプリセット:
PVNMのCOLOR CONFIGで使っているプリセットを、一時的なUI予約indexとして使います。
MASTER 0-15は従来通り0〜15番だけをUI予約として扱います。
EDIT/PLAYの各プリセットを選ぶと、そのプリセットが使うUIロールのindexも予約色として保持します。
画像色が「全256色」の場合は、画像もそのUI色を共有できます。
画像色が「UI予約色を除外」の場合は、そのUI indexを画像ピクセルの候補から外します。
CURRENT SETTINGSは現在のsettings.jsonのCOLOR CONFIG割り当てを使います。

カスタム .pyxpal は、作品全体で特定の色味に固定したい場合だけ使います。

【倍率リサイズ】
ONにすると、出力サイズではなく元画像比率を維持したまま拡大・縮小します。
倍率は -200% ～ +200% です。
内部倍率は 100% + 指定値 です。
例:
-50% = 50%サイズ
0% = 100%サイズ
+100% = 200%サイズ
+200% = 300%サイズ

【リサイズ方式】
方式によって線、髪、目のハイライト、薄いグラデーションの質感が変わります。

nearest:
一番くっきりしますが、ギザつきやすい方式です。
ドット絵・ピクセル素材向けです。
通常のAIイラストや背景では荒く見える場合があります。

lanczos:
高品質縮小の定番です。
細部を残しやすくシャープですが、細い線や髪の周辺に縁取りのようなノイズが出る場合があります。
背景・イベントCGの縮小で候補になります。

bicubic:
なめらか寄りで、lanczosより少し柔らかい方式です。
線の周辺の強調が出にくく、アニメ絵やキャラ絵で扱いやすいです。

bilinear:
さらに柔らかく、少しぼやけます。
細かいノイズが平均化されるため、減色前の安定重視に向きます。

box:
縮小時の平均化が強く、ざらつきや細かいノイズを抑えやすい方式です。
その代わり、絵はやや眠くなります。

hamming:
lanczosほど鋭くなく、bilinearほどぼやけない中間です。
線の破綻を抑えつつ、そこそこシャープにしたい時に向きます。

おすすめ:
背景・イベントCG = lanczos / bicubic
キャラ立ち絵 = bicubic / hamming
減色安定重視 = box / bilinear
ドット絵 = nearest

【透明処理】
透明情報は元画像のアルファから保持します。
`指定色を透明化` は白背景のキャラ素材など、特定色を抜きたい場合だけONにしてください。
`透明許容` を上げると、指定色に近い色も透明化します。
白背景にJPEGノイズやAI生成由来の微妙な色ムラがある場合は 10〜25 くらいが目安です。
0 は従来通り完全一致だけを透明化します。
背景やイベントCGでONにすると、白い背景・ハイライト・髪の周辺などが透明化され、
表示先の背景色によって黒い点や欠けのように見える場合があります。
許容値を上げすぎると、白い服・目のハイライト・髪の明るい部分まで抜けることがあります。
ディザリング後に透明判定しないため、元alphaの透明余白は壊れにくくなっています。

【補正プリセット】
リサイズ後、減色前に適用されます。
設定を変更すると自動的に変換後プレビューへ反映されます。
一括処理でも同じプリセットが適用されます。

NONE:
補正なし。

AUTO:
控えめな自動コントラストと彩度補正。破綻しにくい汎用設定です。

VIVID:
彩度とコントラストを上げます。

VIVID WARM:
VIVIDを暖色寄りにします。夕方、室内、肌色寄りの素材向けです。

VIVID COOL:
VIVIDを寒色寄りにします。夜、雨、SF、透明感のある素材向けです。

SOFT:
彩度とコントラストを少し抑え、明るく柔らかい印象にします。

DARK CINEMA:
暗め、高コントラスト、低彩度寄りにします。

【一括リサイズ / 一括変換】
指定フォルダ以下の PNG / JPG / JPEG / WEBP / BMP を再帰的に処理します。
出力はPNGです。
出力先フォルダ内には入力側のサブフォルダ構造を維持します。
同名ファイルがある場合は _001 のように連番を付け、上書きしません。

入力フォルダを選ぶとファイルリストが表示されます。
リスト内の画像を選択すると、その画像専用の変換設定を編集できます。
未編集の画像は現在の全体設定を使います。

減色OFF:
リサイズのみ実行します。パレット選択は不要です。

減色ON:
PVNM AUTOまたはカスタム .pyxpal、色距離、ディザリング、ノイズ低減などの変換設定を使います。
PVNM AUTOの場合はパレット選択不要です。

【一括リネームコピー】
元ファイルは変更せず、コピー先フォルダに連番ファイルとして複製します。
出力フォルダ未選択時は入力フォルダ内の _renamed に保存します。
出力フォルダを選択している場合は、そのフォルダに保存します。

対象:
全体 = 一括ファイル一覧に表示されている全画像をコピーします。
選択分 = リストで選択中の画像だけコピーします。

ベース名 image / 開始 1 / 桁数 4 の場合:
image_0001.png
image_0002.png
のように保存されます。

既存ファイルがある場合は上書きせず、エラーにします。
PVNM内で既に参照している素材名を直接変更しないため、作品データの参照切れを避けられます。

【変換＋リネーム】
一括変換した結果を、そのままRENAMEタブの連番ルールでPNG保存します。
元ファイルは変更しません。
対象、順番、ベース名、開始番号、桁数はRENAMEタブの設定を使います。
変換設定とパレット設定はCONVERT/BATCHタブの現在設定と、画像ごとの個別設定を使います。

例:
CONVERTで補正・減色を調整
BATCHで出力サイズと減色ON/OFFを指定
RENAMEで image_0001 形式を指定
下部の CONVERT + RENAME を実行

これにより、素材のリサイズ/減色と配布用の連番整理を一度に行えます。
"""


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)

        self.input_path = None
        self.batch_input_dir = None
        self.output_dir = None
        self.image = None
        self.palette_path = None
        self.converted_image = None
        self.batch_files = []
        self.selected_batch_path = None
        self.per_file_settings = {}
        self.global_settings = None
        self._loading_settings = False
        self._preview_after_id = None
        self._trace_handles = []

        self.preview_ref = None
        self.output_ref = None

        self.size_var = tk.StringVar(value="480x320")
        self.keep_aspect_var = tk.BooleanVar(value=False)
        self.fit_mode_var = tk.StringVar(value="contain")

        self.scale_resize_enabled_var = tk.BooleanVar(value=False)
        self.scale_percent_var = tk.StringVar(value="0%")

        self.resize_var = tk.StringVar(value="nearest")
        self.color_preset_var = tk.StringVar(value="NONE")
        self.palette_mode_var = tk.StringVar(value=PALETTE_MODE_AUTO)
        self.palette_image_scope_var = tk.StringVar(value=PALETTE_IMAGE_SCOPE_ALL)
        self.ui_palette_preset_var = tk.StringVar(value=UI_PALETTE_PRESET_MASTER)
        self.color_mode_var = tk.StringVar(value="Pillow標準")
        self.r_weight_var = tk.StringVar(value="1.00")
        self.g_weight_var = tk.StringVar(value="1.00")
        self.b_weight_var = tk.StringVar(value="1.00")

        self.dither_var = tk.StringVar(value="なし")
        self.noise_level_var = tk.StringVar(value="0")
        self.post_dither_noise_var = tk.StringVar(value="0")
        self.skin_level_var = tk.StringVar(value="0")
        self.pixelize_level_var = tk.StringVar(value="0")
        self.edge_level_var = tk.StringVar(value="0")
        self.isolated_level_var = tk.StringVar(value="0")

        self.transparent_enabled_var = tk.BooleanVar(value=False)
        self.transparent_color_var = tk.StringVar(value="#FFFFFF")
        self.transparent_tolerance_var = tk.StringVar(value="0")

        self.trim_var = tk.BooleanVar(value=False)
        self.canvas_var = tk.BooleanVar(value=False)
        self.canvas_size_var = tk.StringVar(value="480x320")
        self.anchor_var = tk.StringVar(value="左下")

        self.palette_extract_count_var = tk.StringVar(value="16")
        self.palette_include_white_var = tk.BooleanVar(value=True)
        self.palette_sort_var = tk.StringVar(value="なし")
        self.use_created_palette_var = tk.BooleanVar(value=True)

        self.batch_size_var = tk.StringVar(value="720x480")
        self.batch_reduce_var = tk.BooleanVar(value=False)
        self.batch_no_upscale_var = tk.BooleanVar(value=True)
        self.rename_base_var = tk.StringVar(value="image")
        self.rename_start_var = tk.StringVar(value="1")
        self.rename_digits_var = tk.StringVar(value="4")
        self.rename_order_var = tk.StringVar(value="ファイル名順")
        self.rename_target_var = tk.StringVar(value="全体")
        self.tool_tab_var = tk.StringVar(value="CONVERT")

        self.preview_scale_options = [
            "25%", "50%", "70%", "80%", "90%", "100%",
            "125%", "150%", "175%", "200%", "225%", "250%",
            "275%", "300%", "325%", "350%", "375%", "400%",
        ]

        self.scale_resize_options = [f"{i}%" for i in range(-200, 201, 10)]

        self.original_preview_scale_var = tk.StringVar(value="100%")
        self.converted_preview_scale_var = tk.StringVar(value="100%")
        self.global_settings = self.snapshot_settings()

        self.build_ui()
        self.install_setting_traces()
        # 起動直後は大量ファイルを自動スキャンせず、リストを空のままにする。
        # 一括入力フォルダボタンを押した時の初期位置だけ assets/images を使う。

    def build_ui(self):
        root_frame = tk.Frame(self.root, padx=10, pady=10)
        root_frame.pack(fill="both", expand=True)

        button_frame = tk.Frame(root_frame)
        button_frame.pack(fill="x", pady=(0, 8))

        tk.Button(button_frame, text="画像を選択", command=self.select_image).pack(side="left", padx=4)
        tk.Button(button_frame, text="一括入力フォルダ", command=self.select_batch_input_dir).pack(side="left", padx=4)
        tk.Button(button_frame, text="出力フォルダを選択", command=self.select_output_dir).pack(side="left", padx=4)
        tk.Button(button_frame, text="HELP", command=self.show_help).pack(side="left", padx=4)

        self.info_label = tk.Label(root_frame, text="画像未選択 / PVNM AUTO / 出力先未選択", anchor="w")
        self.info_label.pack(fill="x", pady=(0, 4))

        self.image_info_label = tk.Label(root_frame, text="元画像解像度: -", anchor="w")
        self.image_info_label.pack(fill="x", pady=(0, 8))

        tab_bar = tk.Frame(root_frame)
        tab_bar.pack(fill="x", pady=(0, 6))
        self.tool_tab_buttons = {}
        self.tool_tab_frames = {}
        for tab_name in ("CONVERT", "BATCH", "RENAME"):
            button = tk.Button(
                tab_bar,
                text=tab_name,
                width=12,
                command=lambda name=tab_name: self.show_tool_tab(name),
            )
            button.pack(side="left", padx=(0, 4))
            self.tool_tab_buttons[tab_name] = button

        self.tool_tab_container = tk.Frame(root_frame)
        self.tool_tab_container.pack(fill="x", pady=(0, 8))

        convert_tab = tk.Frame(self.tool_tab_container)
        batch_tab = tk.Frame(self.tool_tab_container)
        rename_tab = tk.Frame(self.tool_tab_container)
        self.tool_tab_frames["CONVERT"] = convert_tab
        self.tool_tab_frames["BATCH"] = batch_tab
        self.tool_tab_frames["RENAME"] = rename_tab

        settings = tk.LabelFrame(convert_tab, text="変換設定", padx=8, pady=8)
        settings.pack(fill="x", pady=(0, 8))

        row = 0
        tk.Label(settings, text="出力サイズ").grid(row=row, column=0, sticky="w")
        tk.Entry(settings, textvariable=self.size_var, width=12).grid(row=row, column=1, sticky="w", padx=4)

        tk.Checkbutton(settings, text="アスペクト維持", variable=self.keep_aspect_var).grid(row=row, column=2, sticky="w", padx=(16, 0))
        tk.Label(settings, text="収め方").grid(row=row, column=3, sticky="w")
        tk.OptionMenu(settings, self.fit_mode_var, "contain", "cover").grid(row=row, column=4, sticky="w")

        tk.Checkbutton(settings, text="倍率リサイズ", variable=self.scale_resize_enabled_var).grid(row=row, column=5, sticky="w", padx=(16, 0))
        tk.OptionMenu(settings, self.scale_percent_var, *self.scale_resize_options).grid(row=row, column=6, sticky="w")

        row += 1
        tk.Label(settings, text="リサイズ").grid(row=row, column=0, sticky="w", pady=4)
        tk.OptionMenu(settings, self.resize_var, "nearest", "lanczos", "bicubic", "bilinear", "box", "hamming").grid(row=row, column=1, sticky="w")

        tk.Label(settings, text="補正プリセット").grid(row=row, column=2, sticky="w", padx=(16, 0))
        tk.OptionMenu(settings, self.color_preset_var, *COLOR_PRESETS).grid(row=row, column=3, sticky="w")

        tk.Label(settings, text="色距離").grid(row=row, column=4, sticky="w", padx=(16, 0))
        tk.OptionMenu(settings, self.color_mode_var, "Pillow標準", "RGB", "Weighted RGB", "YCbCr", "Lab").grid(row=row, column=5, sticky="w")

        row += 1
        tk.Label(settings, text="R重み").grid(row=row, column=0, sticky="w", pady=4)
        tk.Entry(settings, textvariable=self.r_weight_var, width=6).grid(row=row, column=1, sticky="w")
        tk.Label(settings, text="G重み").grid(row=row, column=2, sticky="w", padx=(16, 0))
        tk.Entry(settings, textvariable=self.g_weight_var, width=6).grid(row=row, column=3, sticky="w")
        tk.Label(settings, text="B重み").grid(row=row, column=4, sticky="w")
        tk.Entry(settings, textvariable=self.b_weight_var, width=6).grid(row=row, column=5, sticky="w")

        tk.Label(settings, text="ディザリング").grid(row=row, column=6, sticky="w", padx=(16, 0))
        tk.OptionMenu(settings, self.dither_var, "なし", "Floyd-Steinberg", "Ordered 2x2", "Ordered 4x4").grid(row=row, column=7, sticky="w")

        row += 1
        tk.Label(settings, text="ノイズ低減 0-10").grid(row=row, column=0, sticky="w", pady=4)
        tk.OptionMenu(settings, self.noise_level_var, *[str(i) for i in range(0, 11)]).grid(row=row, column=1, sticky="w")

        tk.Label(settings, text="後ノイズ 0-10").grid(row=row, column=2, sticky="w", padx=(16, 0))
        tk.OptionMenu(settings, self.post_dither_noise_var, *[str(i) for i in range(0, 11)]).grid(row=row, column=3, sticky="w")

        tk.Label(settings, text="肌色補正 0-10").grid(row=row, column=4, sticky="w", padx=(16, 0))
        tk.OptionMenu(settings, self.skin_level_var, *[str(i) for i in range(0, 11)]).grid(row=row, column=5, sticky="w")

        row += 1
        tk.Label(settings, text="ピクセル化 0-10").grid(row=row, column=0, sticky="w", pady=4)
        tk.OptionMenu(settings, self.pixelize_level_var, *[str(i) for i in range(0, 11)]).grid(row=row, column=1, sticky="w")

        tk.Label(settings, text="輪郭強調 0-10").grid(row=row, column=2, sticky="w", padx=(16, 0))
        tk.OptionMenu(settings, self.edge_level_var, *[str(i) for i in range(0, 11)]).grid(row=row, column=3, sticky="w")

        tk.Label(settings, text="孤立除去 0-10").grid(row=row, column=4, sticky="w", padx=(16, 0))
        tk.OptionMenu(settings, self.isolated_level_var, *[str(i) for i in range(0, 11)]).grid(row=row, column=5, sticky="w")

        row += 1
        tk.Label(settings, text="元画像倍率").grid(row=row, column=0, sticky="w", pady=4)
        tk.OptionMenu(settings, self.original_preview_scale_var, *self.preview_scale_options, command=lambda _: self.show_original_preview()).grid(row=row, column=1, sticky="w")

        tk.Label(settings, text="変換後倍率").grid(row=row, column=2, sticky="w", padx=(16, 0))
        tk.OptionMenu(settings, self.converted_preview_scale_var, *self.preview_scale_options, command=lambda _: self.show_converted_preview()).grid(row=row, column=3, sticky="w")

        row += 1
        tk.Checkbutton(settings, text="指定色を透明化（白背景抜き用）", variable=self.transparent_enabled_var).grid(row=row, column=0, sticky="w", pady=4)
        tk.Entry(settings, textvariable=self.transparent_color_var, width=12).grid(row=row, column=1, sticky="w")
        tk.Label(settings, text="透明許容 0-80").grid(row=row, column=2, sticky="w", padx=(16, 0))
        tk.OptionMenu(settings, self.transparent_tolerance_var,
                      *[str(i) for i in list(range(0, 11)) + list(range(15, 81, 5))]).grid(row=row, column=3, sticky="w")

        tk.Checkbutton(settings, text="透明余白をトリミング", variable=self.trim_var).grid(row=row, column=4, sticky="w", padx=(16, 0))

        tk.Checkbutton(settings, text="キャンバス固定", variable=self.canvas_var).grid(row=row, column=5, sticky="w", padx=(16, 0))
        tk.Entry(settings, textvariable=self.canvas_size_var, width=12).grid(row=row, column=6, sticky="w")

        tk.Label(settings, text="配置").grid(row=row, column=7, sticky="w", padx=(16, 0))
        tk.OptionMenu(settings, self.anchor_var, "左下", "中央下", "右下", "中央").grid(row=row, column=8, sticky="w")

        palette_frame = tk.LabelFrame(convert_tab, text="パレット設定（通常はPVNM AUTOでOK）", padx=8, pady=8)
        palette_frame.pack(fill="x", pady=(0, 8))

        tk.Label(palette_frame, text="方式").grid(row=0, column=0, sticky="w")
        tk.OptionMenu(palette_frame, self.palette_mode_var, *PALETTE_MODES,
                      command=lambda _: self.update_info()).grid(row=0, column=1, sticky="w", padx=4)

        tk.Button(palette_frame, text="カスタムパレットを選択", command=self.select_palette).grid(row=0, column=2, sticky="w", padx=(16, 0))

        tk.Label(palette_frame, text="画像色").grid(row=0, column=3, sticky="w", padx=(16, 0))
        tk.OptionMenu(palette_frame, self.palette_image_scope_var,
                      *PALETTE_IMAGE_SCOPES).grid(row=0, column=4, sticky="w", padx=4)

        tk.Label(palette_frame, text="UIプリセット").grid(row=0, column=5, sticky="w", padx=(16, 0))
        tk.OptionMenu(palette_frame, self.ui_palette_preset_var,
                      *UI_PALETTE_PRESET_OPTIONS).grid(row=0, column=6, sticky="w", padx=4)

        tk.Label(palette_frame, text="色数").grid(row=1, column=0, sticky="w", pady=(6, 0))
        tk.OptionMenu(palette_frame, self.palette_extract_count_var, "16", "32", "64", "128", "256").grid(row=1, column=1, sticky="w", padx=4, pady=(6, 0))

        tk.Checkbutton(palette_frame, text="#FFFFFFを含める", variable=self.palette_include_white_var).grid(row=1, column=2, sticky="w", padx=(16, 0), pady=(6, 0))

        tk.Label(palette_frame, text="並び順").grid(row=1, column=3, sticky="w", padx=(16, 0), pady=(6, 0))
        tk.OptionMenu(palette_frame, self.palette_sort_var, "なし", "明るさ順", "色相順").grid(row=1, column=4, sticky="w", pady=(6, 0))

        tk.Checkbutton(palette_frame, text="作成後このパレットを使用", variable=self.use_created_palette_var).grid(row=1, column=5, sticky="w", padx=(16, 0), pady=(6, 0))
        tk.Button(palette_frame, text="画像からカスタムパレット作成", command=self.create_palette_from_current_image).grid(row=1, column=6, sticky="w", padx=(16, 0), pady=(6, 0))

        batch_frame = tk.LabelFrame(batch_tab, text="一括リサイズ / 一括変換", padx=8, pady=8)
        batch_frame.pack(fill="x", pady=(0, 8))

        tk.Label(batch_frame, text="サイズ").grid(row=0, column=0, sticky="w")
        tk.OptionMenu(batch_frame, self.batch_size_var, *BATCH_TARGET_SIZES).grid(row=0, column=1, sticky="w", padx=4)
        tk.Checkbutton(batch_frame, text="減色も実行", variable=self.batch_reduce_var).grid(row=0, column=2, sticky="w", padx=(16, 0))
        tk.Checkbutton(batch_frame, text="小さい画像は拡大しない", variable=self.batch_no_upscale_var).grid(row=0, column=3, sticky="w", padx=(16, 0))
        tk.Button(batch_frame, text="一括実行", command=self.batch_convert).grid(row=0, column=4, sticky="w", padx=(16, 0))
        tk.Button(batch_frame, text="変換＋リネーム", command=self.batch_convert_and_rename).grid(row=0, column=5, sticky="w", padx=4)

        self.batch_info_label = tk.Label(
            batch_frame,
            text="入力フォルダ未選択 / 出力先未選択時は入力フォルダ内の _pvnm_batch に保存",
            anchor="w",
        )
        self.batch_info_label.grid(row=1, column=0, columnspan=6, sticky="we", pady=(6, 0))

        tk.Label(
            batch_frame,
            text="変換＋リネームはRENAMEタブのベース名/開始番号/桁数/対象設定を使い、変換後PNGを連番名で保存します。",
            anchor="w",
        ).grid(row=2, column=0, columnspan=6, sticky="we", pady=(6, 0))

        rename_frame = tk.LabelFrame(rename_tab, text="一括リネームコピー", padx=8, pady=8)
        rename_frame.pack(fill="x", pady=(0, 8))

        tk.Label(rename_frame, text="ベース名").grid(row=0, column=0, sticky="w")
        tk.Entry(rename_frame, textvariable=self.rename_base_var, width=18).grid(row=0, column=1, sticky="w", padx=4)
        tk.Label(rename_frame, text="開始").grid(row=0, column=2, sticky="w", padx=(16, 0))
        tk.Entry(rename_frame, textvariable=self.rename_start_var, width=6).grid(row=0, column=3, sticky="w", padx=4)
        tk.Label(rename_frame, text="桁数").grid(row=0, column=4, sticky="w", padx=(16, 0))
        tk.OptionMenu(rename_frame, self.rename_digits_var, "4", "5", "6").grid(row=0, column=5, sticky="w", padx=4)
        tk.Label(rename_frame, text="順").grid(row=0, column=6, sticky="w", padx=(16, 0))
        tk.OptionMenu(rename_frame, self.rename_order_var, *BATCH_RENAME_ORDERS).grid(row=0, column=7, sticky="w", padx=4)
        tk.Label(rename_frame, text="対象").grid(row=0, column=8, sticky="w", padx=(16, 0))
        tk.OptionMenu(rename_frame, self.rename_target_var, "全体", "選択分", command=lambda _: self.update_rename_info()).grid(row=0, column=9, sticky="w", padx=4)
        tk.Button(rename_frame, text="プレビュー", command=self.show_rename_preview).grid(row=0, column=10, sticky="w", padx=(16, 0))
        tk.Button(rename_frame, text="コピー実行", command=self.batch_rename_copy).grid(row=0, column=11, sticky="w", padx=4)

        self.rename_info_label = tk.Label(
            rename_frame,
            text="入力フォルダ未選択 / 元画像は変更せず、コピー先だけを連番名にします",
            anchor="w",
        )
        self.rename_info_label.grid(row=1, column=0, columnspan=12, sticky="we", pady=(6, 0))

        self.show_tool_tab("CONVERT")

        status_frame = tk.Frame(root_frame, bd=1, relief="sunken")
        status_frame.pack(fill="x", side="bottom", pady=(6, 0))
        self.status_label = tk.Label(status_frame, text="準備完了", anchor="w")
        self.status_label.pack(fill="x", padx=6, pady=3)

        action_frame = tk.Frame(root_frame, bd=1, relief="groove", padx=6, pady=4)
        action_frame.pack(fill="x", side="bottom", pady=(6, 0))
        tk.Button(action_frame, text="SAVE CURRENT", command=self.convert_and_save).pack(side="left", padx=4)
        tk.Button(action_frame, text="BATCH CONVERT", command=self.batch_convert).pack(side="left", padx=4)
        tk.Button(action_frame, text="RENAME COPY", command=self.batch_rename_copy).pack(side="left", padx=4)
        tk.Button(action_frame, text="CONVERT + RENAME", command=self.batch_convert_and_rename).pack(side="left", padx=4)
        tk.Label(
            action_frame,
            text="一括操作は左のファイル一覧を対象にします。RENAMEの対象を「選択分」にすると選択画像だけ処理します。",
            anchor="w",
        ).pack(side="left", padx=(12, 0), fill="x", expand=True)

        preview_outer = tk.Frame(root_frame)
        preview_outer.pack(fill="both", expand=True)

        list_panel = tk.LabelFrame(preview_outer, text="一括ファイル", padx=8, pady=8)
        list_panel.pack(side="left", fill="y", padx=4)

        list_wrap = tk.Frame(list_panel)
        list_wrap.pack(fill="both", expand=True)
        self.batch_listbox = tk.Listbox(
            list_wrap, width=34, height=18, exportselection=False,
            selectmode="extended")
        self.batch_scrollbar = tk.Scrollbar(list_wrap, orient="vertical",
                                            command=self.batch_listbox.yview)
        self.batch_listbox.config(yscrollcommand=self.batch_scrollbar.set)
        self.batch_listbox.pack(side="left", fill="both", expand=True)
        self.batch_scrollbar.pack(side="right", fill="y")
        self.batch_listbox.bind("<<ListboxSelect>>", self.on_batch_file_select)

        preview_area = tk.Frame(preview_outer)
        preview_area.pack(side="left", fill="both", expand=True, padx=4)
        preview_area.grid_rowconfigure(0, weight=1)
        preview_area.grid_columnconfigure(0, weight=1)

        self.preview_canvas = tk.Canvas(preview_area, highlightthickness=0)
        preview_scroll_y = tk.Scrollbar(
            preview_area, orient="vertical", command=self.preview_canvas.yview)
        preview_scroll_x = tk.Scrollbar(
            preview_area, orient="horizontal", command=self.preview_canvas.xview)
        self.preview_canvas.configure(
            yscrollcommand=preview_scroll_y.set,
            xscrollcommand=preview_scroll_x.set,
        )
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")
        preview_scroll_y.grid(row=0, column=1, sticky="ns")
        preview_scroll_x.grid(row=1, column=0, sticky="ew")
        self.preview_canvas.bind("<Enter>", self._bind_preview_mousewheel)
        self.preview_canvas.bind("<Leave>", self._unbind_preview_mousewheel)

        preview_frame = tk.Frame(self.preview_canvas)
        self.preview_canvas_window = self.preview_canvas.create_window(
            (0, 0), window=preview_frame, anchor="nw")
        preview_frame.bind("<Configure>", self._sync_preview_scrollregion)
        self.preview_canvas.bind("<Configure>", self._sync_preview_canvas_width)

        left = tk.LabelFrame(preview_frame, text="元画像", padx=8, pady=8)
        left.pack(side="left", fill="both", expand=True, padx=4)

        right = tk.LabelFrame(preview_frame, text="変換後", padx=8, pady=8)
        right.pack(side="left", fill="both", expand=True, padx=4)

        self.preview_label = tk.Label(left, text="未選択")
        self.preview_label.pack(fill="both", expand=True)

        self.output_label = tk.Label(right, text="未変換")
        self.output_label.pack(fill="both", expand=True)

    def show_tool_tab(self, tab_name):
        if tab_name not in getattr(self, "tool_tab_frames", {}):
            return
        self.tool_tab_var.set(tab_name)
        for name, frame in self.tool_tab_frames.items():
            if name == tab_name:
                frame.pack(fill="x")
            else:
                frame.pack_forget()
        for name, button in self.tool_tab_buttons.items():
            if name == tab_name:
                button.config(relief="sunken", state="normal")
            else:
                button.config(relief="raised", state="normal")

    def show_help(self):
        win = tk.Toplevel(self.root)
        win.title("HELP")
        win.geometry("760x620")
        text = tk.Text(win, wrap="word")
        text.pack(fill="both", expand=True)
        text.insert("1.0", HELP_TEXT)
        text.config(state="disabled")

    def _sync_preview_scrollregion(self, event=None):
        if not hasattr(self, "preview_canvas"):
            return
        self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))

    def _sync_preview_canvas_width(self, event=None):
        # Do not force the embedded preview frame to the canvas width.
        # Keeping its requested width lets the horizontal scrollbar work when
        # large previews exceed the visible area.
        return

    def _bind_preview_mousewheel(self, event=None):
        self.preview_canvas.bind_all("<MouseWheel>", self._on_preview_mousewheel)
        self.preview_canvas.bind_all("<Shift-MouseWheel>", self._on_preview_shift_mousewheel)
        self.preview_canvas.bind_all("<Button-4>", self._on_preview_mousewheel)
        self.preview_canvas.bind_all("<Button-5>", self._on_preview_mousewheel)
        self.preview_canvas.bind_all("<Shift-Button-4>", self._on_preview_shift_mousewheel)
        self.preview_canvas.bind_all("<Shift-Button-5>", self._on_preview_shift_mousewheel)

    def _unbind_preview_mousewheel(self, event=None):
        for seq in (
                "<MouseWheel>", "<Shift-MouseWheel>",
                "<Button-4>", "<Button-5>",
                "<Shift-Button-4>", "<Shift-Button-5>"):
            try:
                self.preview_canvas.unbind_all(seq)
            except Exception:
                pass

    def _wheel_units(self, event):
        if getattr(event, "num", None) == 4:
            return -3
        if getattr(event, "num", None) == 5:
            return 3
        delta = getattr(event, "delta", 0)
        if delta == 0:
            return 0
        return -1 if delta > 0 else 1

    def _on_preview_mousewheel(self, event):
        units = self._wheel_units(event)
        if units:
            self.preview_canvas.yview_scroll(units, "units")
        return "break"

    def _on_preview_shift_mousewheel(self, event):
        units = self._wheel_units(event)
        if units:
            self.preview_canvas.xview_scroll(units, "units")
        return "break"

    def set_default_batch_input_dir(self):
        default_dir = default_assets_images_dir()
        if not default_dir.is_dir():
            return
        self.batch_input_dir = str(default_dir)
        self.refresh_batch_file_list(select_first=False)
        self.update_batch_info()
        self.status_label.config(
            text=f"一括入力フォルダ初期値: {default_dir} / {len(self.batch_files)} files"
        )

    def install_setting_traces(self):
        for name in SETTING_VAR_NAMES:
            var = getattr(self, name, None)
            if var is None:
                continue
            handle = var.trace_add(
                "write",
                lambda *_args, field=name: self.on_setting_changed(field),
            )
            self._trace_handles.append((var, handle))

    def snapshot_settings(self):
        data = {}
        for name in SETTING_VAR_NAMES:
            var = getattr(self, name)
            data[name] = var.get()
        data["palette_path"] = self.palette_path
        return data

    def apply_settings(self, settings):
        self._loading_settings = True
        try:
            for name in SETTING_VAR_NAMES:
                if name not in settings:
                    continue
                var = getattr(self, name)
                var.set(settings[name])
            if "palette_path" in settings:
                self.palette_path = settings.get("palette_path")
        finally:
            self._loading_settings = False
        self.update_info()

    def selected_batch_paths(self):
        if not hasattr(self, "batch_listbox"):
            return []
        out = []
        for idx in self.batch_listbox.curselection():
            i = int(idx)
            if 0 <= i < len(self.batch_files):
                out.append(Path(self.batch_files[i]))
        return out

    def batch_record_for_path(self, path):
        key = str(path)
        rec = self.per_file_settings.get(key)
        if not isinstance(rec, dict) or "values" not in rec:
            rec = {"values": {}, "touched": set()}
            self.per_file_settings[key] = rec
        if not isinstance(rec.get("touched"), set):
            rec["touched"] = set(rec.get("touched") or [])
        if not isinstance(rec.get("values"), dict):
            rec["values"] = {}
        return rec

    def has_custom_settings(self, path):
        rec = self.per_file_settings.get(str(path))
        return bool(isinstance(rec, dict) and rec.get("touched"))

    def settings_for_batch_path(self, path, base_settings=None):
        settings = dict(base_settings or self.global_settings or self.snapshot_settings())
        rec = self.per_file_settings.get(str(path))
        if isinstance(rec, dict):
            values = rec.get("values") or {}
            touched = rec.get("touched") or set()
            for name in touched:
                if name in values:
                    settings[name] = values[name]
        return settings

    def remember_current_field(self, field_name):
        if not field_name:
            return
        value = getattr(self, field_name).get()
        if self.global_settings is None:
            self.global_settings = self.snapshot_settings()
        self.global_settings[field_name] = value

        for path in self.selected_batch_paths():
            rec = self.batch_record_for_path(path)
            rec["values"][field_name] = value
            rec["touched"].add(field_name)

    def remember_palette_path_change(self):
        if self.global_settings is None:
            self.global_settings = self.snapshot_settings()
        self.global_settings["palette_path"] = self.palette_path
        for path in self.selected_batch_paths():
            rec = self.batch_record_for_path(path)
            rec["values"]["palette_path"] = self.palette_path
            rec["touched"].add("palette_path")

    def on_setting_changed(self, field_name=None):
        if self._loading_settings:
            return
        self.remember_current_field(field_name)
        self.refresh_batch_file_list(select_first=False, keep_selection=True)
        self.update_info()
        self.schedule_preview_update()

    def schedule_preview_update(self, delay_ms=300):
        if self._preview_after_id is not None:
            try:
                self.root.after_cancel(self._preview_after_id)
            except Exception:
                pass
        self._preview_after_id = self.root.after(delay_ms, self.auto_update_preview)

    def auto_update_preview(self):
        self._preview_after_id = None
        if self.image is None:
            return
        self.update_converted_preview(show_errors=False)

    def refresh_batch_file_list(self, select_first=False, keep_selection=False):
        if not hasattr(self, "batch_listbox"):
            return
        old_selection = set()
        if keep_selection:
            old_selection = {
                str(self.batch_files[int(i)])
                for i in self.batch_listbox.curselection()
                if 0 <= int(i) < len(self.batch_files)
            }
        self.batch_listbox.delete(0, "end")
        self.batch_files = []
        if not self.batch_input_dir:
            return

        input_dir = Path(self.batch_input_dir)
        excluded_dirs = [
            input_dir / BATCH_OUTPUT_DIR_NAME,
            input_dir / BATCH_RENAME_OUTPUT_DIR_NAME,
        ]
        if self.output_dir:
            excluded_dirs.append(Path(self.output_dir))
        self.batch_files = list_batch_image_files(self.batch_input_dir, excluded_dirs)
        root = Path(self.batch_input_dir)

        for path in self.batch_files:
            try:
                label = str(Path(path).relative_to(root))
            except Exception:
                label = Path(path).name
            prefix = "[*] " if self.has_custom_settings(path) else "[ ] "
            self.batch_listbox.insert("end", prefix + label)

        if keep_selection and old_selection:
            for idx, path in enumerate(self.batch_files):
                if str(path) in old_selection:
                    self.batch_listbox.selection_set(idx)

        if select_first and self.batch_files:
            self.batch_listbox.selection_set(0)
            self.batch_listbox.activate(0)
            self.on_batch_file_select()

    def on_batch_file_select(self, event=None):
        selection = self.batch_listbox.curselection()
        if not selection:
            return
        idx = int(selection[0])
        if not (0 <= idx < len(self.batch_files)):
            return

        selected_paths = self.selected_batch_paths()
        if not selected_paths:
            return
        path = Path(self.batch_files[idx])
        self.selected_batch_path = path
        settings = self.settings_for_batch_path(path)
        self.apply_settings(settings)

        try:
            self.input_path = str(path)
            self.image = Image.open(path).convert("RGBA")
            self.image = normalize_transparent_rgb(self.image, (255, 255, 255))
            self.converted_image = None
            self.update_info()
            self.image_info_label.config(
                text=f"元画像解像度: {self.image.width} x {self.image.height} / アスペクト比: {self.image.width / self.image.height:.4f}"
            )
            self.show_original_preview()
            self.output_label.config(image="", text="自動プレビュー中...")
            self.status_label.config(text=f"選択中: {path.name}")
            self.schedule_preview_update(delay_ms=80)
        except Exception as e:
            messagebox.showerror("画像読み込みエラー", str(e))

    def select_image(self):
        path = filedialog.askopenfilename(
            title="画像を選択",
            filetypes=(
                ("PNG", "*.png"),
                ("JPEG", "*.jpg"),
                ("JPEG", "*.jpeg"),
                ("BMP", "*.bmp"),
                ("WEBP", "*.webp"),
                ("All files", "*"),
            ),
        )

        if not path:
            return

        try:
            self.selected_batch_path = None
            if hasattr(self, "batch_listbox"):
                self.batch_listbox.selection_clear(0, "end")
            self.input_path = path
            self.image = Image.open(path).convert("RGBA")
            self.image = normalize_transparent_rgb(self.image, (255, 255, 255))
            self.converted_image = None

            self.update_info()
            self.image_info_label.config(
                text=f"元画像解像度: {self.image.width} x {self.image.height} / アスペクト比: {self.image.width / self.image.height:.4f}"
            )

            self.show_original_preview()
            self.output_label.config(image="", text="自動プレビュー中...")
            self.status_label.config(text="画像を読み込みました")
            self.schedule_preview_update(delay_ms=80)

        except Exception as e:
            messagebox.showerror("画像読み込みエラー", str(e))

    def select_batch_input_dir(self):
        default_dir = default_assets_images_dir()
        initial_dir = str(default_dir if default_dir.is_dir() else Path.cwd())
        path = filedialog.askdirectory(
            title="一括入力フォルダを選択",
            initialdir=initial_dir,
        )
        if not path:
            return

        self.batch_input_dir = path
        self.selected_batch_path = None
        self.refresh_batch_file_list(select_first=True)
        self.update_batch_info()
        self.status_label.config(
            text=f"一括入力フォルダを設定しました: {path} / {len(self.batch_files)} files"
        )

    def select_palette(self):
        path = filedialog.askopenfilename(
            title="パレットを選択",
            filetypes=(
                ("Pyxel palette", "*.pyxpal"),
                ("Text", "*.txt"),
                ("All files", "*"),
            ),
        )

        if not path:
            return

        try:
            colors = load_pyxpal(path)
            self.palette_path = path
            self.remember_palette_path_change()
            self.palette_mode_var.set(PALETTE_MODE_CUSTOM)
            self.update_info(extra=f" / {len(colors)}色")
            self.refresh_batch_file_list(select_first=False, keep_selection=True)
            self.status_label.config(text=f"パレットを読み込みました: {len(colors)}色")
        except Exception as e:
            messagebox.showerror("パレット読み込みエラー", str(e))

    def select_output_dir(self):
        path = filedialog.askdirectory(title="出力フォルダを選択")
        if not path:
            return

        self.output_dir = path
        self.update_info()
        self.refresh_batch_file_list(select_first=False)
        self.update_batch_info()
        self.status_label.config(text=f"出力フォルダを設定しました: {path}")

    def create_palette_from_current_image(self):
        try:
            if self.image is None or self.input_path is None:
                raise ValueError("画像が選択されていません")

            color_count = int(self.palette_extract_count_var.get())
            colors = extract_palette_from_image(
                self.image,
                color_count=color_count,
                include_white=self.palette_include_white_var.get(),
                sort_mode=self.palette_sort_var.get(),
            )

            save_path = make_auto_palette_save_path(
                input_path=self.input_path,
                output_dir=self.output_dir,
                prefix=AUTO_PALETTE_PREFIX,
            )

            save_pyxpal(save_path, colors)

            if self.use_created_palette_var.get():
                self.palette_path = str(save_path)
                self.remember_palette_path_change()
                self.palette_mode_var.set(PALETTE_MODE_CUSTOM)
                self.update_info(extra=f" / {len(colors)}色")
                self.refresh_batch_file_list(select_first=False, keep_selection=True)
                self.status_label.config(text=f"パレット作成・使用中: {save_path}")
            else:
                self.status_label.config(text=f"パレット作成完了: {save_path}")

            messagebox.showinfo("パレット作成完了", f"保存しました:\n{save_path}")

        except Exception as e:
            messagebox.showerror("パレット作成エラー", str(e))

    def get_scale_percent(self, scale_var):
        return int(scale_var.get().replace("%", ""))

    def get_scale_resize_percent(self):
        return int(self.scale_percent_var.get().replace("%", ""))

    def update_info(self, extra=""):
        image_text = Path(self.input_path).name if self.input_path else "画像未選択"
        if self.selected_batch_path:
            try:
                rel = Path(self.selected_batch_path).relative_to(Path(self.batch_input_dir))
                image_text = f"一括: {rel}"
            except Exception:
                image_text = f"一括: {Path(self.selected_batch_path).name}"
        if self.palette_mode_var.get() == PALETTE_MODE_CUSTOM:
            pal_text = (f"カスタム: {Path(self.palette_path).name}"
                        if self.palette_path else "カスタムパレット未選択")
        else:
            pal_text = PALETTE_MODE_AUTO
        scope_text = self.palette_image_scope_var.get()
        ui_text = self.ui_palette_preset_var.get()
        out_text = str(Path(self.output_dir)) if self.output_dir else "出力先未選択（元画像フォルダに保存）"
        self.info_label.config(
            text=f"{image_text} / {pal_text} / 画像色: {scope_text} / UI: {ui_text} / 出力先: {out_text}{extra}"
        )

    def update_batch_info(self):
        if not hasattr(self, "batch_info_label"):
            return
        in_text = str(Path(self.batch_input_dir)) if self.batch_input_dir else "入力フォルダ未選択"
        if self.output_dir:
            out_text = str(Path(self.output_dir))
        elif self.batch_input_dir:
            out_text = str(Path(self.batch_input_dir) / BATCH_OUTPUT_DIR_NAME)
        else:
            out_text = "出力先未選択"
        self.batch_info_label.config(text=f"入力: {in_text} / 出力: {out_text}")
        self.update_rename_info()

    def rename_output_dir(self):
        if self.output_dir:
            return Path(self.output_dir)
        if self.batch_input_dir:
            return Path(self.batch_input_dir) / BATCH_RENAME_OUTPUT_DIR_NAME
        return None

    def update_rename_info(self):
        if not hasattr(self, "rename_info_label"):
            return
        if not self.batch_input_dir:
            self.rename_info_label.config(
                text="入力フォルダ未選択 / 元画像は変更せず、コピー先だけを連番名にします"
            )
            return
        out_dir = self.rename_output_dir()
        target = self.rename_target_var.get()
        target_text = "一覧全体" if target == "全体" else "選択中の画像"
        self.rename_info_label.config(
            text=f"対象: {target_text} / コピー先: {out_dir} / 元ファイルは変更しません"
        )

    def rename_source_files(self):
        if not self.batch_input_dir:
            raise ValueError("一括入力フォルダが選択されていません")
        if self.rename_target_var.get() == "選択分":
            files = self.selected_batch_paths()
            if not files:
                raise ValueError("リネーム対象の画像をリストで選択してください")
        else:
            files = list(self.batch_files)
            if not files:
                input_dir = Path(self.batch_input_dir)
                excluded_dirs = [
                    input_dir / BATCH_OUTPUT_DIR_NAME,
                    input_dir / BATCH_RENAME_OUTPUT_DIR_NAME,
                ]
                if self.output_dir:
                    excluded_dirs.append(Path(self.output_dir))
                files = list_batch_image_files(input_dir, excluded_dirs)
        files = sort_rename_files(files, self.rename_order_var.get())
        if not files:
            raise ValueError("対象画像が見つかりませんでした")
        return files

    def make_rename_plan(self, output_suffix=None):
        output_dir = self.rename_output_dir()
        if output_dir is None:
            raise ValueError("一括入力フォルダが選択されていません")
        return build_rename_copy_plan(
            self.rename_source_files(),
            output_dir,
            self.rename_base_var.get(),
            self.rename_start_var.get(),
            self.rename_digits_var.get(),
            output_suffix=output_suffix,
        )

    def format_rename_plan_preview(self, plan, limit=None):
        lines = []
        input_dir = Path(self.batch_input_dir) if self.batch_input_dir else None
        for index, (src, dst) in enumerate(plan):
            if limit is not None and index >= limit:
                lines.append(f"...他 {len(plan) - limit} 件")
                break
            try:
                src_label = str(src.relative_to(input_dir)) if input_dir else str(src)
            except Exception:
                src_label = str(src)
            lines.append(f"{src_label}  ->  {dst.name}")
        return "\n".join(lines)

    def show_rename_preview(self):
        try:
            plan = self.make_rename_plan()
            output_dir = self.rename_output_dir()
            conflicts = [dst for _src, dst in plan if dst.exists()]
            text_lines = [
                f"コピー先: {output_dir}",
                f"対象: {len(plan)} 件",
                f"上書き衝突: {len(conflicts)} 件",
                "",
                self.format_rename_plan_preview(plan),
            ]
            if conflicts:
                text_lines.insert(
                    4,
                    "既存ファイルと衝突しています。コピー実行前にコピー先を空にするか、ベース名/開始番号を変更してください。\n",
                )

            win = tk.Toplevel(self.root)
            win.title("リネームプレビュー")
            win.geometry("820x520")
            text = tk.Text(win, wrap="none")
            text.pack(side="left", fill="both", expand=True)
            y_scroll = tk.Scrollbar(win, orient="vertical", command=text.yview)
            y_scroll.pack(side="right", fill="y")
            text.config(yscrollcommand=y_scroll.set)
            text.insert("1.0", "\n".join(text_lines))
            text.config(state="disabled")
        except Exception as e:
            messagebox.showerror("リネームプレビューエラー", str(e))

    def batch_rename_copy(self):
        try:
            plan = self.make_rename_plan()
            output_dir = self.rename_output_dir()
            conflicts = [dst for _src, dst in plan if dst.exists()]
            if conflicts:
                preview = "\n".join(str(path) for path in conflicts[:10])
                more = "" if len(conflicts) <= 10 else f"\n...他 {len(conflicts) - 10} 件"
                raise ValueError(f"コピー先に既存ファイルがあります:\n{preview}{more}")

            preview = self.format_rename_plan_preview(plan, limit=10)
            ok = messagebox.askyesno(
                "リネームコピー確認",
                f"{len(plan)} 件をコピーします。\nコピー先:\n{output_dir}\n\n{preview}",
            )
            if not ok:
                return

            output_dir.mkdir(parents=True, exist_ok=True)
            for index, (src, dst) in enumerate(plan, 1):
                self.status_label.config(
                    text=f"リネームコピー中 {index}/{len(plan)}: {dst.name}"
                )
                self.root.update_idletasks()
                shutil.copy2(src, dst)

            self.status_label.config(
                text=f"リネームコピー完了: {len(plan)} 件 / {output_dir}"
            )
            messagebox.showinfo(
                "リネームコピー完了",
                f"コピーしました: {len(plan)} 件\n出力先:\n{output_dir}",
            )
            self.refresh_batch_file_list(select_first=False, keep_selection=True)
            self.update_batch_info()
        except Exception as e:
            messagebox.showerror("リネームコピーエラー", str(e))

    def batch_convert_and_rename(self):
        try:
            if not self.batch_input_dir:
                raise ValueError("一括入力フォルダが選択されていません")

            base_settings = dict(self.global_settings or self.snapshot_settings())
            selected_before = self.selected_batch_path

            plan = self.make_rename_plan(output_suffix=".png")
            output_dir = self.rename_output_dir()
            conflicts = [dst for _src, dst in plan if dst.exists()]
            if conflicts:
                preview = "\n".join(str(path) for path in conflicts[:10])
                more = "" if len(conflicts) <= 10 else f"\n...他 {len(conflicts) - 10} 件"
                raise ValueError(f"変換先に既存ファイルがあります:\n{preview}{more}")

            preview = self.format_rename_plan_preview(plan, limit=10)
            ok = messagebox.askyesno(
                "変換＋リネーム確認",
                f"{len(plan)} 件を変換し、連番PNGで保存します。\n"
                f"出力先:\n{output_dir}\n\n{preview}",
            )
            if not ok:
                return

            output_dir.mkdir(parents=True, exist_ok=True)
            reduce_enabled = self.batch_reduce_var.get()
            target_size = self.batch_size_var.get()
            allow_upscale = not self.batch_no_upscale_var.get()

            saved = 0
            errors = []
            total = len(plan)
            for index, (src, dst) in enumerate(plan, 1):
                self.status_label.config(
                    text=f"変換＋リネーム中 {index}/{total}: {dst.name}"
                )
                self.root.update_idletasks()
                try:
                    settings = self.settings_for_batch_path(
                        src, base_settings=base_settings)
                    self.apply_settings(settings)
                    with Image.open(src) as source:
                        img = source.convert("RGBA")
                    converted = self.convert_image(
                        img,
                        apply_palette_enabled=reduce_enabled,
                        batch_size_text=target_size,
                        allow_upscale=allow_upscale,
                    )
                    converted.save(dst)
                    saved += 1
                except Exception as e:
                    errors.append(f"{src.name}: {e}")

            if errors:
                preview_errors = "\n".join(errors[:10])
                more = "" if len(errors) <= 10 else f"\n...他 {len(errors) - 10} 件"
                messagebox.showwarning(
                    "変換＋リネーム完了（一部失敗）",
                    f"保存: {saved} / 失敗: {len(errors)}\n"
                    f"出力先:\n{output_dir}\n\n{preview_errors}{more}",
                )
            else:
                messagebox.showinfo(
                    "変換＋リネーム完了",
                    f"保存: {saved} 件\n出力先:\n{output_dir}",
                )

            self.status_label.config(
                text=f"変換＋リネーム完了: 保存 {saved} 件 / 失敗 {len(errors)} 件"
            )
            if selected_before:
                self.selected_batch_path = selected_before
                self.apply_settings(self.settings_for_batch_path(selected_before))
            else:
                self.apply_settings(base_settings)
            self.refresh_batch_file_list(select_first=False, keep_selection=True)
            self.update_batch_info()
            self.schedule_preview_update(delay_ms=80)
        except Exception as e:
            messagebox.showerror("変換＋リネームエラー", str(e))

    def show_original_preview(self):
        if self.image is None:
            return

        scale = self.get_scale_percent(self.original_preview_scale_var)
        preview = make_preview_image(self.image, scale)
        self.preview_ref = ImageTk.PhotoImage(preview)
        self.preview_label.config(image=self.preview_ref, text="")

    def show_converted_preview(self):
        if self.converted_image is None:
            return

        scale = self.get_scale_percent(self.converted_preview_scale_var)
        preview = make_preview_image(self.converted_image, scale)
        self.output_ref = ImageTk.PhotoImage(preview)
        self.output_label.config(image=self.output_ref, text="")

    def _current_weights(self):
        weights = (
            float(self.r_weight_var.get()),
            float(self.g_weight_var.get()),
            float(self.b_weight_var.get()),
        )
        return weights

    def _current_palette_for_image(self, img):
        if self.palette_mode_var.get() == PALETTE_MODE_CUSTOM:
            if self.palette_path is None:
                raise ValueError("カスタムパレットが選択されていません")
            return apply_ui_reserved_to_palette(
                load_pyxpal(self.palette_path),
                self.ui_palette_preset_var.get(),
            )
        return build_pvnm_auto_palette(
            img,
            ui_preset_name=self.ui_palette_preset_var.get(),
            allow_reserved_rgb_in_free_slots=(
                self.palette_image_scope_var.get()
                == PALETTE_IMAGE_SCOPE_EXCLUDE_UI
            ),
        )

    def _prepare_source_pair(self, source_image):
        transparent_rgb = hex_to_rgb(self.transparent_color_var.get())

        img = source_image.copy().convert("RGBA")
        img = normalize_transparent_rgb(img, (255, 255, 255))

        alpha_mask = make_alpha_mask_from_source(
            img,
            transparent_enabled=False,
            transparent_rgb=transparent_rgb,
            transparent_tolerance=0,
        )

        return img, alpha_mask

    def _apply_color_key_after_resize(self, img, alpha_mask):
        return apply_color_key_to_alpha_mask(
            img,
            alpha_mask,
            transparent_enabled=self.transparent_enabled_var.get(),
            transparent_rgb=hex_to_rgb(self.transparent_color_var.get()),
            transparent_tolerance=int(self.transparent_tolerance_var.get()),
        )

    def _resize_with_current_settings(self, img, alpha_mask):
        if self.scale_resize_enabled_var.get():
            img, alpha_mask = scale_pair_by_percent(
                img,
                alpha_mask,
                self.get_scale_resize_percent(),
                self.resize_var.get(),
            )
        else:
            size = parse_size(self.size_var.get())
            img, alpha_mask = resize_pair(
                img,
                alpha_mask,
                size,
                self.resize_var.get(),
                keep_aspect=self.keep_aspect_var.get(),
                fit_mode=self.fit_mode_var.get(),
            )
        return img, alpha_mask

    def _resize_for_batch(self, img, alpha_mask, target_size_text, allow_upscale):
        target_size = parse_size(target_size_text)
        output_size = fit_inside_size(
            img.size,
            target_size,
            allow_upscale=allow_upscale,
        )
        return resize_pair(
            img,
            alpha_mask,
            output_size,
            self.resize_var.get(),
            keep_aspect=False,
        )

    def convert_image(self, source_image, *, apply_palette_enabled=True,
                      batch_size_text=None, allow_upscale=True):
        img, alpha_mask = self._prepare_source_pair(source_image)

        if batch_size_text is None:
            img, alpha_mask = self._resize_with_current_settings(img, alpha_mask)
        else:
            img, alpha_mask = self._resize_for_batch(
                img,
                alpha_mask,
                batch_size_text,
                allow_upscale=allow_upscale,
            )

        alpha_mask = self._apply_color_key_after_resize(img, alpha_mask)

        img = apply_color_preset(img, self.color_preset_var.get())
        img = restore_alpha(img, alpha_mask)

        if not apply_palette_enabled:
            return restore_alpha(img, alpha_mask)

        weights = self._current_weights()

        img = pixelize_image_10level(img, self.pixelize_level_var.get())
        img = reduce_noise_10level(img, self.noise_level_var.get())
        img = skin_tone_adjust_10level(img, self.skin_level_var.get())
        img = sharpen_edges_10level(img, self.edge_level_var.get())

        palette = self._current_palette_for_image(img)
        allowed_indices = image_allowed_indices_for_scope(
            self.palette_image_scope_var.get(),
            self.ui_palette_preset_var.get(),
        )

        img = apply_palette(
            img,
            palette,
            self.dither_var.get(),
            self.color_mode_var.get(),
            weights,
            allowed_indices=allowed_indices,
        )

        img = post_dither_noise_reduce_10level(img, self.post_dither_noise_var.get())
        img = restore_alpha(img, alpha_mask)

        img = remove_isolated_pixels_10level(img, self.isolated_level_var.get())
        img = restore_alpha(img, alpha_mask)

        if self.trim_var.get():
            img, alpha_mask = trim_transparent_pair(img, alpha_mask)
            img = restore_alpha(img, alpha_mask)

        if self.canvas_var.get():
            canvas_size = parse_size(self.canvas_size_var.get())
            img, alpha_mask = paste_on_canvas_pair(img, alpha_mask, canvas_size, self.anchor_var.get())
            img = restore_alpha(img, alpha_mask)

        return img

    def convert_current_image(self):
        if self.image is None:
            raise ValueError("画像が選択されていません")
        if self.selected_batch_path:
            return self.convert_image(
                self.image,
                apply_palette_enabled=self.batch_reduce_var.get(),
                batch_size_text=self.batch_size_var.get(),
                allow_upscale=not self.batch_no_upscale_var.get(),
            )
        return self.convert_image(self.image, apply_palette_enabled=True)

    def update_converted_preview(self, show_errors=True):
        try:
            self.converted_image = self.convert_current_image()
            self.show_converted_preview()
            used = count_used_colors(self.converted_image)
            self.status_label.config(
                text=f"変換完了: {self.converted_image.width}x{self.converted_image.height} / 使用色 {used} 色"
            )
        except Exception as e:
            self.output_label.config(image="", text="プレビュー待機中")
            self.status_label.config(text=f"プレビュー待機中: {e}")
            if show_errors:
                messagebox.showerror("変換エラー", str(e))

    def convert_and_save(self):
        try:
            self.converted_image = self.convert_current_image()
            self.show_converted_preview()

            save_path = make_auto_save_path(
                input_path=self.input_path,
                output_dir=self.output_dir,
                prefix=AUTO_SAVE_PREFIX,
            )

            self.converted_image.save(save_path)
            used = count_used_colors(self.converted_image)
            self.status_label.config(text=f"保存完了: {save_path} / 使用色 {used} 色")
            messagebox.showinfo("保存完了", f"保存しました:\n{save_path}")

        except Exception as e:
            messagebox.showerror("保存エラー", str(e))

    def batch_convert(self):
        try:
            if not self.batch_input_dir:
                raise ValueError("一括入力フォルダが選択されていません")

            base_settings = dict(self.global_settings or self.snapshot_settings())
            selected_before = self.selected_batch_path

            input_dir = Path(self.batch_input_dir)
            if not input_dir.is_dir():
                raise ValueError("一括入力フォルダが存在しません")

            output_dir = (Path(self.output_dir) if self.output_dir
                          else input_dir / BATCH_OUTPUT_DIR_NAME)

            excluded_dirs = [
                output_dir,
                input_dir / BATCH_OUTPUT_DIR_NAME,
                input_dir / BATCH_RENAME_OUTPUT_DIR_NAME,
            ]
            files = list_batch_image_files(input_dir, excluded_dirs)
            if not files:
                raise ValueError("対象画像が見つかりませんでした")

            saved = 0
            errors = []
            total = len(files)

            for index, path in enumerate(files, 1):
                self.status_label.config(
                    text=f"一括処理中 {index}/{total}: {path.name}"
                )
                self.root.update_idletasks()

                try:
                    settings = self.settings_for_batch_path(
                        path, base_settings=base_settings)
                    self.apply_settings(settings)
                    reduce_enabled = self.batch_reduce_var.get()
                    target_size = self.batch_size_var.get()
                    allow_upscale = not self.batch_no_upscale_var.get()
                    with Image.open(path) as src:
                        img = src.convert("RGBA")
                    converted = self.convert_image(
                        img,
                        apply_palette_enabled=reduce_enabled,
                        batch_size_text=target_size,
                        allow_upscale=allow_upscale,
                    )
                    save_path = batch_output_path(
                        path,
                        input_dir,
                        output_dir,
                        target_size,
                        reduced=reduce_enabled,
                    )
                    converted.save(save_path)
                    saved += 1
                except Exception as e:
                    errors.append(f"{path.name}: {e}")

            if errors:
                preview = "\n".join(errors[:10])
                more = "" if len(errors) <= 10 else f"\n...他 {len(errors) - 10} 件"
                messagebox.showwarning(
                    "一括処理完了（一部失敗）",
                    f"保存: {saved} / 失敗: {len(errors)}\n出力先:\n{output_dir}\n\n{preview}{more}",
                )
            else:
                messagebox.showinfo(
                    "一括処理完了",
                    f"保存: {saved} 件\n出力先:\n{output_dir}",
                )

            self.status_label.config(
                text=f"一括処理完了: 保存 {saved} 件 / 失敗 {len(errors)} 件"
            )
            if selected_before:
                self.selected_batch_path = selected_before
                self.apply_settings(self.settings_for_batch_path(selected_before))
            else:
                self.apply_settings(base_settings)
            self.update_batch_info()
            self.schedule_preview_update(delay_ms=80)

        except Exception as e:
            messagebox.showerror("一括処理エラー", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
