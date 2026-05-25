"""Pillow ベースの高品質テキストレンダラ。

pyxel.text(x, y, str, col, pyxel.Font) は 1bit + 任意サイズへの素朴な
ラスタライズで、ベクター系フォント (IPA_Gothic / NotoSansJP) や設計サイズ
以外のビットマップ系フォント (DotGothic16, BesfTen 等) で見栄えが崩れる。

このモジュールでは Pillow + FreeType を使って:
  1. 任意 TTF/OTF を任意サイズで rasterize (アンチエイリアス可)
  2. アンチエイリアスのグレースケールを現在の pyxel パレットに最近傍量子化
     (前景色 ↔ 背景色の間のグレーは中間パレット色へマップ)
  3. pyxel.Image にコピーし、blt で描画
  4. (font_path, size, text, fg_idx, bg_idx, palette_hash) でキャッシュ
     → 同じ文字列の 2 回目以降は即返し

公開 API:
  draw_text(x, y, text, col, font_path, size, antialias=True, bg_col=None)
"""
import os
import hashlib
import ctypes
import numpy as np
import pyxel
from PIL import Image, ImageDraw, ImageFont

# 量子化済み pyxel.Image のキャッシュ
# key: (font_path, size, text, fg_idx, bg_idx, palette_hash, antialias)
_cache: dict = {}
# LRU 制限 (画面に出るテキストはせいぜい数百種類なので 512 で十分)
_CACHE_MAX = 512

# ImageFont のキャッシュ (path, size → ImageFont)。
# 同じフォントを毎回 truetype() で開くと数十 ms かかるので memoize する。
_font_cache: dict = {}

# 日本語フォントフォールバック: メインフォントが Latin 系のみ (BestTen-DOT 等)
# だと .notdef (□×) になる。non-ASCII を検出したらこっちで描く。
_fallback_font_path: str = ""


def set_fallback_font(path: str) -> None:
    """日本語等の非 ASCII グリフ用フォールバックフォントのパスを設定。"""
    global _fallback_font_path
    _fallback_font_path = path or ""


def _autodetect_fallback() -> str:
    """assets/fonts 内に NotoSansJP-Regular.ttf があれば自動採用する。
    main.py が明示的に set_fallback_font() を呼ばなくても効くようにする。"""
    if _fallback_font_path:
        return _fallback_font_path
    candidates = [
        os.path.join(os.path.dirname(__file__), "..",
                     "assets/fonts/NotoSansJP-Regular.ttf"),
    ]
    for c in candidates:
        ap = os.path.normpath(c)
        if os.path.exists(ap):
            return ap
    return ""


def _get_font(path: str, size: int):
    """ImageFont を取得 (キャッシュ経由)。失敗時 None。"""
    key = (path, int(size))
    f = _font_cache.get(key)
    if f is not None:
        return f
    try:
        f = ImageFont.truetype(path, int(size))
    except Exception as e:
        print(f"[text_renderer] font load failed {path} size={size}: {e}")
        f = None
    _font_cache[key] = f
    return f


def _palette_hash() -> str:
    """現在の pyxel.colors[] の短いハッシュ (キャッシュキー用)。"""
    n = min(256, len(pyxel.colors))
    buf = bytes()
    for i in range(n):
        c = pyxel.colors[i]
        buf += bytes((
            (c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF,
        ))
    return hashlib.md5(buf).hexdigest()[:8]


def _palette_array() -> np.ndarray:
    """pyxel.colors[] を (256, 3) uint8 配列で返す。"""
    arr = np.zeros((256, 3), dtype=np.uint8)
    n = min(256, len(pyxel.colors))
    for i in range(n):
        c = pyxel.colors[i]
        arr[i, 0] = (c >> 16) & 0xFF
        arr[i, 1] = (c >> 8) & 0xFF
        arr[i, 2] = c & 0xFF
    return arr


def _measure(font, text: str) -> tuple:
    """テキストの「描画後に必要なボックスサイズ」(w, h) を返す。

    PIL `getbbox` の高さは bbox の縦範囲なので、descender が含まれていれば
    その分だけ大きい。フォント metrics の ascent+descent を上限として併用し、
    かつ少しの余白を足して切れを防ぐ。
    """
    if font is None:
        return max(1, len(text) * 4), 6
    try:
        bbox = font.getbbox(text)
        w_box = max(1, bbox[2] - bbox[0])
        h_box = max(1, bbox[3] - bbox[1])
    except Exception:
        try:
            w_box, h_box = font.getsize(text)
        except Exception:
            w_box, h_box = max(1, len(text) * 8), 12
    try:
        asc, dsc = font.getmetrics()
        h_metric = asc + dsc
    except Exception:
        h_metric = h_box
    return w_box, max(h_box, h_metric)


def _select_font_for_char(c: str, primary, fallback):
    """文字単位でメイン/フォールバックフォントを選ぶ。

    ヒューリスティック: 非 ASCII (ord > 0x7F) で fallback が利用可能なら
    fallback を使う。これでメインが Latin 専用フォント (BestTen-DOT 等) でも
    日本語が .notdef にならない。
    """
    if fallback is not None and ord(c) > 0x7F:
        return fallback
    return primary


def _char_advance(font, c: str) -> int:
    """文字 c の x 進み幅 (advance width) を整数で返す。"""
    try:
        return max(1, int(round(font.getlength(c))))
    except Exception:
        try:
            return max(1, font.getbbox(c)[2] - font.getbbox(c)[0])
        except Exception:
            return 8


def _render_to_image(text: str, font, size: int, fg_idx: int, bg_idx: int,
                     antialias: bool, fallback_font=None) -> "tuple | None":
    """text を pyxel.Image にラスタライズし (img, colkey) を返す。失敗時 None。

    非 ASCII 文字は `fallback_font` (= 日本語フォント) で描画することで、
    Latin 系メインフォントでも日本語の .notdef (□×) を回避する。
    各文字を anchor="ls" (baseline 基準) で逐次描画してフォント間の
    ベースライン整合を取る。
    """
    if not text or font is None:
        return None

    # フォント metrics: fallback が利用可能なら常に metrics に加える (テキストが
    # ASCII のみでも)。こうしないと "[P:Last E]" (ASCII) と "[C:プロローグ目]"
    # (CJK 混在) でキャンバス高/baseline が変わり、隣接した文字列が縦にズレる
    # (sc35 で観測された現象)。
    fonts_for_metrics = [font]
    if fallback_font is not None:
        fonts_for_metrics.append(fallback_font)
    max_ascent = 0
    max_descent = 0
    for f in fonts_for_metrics:
        try:
            a, d = f.getmetrics()
        except Exception:
            a, d = size, max(2, size // 4)
        if a > max_ascent: max_ascent = a
        if d > max_descent: max_descent = d
    if max_ascent <= 0: max_ascent = size
    if max_descent <= 0: max_descent = max(2, size // 4)

    # 各文字の advance を足して total width
    total_w = 0
    for c in text:
        f = _select_font_for_char(c, font, fallback_font)
        total_w += _char_advance(f, c)
    margin = max(1, size // 8)
    w = total_w + margin * 2
    h = max_ascent + max_descent + margin * 2

    canvas = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(canvas)
    baseline_y = margin + max_ascent

    cur_x = margin
    for c in text:
        f = _select_font_for_char(c, font, fallback_font)
        try:
            # anchor="ls" = left edge / baseline。ベースライン揃えで描画。
            draw.text((cur_x, baseline_y), c, font=f, fill=255, anchor="ls")
        except (TypeError, ValueError):
            # 古い PIL: anchor 未対応 → 自前で baseline 換算
            try:
                a, _ = f.getmetrics()
            except Exception:
                a = size
            draw.text((cur_x, baseline_y - a), c, font=f, fill=255)
        except Exception as e:
            print(f"[text_renderer] draw failed for {c!r}: {e}")
        cur_x += _char_advance(f, c)

    if not antialias:
        # 2値化 (ハードエッジ)。
        # 閾値: 32 (約 12%)。pixel font (BestTen-DOT 等) を非設計サイズで
        # ラスタライズすると細い縦ストローク (例: "]" の右辺) が低輝度ピクセル
        # にしか乗らないことがあり、128 だと丸ごと消える (sc38)。
        # 32 にして「描画された痕跡があれば残す」方針に変更。
        arr_l = np.array(canvas, dtype=np.uint8)
        arr_l = (arr_l >= 32).astype(np.uint8) * 255
        canvas = Image.fromarray(arr_l, mode="L")

    # トリミング:
    #   - 横方向: 左右の空白カラムを削除 (テキスト先頭が画像左端に来る)
    #   - 縦方向: トリミングしない (canvas 高 = 一定 = ascent+descent+margin*2)
    # 縦も合わせて trim すると、ASCII のみと CJK 混在で異なる y オフセットの
    # 画像が出来上がり、caller 側で同じ (x, y) に貼った時に縦ズレを引き起こす。
    arr = np.array(canvas, dtype=np.uint8)
    nonzero_cols = np.argwhere(arr.any(axis=0))
    if nonzero_cols.size == 0:
        return None
    x0 = int(nonzero_cols.min())
    x1 = int(nonzero_cols.max()) + 1
    arr = arr[:, x0:x1]
    rh, rw = arr.shape
    if rh <= 0 or rw <= 0:
        return None

    # アンチエイリアスグレースケール → 前景/背景補間の RGB → パレット index
    pal = _palette_array()
    fg = pal[fg_idx] if 0 <= fg_idx < 256 else np.array([255, 255, 255])
    if bg_idx is None or bg_idx < 0:
        # 背景透明: グレー値そのまま使い、α 0 と扱う。実装は colkey で扱うので
        # 背景色には pyxel.colors[0] (= UI BG) を採用しておく。グレー強度に
        # 応じて bg→fg 補間する。完全 0 のピクセルは colkey=0 で透明。
        bg = pal[0]
    else:
        bg = pal[bg_idx]
    fg_i = fg.astype(np.int32)
    bg_i = bg.astype(np.int32)

    # alpha = arr/255。各ピクセルの RGB = bg + alpha*(fg-bg)
    a = arr.astype(np.int32)
    # broadcast: (rh, rw, 1) * (3,) → (rh, rw, 3)
    diff = (fg_i - bg_i)
    rgb = bg_i + (a[:, :, None] * diff + 127) // 255  # (rh, rw, 3)
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)

    # alpha==0 のピクセルは「透明 = 背景と同じ index」にして blt の
    # colkey=bg_idx で抜く。 bg_idx 指定が無いケースでは index 0 を colkey に使う想定。
    transparent_mask = (arr == 0)

    # 最近傍量子化 (PIL の quantize ベースで高速化)
    pal_pil = Image.new("P", (1, 1))
    flat = []
    for i in range(256):
        flat.append(int(pal[i, 0]))
        flat.append(int(pal[i, 1]))
        flat.append(int(pal[i, 2]))
    while len(flat) < 768:
        flat.append(0)
    pal_pil.putpalette(flat)
    rgb_pil = Image.fromarray(rgb, mode="RGB")
    q = rgb_pil.quantize(palette=pal_pil, dither=Image.Dither.NONE)
    idx_arr = np.array(q, dtype=np.uint8)

    # 透明領域用の colkey を「テキスト本体で使われていない index」から選ぶ。
    # 旧実装は colkey=0 固定だったため、fg=0 (= EDIT_BG など暗い UI 色) の
    # テキストを描画すると本体ピクセルも index 0 に量子化され、colkey=0 で
    # 一緒に抜けて見えなくなっていた (sc33 の現象)。
    used = set(np.unique(idx_arr[~transparent_mask]).tolist()) if transparent_mask.any() else set(np.unique(idx_arr).tolist())
    colkey = None
    # bg_idx 指定があればそれを優先 (テキストに含まれていない場合のみ採用)
    if bg_idx is not None and bg_idx >= 0 and bg_idx not in used:
        colkey = bg_idx
    if colkey is None:
        # 255 → 0 の順で空き index を探す。背景 (透明領域) は元々 RGB=bg なので
        # 量子化結果に bg_idx が含まれていることが多い → 高 index 優先で空きを探す。
        for cand in range(255, -1, -1):
            if cand not in used:
                colkey = cand
                break
        if colkey is None:
            # 全 index 使用済み (極めて稀): やむを得ず 0 を使う
            colkey = 0
    idx_arr[transparent_mask] = colkey

    img = pyxel.Image(rw, rh)
    flat_bytes = np.ascontiguousarray(idx_arr).tobytes()
    ctypes.memmove(img.data_ptr(), flat_bytes, len(flat_bytes))
    # pyxel.Image は属性追加不可なので (img, colkey) で返してキャッシュ側に保存。
    return (img, int(colkey))


def _cache_evict():
    """LRU 風: 適当に古い半分を捨てる。dict 挿入順を信頼。"""
    if len(_cache) < _CACHE_MAX:
        return
    keys = list(_cache.keys())
    for k in keys[:len(keys) // 2]:
        del _cache[k]


def draw_text(x: int, y: int, text: str, col: int,
              font_path: str, size: int,
              antialias: bool = True,
              bg_col: "int | None" = None) -> tuple:
    """テキストを (x, y) に描画する。pyxel.text(font=...) の代替。

    Parameters
    ----------
    x, y       : 描画位置 (左上)
    text       : 描画する文字列 (UTF-8)
    col        : 前景色 (パレット index 0-255)
    font_path  : TTF/OTF の絶対 or 相対パス
    size       : フォントピクセルサイズ
    antialias  : True ならアンチエイリアス付き (推奨)
    bg_col     : 背景色 index。None なら透明 (colkey=0 で抜く)。

    Returns
    -------
    (width, height) ピクセル単位。テキストを描画した実サイズ。
    """
    if not text:
        return (0, 0)
    font = _get_font(font_path, size)
    if font is None:
        # フォントロード失敗時は pyxel.text にフォールバック
        pyxel.text(x, y, text, col)
        return (len(text) * 4, 6)

    fg_idx = max(0, min(255, int(col)))
    bg_idx = -1 if bg_col is None else max(0, min(255, int(bg_col)))
    # 日本語フォールバック: テキストに非 ASCII が含まれていれば自動で適用
    fb_path = _autodetect_fallback()
    fb_font = None
    if fb_path and fb_path != font_path and any(ord(c) > 0x7F for c in text):
        fb_font = _get_font(fb_path, size)
    key = (font_path, int(size), text, fg_idx, bg_idx,
           _palette_hash(), bool(antialias),
           fb_path if fb_font is not None else "")
    cached = _cache.get(key)
    if cached is None:
        cached = _render_to_image(text, font, size, fg_idx, bg_idx,
                                  antialias, fallback_font=fb_font)
        if cached is None:
            return (0, 0)
        _cache_evict()
        _cache[key] = cached

    img, colkey = cached
    iw, ih = img.width, img.height
    # colkey はテキスト本体と衝突しない index (0 とは限らない)
    pyxel.blt(x, y, img, 0, 0, iw, ih, colkey)
    return (iw, ih)


def canvas_height_for(font_path: str, size: int) -> int:
    """draw_text() が生成する pyxel.Image の高さ (= 縦中央揃えに使うべき値) を返す。

    widgets._font_render_h() と一致させることで、caller の `ty = y + (nh-rh)/2`
    中央揃え計算が実画像と完全に一致する (sc41 のノード枠下にハミ出る現象を防ぐ)。
    """
    primary = _get_font(font_path, size)
    if primary is None:
        return max(2, size)
    fb_path = _autodetect_fallback()
    fonts = [primary]
    if fb_path and fb_path != font_path:
        fb = _get_font(fb_path, size)
        if fb is not None:
            fonts.append(fb)
    max_a, max_d = 0, 0
    for f in fonts:
        try:
            a, d = f.getmetrics()
            max_a = max(max_a, a)
            max_d = max(max_d, d)
        except Exception:
            pass
    if max_a <= 0:
        max_a = size
    if max_d <= 0:
        max_d = max(2, size // 4)
    margin = max(1, size // 8)
    return max_a + max_d + margin * 2


def measure(text: str, font_path: str, size: int) -> tuple:
    """テキストの描画後サイズを (w, h) で返す (実描画なし)。

    日本語フォールバックが効くケースでも実際の描画幅と一致する advance
    ベースの計算をする (ボタンクリック判定との一貫性を保つため)。
    """
    if not text:
        return (0, 6)
    primary = _get_font(font_path, size)
    if primary is None:
        return (max(1, len(text) * 4), 6)
    fb_path = _autodetect_fallback()
    fallback = None
    if fb_path and fb_path != font_path and any(ord(c) > 0x7F for c in text):
        fallback = _get_font(fb_path, size)
    total_w = 0
    for c in text:
        f = _select_font_for_char(c, primary, fallback)
        total_w += _char_advance(f, c)
    # 高さは ascent+descent (混在時は最大値)
    fonts = [primary] + ([fallback] if fallback is not None else [])
    h = 0
    for f in fonts:
        try:
            a, d = f.getmetrics()
            h = max(h, a + d)
        except Exception:
            pass
    if h <= 0:
        h = size
    return (max(1, total_w), h)


def clear_cache():
    """全キャッシュをクリア。パレット大幅変更後などに呼ぶ。"""
    _cache.clear()
