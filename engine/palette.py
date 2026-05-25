"""254色マスターパレットの読み込み・生成、およびシーン単位パレットの構築。

assets/images/MasterColor.png を元に MasterColor.pyxpal を生成・キャッシュし、
pyxel.load_pal() で画面パレット (pyxel.colors[0..255]) に適用する。

レイアウト:
  - インデックス 0-15: エディタ UI 用に予約 (_RESERVED_UI_PALETTE)
                       ui/colors.py の BG/PANEL/.../CHOICE_HOVER と対応する
  - インデックス 16-255: MasterColor.png から抽出した一意な色 (先着順)

PNG が更新されると mtime を比較して .pyxpal を自動再生成する。

シーン単位パレット (build_scene_palette):
  プレイ時に「そのシーンに登場する画像 (BG + キャラ最大3)」から最適化された
  256色パレットを動的構築する。0-15 と settings.json で参照されている
  全インデックス (PLAY_*, speaker_colors) はマスターパレットの値で固定し、
  残りスロットを画像の頻出色で埋めることで色破綻を抑える。
"""
from __future__ import annotations

import os
import threading
import unicodedata
import pyxel

try:
    import numpy as np
    if not all(hasattr(np, name) for name in ("zeros", "asarray", "uint8")):
        raise ImportError("incomplete numpy module")
except Exception:
    from engine import mini_numpy as np

try:
    from PIL import Image
except ImportError:
    Image = None

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER_PNG    = os.path.join(_ROOT, "assets", "images", "MasterColor.png")
MASTER_PYXPAL = os.path.join(_ROOT, "assets", "images", "MasterColor.pyxpal")

# インデックス 0-15 はエディタ UI 用に予約 (ui/colors.py のデフォルト役割と対応)
_RESERVED_UI_PALETTE = [
    "1E1E1E", "2D2D30", "3A3D41", "1E1E1E",
    "1E1E1E", "555555", "999999", "D4D4D4",
    "4A4F55", "007ACC", "FFEC27", "FFFFFF",
    "5A8836", "1B1B1C", "3A3D41", "4A4F55",
]

_master_palette: "np.ndarray | None" = None


def _existing_path_variant(path: str) -> "str | None":
    """Return an existing NFC/NFD spelling for a filesystem path."""
    if not path:
        return None
    if os.path.exists(path):
        return path
    candidates: list[str] = []
    for form in ("NFC", "NFD"):
        try:
            candidates.append(unicodedata.normalize(form, path))
        except Exception:
            pass
    for candidate in candidates:
        if candidate != path and os.path.exists(candidate):
            return candidate
    return None


def _hex_to_rgb(h: str) -> tuple:
    v = int(h, 16)
    return ((v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF)


def _write_pyxpal(colors: list, path: str = MASTER_PYXPAL):
    """常に 256 行書き出す (不足分は黒で埋める)。pyxel.colors[256] の不変性を保つため。"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    padded = list(colors[:256])
    if len(padded) < 256:
        padded.extend([(0, 0, 0)] * (256 - len(padded)))
    with open(path, "w") as f:
        for r, g, b in padded:
            f.write(f"{r:02x}{g:02x}{b:02x}\n")


def ensure_pyxpal(force: bool = False):
    """MasterColor.pyxpal を用意する。優先順位:

    1. MasterColor.pyxpal が存在する → そのまま利用 (PNG の有無に関わらず)。
       ただし PNG が存在し、かつ pyxpal より新しい場合は PNG から再生成。
    2. pyxpal が無く PNG がある → PNG から生成。
    3. pyxpal も PNG も無い → 予約 UI パレット (16色) + 黒埋めで .pyxpal を新規作成。
    """
    if not os.path.exists(MASTER_PYXPAL):
        if not os.path.exists(MASTER_PNG):
            print(f"[palette] {MASTER_PYXPAL} not found — writing default palette")
            _write_pyxpal([_hex_to_rgb(h) for h in _RESERVED_UI_PALETTE])
            return
        # pyxpal は無いが PNG があるので生成へ進む
    else:
        # pyxpal があり PNG が無ければ何もせず利用
        if not os.path.exists(MASTER_PNG):
            return
        # 両方ある: mtime 比較でキャッシュ判定
        if (not force
                and os.path.getmtime(MASTER_PYXPAL)
                    >= os.path.getmtime(MASTER_PNG)):
            return  # キャッシュ有効

    if Image is None:
        if not os.path.exists(MASTER_PYXPAL):
            _write_pyxpal([_hex_to_rgb(h) for h in _RESERVED_UI_PALETTE])
        return

    colors = [_hex_to_rgb(h) for h in _RESERVED_UI_PALETTE]
    seen = set(colors)
    with Image.open(MASTER_PNG) as img:
        for rgb in img.convert("RGB").getdata():
            if rgb in seen:
                continue
            seen.add(rgb)
            colors.append(rgb)
            if len(colors) >= 256:
                break
    _write_pyxpal(colors)
    print(f"[palette] generated {MASTER_PYXPAL} ({len(colors)} colors)")


def load() -> np.ndarray:
    """MasterColor.pyxpal を pyxel.colors[] に適用し、numpy 配列を返す。

    pyxel.init() の後に1度だけ呼ぶ。返り値はクオンタイズ用 (256, 3) uint8。
    pyxpal の長さが 256 未満なら不足分を黒で埋め、pyxel.colors[] にも追加する。
    """
    global _master_palette
    ensure_pyxpal()
    pyxel.load_pal(MASTER_PYXPAL)
    n = len(pyxel.colors)
    if n < 256:
        for _ in range(256 - n):
            pyxel.colors.append(0)
    arr = np.zeros((256, 3), dtype=np.uint8)
    for i in range(256):
        rgb = pyxel.colors[i]
        arr[i, 0] = (rgb >> 16) & 0xFF
        arr[i, 1] = (rgb >> 8) & 0xFF
        arr[i, 2] = rgb & 0xFF
    _master_palette = arr
    return arr


def load_array_only() -> np.ndarray:
    """Load MasterColor.pyxpal into memory without touching pyxel.colors.

    Export/build tasks may run outside a live Pyxel app. In that context
    pyxel.load_pal() panics because pyxel.init() has not been called, but we
    still need the master palette as a numpy array for reserved colors and
    prebuilt image manifests.
    """
    global _master_palette
    ensure_pyxpal()
    arr = np.zeros((256, 3), dtype=np.uint8)
    try:
        with open(MASTER_PYXPAL, encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        for i, line in enumerate(lines[:256]):
            v = int(line.lstrip("#"), 16)
            arr[i, 0] = (v >> 16) & 0xFF
            arr[i, 1] = (v >> 8) & 0xFF
            arr[i, 2] = v & 0xFF
    except Exception:
        # Last-ditch fallback mirrors the reserved UI colors and leaves the
        # remaining slots black.
        for i, h in enumerate(_RESERVED_UI_PALETTE[:256]):
            arr[i] = _hex_to_rgb(h)
    _master_palette = arr
    return arr


def as_array() -> "np.ndarray | None":
    """直前に load() で読み込んだマスターパレット (256, 3) を返す。

    main.py 起動後ならば常に non-None。
    """
    return _master_palette


# ── シーンパレット構築 ──────────────────────────────────────────────

# (reserved_key, file_key) → (256, 3) np.ndarray
_scene_palette_cache: dict = {}
_scene_palette_lock = threading.Lock()


def _load_rgb_for_palette(abs_path: str, transparent_fill: tuple,
                          max_size: int = 256) -> "Image.Image | None":
    """画像を RGB に正規化して読み込む (パレット抽出専用)。

    透明領域は `transparent_fill` (= reserved index 0 RGB) でコンポジットする。
    こうすることで Adaptive Palette は透明領域を「reserved 0 と同じ色」として
    扱い、抽出色集合と重複検出で弾かれる。残りの free スロットを真の画像色に
    使えるので色解像度が無駄にならない。

    速度のため最大辺 max_size に縮小する。
    """
    resolved = _existing_path_variant(abs_path)
    if not resolved:
        return None
    if Image is None:
        return None
    try:
        with Image.open(resolved) as im:
            if "A" in im.getbands():
                rgba = im.convert("RGBA")
                bg = Image.new("RGB", rgba.size, transparent_fill)
                bg.paste(rgba, mask=rgba.split()[3])
                rgb = bg
            else:
                rgb = im.convert("RGB")
            w, h = rgb.size
            if max(w, h) > max_size:
                scale = max_size / max(w, h)
                rgb = rgb.resize((max(1, int(w * scale)),
                                  max(1, int(h * scale))), Image.LANCZOS)
            return rgb
    except Exception:
        return None


def _adaptive_palette_from_images(abs_paths: list, target_colors: int,
                                  transparent_fill: tuple) -> list:
    """複数画像を1枚に縦結合し、Pillow Adaptive Palette (Median Cut 系) で
    `target_colors` 個の代表色を抽出して `[(r,g,b), ...]` で返す。

    画像ごとの頻度をそのまま使うと「肌グラデーションの中間色」など微妙に
    違う多数の色が頻度上位を占め、希少だが鮮やかな差し色が落ちる。
    Median Cut なら RGB 立方体を再帰分割して色域を広くカバーする代表色を
    返すので、VN 系 (アンチエイリアス強い・グラデ多用) の絵に向く。
    """
    tiles = []
    if Image is None:
        return []
    for ap in abs_paths:
        rgb = _load_rgb_for_palette(ap, transparent_fill)
        if rgb is not None:
            tiles.append(rgb)
    if not tiles:
        return []
    total_w = max(t.width for t in tiles)
    total_h = sum(t.height for t in tiles)
    canvas = Image.new("RGB", (total_w, total_h), transparent_fill)
    y = 0
    for t in tiles:
        canvas.paste(t, ((total_w - t.width) // 2, y))
        y += t.height
    n = max(1, min(256, int(target_colors)))
    paletted = canvas.convert(
        "P",
        palette=Image.Palette.ADAPTIVE,
        colors=n,
        dither=Image.Dither.NONE,
    )
    raw = paletted.getpalette() or []
    out: list = []
    seen: set = set()
    # Pillow は palette を 768 entry にパディングするので、有効範囲は n*3 まで
    for i in range(n):
        if i * 3 + 2 >= len(raw):
            break
        rgb = (raw[i * 3], raw[i * 3 + 1], raw[i * 3 + 2])
        if rgb in seen:
            continue
        seen.add(rgb)
        out.append(rgb)
    return out


def reserved_from_settings(settings: dict | None) -> dict:
    """マスターパレット上で「シーンパレットでも保持すべき」インデックス集合を
    {index: (r,g,b)} で返す。

    内訳:
      1. 0-15 (UI 役割の安全領域) は常に MasterColor の値で固定
      2. settings.json["dialog_role_indices"] で参照されている全 index
         (例: PLAY_TEXT=50, PLAY_SPEAKER_FG=214 …)
      3. settings.json["speaker_colors"] で参照されている全 index
         (narration_text_color, 各 speaker の name/name_bg/text_color)

    マスターパレット未ロード時は空 dict (load() 後に呼ぶこと)。
    """
    if _master_palette is None:
        return {}
    pal = _master_palette
    reserved: dict = {}

    def _put(idx):
        if isinstance(idx, int) and 0 <= idx <= 255:
            reserved[idx] = (int(pal[idx, 0]), int(pal[idx, 1]), int(pal[idx, 2]))

    for i in range(16):
        _put(i)
    if not isinstance(settings, dict):
        return reserved
    role = settings.get("dialog_role_indices") or {}
    if isinstance(role, dict):
        for v in role.values():
            _put(v)
    sc = settings.get("speaker_colors") or {}
    if isinstance(sc, dict):
        _put(sc.get("narration_text_color"))
        speakers = sc.get("speakers") or {}
        if isinstance(speakers, dict):
            for entry in speakers.values():
                if not isinstance(entry, dict):
                    continue
                for k in ("name_color", "name_bg_color", "text_color"):
                    _put(entry.get(k))
    return reserved


def build_scene_palette(image_paths: list, reserved: dict,
                        base_dir: str = ".") -> np.ndarray:
    """シーン用の (256, 3) uint8 パレットを構築する。

    Parameters
    ----------
    image_paths : シーンで使う画像パスのリスト (BG + キャラ立ち絵 + 顔差分等)。
                  相対パスは base_dir 起点で解決する。空文字や存在しないパスは無視。
    reserved    : `reserved_from_settings()` の戻り値。
                  これらの index は必ず指定 RGB のまま保持される。
    base_dir    : 相対パス解決の基準。

    アルゴリズム:
      1. 全画像を縮小・縦結合して 1 枚のキャンバスにする (BG/キャラの色比率を均す)
      2. Pillow Adaptive Palette (Median Cut 系) で free slot 数 + α の代表色を抽出
      3. reserved の RGB と重複する色は除外
      4. 残りを free slots (reserved 以外) に詰める。余りは (0,0,0)

    透明領域は reserved index 0 の RGB でコンポジットする。これにより
    Adaptive 抽出で「透明領域色」が独自スロットを取らず、reserved とまとめて
    1 スロット扱いになるので free slot を画像の真の色に多く割り当てられる。
    """
    file_keys = []
    for p in image_paths:
        if not p:
            continue
        ap = p if os.path.isabs(p) else os.path.join(base_dir, p)
        resolved = _existing_path_variant(ap)
        if not resolved:
            continue
        try:
            mtime = os.path.getmtime(resolved)
        except OSError:
            mtime = 0
        file_keys.append((resolved, mtime))
    file_keys.sort()
    res_key = tuple(sorted(reserved.items()))
    cache_key = (res_key, tuple(file_keys))
    with _scene_palette_lock:
        cached = _scene_palette_cache.get(cache_key)
        if cached is not None:
            return cached

    free_slots = [i for i in range(256) if i not in reserved]
    target = len(free_slots)
    transparent_fill = reserved.get(0, (0, 0, 0))

    # reserved との重複で何色か削られることを見越して多めに抽出
    extract_n = min(256, target + max(16, len(reserved)))
    abs_paths = [ap for ap, _ in file_keys]
    candidates = _adaptive_palette_from_images(
        abs_paths, extract_n, transparent_fill)

    reserved_rgbs = set(reserved.values())
    picked: list = []
    for rgb in candidates:
        if rgb in reserved_rgbs:
            continue
        picked.append(rgb)
        if len(picked) >= target:
            break

    out = np.zeros((256, 3), dtype=np.uint8)
    for i, rgb in reserved.items():
        out[i] = rgb
    for slot, rgb in zip(free_slots, picked):
        out[slot] = rgb

    with _scene_palette_lock:
        _scene_palette_cache[cache_key] = out
    return out


def apply_to_pyxel_colors(pal: np.ndarray) -> None:
    """(256, 3) uint8 パレットを pyxel.colors[0..255] に書き込む。"""
    arr = np.asarray(pal, dtype=np.uint8)
    n = len(pyxel.colors)
    if n < 256:
        for _ in range(256 - n):
            pyxel.colors.append(0)
    for i in range(min(256, len(arr))):
        r, g, b = int(arr[i, 0]), int(arr[i, 1]), int(arr[i, 2])
        pyxel.colors[i] = (r << 16) | (g << 8) | b


def snapshot_pyxel_colors() -> np.ndarray:
    """現在の pyxel.colors[0..255] をスナップショットして (256, 3) uint8 で返す。

    ImageCache の量子化基準として登録するときに使う。マスターパレット
    読込み直後に呼べば、量子化は実際の画面色との最近傍マッチになる。
    """
    arr = np.zeros((256, 3), dtype=np.uint8)
    n = min(256, len(pyxel.colors))
    for i in range(n):
        rgb = pyxel.colors[i]
        arr[i, 0] = (rgb >> 16) & 0xFF
        arr[i, 1] = (rgb >> 8) & 0xFF
        arr[i, 2] = rgb & 0xFF
    return arr
