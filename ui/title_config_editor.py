"""タイトル設定画面 (720×480 フルスクリーン)

タイトルテキスト / 背景画像 / BGM / BGM 音量 / BGM ループを設定。
ファイル選択は親 (main.py) 側のファイルピッカーへ委譲する。
"""
import os
import pyxel
from ui.colors import (
    EDIT_BG, EDIT_PANEL, EDIT_BORDER, EDIT_TEXT, EDIT_TEXT_DIM, EDIT_ACCENT,
    EDIT_BTN_HOVER, EDIT_TITLE_BG,
)
import ui.widgets as _w
from ui.widgets import (
    draw_panel, draw_titlebar, draw_button, draw_unicode,
    draw_ui_text, ui_text_h,
    is_hover, is_clicked, NumericSlider,
    title_bar_h, label_h, slider_h,
    text_btn_w,
)
from engine.title_colors import (
    TITLE_BUTTON_COLOR_ROLES,
    normalize_button_colors,
)
from ui.confirm_dialog import ConfirmDialog

# レイアウト
_BTN_H   = 32
_PANEL_H = 480 - _BTN_H
_FONT_SIZE = 14

# 行レイアウト
_MARGIN_X = 16
_GAP      = 8
_COLOR_ROLE_ROW_H = 24
_COLOR_GRID_CELL = 10
_COLOR_GRID_COLS = 16
_COLOR_GRID_ROWS = 16


def _hex_for_idx(idx: int) -> str:
    if not isinstance(idx, int) or idx < 0 or idx >= len(pyxel.colors):
        return "------"
    return f"{pyxel.colors[idx]:06X}"


def _compute_display_order() -> list[int]:
    items = [(i, pyxel.colors[i]) for i in range(256)]
    items.sort(key=lambda it: (it[1], it[0]))
    return [it[0] for it in items]


class TitleConfigEditor:
    """タイトル画面 (Title Screen) の設定エディタ。

    result:
        None         — 操作中
        "saved"      — SAVE & CLOSE
        "cancelled"  — CANCEL / ESC
        "bg_pick"    — 背景画像をファイルピッカーで選びたい (親が処理)
        "bgm_pick"   — BGM をファイルピッカーで選びたい (親が処理)
        "preview"    — 現在の設定でタイトル画面をプレビュー再生
    """

    def __init__(self):
        self.active = False
        self.result = None

        self._cfg = {}        # 編集中の値
        self._saved = {}      # REVERT / CANCEL 用
        self._sl_bgm_vol = NumericSlider(1, 10, 1, False)
        self._color_roles = list(TITLE_BUTTON_COLOR_ROLES)
        self._sel_color_role = self._color_roles[0][0]
        self._display_order: list[int] = list(range(256))
        self._discard_confirm = ConfirmDialog()

    # ── 公開 API ──────────────────────────────────────────────
    def open(self, title_config: dict = None):
        self.active = True
        self.result = None
        self._cfg = dict(title_config or {})
        self._cfg.setdefault("bg_image", "")
        self._cfg.setdefault("bg_fullscreen", False)
        self._cfg.setdefault("bgm_file", "")
        self._cfg.setdefault("bgm_volume", 7)
        self._cfg.setdefault("bgm_loop", True)
        self._cfg["button_colors"] = normalize_button_colors(
            self._cfg.get("button_colors"))
        self._saved = dict(self._cfg)
        self._saved["button_colors"] = dict(self._cfg["button_colors"])
        self._sel_color_role = self._color_roles[0][0]
        self._display_order = _compute_display_order()

    def get_config(self) -> dict:
        out = dict(self._cfg)
        out["button_colors"] = normalize_button_colors(
            self._cfg.get("button_colors"))
        return out

    def _saved_config(self) -> dict:
        out = dict(self._saved)
        out["button_colors"] = normalize_button_colors(
            self._saved.get("button_colors"))
        return out

    def _dirty(self) -> bool:
        return self.get_config() != self._saved_config()

    def refresh_palette_grid(self):
        """Rebuild the 16x16 palette grid from the current master palette."""
        self._display_order = _compute_display_order()

    def set_bg_image(self, path: str):
        self._cfg["bg_image"] = path

    def set_bgm_file(self, path: str):
        self._cfg["bgm_file"] = path

    def _revert(self):
        self._cfg = dict(self._saved)
        self._cfg["button_colors"] = dict(self._saved.get(
            "button_colors", normalize_button_colors()))

    def _finish_cancelled(self):
        self._revert()
        self.result = "cancelled"
        self.active = False

    def _request_cancel(self):
        if self._dirty():
            self._discard_confirm.open(
                "UNSAVED CHANGES",
                "Title config has unsaved edits.\n"
                "Discard changes and return?",
                ok_label="DISCARD",
                cancel_label="KEEP EDITING",
            )
        else:
            self._finish_cancelled()

    def _update_discard_confirm(self) -> bool:
        if not self._discard_confirm.active:
            return False
        self._discard_confirm.update()
        result = self._discard_confirm.result
        if result == "ok":
            self._discard_confirm.result = None
            self._finish_cancelled()
        elif result == "cancel":
            self._discard_confirm.result = None
        return True

    # ── 内部レイアウト ─────────────────────────────────────────
    def _row_h(self) -> int:
        return max(32, _w._font_render_h(_FONT_SIZE) + 8)

    def _layout(self):
        """各行の Y 位置を計算して返す。"""
        x  = _MARGIN_X
        w  = 720 - _MARGIN_X * 2
        y  = title_bar_h() + 12
        rh = self._row_h()
        sh = slider_h()
        rows = {}

        rows["bg_image"]   = (x, y, w, rh)
        y += rh + _GAP

        rows["bg_fullscreen"] = (x, y, w, rh)
        y += rh + _GAP

        rows["bgm_file"]   = (x, y, w, rh)
        y += rh + _GAP

        rows["bgm_volume"] = (x, y, w, sh)
        y += sh + _GAP

        rows["bgm_loop"]   = (x, y, w, rh)
        y += rh + _GAP + 10

        rows["button_colors"] = (x, y, w, _PANEL_H - y - 8)
        return rows

    # ── update ────────────────────────────────────────────────
    def update(self):
        if not self.active:
            return
        if self._update_discard_confirm():
            return
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        right_clicked = pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT)

        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self._request_cancel()
            return

        rows = self._layout()

        # EDIT_BG IMAGE ボタン
        x, y, w, h = rows["bg_image"]
        if is_clicked(mx, my, x, y, w, h):
            self.result = "bg_pick"
            return
        if right_clicked and is_hover(mx, my, x, y, w, h):
            self._cfg["bg_image"] = ""
            return

        # EDIT_BG FULLSCREEN チェックボックス
        x, y, w, h = rows["bg_fullscreen"]
        fs_on = bool(self._cfg.get("bg_fullscreen", False))
        fs_lbl = ("[X] BACKGROUND FULLSCREEN" if fs_on
                  else "[ ] BACKGROUND FULLSCREEN")
        fs_w = max(80, _w.text_px_w(fs_lbl, _FONT_SIZE) + 14)
        if is_clicked(mx, my, x, y, fs_w, h):
            self._cfg["bg_fullscreen"] = not fs_on

        # BGM ボタン
        x, y, w, h = rows["bgm_file"]
        if is_clicked(mx, my, x, y, w, h):
            self.result = "bgm_pick"
            return
        if right_clicked and is_hover(mx, my, x, y, w, h):
            self._cfg["bgm_file"] = ""
            return

        # BGM VOLUME スライダー
        x, y, w, h = rows["bgm_volume"]
        nv = self._sl_bgm_vol.handle(x, y, w, h, mx, my,
                                     int(self._cfg.get("bgm_volume", 7)))
        if nv is not None:
            self._cfg["bgm_volume"] = int(nv)

        # BGM LOOP チェックボックス
        x, y, w, h = rows["bgm_loop"]
        loop_on = bool(self._cfg.get("bgm_loop", True))
        loop_lbl = ("[X] BACKGROUND MUSIC LOOP" if loop_on
                    else "[ ] BACKGROUND MUSIC LOOP")
        loop_w = max(80, _w.text_px_w(loop_lbl, _FONT_SIZE) + 14)
        if is_clicked(mx, my, x, y, loop_w, h):
            self._cfg["bgm_loop"] = not loop_on

        # BUTTON COLORS: role list + palette grid
        self._update_button_colors(mx, my, rows["button_colors"])

        # ── 下部ボタンバー ──
        bar_y = _PANEL_H + (_BTN_H - 20) // 2
        bw = 126
        if is_clicked(mx, my, 4, bar_y, bw, 20):
            self.result = "saved"
            self.active = False
        if is_clicked(mx, my, 134, bar_y, bw, 20):
            self._revert()
        if is_clicked(mx, my, 264, bar_y, 80, 20):
            self._request_cancel()
        # PLAY PREVIEW
        if is_clicked(mx, my, 350, bar_y, 110, 20):
            self.result = "preview"

    def _update_button_colors(self, mx: int, my: int, rect: tuple):
        x, y, w, h = rect
        role_x, role_y, role_w = x + 8, y + 24, 250
        for i, (key, _label, _desc, _default) in enumerate(self._color_roles):
            ry = role_y + i * _COLOR_ROLE_ROW_H
            if is_clicked(mx, my, role_x, ry, role_w, _COLOR_ROLE_ROW_H):
                self._sel_color_role = key
                return

        gx, gy = self._palette_grid_origin(rect)
        grid_w = _COLOR_GRID_COLS * _COLOR_GRID_CELL
        grid_h = _COLOR_GRID_ROWS * _COLOR_GRID_CELL
        if is_clicked(mx, my, gx, gy, grid_w, grid_h):
            col = (mx - gx) // _COLOR_GRID_CELL
            row = (my - gy) // _COLOR_GRID_CELL
            pos = row * _COLOR_GRID_COLS + col
            if 0 <= pos < len(self._display_order):
                self._button_colors()[self._sel_color_role] = self._display_order[pos]

    def _button_colors(self) -> dict:
        colors = self._cfg.get("button_colors")
        if not isinstance(colors, dict):
            colors = normalize_button_colors(colors)
            self._cfg["button_colors"] = colors
        return colors

    def _color_idx(self, role: str) -> int:
        return normalize_button_colors(self._button_colors()).get(role, 0)

    def _palette_grid_origin(self, rect: tuple) -> tuple[int, int]:
        x, y, _w, _h = rect
        return x + 278, y + 44

    # ── draw ──────────────────────────────────────────────────
    def draw(self):
        if not self.active:
            return
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        pyxel.cls(EDIT_BG)

        draw_panel(0, 0, 720, _PANEL_H)
        draw_titlebar(0, 0, 720, "TITLE CONFIG")

        rows = self._layout()
        lh = label_h()

        # EDIT_BG IMAGE
        x, y, w, h = rows["bg_image"]
        bg = self._cfg.get("bg_image", "")
        bg_name = os.path.basename(bg) if bg else ""
        bg_lbl = (f"[BACKGROUND IMAGE]:{bg_name}" if bg_name
                  else "[BACKGROUND IMAGE]")
        draw_button(x, y, w, bg_lbl, h=h,
                    hover=is_hover(mx, my, x, y, w, h),
                    size=_FONT_SIZE)

        # EDIT_BG FULLSCREEN
        x, y, w, h = rows["bg_fullscreen"]
        fs_on = bool(self._cfg.get("bg_fullscreen", False))
        fs_lbl = ("[X] BACKGROUND FULLSCREEN" if fs_on
                  else "[ ] BACKGROUND FULLSCREEN")
        fs_w = max(80, _w.text_px_w(fs_lbl, _FONT_SIZE) + 14)
        draw_button(x, y, fs_w, fs_lbl, h=h,
                    active=fs_on,
                    hover=is_hover(mx, my, x, y, fs_w, h),
                    size=_FONT_SIZE)

        # BGM FILE
        x, y, w, h = rows["bgm_file"]
        bgm = self._cfg.get("bgm_file", "")
        bgm_name = os.path.basename(bgm) if bgm else ""
        bgm_lbl = (f"[BACKGROUND MUSIC]:{bgm_name}" if bgm_name
                   else "[BACKGROUND MUSIC]")
        draw_button(x, y, w, bgm_lbl, h=h,
                    hover=is_hover(mx, my, x, y, w, h),
                    size=_FONT_SIZE)

        # BGM VOLUME
        x, y, w, h = rows["bgm_volume"]
        cur_vol = int(self._cfg.get("bgm_volume", 7))
        self._sl_bgm_vol.draw(x, y, w, h,
                              "BACKGROUND MUSIC VOLUME",
                              cur_vol, label_h=lh)

        # BGM LOOP
        x, y, w, h = rows["bgm_loop"]
        loop_on = bool(self._cfg.get("bgm_loop", True))
        loop_lbl = ("[X] BACKGROUND MUSIC LOOP" if loop_on
                    else "[ ] BACKGROUND MUSIC LOOP")
        loop_w = max(80, _w.text_px_w(loop_lbl, _FONT_SIZE) + 14)
        draw_button(x, y, loop_w, loop_lbl, h=h,
                    active=loop_on,
                    hover=is_hover(mx, my, x, y, loop_w, h),
                    size=_FONT_SIZE)

        self._draw_button_colors(mx, my, rows["button_colors"])

        # ── 下部ツールバー ──
        pyxel.rect(0, _PANEL_H, 720, _BTN_H, EDIT_TITLE_BG)
        pyxel.line(0, _PANEL_H, 720, _PANEL_H, EDIT_BORDER)

        bar_y = _PANEL_H + (_BTN_H - 20) // 2
        bw = 126
        draw_button(4,   bar_y, bw, "SAVE & CLOSE", h=20,
                    hover=is_hover(mx, my, 4,   bar_y, bw, 20),
                    size=_FONT_SIZE)
        draw_button(134, bar_y, bw, "REVERT ALL",   h=20,
                    hover=is_hover(mx, my, 134, bar_y, bw, 20),
                    size=_FONT_SIZE)
        draw_button(264, bar_y, 80, "CANCEL",       h=20,
                    hover=is_hover(mx, my, 264, bar_y, 80, 20),
                    size=_FONT_SIZE)
        draw_button(350, bar_y, 110, "PLAY PREVIEW", h=20,
                    hover=is_hover(mx, my, 350, bar_y, 110, 20),
                    size=_FONT_SIZE)
        draw_unicode(470, _PANEL_H + (_BTN_H - 10) // 2,
                     "ESC = CANCEL", EDIT_TEXT_DIM, size=10)

        # カーソル
        pyxel.line(mx - 4, my, mx + 4, my, 7)
        pyxel.line(mx, my - 4, mx, my + 4, 7)
        self._discard_confirm.draw()

    def _draw_button_colors(self, mx: int, my: int, rect: tuple):
        x, y, w, h = rect
        pyxel.rect(x, y, w, h, EDIT_PANEL)
        pyxel.rectb(x, y, w, h, EDIT_BORDER)
        draw_unicode(x + 8, y + 5, "BUTTON COLORS", EDIT_ACCENT,
                     size=_FONT_SIZE)

        role_x, role_y, role_w = x + 8, y + 24, 250
        for i, (key, label, _desc, _default) in enumerate(self._color_roles):
            ry = role_y + i * _COLOR_ROLE_ROW_H
            selected = (key == self._sel_color_role)
            hover = is_hover(mx, my, role_x, ry, role_w, _COLOR_ROLE_ROW_H)
            bg = EDIT_ACCENT if selected else (EDIT_BTN_HOVER if hover else EDIT_BG)
            fg = EDIT_BG if selected else EDIT_TEXT
            pyxel.rect(role_x, ry, role_w, _COLOR_ROLE_ROW_H - 1, bg)
            pyxel.rectb(role_x, ry, role_w, _COLOR_ROLE_ROW_H - 1, EDIT_BORDER)
            idx = self._color_idx(key)
            pyxel.rect(role_x + 6, ry + 6, 12, 12, idx)
            pyxel.rectb(role_x + 6, ry + 6, 12, 12, EDIT_BORDER)
            draw_unicode(role_x + 24, ry + 4, label, fg, size=12)
            draw_unicode(role_x + role_w - 48, ry + 4, str(idx), fg, size=12)

        sel_label = ""
        sel_desc = ""
        for key, label, desc, _default in self._color_roles:
            if key == self._sel_color_role:
                sel_label, sel_desc = label, desc
                break
        sel_idx = self._color_idx(self._sel_color_role)
        detail_x = x + 452
        detail_y = y + 44
        detail_w = w - (detail_x - x) - 8
        pyxel.rect(detail_x, detail_y, detail_w, 66, EDIT_BG)
        pyxel.rectb(detail_x, detail_y, detail_w, 66, EDIT_BORDER)
        pyxel.rect(detail_x + 8, detail_y + 8, 36, 36, sel_idx)
        pyxel.rectb(detail_x + 8, detail_y + 8, 36, 36, EDIT_BORDER)
        draw_unicode(detail_x + 52, detail_y + 6, sel_label, EDIT_TEXT,
                     size=12)
        draw_unicode(detail_x + 52, detail_y + 26,
                     f"IDX {sel_idx}  #{_hex_for_idx(sel_idx)}",
                     EDIT_TEXT_DIM, size=12)
        draw_unicode(detail_x + 8, detail_y + 48, sel_desc, EDIT_TEXT_DIM,
                     size=10)

        gx, gy = self._palette_grid_origin(rect)
        pyxel.rectb(gx - 1, gy - 1,
                    _COLOR_GRID_COLS * _COLOR_GRID_CELL + 2,
                    _COLOR_GRID_ROWS * _COLOR_GRID_CELL + 2,
                    EDIT_BORDER)
        for pos, idx in enumerate(self._display_order[:256]):
            cx = gx + (pos % _COLOR_GRID_COLS) * _COLOR_GRID_CELL
            cy = gy + (pos // _COLOR_GRID_COLS) * _COLOR_GRID_CELL
            pyxel.rect(cx, cy, _COLOR_GRID_CELL, _COLOR_GRID_CELL, idx)
            if idx == sel_idx:
                pyxel.rectb(cx, cy, _COLOR_GRID_CELL, _COLOR_GRID_CELL,
                            EDIT_TEXT)
