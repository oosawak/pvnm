"""汎用確認ダイアログ (インゲーム オーバーレイ)"""
import pyxel
from ui.colors import *
import ui.widgets as _w
from ui.widgets import (
    draw_panel, draw_button, draw_unicode, is_clicked, is_hover,
    title_bar_h, text_px_w,
)

_DW  = 440
_GAP = 8
_PAD_X = 10
_PAD_Y = 8


class ConfirmDialog:
    """
    はい/いいえ の確認ダイアログ。
    open(title, message, ok_label="OK", cancel_label="CANCEL") で開き、
    毎フレーム update() / draw() を呼ぶ。
    result に "ok" または "cancel" が入り active=False になる。
    """

    def __init__(self):
        self.active = False
        self.result = None
        self._title = ""
        self._message = ""
        self._ok_label = "OK"
        self._cancel_label = "CANCEL"

    def open(self, title: str, message: str,
             ok_label: str = "OK", cancel_label: str = "CANCEL"):
        self.active = True
        self.result = None
        self._title = title
        self._message = message
        self._ok_label = ok_label
        self._cancel_label = cancel_label

    def _message_lines(self):
        max_w = _DW - _PAD_X * 2
        out = []
        for raw in str(self._message).splitlines() or [""]:
            line = ""
            for ch in raw:
                test = line + ch
                if line and text_px_w(test, _w._ui_font_size) > max_w:
                    out.append(line)
                    line = ch
                else:
                    line = test
            out.append(line)
        return out

    def _dialog_height(self):
        _BH = max(24, _w._ui_render_h() + 4)
        line_h = _w._ui_render_h() + 4
        msg_h = max(line_h, len(self._message_lines()) * line_h)
        return title_bar_h() + _PAD_Y + msg_h + 12 + _BH + 12

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
        if is_clicked(mx, my, bx, by, _BW, _BH):
            self._close("ok")
        elif is_clicked(mx, my, bx + _BW + _GAP, by, _BW, _BH):
            self._close("cancel")

    def draw(self):
        if not self.active:
            return
        W, H = pyxel.width, pyxel.height
        _ui_rh = _w._ui_render_h()
        _BH = max(24, _ui_rh + 4)
        _BW = 124
        _DH = self._dialog_height()
        _tbh = title_bar_h()

        for y in range(0, H, 2):
            pyxel.line(0, y, W - 1, y, 0)

        dx, dy = self._pos()
        pyxel.rect(dx - 3, dy - 3, _DW + 6, _DH + 6, EDIT_BORDER)
        draw_panel(dx, dy, _DW, _DH)

        pyxel.rect(dx, dy, _DW, _tbh, EDIT_TITLE_BG)
        draw_unicode(dx + 6, dy + (_tbh - _ui_rh) // 2,
                     self._title, EDIT_TEXT, size=_w._ui_font_size)

        line_h = _ui_rh + 4
        ty = dy + _tbh + _PAD_Y
        for line in self._message_lines():
            draw_unicode(dx + _PAD_X, ty, line, EDIT_TEXT_DIM,
                         size=_w._ui_font_size)
            ty += line_h

        mx, my = pyxel.mouse_x, pyxel.mouse_y
        bx, by = self._btn_origin(dx, dy)
        draw_button(bx, by, _BW, self._ok_label, h=_BH,
                    hover=is_hover(mx, my, bx, by, _BW, _BH))
        draw_button(bx + _BW + _GAP, by, _BW, self._cancel_label, h=_BH,
                    hover=is_hover(mx, my, bx + _BW + _GAP, by, _BW, _BH))

    def _pos(self):
        W, H = pyxel.width, pyxel.height
        _DH = self._dialog_height()
        return (W - _DW) // 2, (H - _DH) // 2

    def _btn_origin(self, dx, dy):
        _BH = max(24, _w._ui_render_h() + 4)
        _BW = 124
        _DH = self._dialog_height()
        total = 2 * _BW + _GAP
        bx = dx + (_DW - total) // 2
        by = dy + _DH - _BH - 10
        return bx, by

    def _close(self, result: str):
        self.result = result
        self.active = False
