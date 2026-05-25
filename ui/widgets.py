"""基本UIウィジェット (720×480 対応)"""
import os
import math
import unicodedata
import pyxel
from ui.colors import *


def _nfc(text: str) -> str:
    """macOS APFS のファイル名は NFD (フ+゜) で返るが、BDF は precomposed 形
    (プ U+30D7) しか持たないので、描画前に NFC に正規化する。"""
    if not text:
        return text
    try:
        return unicodedata.normalize("NFC", text)
    except Exception:
        return text


def _gap_count(text: str) -> int:
    """Return the number of inter-character gaps for optional tracking."""
    if not text:
        return 0
    count = 0
    for ch in text:
        if not unicodedata.combining(ch):
            count += 1
    return max(0, count - 1)

# ── フォント設定 ──────────────────────────────────────────────
# UI 全体は efont b12.bdf に統一する。
# サイズ可変・UI scale は廃止: pyxel.Font(BDF) はビットマップなのでスケール不可、
# サイズは離散 (10/12/14/16/17/18/19/20/21/22/23/24) で b12 が標準。
_editor_font: "pyxel.Font | None" = None  # legacy (TTF) フォールバック用、通常未使用
_editor_font_size = 12     # 固定 12 (BDF b12.bdf)
_ui_font_size     = 12     # 固定 12 (BDF b12.bdf)
_editor_font_path = ""     # legacy TTF path (BDF 採用後はほぼ使われない)
_sized_font_cache: "dict[int, pyxel.Font]" = {}  # legacy

# ── UI Scale (pyxel デフォルトフォントの拡大倍率) ──────────────
# pyxel.text() のデフォルトフォント (4×6px) を任意倍率で表示するための設定。
# UIラベルに使用。1 = 等倍（従来通り） / 2,3,4,... で拡大。
_ui_scale = 1
_UI_SCALE_MIN = 1
_UI_SCALE_MAX = 4
# 拡大描画用オフスクリーンImage (複数サイズを共有) とラベルキャッシュ
_ui_text_img: "pyxel.Image | None" = None
_UI_TEXT_IMG_W = 720      # 1行あたりの最大幅（スクリーン幅と同等）
_UI_TEXT_IMG_H = 8        # デフォルトフォントの高さ(6) + 余白
# default font の1文字幅
UI_GLYPH_W = 4
UI_GLYPH_H = 6

TITLE_BAR_H = 22           # 後方互換用（非推奨: title_bar_h() を使用）

# フォントファイルの基本パス
_font_base_dir = ""

# ── efont BDF ピクセルフォント ────────────────────────────────
# pyxel.Font(BDF) はベクター TTF と違ってラスタライズ不要 (各グリフが事前に
# ビットマップとして格納されている)。日本語 kanji/kana を含む全文字が
# pyxel 標準の描画で破綻なく表示できるので、UI 全体をこれに統一する。
_BDF_AVAILABLE_SIZES = (10, 12, 14, 16, 17, 18, 19, 20, 21, 22, 23, 24)
_bdf_dir: str = ""           # efont-unicode-bdf ディレクトリの絶対パス
_bdf_fonts: dict = {}        # 実サイズ → pyxel.Font (LRU 不要、5 個だけ)


def set_bdf_dir(path: str) -> None:
    """BDF フォントディレクトリ (e.g. assets/fonts/efont-unicode-bdf) を設定。"""
    global _bdf_dir
    _bdf_dir = path or ""


def _get_bdf(target_size: int):
    """target_size に最も近い BDF サイズの pyxel.Font を返す。

    efont-unicode-bdf の "b" (Biwidth: ASCII + 日本語両対応) を採用。
    "f" (Fixed) は ASCII を含まないため UI には不向き。

    Returns
    -------
    (font, actual_size) のタプル。BDF dir 未設定または読込失敗時は (None, target_size)。
    """
    if not _bdf_dir:
        return None, target_size
    # 最も近いサイズを選択
    actual = min(_BDF_AVAILABLE_SIZES, key=lambda s: abs(s - target_size))
    font = _bdf_fonts.get(actual)
    if font is not None:
        return font, actual
    path = os.path.join(_bdf_dir, f"b{actual}.bdf")
    if not os.path.exists(path):
        return None, target_size
    try:
        font = pyxel.Font(path)
    except Exception as e:
        print(f"[widgets] BDF load failed ({path}): {e}")
        return None, target_size
    _bdf_fonts[actual] = font
    return font, actual


def set_ui_scale(n: int):
    """[DEPRECATED] BDF 統一により UI スケールは無効化。互換のため受取るが no-op。"""
    pass


def get_ui_scale() -> int:
    """[DEPRECATED] 互換のため常に 1 を返す。"""
    return 1


def ui_text_w(text: str, scale: int = 0) -> int:
    """UI ラベルの描画幅 (px)。

    BDF 利用可能なら `_ui_font_size * (scale or _ui_scale)` に最も近い
    BDF サイズで実測。BDF 未設定時は旧来の 4×6 デフォルトフォント × scale。
    """
    s = scale if scale > 0 else _ui_scale
    target = _ui_font_size * s
    bdf, _ = _get_bdf(target)
    if bdf is not None:
        try:
            return bdf.text_width(_nfc(text))
        except Exception:
            pass
    return len(text) * UI_GLYPH_W * s


def ui_text_h(scale: int = 0) -> int:
    """UI ラベルの描画高 (px)。BDF 統一で draw_unicode と同じ高さになる。"""
    s = scale if scale > 0 else _ui_scale
    target = _ui_font_size * s
    bdf, actual = _get_bdf(target)
    if bdf is not None:
        return int(actual)
    return UI_GLYPH_H * s


def _ensure_ui_text_img() -> "pyxel.Image | None":
    """拡大用オフスクリーンImageを遅延生成"""
    global _ui_text_img
    if _ui_text_img is None:
        try:
            _ui_text_img = pyxel.Image(_UI_TEXT_IMG_W, _UI_TEXT_IMG_H)
        except Exception:
            _ui_text_img = None
    return _ui_text_img


# ── テキスト描画 (新ロジック) ───────────────────────────────────
# pyxel デフォルトフォント (4×6) のみを ui_scale 倍で描画する。
# 中央揃えロジックは廃止 — すべて左上原点・左詰め。
# クリック判定は "テキストの矩形" を使う ([label] スタイル)。

def draw_ui_text(x: int, y: int, text: str, color: int, scale: int = 0):
    """UI ラベルを描画。BDF 統一で日本語も英数も同じ高さ・字種で表示される。

    `scale` は legacy 互換引数。BDF 採用時は `_ui_font_size * scale` に最も
    近い BDF サイズが選ばれる (= サイズ倍率の代わりに「大きい BDF」を採用)。
    """
    if not text:
        return
    s = scale if scale > 0 else _ui_scale
    target = _ui_font_size * s
    bdf, _ = _get_bdf(target)
    if bdf is not None:
        pyxel.text(int(x), int(y), _nfc(text), int(color), bdf)
        return
    # ── レガシーフォールバック (BDF 未設定時) ─────────────────
    if s <= 1:
        pyxel.text(int(x), int(y), text, color)
        return
    img = _ensure_ui_text_img()
    if img is None:
        pyxel.text(int(x), int(y), text, color)
        return
    n = len(text)
    src_w = min(n * UI_GLYPH_W, _UI_TEXT_IMG_W)
    key = 0 if color != 0 else 1
    img.rect(0, 0, _UI_TEXT_IMG_W, _UI_TEXT_IMG_H, key)
    img.text(0, 0, text, color)
    ox = (src_w * (s - 1)) // 2
    oy = (UI_GLYPH_H * (s - 1)) // 2
    pyxel.blt(int(x) + ox, int(y) + oy, img, 0, 0, src_w, UI_GLYPH_H,
              key, scale=float(s))


def _bracketed(label: str) -> str:
    """ラベルが [...] 形式でなければ角括弧で囲む。"""
    if not label:
        return "[]"
    # すでに [ で始まっていれば触らない（[EDIT_BG IMAGE]:filename 等への配慮）
    if label[0] == "[":
        return label
    return f"[{label}]"


def text_btn_w(label: str, scale: int = 0) -> int:
    """[label] テキストボタンの描画幅 (= クリック判定幅)"""
    return ui_text_w(_bracketed(label), scale)


def text_btn_h(scale: int = 0) -> int:
    """テキストボタンの高さ (= テキスト高さ)"""
    return ui_text_h(scale)


def text_btn_hover(mx: int, my: int, x: int, y: int,
                   label: str, scale: int = 0) -> bool:
    """テキスト矩形に対するホバー判定。"""
    return (x <= mx < x + text_btn_w(label, scale)
            and y <= my < y + text_btn_h(scale))


def text_btn_clicked(mx: int, my: int, x: int, y: int,
                     label: str, scale: int = 0) -> bool:
    return (pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT)
            and text_btn_hover(mx, my, x, y, label, scale))


def draw_text_btn(x: int, y: int, label: str,
                  hover: bool = False, active: bool = False,
                  scale: int = 0) -> int:
    """背景なしテキストボタン: [label] を左詰めで描画。返値=描画幅。

    ラベルに非ASCII文字 (日本語等) が含まれる場合は TTF フォントで
    描画する (ファイル名に日本語を含むボタンラベル対応)。
    """
    lab = _bracketed(label)
    if active:
        col = EDIT_ACCENT
    elif hover:
        col = EDIT_TEXT
    else:
        col = EDIT_TEXT_DIM
    if any(ord(c) > 0x7F for c in lab):
        draw_unicode(x, y, lab, col, size=_ui_font_size)
        return text_px_w(lab, _ui_font_size)
    draw_ui_text(x, y, lab, col, scale=scale)
    return ui_text_w(lab, scale)


def draw_swatch(x: int, y: int, color: int, size: int = 0) -> int:
    """色タイル (size×size) を描画。size=0 でテキスト高さに合わせる。返値=幅。"""
    s = size if size > 0 else ui_text_h()
    pyxel.rect(x, y, s, s, color)
    pyxel.rectb(x, y, s, s, EDIT_BORDER)
    return s


def draw_swatch_label(x: int, y: int, color_idx: int, label: str,
                      fg: int | None = None, scale: int = 0) -> int:
    """[色タイル] label を左詰めで描画。返値=描画総幅。"""
    if fg is None:
        fg = EDIT_TEXT
    sz = ui_text_h(scale)
    draw_swatch(x, y, color_idx, sz)
    draw_ui_text(x + sz + 4, y, label, fg, scale=scale)
    return sz + 4 + ui_text_w(label, scale)


# ── リセットボタン (↻) ─────────────────────────────────────────
# pyxel デフォルトフォントは ASCII のみで ↻ を持たないため、TTF (editor_font)
# で描画する。ボタン全体は draw_unicode で "[↻]" として描く。

_RESET_GLYPH = "R"


def reset_btn_w() -> int:
    """↻ リセットボタンの描画幅 (= クリック判定幅)。"""
    return text_px_w(f"[{_RESET_GLYPH}]", _ui_font_size) + 4


def draw_reset_btn(x: int, y: int, h: int, hover: bool = False) -> int:
    """[↻] リセットボタンを (y..y+h) 内で縦中央に描画。返値=幅。"""
    label = f"[{_RESET_GLYPH}]"
    rh = _ui_render_h()
    ty = y + max(0, (h - rh) // 2)
    col = EDIT_TEXT if hover else EDIT_TEXT_DIM
    draw_unicode(x + 2, ty, label, col, size=_ui_font_size)
    return reset_btn_w()


def set_font_base_dir(base_dir: str):
    global _font_base_dir
    _font_base_dir = base_dir


def _resolve_font_path(font_file: str) -> str:
    if not font_file:
        return ""
    if os.path.isabs(font_file) and os.path.exists(font_file):
        return font_file
    if _font_base_dir:
        candidate = os.path.join(_font_base_dir, "assets", "fonts", font_file)
        if os.path.exists(candidate):
            return candidate
    return font_file if os.path.exists(font_file) else ""


def load_pyxel_font(font_file: str, size: int) -> "pyxel.Font | None":
    """pyxel.Font を生成する。フォントファイルを解決して返す。"""
    path = _resolve_font_path(font_file)
    if not path:
        try:
            return pyxel.Font(font_file, size)
        except Exception:
            return None
    try:
        return pyxel.Font(path, size)
    except Exception:
        return None


def _get_sized_font(size: int) -> "pyxel.Font | None":
    """エディタフォントを指定サイズで取得（キャッシュ付き）。"""
    if size <= 0:
        size = _editor_font_size
    if size == _editor_font_size and _editor_font is not None:
        return _editor_font
    cached = _sized_font_cache.get(size)
    if cached is not None:
        return cached
    if not _editor_font_path:
        return _editor_font
    try:
        f = pyxel.Font(_editor_font_path, size)
    except Exception:
        f = None
    if f is not None:
        _sized_font_cache[size] = f
    return f or _editor_font


def set_editor_font(font: "pyxel.Font | None", size: int = 16, path: str = ""):
    """[DEPRECATED] BDF 統一後は使われない。互換のため受取るだけ (legacy TTF
    フォールバックパスとして path だけは保持)。"""
    global _editor_font, _editor_font_path
    _editor_font = font
    if path:
        _editor_font_path = _resolve_font_path(path) or path
    _sized_font_cache.clear()


def set_ui_font_size(size: int):
    """[DEPRECATED] BDF サイズは離散・固定。互換のため受取るが no-op。"""
    pass


# ── フォント描画高さ ─────────────────────────────────────────────
def _font_render_h(size: int) -> int:
    """フォントの実描画高さ。

    BDF が利用可能なら BDF の実サイズ (= ピクセル単位の表示高) を返す。caller の
    縦中央揃え計算と完全に一致する。
    """
    bdf, actual = _get_bdf(size)
    if bdf is not None:
        return int(actual)
    return size * 2

def _ui_render_h() -> int:
    return _font_render_h(_ui_font_size)

def _editor_render_h() -> int:
    return _font_render_h(_editor_font_size)


# ── 動的サイズ関数 ─────────────────────────────────────────────
# pyxel デフォルトフォントの ui_scale 倍 (= ui_text_h()) も考慮し、
# UIラベル領域として常に十分な高さを返す。
def title_bar_h(): return max(_ui_render_h() + 4, ui_text_h() + 6)
def tab_h():       return max(_ui_render_h() + 4, ui_text_h() + 6)
def item_h():      return max(_ui_render_h() + 4, ui_text_h() + 6)
def field_h():     return _ui_render_h() + label_h() + 2
def label_h():     return max(8, _ui_font_size - 4, ui_text_h() + 2)
def anim_fh():     return max(_ui_render_h() + 2, ui_text_h() + 4)

# 全スライダー共通 — ノブ大きさ・トラック幅・行ピッチを全行で統一
def slider_h() -> int:
    """1スライダー描画分の高さ。ラベル(ui_text_h+2) + ノブ領域(16)。"""
    return ui_text_h() + 2 + 16

def slider_pitch() -> int:
    """スライダー行のピッチ。下に1スライダー分の余白を確保 (= 2倍)。"""
    return slider_h() * 2


def text_px_w(text: str, size: int = 0, letter_spacing: int = 0) -> int:
    """テキストの描画幅を計測。

    BDF フォントが利用可能ならその `text_width()` を使う → 実描画と完全一致
    (ボタン重なり問題は出ない)。フォールバックは旧 pyxel.Font または経験則。
    """
    text = _nfc(text)
    spacing = max(0, int(letter_spacing or 0))
    sz = size if size > 0 else _editor_font_size
    bdf, _ = _get_bdf(sz)
    if bdf is not None:
        try:
            return bdf.text_width(text) + spacing * _gap_count(text)
        except Exception:
            pass
    if _editor_font is not None:
        try:
            return _editor_font.text_width(text) + spacing * _gap_count(text)
        except Exception:
            pass
    half = sz // 2 + 1
    return sum(sz if ord(c) > 0x7F else half for c in text) + spacing * _gap_count(text)


# UI 全体のアンチエイリアス有無を一括切替するモジュール変数。
# 既定 False: pyxel の retro/ピクセル美学に合わせ 1bit ハードエッジ。
# - halo (sc35) が出ない
# - 個別グリフの色ブレ (sc37 の "]" 等) が起きない
# - 位置がピクセル単位できっちり揃う
# 大きい dialog 文字など滑らかさを優先したい箇所は per-call で antialias=True
# を渡すか、set_antialias(True) で全体切替できる。
_ui_antialias: bool = False


def set_antialias(enabled: bool) -> None:
    """draw_unicode のアンチエイリアス既定値を切替える。"""
    global _ui_antialias
    _ui_antialias = bool(enabled)


def get_antialias() -> bool:
    return _ui_antialias


def draw_unicode(x: int, y: int, text: str, color: int, size: int = 0,
                 bg_col: "int | None" = None,
                 antialias: "bool | None" = None,
                 letter_spacing: int = 0):
    """日本語を含む文字列を描画。

    BDF フォントが利用可能なら `pyxel.text(..., font)` で直接描画する。BDF は
    事前ビットマップなのでラスタライズ崩れなし、サイズごとに専用デザインで
    クリーンな見た目になる。

    後方互換: `bg_col` / `antialias` 引数は BDF には不要なので無視される。
    """
    if not text:
        return
    text = _nfc(text)
    sz = size if size > 0 else _editor_font_size
    spacing = max(0, int(letter_spacing or 0))
    bdf, _ = _get_bdf(sz)
    if bdf is not None:
        if spacing > 0 and _gap_count(text) > 0:
            cx = int(x)
            iy = int(y)
            last_x = cx
            for ch in text:
                if unicodedata.combining(ch):
                    pyxel.text(last_x, iy, ch, int(color), bdf)
                else:
                    last_x = cx
                    pyxel.text(cx, iy, ch, int(color), bdf)
                    cx += bdf.text_width(ch) + spacing
            return
        pyxel.text(int(x), int(y), text, int(color), bdf)
        return
    # フォールバック: 旧 pyxel.Font (TTF) → pyxel.text 内蔵フォント
    if _editor_font:
        pyxel.text(x, y, text, color, _editor_font)
    else:
        pyxel.text(x, y, text, color)


def draw_panel(x, y, w, h, bg=None, border=None):
    if bg is None:
        bg = EDIT_PANEL
    if border is None:
        border = EDIT_BORDER
    pyxel.rect(x, y, w, h, bg)
    pyxel.rectb(x, y, w, h, border)


def draw_titlebar(x, y, w, title, bg=None, fg=None):
    """タイトルバー: 背景バー + 左詰めテキスト (中央揃えなし)。"""
    if bg is None:
        bg = EDIT_TITLE_BG
    if fg is None:
        fg = EDIT_TEXT
    h = title_bar_h()
    pyxel.rect(x, y, w, h, bg)
    # 上下のパディングを 2px に固定、左詰め
    max_chars = max(1, (w - 8) // (UI_GLYPH_W * _ui_scale))
    if len(title) > max_chars:
        title = title[:max_chars]
    draw_ui_text(x + 4, y + 2, title, fg)


def button_w(label: str, padding: int = 0, scale: int = 0) -> int:
    """[label] テキストボタンの幅。padding は後方互換のため残してあるが未使用。"""
    return text_btn_w(label, scale)


def draw_button(x, y, w, label, h=22, active=False, hover=False, size: int = 0):
    """旧 API 互換: 背景なしテキストボタン [label] を、与えられた (y..y+h) の
    縦範囲で上下中央に配置して描画。横は左詰め (x から開始)。
    クリック判定の幅は呼び出し側で text_btn_w(label) を使うこと。"""
    lab = _bracketed(label)
    fsz = size if size > 0 else _ui_font_size
    if size > 0:
        th = _font_render_h(fsz)
        ty = y + max(0, (h - th) // 2)
        if active:
            col = EDIT_ACCENT
        elif hover:
            col = EDIT_TEXT
        else:
            col = EDIT_TEXT_DIM
        draw_unicode(x + 2, ty, lab, col, size=fsz)
        return
    if any(ord(c) > 0x7F for c in lab):
        th = _ui_render_h()
    else:
        th = text_btn_h()
    ty = y + max(0, (h - th) // 2)
    draw_text_btn(x, ty, label, hover=hover, active=active)


def draw_list_item(x, y, w, label, h=26, selected=False, hover=False):
    """リストアイテムを描画。

    ラベルに非ASCII文字 (日本語等) が含まれる場合は TTF フォント描画に
    フォールバック。英数字のみならデフォルトフォントを ui_scale 倍で描画。
    アンチエイリアス halo を防ぐため、実 row 背景色を bg_col に渡す。
    """
    has_unicode = any(ord(c) > 0x7F for c in label)
    if has_unicode:
        ty = y + max(0, (h - _ui_render_h()) // 2)
        if selected:
            pyxel.rect(x, y, w, h, EDIT_ACCENT)
            draw_unicode(x + 4, ty, label, EDIT_BG, size=_ui_font_size,
                         bg_col=EDIT_ACCENT)
        elif hover:
            pyxel.rect(x, y, w, h, EDIT_BTN_HOVER)
            draw_unicode(x + 4, ty, label, EDIT_TEXT, size=_ui_font_size,
                         bg_col=EDIT_BTN_HOVER)
        else:
            draw_unicode(x + 4, ty, label, EDIT_TEXT_DIM,
                         size=_ui_font_size, bg_col=EDIT_BG)
        return

    th = ui_text_h()
    ty = y + max(0, (h - th) // 2)
    if selected:
        pyxel.rect(x, y, w, h, EDIT_ACCENT)
        draw_ui_text(x + 4, ty, label, EDIT_BG)
    elif hover:
        pyxel.rect(x, y, w, h, EDIT_BTN_HOVER)
        draw_ui_text(x + 4, ty, label, EDIT_TEXT)
    else:
        draw_ui_text(x + 4, ty, label, EDIT_TEXT_DIM)


def draw_field(x, y, w, label, value, active=False, h=32, label_h=0, font_size=0):
    """ラベル(英)＋テキストフィールド(値は日本語対応)。

    label_h <= 0 の場合は globals()['label_h']() を自動で使用。
    label とフィールドが重ならないよう動的に計算する。
    """
    lh = label_h if label_h and label_h > 0 else globals()["label_h"]()
    # ラベル幅がフィールド幅を超える場合は省略
    max_chars = max(1, (w - 4) // (UI_GLYPH_W * _ui_scale))
    disp_label = label if len(label) <= max_chars else label[:max_chars]
    draw_ui_text(x + 2, y + 1, disp_label, EDIT_ACCENT if active else EDIT_TEXT_DIM)
    fy  = y + lh
    ih  = max(0, h - lh)
    pyxel.rect(x, fy, w, ih, EDIT_HIGHLIGHT if active else EDIT_BG)
    pyxel.rectb(x, fy, w, ih, EDIT_ACCENT if active else EDIT_BORDER)
    fsz = font_size if font_size > 0 else _editor_font_size
    rh  = _font_render_h(fsz)
    ty  = fy + max(0, (ih - rh) // 2)
    draw_unicode(x + 3, ty, value, EDIT_TEXT if active else EDIT_TEXT_DIM, size=fsz)


def is_hover(mx, my, x, y, w, h):
    return x <= mx < x + w and y <= my < y + h


def is_clicked(mx, my, x, y, w, h):
    return pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) and is_hover(mx, my, x, y, w, h)


_pointer_frame = -1
_pointer_last_pos: tuple[int, int] | None = None
_pointer_active = False


def pointer_intent_active() -> bool:
    """True only when the pointer was intentionally used this frame.

    Pyxel keeps the last mouse/touch coordinate alive. On handheld Android
    devices this stale coordinate can sit over a SAVE slot or title button and
    steal selection back from the D-pad every frame. Treat hover as meaningful
    only after actual pointer motion, click/tap, or wheel input.
    """
    global _pointer_frame, _pointer_last_pos, _pointer_active
    frame = pyxel.frame_count
    if frame != _pointer_frame:
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        moved = _pointer_last_pos is not None and (mx, my) != _pointer_last_pos
        clicked = (
            pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT)
            or pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT)
            or pyxel.btn(pyxel.MOUSE_BUTTON_LEFT)
            or pyxel.btn(pyxel.MOUSE_BUTTON_RIGHT)
        )
        wheeled = getattr(pyxel, "mouse_wheel", 0) != 0
        _pointer_active = bool(moved or clicked or wheeled)
        _pointer_last_pos = (mx, my)
        _pointer_frame = frame
    return _pointer_active


class NumericSlider:
    """左右ドラッグで数値を変更するスライダーウィジェット。"""

    def __init__(self, min_val, max_val, step=1, is_float=False):
        self.min       = float(min_val)
        self.max       = float(max_val)
        self.step      = float(step)
        self.is_float  = is_float
        self._dragging = False
        self._drag_x0  = 0
        self._val0     = 0.0

    @property
    def dragging(self) -> bool:
        return self._dragging

    def handle(self, x: int, y: int, w: int, h: int,
               mx: int, my: int, val):
        """毎フレーム update() から呼ぶ。値が変化した場合は新しい値を返す。"""
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) and is_hover(mx, my, x, y, w, h):
            self._dragging = True
            self._drag_x0  = mx
            self._val0     = float(val)

        if not pyxel.btn(pyxel.MOUSE_BUTTON_LEFT):
            self._dragging = False

        if self._dragging:
            span    = max(0.001, self.max - self.min)
            delta   = (mx - self._drag_x0) * span / max(1, w)
            raw     = max(self.min, min(self.max, self._val0 + delta))
            snapped = round(raw / self.step) * self.step
            if self.is_float:
                dec = (max(0, -int(math.floor(math.log10(self.step))))
                       if self.step < 1 else 1)
                return round(float(snapped), dec)
            return int(round(snapped))
        return None

    # 値テキスト枠の予約幅 (全スライダー共通) — トラック幅が常に揃うようにする
    VAL_RESERVE_CHARS = 6   # "-99999" や "999.99" を想定

    def draw(self, x: int, y: int, w: int, h: int,
             label: str, val, label_h: int = 0, value_text: str | None = None):
        """毎フレーム draw() から呼ぶ。

        label_h <= 0 で globals()['label_h']() (動的) を使用。
        明示指定でも UI scale に対応するため最低 ui_text_h()+2 を保証する。
        """
        lh = label_h if label_h and label_h > 0 else globals()["label_h"]()
        # ラベルとトラックが重ならないよう、UIスケール下限を強制
        lh = max(lh, ui_text_h() + 2)

        # ラベル幅が w を超える場合は省略
        max_chars = max(1, (w - 4) // (UI_GLYPH_W * _ui_scale))
        disp_label = label if len(label) <= max_chars else label[:max_chars]

        # ラベル (UI scale 倍で描画)
        draw_ui_text(x + 2, y + 1, disp_label,
                     EDIT_ACCENT if self._dragging else EDIT_TEXT_DIM)

        sy = y + lh
        sh = h - lh
        if sh < 4:
            return

        # 値テキスト（右端、UI scale 倍）
        if value_text is not None:
            val_str = value_text
        elif self.is_float:
            dec = (max(0, -int(math.floor(math.log10(self.step))))
                   if self.step < 1 else 1)
            val_str = f"{float(val):.{dec}f}"
        else:
            val_str = str(int(val))
        # 値テキスト枠は全スライダー一律 → トラック幅が常に揃う
        vw = ui_text_w("9" * self.VAL_RESERVE_CHARS) + 2
        vh = ui_text_h()
        draw_ui_text(x + w - ui_text_w(val_str) - 2,
                     sy + max(0, (sh - vh) // 2), val_str, EDIT_TEXT)

        # トラック
        tx  = x + 2
        tw  = max(4, w - vw - 8)
        mid = sy + sh // 2
        pyxel.rect(tx, mid - 1, tw, 3, EDIT_BORDER)

        # ハンドル位置
        span  = max(0.001, self.max - self.min)
        ratio = max(0.0, min(1.0, (float(val) - self.min) / span))
        hx    = tx + int(ratio * max(0, tw - 1))

        # 塗り（左端 → ハンドル）
        if hx > tx:
            pyxel.rect(tx, mid - 1, hx - tx, 3, EDIT_ACCENT)

        # ハンドル
        hw = 5
        hh = max(4, sh - 2)
        pyxel.rect(hx - hw // 2, sy + 1, hw, hh,
                   EDIT_ACCENT if self._dragging else EDIT_BTN_BG)
        pyxel.rectb(hx - hw // 2, sy + 1, hw, hh, EDIT_ACCENT)
