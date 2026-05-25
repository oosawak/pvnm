"""終了確認ダイアログ (インゲーム オーバーレイ)"""
import pyxel
from ui.colors import *
import ui.widgets as _w
from ui.widgets import (
    draw_panel, draw_button, draw_unicode, is_clicked, is_hover,
    title_bar_h,
)

_DW  = 440
_GAP = 8


class QuitDialog:
    """
    終了確認ダイアログ。
    open() で開き、毎フレーム update() / draw() を呼ぶ。
    result に結果が入り active=False になる。
      "save_quit" : 保存して終了
      "quit"      : 保存しないで終了
      "cancel"    : キャンセル
    """

    def __init__(self):
        self.active = False
        self.dirty  = False   # 未保存フラグ（表示用）
        self.result = None

    def open(self, dirty: bool):
        self.active = True
        self.dirty  = dirty
        self.result = None

    def update(self):
        if not self.active:
            return
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self._close("cancel")
            return
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        _BH = max(24, _w._ui_render_h() + 4)
        _BW = 124
        dx, dy = self._pos()
        bx, by = self._btn_origin(dx, dy)
        if is_clicked(mx, my, bx,              by, _BW, _BH):
            self._close("save_quit")
        elif is_clicked(mx, my, bx + _BW + _GAP,  by, _BW, _BH):
            self._close("quit")
        elif is_clicked(mx, my, bx + 2*(_BW+_GAP), by, _BW, _BH):
            self._close("cancel")

    def draw(self):
        if not self.active:
            return
        W, H = pyxel.width, pyxel.height
        _ui_rh = _w._ui_render_h()
        _BH = max(24, _ui_rh + 4)
        _BW = 124
        _DH = title_bar_h() + 30 + _BH + 16
        _tbh = title_bar_h()

        # 薄暗いオーバーレイ
        for y in range(0, H, 2):
            pyxel.line(0, y, W - 1, y, 0)

        dx, dy = self._pos()
        pyxel.rect(dx - 3, dy - 3, _DW + 6, _DH + 6, EDIT_BORDER)
        draw_panel(dx, dy, _DW, _DH)

        # タイトルバー
        pyxel.rect(dx, dy, _DW, _tbh, EDIT_TITLE_BG)
        draw_unicode(dx + 6, dy + (_tbh - _ui_rh) // 2,
                     "終了の確認", EDIT_TEXT, size=_w._ui_font_size)

        # メッセージ
        msg = ("未保存の変更があります。" if self.dirty
               else "PVNMを終了します。")
        pyxel.text(dx + 8, dy + _tbh + 8, msg, EDIT_TEXT_DIM)

        # ボタン
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        bx, by = self._btn_origin(dx, dy)
        _b = [
            (bx,               "保存して終了"),
            (bx + _BW + _GAP,  "保存せず終了"),
            (bx + 2*(_BW+_GAP),"キャンセル"),
        ]
        for bxi, label in _b:
            draw_button(bxi, by, _BW, label, h=_BH,
                        hover=is_hover(mx, my, bxi, by, _BW, _BH))

    # ── 内部ヘルパー ────────────────────────────────────────

    def _pos(self):
        W, H = pyxel.width, pyxel.height
        _BH = max(24, _w._ui_render_h() + 4)
        _DH = title_bar_h() + 30 + _BH + 16
        return (W - _DW) // 2, (H - _DH) // 2

    def _btn_origin(self, dx, dy):
        _BH = max(24, _w._ui_render_h() + 4)
        _BW = 124
        _DH = title_bar_h() + 30 + _BH + 16
        total = 3 * _BW + 2 * _GAP
        bx = dx + (_DW - total) // 2
        by = dy + _DH - _BH - 10
        return bx, by

    def _close(self, result: str):
        self.result = result
        self.active = False
