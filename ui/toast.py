"""トースト通知ウィジェット (720×480 対応)"""
import pyxel
from ui.colors import *

_DURATION = 90   # 表示フレーム数（30fps × 3秒）
_FADE     = 20   # フェードアウト開始フレーム数
_FONT_W   = 4    # pyxel内蔵フォント幅
_H        = 16   # トーストボックス高さ


class Toast:
    def __init__(self):
        self._msg   = ""
        self._timer = 0
        self._col   = EDIT_HIGHLIGHT

    def show(self, msg: str, col: int | None = None):
        self._msg   = msg
        self._timer = _DURATION
        self._col   = EDIT_HIGHLIGHT if col is None else col

    def update(self):
        if self._timer > 0:
            self._timer -= 1

    def draw(self):
        if self._timer <= 0:
            return
        W  = pyxel.width
        tw = len(self._msg) * _FONT_W
        x  = (W - tw) // 2
        y  = 6
        pyxel.rect(x - 8, y - 3, tw + 16, _H, EDIT_BG)
        pyxel.rectb(x - 8, y - 3, tw + 16, _H, self._col)
        col = self._col if self._timer > _FADE else EDIT_TEXT_DIM
        pyxel.text(x, y + (_H - 6) // 2 - 2, self._msg, col)
