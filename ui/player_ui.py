"""プレイヤーUI: ダイアログボックス右上のボタンバー"""
import pyxel
from ui.colors import (
    PLAY_BG, PLAY_BORDER, PLAY_TEXT, PLAY_ACCENT,
    PLAY_CHOICE_BG, PLAY_CHOICE_HOVER,
)
from ui.widgets import draw_unicode, text_px_w, _font_render_h

# ボタン定義
_BUTTONS = ["SAVE", "AUTO", "SKIP", "LOG", "OPT"]
BTN_W = 40
BTN_H = 14
BTN_GAP = 18


class PlayerUI:
    """ダイアログ右上に表示するボタンバー。

    属性:
        active_btn: 押されたボタン名 (1フレームだけ有効、消費後 None)
        auto_on:    オート再生中フラグ
        skip_on:    スキップ中フラグ
    """

    def __init__(self, dialog_x: int, dialog_y: int,
                 dialog_w: int):
        self._dx = dialog_x
        self._dy = dialog_y
        self._dw = dialog_w
        self.active_btn: str | None = None
        self.auto_on = False
        self.skip_on = False
        self._hover = -1

    def _bar_x(self) -> int:
        total_w = len(_BUTTONS) * BTN_W + (len(_BUTTONS) - 1) * BTN_GAP
        return self._dx + self._dw - total_w - 8

    def _bar_y(self) -> int:
        return self._dy + 4

    def update(self):
        self.active_btn = None
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        bx = self._bar_x()
        by = self._bar_y()
        self._hover = -1

        for i in range(len(_BUTTONS)):
            x = bx + i * (BTN_W + BTN_GAP)
            if x <= mx < x + BTN_W and by <= my < by + BTN_H:
                self._hover = i
                if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
                    self.active_btn = _BUTTONS[i]
                break

    def draw(self):
        bx = self._bar_x()
        by = self._bar_y()

        for i, label in enumerate(_BUTTONS):
            x = bx + i * (BTN_W + BTN_GAP)
            hover = (self._hover == i)

            # AUTO/SKIP がアクティブなら強調
            active = ((label == "AUTO" and self.auto_on) or
                      (label == "SKIP" and self.skip_on))

            if active:
                bg, fg = PLAY_ACCENT, PLAY_BG
            elif hover:
                bg, fg = PLAY_CHOICE_HOVER, PLAY_BG
            else:
                bg, fg = PLAY_CHOICE_BG, PLAY_TEXT

            pyxel.rect(x, by, BTN_W, BTN_H, bg)
            pyxel.rectb(x, by, BTN_W, BTN_H, PLAY_BORDER)
            size = 10
            tw = text_px_w(label, size)
            rh = _font_render_h(size)
            draw_unicode(x + (BTN_W - tw) // 2,
                         by + (BTN_H - rh) // 2,
                         label, fg, size=size)
