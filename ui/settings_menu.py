"""統合設定メニュー: TITLE / ENDING / COLOR をツリー構造で一元管理"""
import pyxel
import ui.widgets as _w
from ui.widgets import (
    draw_panel, draw_button, draw_unicode,
    ui_text_h, ui_text_w,
    is_hover, is_clicked, _font_render_h, load_pyxel_font,
    button_w,
)
from ui.colors import *

_FONT_SIZE = 14

# ── レイアウト ─────────────────────────────────────────────────
MARGIN_X = 40
MARGIN_Y = 20
PAD = 10

# ツリーカテゴリ
_CATEGORIES = [
    ("project",  "PROJECT"),
    ("title",    "TITLE CONFIG"),
    ("ending",   "ENDING CONFIG"),
    ("gallery",  "CG GALLERY"),
    ("extra_text", "EXTRA TEXT"),
    ("color",    "COLOR CONFIG"),
    ("speakers", "SPEAKER COLORS"),
    ("tools",    "TOOLS"),
    ("export",   "EXPORT"),
]

_EXPORT_ACTIONS = [
    ("pyxapp", "PYXAPP"),
    ("pyxapp_external", "PYXAPP + ASSETS"),
    ("macos", "macOS APP"),
    ("windows_exe", "WINDOWS EXE"),
    ("web", "WEB HTML"),
    ("capacitor", "ANDROID PROJECT"),
    ("android_debug_apk", "ANDROID APK DEBUG"),
    ("android_release_apk", "ANDROID APK RELEASE"),
]

_PROJECT_ACTIONS = [
    ("save", "SAVE PROJECT"),
    ("save_as", "SAVE AS PROJECT"),
]

_TOOLS_ACTIONS = [
    ("palette", "VN PALETTE TOOL"),
]


def _header_h():
    return _font_render_h(_FONT_SIZE) + 10


def _cat_h():
    return _font_render_h(_FONT_SIZE) + 12


def _btn_h():
    return _font_render_h(_FONT_SIZE) + 8


def _tree_w() -> int:
    """ラベル最長 + マーカー + パディングが収まる幅。"""
    longest = max((_w.text_px_w("> " + lbl, _FONT_SIZE)
                   for _, lbl in _CATEGORIES), default=160)
    return longest + 24


class SettingsMenu:
    """統合設定画面。各カテゴリ選択で対応エディタへ遷移。

    result:
        None      — まだ操作中
        "title"   — TITLE Config を開く
        "ending"  — ENDING Config を開く
        "color"   — Color Config を開く (エディタ + ダイアログ統合)
        "project:*" — Save / Save As action を開始
        "export:*"— Export action を開始
        "tool:*"  — Tool action を開始
        "closed"  — 閉じた (ESC / CLOSE ボタン)
    """

    def __init__(self):
        self.active = False
        self.result = None
        self._hover = -1
        self._selected = -1
        self._font = load_pyxel_font("IPA_PGothic.ttf", 14)

    def open(self, title_config: dict = None):
        # title_config 引数は呼び出し側 (main.py) との後方互換のため受け取るが、
        # 設定値は親側で保持し、TITLE Config を開く際に TitleConfigEditor へ渡す。
        self.active = True
        self.result = None
        self._hover = -1
        self._selected = -1

    def update(self):
        if not self.active:
            return

        mx, my = pyxel.mouse_x, pyxel.mouse_y

        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self.result = "closed"
            self.active = False
            return

        W, H = pyxel.width, pyxel.height
        px, py = MARGIN_X, MARGIN_Y
        pw = W - MARGIN_X * 2
        ph = H - MARGIN_Y * 2
        hh = _header_h()
        ch = _cat_h()
        tw = _tree_w()

        tree_x = px + PAD
        tree_y = py + hh + PAD

        self._hover = -1
        for i, (key, _label) in enumerate(_CATEGORIES):
            cy = tree_y + i * ch
            if is_hover(mx, my, tree_x, cy, tw, ch - 2):
                self._hover = i
                if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
                    self._selected = i
                    if key in ("project", "export", "tools"):
                        return
                    self.result = key
                    return

        selected_key = self._selected_key()
        if selected_key == "project":
            for action, x, y, w, h in self._project_button_rects(
                    px, py, pw, ph, hh, tw):
                if is_clicked(mx, my, x, y, w, h):
                    self.result = "project:" + action
                    return
        elif selected_key == "export":
            for action, x, y, w, h in self._export_button_rects(
                    px, py, pw, ph, hh, tw):
                if is_clicked(mx, my, x, y, w, h):
                    self.result = "export:" + action
                    return
        elif selected_key == "tools":
            for action, x, y, w, h in self._tool_button_rects(
                    px, py, pw, ph, hh, tw):
                if is_clicked(mx, my, x, y, w, h):
                    self.result = "tool:" + action
                    return

        # CLOSE ボタン
        bh = _btn_h()
        cw = max(64, button_w("CLOSE"))
        close_x = px + pw - PAD - cw
        close_y = py + ph - bh - 4
        if is_clicked(mx, my, close_x, close_y, cw, bh):
            self.result = "closed"
            self.active = False
            return

    def draw(self):
        if not self.active:
            return

        W, H = pyxel.width, pyxel.height
        px, py = MARGIN_X, MARGIN_Y
        pw = W - MARGIN_X * 2
        ph = H - MARGIN_Y * 2
        hh = _header_h()
        ch = _cat_h()
        tw = _tree_w()

        draw_panel(px, py, pw, ph, bg=EDIT_PANEL, border=EDIT_BORDER)

        # ヘッダ
        pyxel.rect(px + 1, py + 1, pw - 2, hh - 2, EDIT_TITLE_BG)
        th = _font_render_h(_FONT_SIZE)
        draw_unicode(px + 8, py + max(1, (hh - th) // 2),
                     "SETTINGS  (ESC=Close)", EDIT_TEXT, size=_FONT_SIZE)

        mx, my = pyxel.mouse_x, pyxel.mouse_y

        # ツリーリスト
        tree_x = px + PAD
        tree_y = py + hh + PAD
        tree_h = len(_CATEGORIES) * ch + 4
        pyxel.rect(tree_x, tree_y - 2, tw, tree_h, EDIT_BG)
        pyxel.rectb(tree_x, tree_y - 2, tw, tree_h, EDIT_BORDER)

        for i, (_key, label) in enumerate(_CATEGORIES):
            cy = tree_y + i * ch
            selected = (self._selected == i)
            hover = (self._hover == i) and not selected

            if selected:
                pyxel.rect(tree_x + 1, cy, tw - 2, ch - 2, EDIT_ACCENT)
                fg = EDIT_BG
            elif hover:
                pyxel.rect(tree_x + 1, cy, tw - 2, ch - 2, EDIT_BTN_HOVER)
                fg = EDIT_TEXT
            else:
                fg = EDIT_TEXT_DIM

            marker = "> " if selected else "  "
            ty = cy + max(0, (ch - _font_render_h(_FONT_SIZE)) // 2)
            draw_unicode(tree_x + 8, ty, marker + label, fg, size=_FONT_SIZE)

        self._draw_export_detail(px, py, pw, ph, hh, tw)
        self._draw_project_detail(px, py, pw, ph, hh, tw)
        self._draw_tools_detail(px, py, pw, ph, hh, tw)

        # CLOSE ボタン
        bh = _btn_h()
        cw = max(64, button_w("CLOSE"))
        close_x = px + pw - PAD - cw
        close_y = py + ph - bh - 4
        ch_ = is_hover(mx, my, close_x, close_y, cw, bh)
        draw_button(close_x, close_y, cw, "CLOSE", h=bh, hover=ch_,
                    size=_FONT_SIZE)

    def _export_button_rects(self, px: int, py: int, pw: int, ph: int,
                             hh: int, tw: int):
        detail_x = px + PAD + tw + PAD
        detail_y = py + hh + PAD - 2
        detail_w = px + pw - PAD - detail_x
        bh = _btn_h()
        gap = 8
        x = detail_x + PAD
        y = detail_y + PAD + _font_render_h(_FONT_SIZE) + 10
        w = max(180, min(detail_w - PAD * 2, button_w("ANDROID APK RELEASE") + 32))
        for action, _label in _EXPORT_ACTIONS:
            yield action, x, y, w, bh
            y += bh + gap

    def _project_button_rects(self, px: int, py: int, pw: int, ph: int,
                              hh: int, tw: int):
        detail_x = px + PAD + tw + PAD
        detail_y = py + hh + PAD - 2
        detail_w = px + pw - PAD - detail_x
        bh = _btn_h()
        gap = 8
        x = detail_x + PAD
        y = detail_y + PAD + _font_render_h(_FONT_SIZE) + 10
        w = max(180, min(detail_w - PAD * 2,
                         button_w("SAVE AS PROJECT") + 32))
        for action, _label in _PROJECT_ACTIONS:
            yield action, x, y, w, bh
            y += bh + gap

    def _tool_button_rects(self, px: int, py: int, pw: int, ph: int,
                           hh: int, tw: int):
        detail_x = px + PAD + tw + PAD
        detail_y = py + hh + PAD - 2
        detail_w = px + pw - PAD - detail_x
        bh = _btn_h()
        gap = 8
        x = detail_x + PAD
        y = detail_y + PAD + _font_render_h(_FONT_SIZE) + 10
        w = max(180, min(detail_w - PAD * 2,
                         button_w("VN PALETTE TOOL") + 32))
        for action, _label in _TOOLS_ACTIONS:
            yield action, x, y, w, bh
            y += bh + gap

    def _selected_key(self) -> str | None:
        if 0 <= self._selected < len(_CATEGORIES):
            return _CATEGORIES[self._selected][0]
        return None

    def _draw_export_detail(self, px: int, py: int, pw: int, ph: int,
                            hh: int, tw: int):
        detail_x = px + PAD + tw + PAD
        detail_y = py + hh + PAD - 2
        detail_w = px + pw - PAD - detail_x
        detail_h = ph - hh - PAD - _btn_h() - 16
        if detail_w <= 80 or detail_h <= 40:
            return

        pyxel.rect(detail_x, detail_y, detail_w, detail_h, EDIT_BG)
        pyxel.rectb(detail_x, detail_y, detail_w, detail_h, EDIT_BORDER)

        if self._selected_key() != "export":
            return

        title_y = detail_y + PAD
        draw_unicode(detail_x + PAD, title_y, "EXPORT",
                     EDIT_TEXT, size=_FONT_SIZE)

        mx, my = pyxel.mouse_x, pyxel.mouse_y
        for action, x, y, w, h in self._export_button_rects(
                px, py, pw, ph, hh, tw):
            label = next((lbl for key, lbl in _EXPORT_ACTIONS if key == action),
                         action.upper())
            draw_button(x, y, w, label, h=h,
                        hover=is_hover(mx, my, x, y, w, h),
                        size=_FONT_SIZE)

    def _draw_project_detail(self, px: int, py: int, pw: int, ph: int,
                             hh: int, tw: int):
        if self._selected_key() != "project":
            return

        detail_x = px + PAD + tw + PAD
        detail_y = py + hh + PAD - 2
        detail_w = px + pw - PAD - detail_x
        detail_h = ph - hh - PAD - _btn_h() - 16
        if detail_w <= 80 or detail_h <= 40:
            return

        pyxel.rect(detail_x, detail_y, detail_w, detail_h, EDIT_BG)
        pyxel.rectb(detail_x, detail_y, detail_w, detail_h, EDIT_BORDER)

        title_y = detail_y + PAD
        draw_unicode(detail_x + PAD, title_y, "PROJECT",
                     EDIT_TEXT, size=_FONT_SIZE)

        mx, my = pyxel.mouse_x, pyxel.mouse_y
        for action, x, y, w, h in self._project_button_rects(
                px, py, pw, ph, hh, tw):
            label = next((lbl for key, lbl in _PROJECT_ACTIONS
                          if key == action), action.upper())
            draw_button(x, y, w, label, h=h,
                        hover=is_hover(mx, my, x, y, w, h),
                        size=_FONT_SIZE)

    def _draw_tools_detail(self, px: int, py: int, pw: int, ph: int,
                           hh: int, tw: int):
        if self._selected_key() != "tools":
            return

        detail_x = px + PAD + tw + PAD
        detail_y = py + hh + PAD - 2
        detail_w = px + pw - PAD - detail_x
        detail_h = ph - hh - PAD - _btn_h() - 16
        if detail_w <= 80 or detail_h <= 40:
            return

        pyxel.rect(detail_x, detail_y, detail_w, detail_h, EDIT_BG)
        pyxel.rectb(detail_x, detail_y, detail_w, detail_h, EDIT_BORDER)

        title_y = detail_y + PAD
        draw_unicode(detail_x + PAD, title_y, "TOOLS",
                     EDIT_TEXT, size=_FONT_SIZE)

        mx, my = pyxel.mouse_x, pyxel.mouse_y
        for action, x, y, w, h in self._tool_button_rects(
                px, py, pw, ph, hh, tw):
            label = next((lbl for key, lbl in _TOOLS_ACTIONS if key == action),
                         action.upper())
            draw_button(x, y, w, label, h=h,
                        hover=is_hover(mx, my, x, y, w, h),
                        size=_FONT_SIZE)
