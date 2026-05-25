"""
画像キャッシュ: PNG → Pyxelパレット16色 numpy配列 → pyxel.Image

変換フロー:
  1. Pillowで画像をロード・リサイズ
  2. 指定パレット（省略時は現在の pyxel.colors[]）に最近傍量子化
  3. numpy uint8配列（パレットインデックス）をディスクキャッシュ(.npy)
  4. pyxel.Image オブジェクトを生成して返す（メモリキャッシュ）

カスタムパレット対応:
  get() の palette 引数に shape (16, 3) の uint8 RGB 配列を渡すと
  そのパレットで量子化する。省略時は pyxel.colors[] をその都度参照する。
  パレットハッシュがキャッシュキーに含まれるため、パレット変更後に
  同じ画像を要求すると自動的に再変換される。
"""
from __future__ import annotations

import os
import json
import ctypes
import hashlib
import io
import posixpath
import sys
import time
import unicodedata
import pyxel

try:
    import numpy as np
    if not all(hasattr(np, name) for name in (
        "array", "asarray", "load", "save", "uint8", "zeros",
    )):
        raise ImportError("incomplete numpy module")
except Exception:
    from engine import mini_numpy as np

try:
    from PIL import Image
except ImportError:
    Image = None

COLOR_KEY_AUTO = -2
COLOR_KEY_NONE = -1

_SLOW_IMAGE_LOAD_MS = 120.0
_last_fetch_method = "-"


def _existing_path_variant(path: str) -> "str | None":
    """Return an existing Unicode-normalized variant of path if needed.

    Project files authored on macOS may contain decomposed Japanese path
    components. Windows checkouts or zip extraction can surface the same names
    as precomposed Unicode, so try both common forms before treating an image as
    missing.
    """
    if not path:
        return None
    path = str(path)
    if os.path.exists(path):
        return path
    for form in ("NFC", "NFD"):
        try:
            candidate = unicodedata.normalize(form, path)
        except Exception:
            continue
        if candidate != path and os.path.exists(candidate):
            return candidate
    return None


def normalize_asset_key_path(path: str) -> str:
    """Return a stable NFC, slash-separated asset identity for manifests."""
    text = str(path or "").replace("\\", "/")
    text = posixpath.normpath(text)
    if text == ".":
        text = ""
    while text.startswith("./"):
        text = text[2:]
    return unicodedata.normalize("NFC", text)


_text_to_uint8_fn = None
_prefetch_bridge_ready = False
_PREFETCH_MAX_ENTRIES = 6
_WEB_ASYNC_PREFETCH_DEFAULT = False


def _web_debug_log(kind: str, message: str) -> None:
    """Mirror lightweight image-cache diagnostics to the Web debug log."""
    if sys.platform != "emscripten":
        return
    try:
        from js import window  # type: ignore

        add = getattr(getattr(window, "PVNM_DEBUG_LOG", None), "add", None)
        if callable(add):
            add(kind, str(message))
    except Exception:
        pass


def _web_async_prefetch_enabled() -> bool:
    """Return whether experimental JS-side image prefetch is enabled.

    Background fetch can race with the synchronous Pyxel image load on some
    Android WebViews. Keep the bridge available for future diagnostics, but
    default it off so actual scene rendering remains deterministic.
    """
    if sys.platform != "emscripten":
        return False
    try:
        from js import window  # type: ignore

        value = getattr(window, "PVNM_ENABLE_IMAGE_PREFETCH", None)
        if value is not None:
            return bool(value)
    except Exception:
        pass
    return _WEB_ASYNC_PREFETCH_DEFAULT


def _ensure_prefetch_bridge():
    """Install a tiny JS async prefetch queue for Web/Android image caches."""
    global _prefetch_bridge_ready
    if sys.platform != "emscripten":
        return None
    try:
        from js import Function, window  # type: ignore

        api = getattr(window, "PVNM_IMAGE_PREFETCH", None)
        if api is not None:
            _prefetch_bridge_ready = True
            return api
        installer = Function.new(
            "maxEntriesArg",
            """
            if (window.PVNM_IMAGE_PREFETCH) {
              return window.PVNM_IMAGE_PREFETCH;
            }
            let order = [];
            const records = new Map();
            let active = 0;
            const maxInFlight = 1;
            const entryLimit = Math.max(1, Number(maxEntriesArg) || 6);
            function log(kind, msg) {
              try {
                if (window.PVNM_DEBUG_LOG && window.PVNM_DEBUG_LOG.add) {
                  window.PVNM_DEBUG_LOG.add(kind, String(msg));
                }
              } catch (_e) {}
            }
            function compact() {
              const fresh = [];
              for (const url of order) {
                if (records.has(url)) fresh.push(url);
              }
              order = fresh;
            }
            function trim() {
              compact();
              while (records.size > entryLimit) {
                let removed = false;
                for (const url of order.slice()) {
                  const rec = records.get(url);
                  if (!rec) continue;
                  if (rec.state === "ready" || rec.state === "error") {
                    records.delete(url);
                    removed = true;
                    break;
                  }
                }
                if (!removed) break;
                compact();
              }
            }
            function pump() {
              if (active >= maxInFlight) return;
              let nextUrl = "";
              for (const url of order) {
                const rec = records.get(url);
                if (rec && rec.state === "queued") {
                  nextUrl = url;
                  break;
                }
              }
              if (!nextUrl) return;
              const rec = records.get(nextUrl);
              if (!rec) return;
              rec.state = "pending";
              rec.started = performance.now();
              active += 1;
              fetch(nextUrl, { cache: "force-cache", credentials: "same-origin" })
                .then((response) => {
                  rec.status = response.status || 0;
                  if (!response.ok) {
                    throw new Error(`HTTP ${response.status || 0}`);
                  }
                  return response.arrayBuffer();
                })
                .then((buffer) => {
                  rec.bytes = new Uint8Array(buffer);
                  rec.byteLength = rec.bytes.length;
                  rec.state = "ready";
                  rec.done = performance.now();
                  log(
                    "image.prefetch.ready",
                    `${nextUrl} (${rec.byteLength} bytes, ${(rec.done - rec.started).toFixed(1)}ms)`
                  );
                })
                .catch((err) => {
                  rec.state = "error";
                  rec.error = String(err && err.message ? err.message : err);
                  rec.done = performance.now();
                  log("image.prefetch.error", `${nextUrl} ${rec.error}`);
                })
                .finally(() => {
                  active = Math.max(0, active - 1);
                  trim();
                  pump();
                });
            }
            window.PVNM_IMAGE_PREFETCH = {
              prefetch(url) {
                url = String(url || "");
                if (!url) return "empty";
                const existing = records.get(url);
                if (existing) return existing.state;
                records.set(url, {
                  state: "queued",
                  bytes: null,
                  error: "",
                  byteLength: 0,
                  started: 0,
                  done: 0,
                  status: 0,
                });
                order.push(url);
                log("image.prefetch.queue", url);
                trim();
                pump();
                return "queued";
              },
              take(url) {
                url = String(url || "");
                const rec = records.get(url);
                if (!rec || rec.state !== "ready" || !rec.bytes) return null;
                const bytes = rec.bytes;
                records.delete(url);
                compact();
                return bytes;
              },
              status(url) {
                url = String(url || "");
                const rec = records.get(url);
                return rec ? rec.state : "miss";
              },
              stats() {
                let queued = 0, pending = 0, ready = 0, error = 0, bytes = 0;
                for (const rec of records.values()) {
                  if (rec.state === "queued") queued += 1;
                  else if (rec.state === "pending") pending += 1;
                  else if (rec.state === "ready") {
                    ready += 1;
                    bytes += rec.byteLength || 0;
                  } else if (rec.state === "error") error += 1;
                }
                return { queued, pending, ready, error, bytes, active };
              },
              clear() {
                records.clear();
                order = [];
                active = 0;
              },
            };
            return window.PVNM_IMAGE_PREFETCH;
            """,
        )
        api = installer(_PREFETCH_MAX_ENTRIES)
        _prefetch_bridge_ready = True
        return api
    except Exception as e:
        if not _prefetch_bridge_ready:
            print(f"[ImageCache] JS prefetch bridge unavailable: {e}")
        return None


def _prefetch_binary_async(url: str) -> bool:
    if sys.platform != "emscripten" or not url:
        return False
    if not _web_async_prefetch_enabled():
        return False
    api = _ensure_prefetch_bridge()
    if api is None:
        return False
    try:
        state = str(api.prefetch(str(url)))
        _web_debug_log("image.prefetch", f"{url} state={state}")
        return state in ("queued", "pending", "ready")
    except Exception as e:
        print(f"[ImageCache] JS prefetch failed ({url}): {e}")
        return False


def _take_prefetched_binary(url: str) -> "tuple[bytes, str] | None":
    if sys.platform != "emscripten" or not url:
        return None
    if not _web_async_prefetch_enabled():
        return None
    api = _ensure_prefetch_bridge()
    if api is None:
        return None
    try:
        view = api.take(str(url))
        if view is None:
            return None
        data, method = _uint8_array_to_bytes(view)
        return data, "prefetch/" + method
    except Exception:
        return None


def normalize_color_key(value, default: int = COLOR_KEY_AUTO) -> int:
    """Normalize a character COLOR KEY value.

    -2 / "auto" = derive a safe colkey from PNG alpha
    -1 / "none" = no transparent color
    0..255      = explicit Pyxel palette index
    """
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("auto", "a", ""):
            return COLOR_KEY_AUTO
        if s in ("none", "off", "no", "-1"):
            return COLOR_KEY_NONE
        try:
            value = int(s)
        except Exception:
            return default
    try:
        n = int(value)
    except Exception:
        return default
    if n <= COLOR_KEY_AUTO:
        return COLOR_KEY_AUTO
    if n == COLOR_KEY_NONE:
        return COLOR_KEY_NONE
    return max(0, min(255, n))


def color_key_label(value) -> str:
    n = normalize_color_key(value)
    if n == COLOR_KEY_AUTO:
        return "AUTO"
    if n == COLOR_KEY_NONE:
        return "NONE"
    return str(n)


# ── パレットユーティリティ ────────────────────────────────────────


def _build_palette() -> np.ndarray:
    """現在の pyxel.colors から shape (256, 3) uint8 RGB 配列を返す"""
    pal = np.zeros((256, 3), dtype=np.uint8)
    for i in range(256):
        rgb = pyxel.colors[i]
        pal[i, 0] = (rgb >> 16) & 0xFF
        pal[i, 1] = (rgb >> 8) & 0xFF
        pal[i, 2] = rgb & 0xFF
    return pal


# モジュールレベルのデフォルトパレット (= マスターパレット)。
# main.py 起動時に set_default_palette() で登録される。
# これがセットされていれば pyxel.colors[] を毎回スキャンせず、
# 一定の参照パレットでクオンタイズするのでキャッシュ命中率が高い。
_default_palette: "np.ndarray | None" = None


def set_default_palette(palette: "np.ndarray | None"):
    """ImageCache.get(palette=None) 時に使われるデフォルトパレットを登録する。"""
    global _default_palette
    _default_palette = (None if palette is None
                        else np.asarray(palette, dtype=np.uint8))


def _palette_hash(palette: np.ndarray) -> str:
    """パレット配列の短いハッシュ文字列を返す（キャッシュ識別用）"""
    return hashlib.md5(
        np.asarray(palette, dtype=np.uint8).tobytes()
    ).hexdigest()[:8]


def palette_hash(palette: np.ndarray) -> str:
    """Public wrapper used by export/manifest code."""
    return _palette_hash(palette)


def _allowed_indices_hash(allowed_indices: "set[int] | list[int] | tuple[int, ...] | None") -> str:
    if not allowed_indices:
        return ""
    clean = sorted({
        int(idx) for idx in allowed_indices
        if isinstance(idx, int) and 0 <= int(idx) <= 255
    })
    if not clean or len(clean) >= 256:
        return ""
    payload = ",".join(str(idx) for idx in clean)
    return hashlib.md5(payload.encode("ascii")).hexdigest()[:6]


def palette_cache_hash(palette: np.ndarray,
                       allowed_indices: "set[int] | list[int] | tuple[int, ...] | None" = None) -> str:
    """Return the cache identity for a palette plus optional allowed indices."""
    base = _palette_hash(palette)
    allowed_hash = _allowed_indices_hash(allowed_indices)
    return base if not allowed_hash else f"{base}a{allowed_hash}"


def image_cache_hash(palette: np.ndarray,
                     allowed_indices: "set[int] | list[int] | tuple[int, ...] | None" = None,
                     alpha_colkey: bool = False) -> str:
    """Return the full image-cache identity for palette/options."""
    ph = palette_cache_hash(palette, allowed_indices)
    return f"{ph}t" if alpha_colkey else ph


def manifest_palette_key(path_keys: list, reserved: dict) -> str:
    """Return a portable key for a prebuilt scene/image palette.

    The runtime cannot rebuild scene palettes when original PNG/JPG files are
    absent, so export stores palettes keyed by the participating image identities
    plus the reserved UI/speaker colors.
    """
    norm_paths = sorted({normalize_asset_key_path(p) for p in path_keys if p})
    res = []
    for idx, rgb in sorted((reserved or {}).items()):
        try:
            res.append([int(idx), [int(rgb[0]), int(rgb[1]), int(rgb[2])]])
        except Exception:
            continue
    payload = json.dumps(
        {"paths": norm_paths, "reserved": res},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return hashlib.md5(payload.encode("utf-8")).hexdigest()[:12]


def palette_from_hex(hex_list: list) -> np.ndarray:
    """
    "#RRGGBB" 文字列リストから shape (16, 3) uint8 パレット配列を作成する。

    settings.json やファイルから読み込んだ Hex リストを
    ImageCache.get() の palette 引数に渡す形式に変換するヘルパー。

    Parameters
    ----------
    hex_list : 最大16要素の "#RRGGBB" 文字列リスト（不足分はゼロ埋め）
    """
    pal = np.zeros((16, 3), dtype=np.uint8)
    for i, h in enumerate(hex_list[:16]):
        try:
            v = int(h.lstrip("#"), 16)
            pal[i, 0] = (v >> 16) & 0xFF
            pal[i, 1] = (v >> 8) & 0xFF
            pal[i, 2] = v & 0xFF
        except (ValueError, TypeError):
            pass
    return pal


# ── 量子化 ───────────────────────────────────────────────────────


def _quantize(img_rgb: Image.Image, palette: np.ndarray,
              allowed_indices: "set[int] | None" = None) -> np.ndarray:
    """RGB PIL画像 → uint8 palette インデックス配列 (H×W)。

    Pillow の C 実装 quantize() (K-D tree) で固定パレットへ最近傍マップする。
    純 numpy 実装より 1000 倍以上速い (720x480 で 2s → 1ms)。
    視覚品質: 色誤差は K-D tree 近似のため極わずかに増えるが、隣接した同等
    近傍色との置換に留まり人間には認識不能 (256 階調空間で <2 程度の差)。
    """
    if Image is None:
        return None
    pal_image = Image.new("P", (1, 1))
    flat = []
    for i in range(min(256, len(palette))):
        flat.append(int(palette[i, 0]))
        flat.append(int(palette[i, 1]))
        flat.append(int(palette[i, 2]))
    # Pillow は putpalette に 768 要素 (= 256 色 × 3) を期待するので不足分は黒で埋める
    while len(flat) < 256 * 3:
        flat.append(0)
    pal_image.putpalette(flat)
    quantized = img_rgb.quantize(palette=pal_image, dither=Image.Dither.NONE)
    arr = np.array(quantized, dtype=np.uint8)
    if allowed_indices:
        _remap_disallowed_indices(arr, img_rgb, palette, allowed_indices)
    return arr


def _remap_disallowed_indices(arr, img_rgb: Image.Image, palette: np.ndarray,
                              allowed_indices: set[int]) -> None:
    """Move pixels from reserved palette indices to the nearest allowed color."""
    allowed = sorted({
        int(idx) for idx in allowed_indices
        if isinstance(idx, int) and 0 <= int(idx) < len(palette)
    })
    if not allowed or len(allowed) >= 256:
        return
    allowed_set = set(allowed)
    try:
        w, h = img_rgb.size
        pix = img_rgb.load()
    except Exception:
        return
    nearest_cache: dict[tuple[int, int, int], int] = {}
    for y in range(h):
        for x in range(w):
            try:
                idx = int(arr[y, x])
            except Exception:
                continue
            if idx in allowed_set:
                continue
            try:
                rgb = pix[x, y]
                if not isinstance(rgb, tuple):
                    continue
                key = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
            except Exception:
                continue
            mapped = nearest_cache.get(key)
            if mapped is None:
                mapped = _nearest_allowed_index(key, palette, allowed)
                nearest_cache[key] = mapped
            try:
                arr[y, x] = mapped
            except Exception:
                pass


def _nearest_allowed_index(rgb: tuple[int, int, int],
                           palette: np.ndarray, allowed: list[int]) -> int:
    best_idx = allowed[0]
    best_d = 1 << 62
    r, g, b = rgb
    for idx in allowed:
        pr = int(palette[idx, 0])
        pg = int(palette[idx, 1])
        pb = int(palette[idx, 2])
        d = (r - pr) * (r - pr) + (g - pg) * (g - pg) + (b - pb) * (b - pb)
        if d < best_d:
            best_d = d
            best_idx = idx
    return best_idx


def _has_transparent_alpha(alpha_img: Image.Image) -> bool:
    try:
        return alpha_img.getextrema()[0] < 128
    except Exception:
        return False


def _apply_alpha_colkey(arr: np.ndarray, alpha_img: Image.Image,
                        img_rgb: Image.Image, palette: np.ndarray) -> "int | None":
    """Reserve one palette index for transparent pixels in arr.

    Opaque pixels are guaranteed not to use the selected colkey. This lets
    Pyxel's colkey rendering reproduce PNG alpha without the user choosing an
    index manually.
    """
    alpha = alpha_img.convert("L")
    if not _has_transparent_alpha(alpha):
        return None
    w, h = alpha.size
    alpha_bytes = alpha.tobytes()
    used = [False] * 256
    for y in range(h):
        row_base = y * w
        for x in range(w):
            if alpha_bytes[row_base + x] >= 128:
                try:
                    used[int(arr[y, x]) & 0xFF] = True
                except Exception:
                    pass

    chosen = None
    for idx in range(256):
        if not used[idx]:
            chosen = idx
            break
    if chosen is None:
        chosen = 0
        _remap_opaque_colkey_conflicts(arr, alpha_bytes, w, h, img_rgb,
                                       palette, chosen)

    for y in range(h):
        row_base = y * w
        for x in range(w):
            if alpha_bytes[row_base + x] < 128:
                arr[y, x] = chosen
    return int(chosen)


def _remap_opaque_colkey_conflicts(arr: np.ndarray, alpha_bytes: bytes,
                                   w: int, h: int, img_rgb: Image.Image,
                                   palette: np.ndarray, chosen: int) -> None:
    allowed = [idx for idx in range(min(256, len(palette))) if idx != chosen]
    if not allowed:
        return
    pix = img_rgb.load()
    cache: dict[tuple[int, int, int], int] = {}
    for y in range(h):
        row_base = y * w
        for x in range(w):
            if alpha_bytes[row_base + x] < 128:
                continue
            try:
                if int(arr[y, x]) != chosen:
                    continue
                rgb = pix[x, y]
                key = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
            except Exception:
                continue
            mapped = cache.get(key)
            if mapped is None:
                mapped = _nearest_allowed_index(key, palette, allowed)
                cache[key] = mapped
            arr[y, x] = mapped


def _fill_pyxel_image(pyx_img: pyxel.Image, arr: np.ndarray):
    """uint8 numpy配列をpyxel.Imageに直接書き込む"""
    flat = np.ascontiguousarray(arr).tobytes()
    ctypes.memmove(pyx_img.data_ptr(), flat, len(flat))


def _load_npy_bytes(data: bytes):
    """Load a uint8 .npy payload from bytes with NumPy or mini_numpy."""
    try:
        return np.load(io.BytesIO(data))
    except Exception:
        load_bytes = getattr(np, "load_bytes", None)
        if callable(load_bytes):
            return load_bytes(data)
        raise


def _uint8_array_to_bytes(view):
    """Convert a JS Uint8Array to Python bytes with a fast path."""
    try:
        return bytes(view.to_py()), "to_py"
    except Exception:
        length = int(getattr(view, "length", 0) or 0)
        return bytes(int(view[i]) & 0xFF for i in range(length)), "py_loop"


def _xhr_bytes_from_arraybuffer(url: str):
    """Fetch binary data with XHR arraybuffer when the WebView supports it."""
    from js import Uint8Array, XMLHttpRequest  # type: ignore

    xhr = XMLHttpRequest.new()
    xhr.open("GET", str(url), False)
    xhr.responseType = "arraybuffer"
    xhr.send()
    status = int(getattr(xhr, "status", 0) or 0)
    if status and not (200 <= status < 300):
        return None, status
    response = getattr(xhr, "response", None)
    if response is None:
        return None, status
    view = Uint8Array.new(response)
    data, method = _uint8_array_to_bytes(view)
    return data, status, "arraybuffer/" + method


def _xhr_bytes_from_text(url: str):
    """Compatibility path for WebViews that reject sync arraybuffer XHR."""
    global _text_to_uint8_fn
    from js import XMLHttpRequest  # type: ignore

    xhr = XMLHttpRequest.new()
    xhr.open("GET", str(url), False)
    try:
        xhr.overrideMimeType("text/plain; charset=x-user-defined")
    except Exception:
        pass
    xhr.send()
    status = int(getattr(xhr, "status", 0) or 0)
    if status and not (200 <= status < 300):
        return None, status
    text = str(getattr(xhr, "responseText", "") or "")
    try:
        # Some WebViews map x-user-defined bytes directly to U+0000..U+00FF.
        return text.encode("latin-1"), status, "text/latin1"
    except Exception:
        pass
    try:
        # Other WebViews map bytes to a private-use range. Convert in JS so
        # Python does not spend ~1s looping over a 720x480 cache string.
        from js import Function  # type: ignore

        if _text_to_uint8_fn is None:
            _text_to_uint8_fn = Function.new(
                "text",
                "const out = new Uint8Array(text.length);"
                "for (let i = 0; i < text.length; i++) {"
                "  out[i] = text.charCodeAt(i) & 255;"
                "}"
                "return out;",
            )
        view = _text_to_uint8_fn(text)
        data, method = _uint8_array_to_bytes(view)
        return data, status, "text/js_" + method
    except Exception:
        return bytes((ord(ch) & 0xFF) for ch in text), status, "text/py_loop"


def _set_last_fetch_method(method: str) -> None:
    global _last_fetch_method
    _last_fetch_method = method


def _fetch_binary_sync(url: str) -> "bytes | None":
    """Synchronously fetch a same-origin binary asset in Pyodide/Web.

    Pyxel's draw/update path is synchronous, so image cache misses need a small
    blocking read. The files are local Capacitor/WebView assets, not network
    downloads.
    """
    if sys.platform != "emscripten" or not url:
        return None
    t0 = time.perf_counter()
    method = "arraybuffer"
    try:
        prefetched = _take_prefetched_binary(url)
        if prefetched is not None:
            data, method = prefetched
            _set_last_fetch_method(method)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            _web_debug_log(
                "image.loaded",
                f"{url} ({len(data)} bytes, {elapsed_ms:.1f}ms, {method})",
            )
            return data
        _web_debug_log("image.fetch", str(url))
        try:
            data, status, method = _xhr_bytes_from_arraybuffer(url)
        except Exception:
            data, status, method = _xhr_bytes_from_text(url)
        _set_last_fetch_method(method)
        if status and not (200 <= status < 300):
            msg = f"HTTP {status} loading image cache: {url}"
            print(f"[ImageCache] {msg}")
            _web_debug_log("image.error", msg)
            return None
        if data is None:
            return None
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        _web_debug_log(
            "image.loaded",
            f"{url} ({len(data)} bytes, {elapsed_ms:.1f}ms, {method})",
        )
        return data
    except Exception as e:
        _set_last_fetch_method("error")
        print(f"[ImageCache] external cache fetch failed ({url}): {e}")
        return None


# ── メインクラス ─────────────────────────────────────────────────


class ImageCache:
    """
    画像ファイルを Pyxel 用に変換・キャッシュする。

    Parameters
    ----------
    base_dir  : プロジェクトルート（相対パス解決に使う）
    cache_dir : ディスクキャッシュ保存先（base_dir からの相対）
    """

    def __init__(self, base_dir: str, cache_dir: str = ".pvnm_cache"):
        self.base_dir  = base_dir
        self.cache_dir = os.path.join(base_dir, cache_dir)
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
        except Exception:
            pass
        self._manifest = self._load_manifest()
        # (cache_key, w, h, palette_hash) → pyxel.Image
        self._img_cache: dict[tuple, pyxel.Image] = {}
        self._auto_colkeys: dict[tuple, int | None] = {}
        self._last_load_source = "-"

    # ── 公開 API ────────────────────────────────────────────────

    def get(self, file_path: str,
            width: int = 0, height: int = 0,
            palette: np.ndarray | None = None,
            allowed_indices: "set[int] | None" = None,
            alpha_colkey: bool = False) -> "pyxel.Image | None":
        """
        ファイルパスから pyxel.Image を返す。

        Parameters
        ----------
        width, height : 0 の場合は元サイズ。片方だけ 0 なら比率を保つ。
        palette       : shape (16, 3) uint8 の RGB パレット配列。
                        None の場合は pyxel.colors[] をその都度参照する。
                        palette_from_hex() で Hex リストから生成できる。
        """
        if not file_path:
            return None
        abs_path = self._resolve(file_path)
        path_key = self._cache_key_path(file_path, abs_path)

        # パレット決定:
        #   - palette 引数が明示されればそれを使う
        #   - 無ければ set_default_palette() で登録されたマスターを使う (推奨)
        #   - それも無ければ毎回 pyxel.colors[] を取得 (旧挙動)
        if palette is not None:
            pal = np.asarray(palette, dtype=np.uint8)
        elif _default_palette is not None:
            pal = _default_palette
        else:
            pal = _build_palette()
        ph  = image_cache_hash(pal, allowed_indices, alpha_colkey)

        w, h = self._actual_size(abs_path, path_key, ph, width, height)
        if w <= 0 or h <= 0:
            return None
        key  = (path_key, w, h, ph)
        if key in self._img_cache:
            return self._img_cache[key]

        t0 = time.perf_counter()
        t_arr0 = t0
        arr = self._load_array(abs_path, path_key, w, h, pal, ph,
                               allowed_indices=allowed_indices,
                               alpha_colkey=alpha_colkey)
        t_arr1 = time.perf_counter()
        if arr is None:
            msg = f"missing image cache {path_key} {w}x{h} palette={ph}"
            print(f"[ImageCache] {msg}")
            _web_debug_log("image.missing", msg)
            return None

        t_img0 = time.perf_counter()
        pyx_img = pyxel.Image(w, h)
        _fill_pyxel_image(pyx_img, arr)
        t_img1 = time.perf_counter()
        self._img_cache[key] = pyx_img
        total_ms = (t_img1 - t0) * 1000.0
        if total_ms >= _SLOW_IMAGE_LOAD_MS:
            msg = (
                f"slow load {path_key} {w}x{h} "
                f"source={self._last_load_source} "
                f"total={total_ms:.1f}ms "
                f"array={(t_arr1 - t_arr0) * 1000.0:.1f}ms "
                f"image={(t_img1 - t_img0) * 1000.0:.1f}ms"
            )
            print(f"[ImageCache] {msg}")
            _web_debug_log("image.slow", msg)
        return pyx_img

    def prefetch(self, file_path: str,
                 width: int = 0, height: int = 0,
                 palette: np.ndarray | None = None,
                 allowed_indices: "set[int] | None" = None,
                 alpha_colkey: bool = False) -> bool:
        """Queue an exported external cache file for async JS-side fetch.

        Web/Android uses this to move the slow local asset fetch out of the
        Pyxel/Python frame. The actual pyxel.Image is still created lazily by
        get(), but get() can consume the prefetched bytes without sync XHR.
        """
        if sys.platform != "emscripten" or not file_path:
            return False
        abs_path = self._resolve(file_path)
        path_key = self._cache_key_path(file_path, abs_path)
        if palette is not None:
            pal = np.asarray(palette, dtype=np.uint8)
        elif _default_palette is not None:
            pal = _default_palette
        else:
            pal = _build_palette()
        ph = image_cache_hash(pal, allowed_indices, alpha_colkey)
        w, h = self._actual_size(abs_path, path_key, ph, width, height)
        if w <= 0 or h <= 0:
            return False
        if (path_key, w, h, ph) in self._img_cache:
            return True
        url = self._manifest_cache_url(path_key, w, h, ph)
        if not url:
            return False
        return _prefetch_binary_async(url)

    def cache_filename_for(self, file_path: str, width: int, height: int,
                           palette: np.ndarray,
                           allowed_indices: "set[int] | None" = None,
                           alpha_colkey: bool = False) -> str:
        """Return the v2 cache filename for a path/size/palette tuple."""
        abs_path = self._resolve(file_path)
        path_key = self._cache_key_path(file_path, abs_path)
        ph = image_cache_hash(np.asarray(palette, dtype=np.uint8),
                              allowed_indices, alpha_colkey)
        return os.path.basename(self._disk_cache_path(path_key, width, height, ph))

    def get_auto_colkey(self, file_path: str,
                        width: int = 0, height: int = 0,
                        palette: np.ndarray | None = None,
                        allowed_indices: "set[int] | None" = None) -> "int | None":
        """Return the auto-derived colkey for a PNG-alpha image cache entry."""
        if not file_path:
            return None
        abs_path = self._resolve(file_path)
        path_key = self._cache_key_path(file_path, abs_path)
        if palette is not None:
            pal = np.asarray(palette, dtype=np.uint8)
        elif _default_palette is not None:
            pal = _default_palette
        else:
            pal = _build_palette()
        ph = image_cache_hash(pal, allowed_indices, True)
        w, h = self._actual_size(abs_path, path_key, ph, width, height)
        if w <= 0 or h <= 0:
            return None
        key = (path_key, w, h, ph)
        if key not in self._auto_colkeys:
            self.get(file_path, width, height, palette=palette,
                     allowed_indices=allowed_indices, alpha_colkey=True)
        return self._auto_colkeys.get(key)

    def source_size(self, file_path: str) -> tuple[int, int]:
        """Return original source dimensions from the file or manifest."""
        if not file_path:
            return 0, 0
        abs_path = self._resolve(file_path)
        if abs_path and Image is not None:
            try:
                with Image.open(abs_path) as img:
                    return int(img.width), int(img.height)
            except Exception:
                pass
        path_key = self._cache_key_path(file_path, abs_path)
        images = self._manifest.get("images", {})
        by_path = images.get(path_key) if isinstance(images, dict) else None
        if isinstance(by_path, dict):
            for entry in by_path.values():
                if not isinstance(entry, dict):
                    continue
                size = entry.get("original_size")
                if isinstance(size, list) and len(size) >= 2:
                    try:
                        return max(0, int(size[0])), max(0, int(size[1]))
                    except Exception:
                        pass
        return 0, 0

    def get_prebuilt_palette(self, image_paths: list,
                             reserved: dict) -> "np.ndarray | None":
        """Return an exported scene/image palette from image_manifest.json.

        This is used when original images are not bundled. If no matching
        manifest entry exists, callers should fall back to rebuilding from the
        source images.
        """
        palettes = self._manifest.get("palettes", {})
        if not isinstance(palettes, dict):
            return None
        path_keys = [
            self._cache_key_path(path, self._resolve(path))
            for path in image_paths or []
            if path
        ]
        key = manifest_palette_key(path_keys, reserved)
        entry = palettes.get(key)
        colors = entry.get("colors") if isinstance(entry, dict) else None
        if not isinstance(colors, list) or len(colors) < 256:
            return None
        arr = np.zeros((256, 3), dtype=np.uint8)
        try:
            for i, item in enumerate(colors[:256]):
                if isinstance(item, str):
                    v = int(item.lstrip("#"), 16)
                    arr[i, 0] = (v >> 16) & 0xFF
                    arr[i, 1] = (v >> 8) & 0xFF
                    arr[i, 2] = v & 0xFF
                elif isinstance(item, (list, tuple)) and len(item) >= 3:
                    arr[i, 0] = int(item[0]) & 0xFF
                    arr[i, 1] = int(item[1]) & 0xFF
                    arr[i, 2] = int(item[2]) & 0xFF
            return arr
        except Exception:
            return None

    def invalidate(self, file_path: str):
        """ファイルのメモリキャッシュを削除（ファイル更新後に呼ぶ）"""
        abs_path = self._resolve(file_path)
        if not abs_path:
            return
        path_key = self._cache_key_path(file_path, abs_path)
        remove = [k for k in self._img_cache if k[0] == path_key]
        for k in remove:
            del self._img_cache[k]
        remove_ck = [k for k in self._auto_colkeys if k[0] == path_key]
        for k in remove_ck:
            del self._auto_colkeys[k]

    def invalidate_all(self):
        """全メモリキャッシュを破棄する。

        パレットを一括変更した後に呼ぶことで、次の get() 呼び出し時に
        新しいパレットで再変換される。ディスクキャッシュはパレットハッシュ
        別に管理されているため自動的に正しいファイルが選択される。
        """
        self._img_cache.clear()
        self._auto_colkeys.clear()

    def clean_disk_cache(self, keep_hashes: set | None = None):
        """
        ディスクキャッシュから不要なエントリを削除する。

        Parameters
        ----------
        keep_hashes : 保持するパレットハッシュの集合。
                      None の場合は現在の pyxel.colors[] のハッシュのみ保持。
        """
        if keep_hashes is None:
            keep_hashes = {_palette_hash(_build_palette())}
        try:
            for fname in os.listdir(self.cache_dir):
                if not fname.endswith(".npy"):
                    continue
                # ファイル名フォーマット: {filehash}_{w}x{h}_{palettehash}.npy
                stem = fname[:-4]
                parts = stem.rsplit("_", 1)
                if len(parts) == 2 and parts[1] not in keep_hashes:
                    try:
                        os.remove(os.path.join(self.cache_dir, fname))
                    except OSError:
                        pass
        except OSError:
            pass

    # ── 内部 ────────────────────────────────────────────────────

    def _load_manifest(self) -> dict:
        path = os.path.join(self.base_dir, "image_manifest.json")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _resolve(self, path: str) -> "str | None":
        if os.path.isabs(path):
            abs_path = path
        else:
            abs_path = os.path.join(self.base_dir, path)
        return _existing_path_variant(abs_path)

    def _cache_key_path(self, path: str, abs_path: "str | None") -> str:
        """Return a portable path identity for disk/memory cache keys.

        Relative project paths keep exported games compatible with editor-side
        caches. Absolute paths under base_dir are normalized back to relative
        paths. External absolute paths deliberately keep an "abs:" identity.
        """
        if not os.path.isabs(path):
            return normalize_asset_key_path(path)
        base = os.path.abspath(self.base_dir)
        if abs_path:
            ap = os.path.abspath(abs_path)
            try:
                rel = os.path.relpath(ap, base)
                if rel == "." or not rel.startswith(".." + os.sep):
                    return normalize_asset_key_path(rel)
            except ValueError:
                pass
        try:
            rel = os.path.relpath(os.path.abspath(path), base)
            if rel == "." or not rel.startswith(".." + os.sep):
                return normalize_asset_key_path(rel)
        except ValueError:
            pass
        return "abs:" + normalize_asset_key_path(os.path.abspath(path))

    def _actual_size(self, abs_path: "str | None", path_key: str, ph: str,
                     w: int, h: int) -> tuple:
        if w > 0 and h > 0:
            return w, h
        if abs_path and Image is not None:
            try:
                with Image.open(abs_path) as img:
                    iw, ih = img.size
            except Exception:
                iw, ih = self._manifest_original_size(path_key, ph)
        else:
            iw, ih = self._manifest_original_size(path_key, ph)
        if iw <= 0 or ih <= 0:
            return max(w, 0), max(h, 0)
        if w > 0:
            return w, max(1, round(ih * w / iw))
        if h > 0:
            return max(1, round(iw * h / ih)), h
        return iw, ih

    def _disk_cache_path(self, path_key: str, w: int, h: int, ph: str) -> str:
        fh = hashlib.md5(path_key.encode("utf-8")).hexdigest()[:12]
        return os.path.join(self.cache_dir, f"v2_{fh}_{w}x{h}_{ph}.npy")

    def _manifest_image_entry(self, path_key: str, ph: str) -> dict:
        images = self._manifest.get("images", {})
        if not isinstance(images, dict):
            return {}
        by_path = images.get(path_key)
        if not isinstance(by_path, dict):
            return {}
        by_palette = by_path.get(ph)
        return by_palette if isinstance(by_palette, dict) else {}

    def _manifest_original_size(self, path_key: str, ph: str) -> tuple:
        entry = self._manifest_image_entry(path_key, ph)
        size = entry.get("original_size")
        if isinstance(size, list) and len(size) >= 2:
            try:
                return max(0, int(size[0])), max(0, int(size[1]))
            except Exception:
                pass
        sizes = entry.get("sizes")
        if isinstance(sizes, dict):
            for key in sizes:
                try:
                    ws, hs = str(key).split("x", 1)
                    return max(0, int(ws)), max(0, int(hs))
                except Exception:
                    continue
        return 0, 0

    def _manifest_cache_path(self, path_key: str, w: int, h: int,
                             ph: str) -> "str | None":
        name = self._manifest_cache_name(path_key, w, h, ph)
        if not name:
            return None
        return os.path.join(self.cache_dir, os.path.basename(str(name)))

    def _manifest_cache_name(self, path_key: str, w: int, h: int,
                             ph: str) -> "str | None":
        rec = self._manifest_cache_record(path_key, w, h, ph)
        if isinstance(rec, str):
            return os.path.basename(str(rec))
        if isinstance(rec, dict):
            name = rec.get("cache")
            return os.path.basename(str(name)) if name else None
        return None

    def _manifest_cache_record(self, path_key: str, w: int, h: int,
                               ph: str):
        entry = self._manifest_image_entry(path_key, ph)
        sizes = entry.get("sizes")
        if not isinstance(sizes, dict):
            return None
        return sizes.get(f"{w}x{h}")

    def _manifest_auto_colkey(self, path_key: str, w: int, h: int,
                              ph: str) -> "int | None":
        rec = self._manifest_cache_record(path_key, w, h, ph)
        if isinstance(rec, dict):
            value = rec.get("auto_colkey")
            if isinstance(value, int) and 0 <= value <= 255:
                return value
        return None

    def _manifest_cache_url(self, path_key: str, w: int, h: int,
                            ph: str) -> "str | None":
        name = self._manifest_cache_name(path_key, w, h, ph)
        if not name:
            return None
        ext = self._manifest.get("external_cache", {})
        base = ""
        if isinstance(ext, dict):
            base = str(ext.get("base_url") or ext.get("base") or "")
        if not base:
            base = str(self._manifest.get("external_cache_base") or "")
        if not base:
            return None
        return base.rstrip("/") + "/" + os.path.basename(str(name))

    def _load_external_cache_array(self, path_key: str, w: int, h: int,
                                   ph: str, cache_path: str):
        url = self._manifest_cache_url(path_key, w, h, ph)
        t_fetch0 = time.perf_counter()
        data = _fetch_binary_sync(url) if url else None
        t_fetch1 = time.perf_counter()
        if not data:
            return None
        try:
            t_decode0 = time.perf_counter()
            arr = _load_npy_bytes(data)
            t_decode1 = time.perf_counter()
            if arr.shape != (h, w):
                return None
            total_ms = (t_decode1 - t_fetch0) * 1000.0
            if total_ms >= _SLOW_IMAGE_LOAD_MS:
                msg = (
                    f"external {path_key} {w}x{h} "
                    f"total={total_ms:.1f}ms "
                    f"fetch={(t_fetch1 - t_fetch0) * 1000.0:.1f}ms "
                    f"decode={(t_decode1 - t_decode0) * 1000.0:.1f}ms "
                    f"method={_last_fetch_method}"
                )
                print(f"[ImageCache] {msg}")
                _web_debug_log("image.external", msg)
            return arr
        except Exception as e:
            print(f"[ImageCache] external cache decode failed ({url}): {e}")
            return None

    def _load_array(self, abs_path: "str | None", path_key: str, w: int, h: int,
                    pal: np.ndarray, ph: str,
                    allowed_indices: "set[int] | None" = None,
                    alpha_colkey: bool = False) -> "np.ndarray | None":
        cache_path = self._disk_cache_path(path_key, w, h, ph)
        manifest_path = self._manifest_cache_path(path_key, w, h, ph)
        cache_key = (path_key, w, h, ph)
        if abs_path:
            src_mtime = os.path.getmtime(abs_path)
            if (os.path.exists(cache_path)
                    and os.path.getmtime(cache_path) >= src_mtime):
                try:
                    arr = np.load(cache_path)
                    if alpha_colkey:
                        self._remember_auto_colkey(cache_key, arr, abs_path,
                                                   w, h)
                    self._last_load_source = "source_disk_cache"
                    return arr
                except Exception:
                    pass
        else:
            for path in (manifest_path, cache_path):
                if not path or not os.path.exists(path):
                    continue
                try:
                    arr = np.load(path)
                    if arr.shape == (h, w):
                        if alpha_colkey:
                            self._auto_colkeys[cache_key] = (
                                self._manifest_auto_colkey(path_key, w, h, ph))
                        self._last_load_source = (
                            "manifest_cache"
                            if path == manifest_path else "export_cache")
                        return arr
                except Exception:
                    pass
            arr = self._load_external_cache_array(path_key, w, h, ph,
                                                  cache_path)
            if arr is not None:
                if alpha_colkey:
                    self._auto_colkeys[cache_key] = (
                        self._manifest_auto_colkey(path_key, w, h, ph))
                self._last_load_source = "external_cache/" + _last_fetch_method
                return arr
            return None

        arr, auto_colkey = self._process(
            abs_path, w, h, pal, allowed_indices,
            alpha_colkey=alpha_colkey)
        if alpha_colkey:
            self._auto_colkeys[cache_key] = auto_colkey
        if arr is not None:
            self._last_load_source = "source_process"
            try:
                np.save(cache_path, arr)
            except Exception:
                pass
        return arr

    def _process(self, abs_path: str, w: int, h: int,
                 pal: np.ndarray,
                 allowed_indices: "set[int] | None" = None,
                 alpha_colkey: bool = False):
        if Image is None:
            print(f"[ImageCache] Pillow unavailable; cannot process {abs_path}")
            return None, None
        try:
            with Image.open(abs_path) as src:
                alpha = None
                if "A" in src.getbands():
                    rgba = src.convert("RGBA").resize((w, h), Image.LANCZOS)
                    alpha = rgba.split()[3]
                    bg   = Image.new("RGB", (w, h), (0, 0, 0))
                    bg.paste(rgba, mask=alpha)
                    rgb  = bg
                else:
                    rgb  = src.convert("RGB").resize((w, h), Image.LANCZOS)
                arr = _quantize(rgb, pal, allowed_indices=allowed_indices)
                auto_colkey = None
                if alpha_colkey and arr is not None and alpha is not None:
                    auto_colkey = _apply_alpha_colkey(arr, alpha, rgb, pal)
                return arr, auto_colkey
        except Exception as e:
            print(f"[ImageCache] {abs_path}: {e}")
            return None, None

    def _remember_auto_colkey(self, cache_key: tuple, arr,
                              abs_path: str, w: int, h: int) -> None:
        """Recover auto colkey for an existing disk cache using source alpha."""
        if Image is None:
            self._auto_colkeys[cache_key] = None
            return
        try:
            with Image.open(abs_path) as src:
                if "A" not in src.getbands():
                    self._auto_colkeys[cache_key] = None
                    return
                alpha = src.convert("RGBA").resize(
                    (w, h), Image.LANCZOS).split()[3]
                if not _has_transparent_alpha(alpha):
                    self._auto_colkeys[cache_key] = None
                    return
                alpha_bytes = alpha.convert("L").tobytes()
                counts: dict[int, int] = {}
                for y in range(h):
                    row_base = y * w
                    for x in range(w):
                        if alpha_bytes[row_base + x] < 128:
                            idx = int(arr[y, x]) & 0xFF
                            counts[idx] = counts.get(idx, 0) + 1
                self._auto_colkeys[cache_key] = (
                    max(counts, key=counts.get) if counts else None)
        except Exception:
            self._auto_colkeys[cache_key] = None
