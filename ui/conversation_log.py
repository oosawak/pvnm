"""会話ログ: 過去のセリフ一覧をスクロール表示するモーダルオーバーレイ"""
import pyxel
from ui.widgets import _font_render_h, _ui_font_size, draw_unicode
from engine.text_wrap import wrap_text


class ConversationLog:
    """モーダルオーバーレイで会話ログを表示する。"""

    MARGIN_X = 40
    MARGIN_Y = 24
    PAD = 12
    SCROLL_SPEED = 20

    def __init__(self):
        self.active = False
        self.closed = False
        self._entries: list[tuple[str, str]] = []
        self._scroll_y = 0
        self._max_scroll = 0
        self._font_size = 12
        self._controller = None

    def open(self, entries: list[tuple[str, str]], controller=None,
             font_size: int | None = None):
        self._entries = list(entries)
        self._controller = controller
        if font_size:
            try:
                self._font_size = max(12, min(24, int(font_size)))
            except Exception:
                self._font_size = max(12, _ui_font_size())
        self.active = True
        self.closed = False
        self._scroll_y = 0
        self._calc_max_scroll()
        self._scroll_y = self._max_scroll

    def _calc_max_scroll(self):
        fh = _font_render_h(self._font_size)
        lh = fh + 4
        content_h = 0
        W = pyxel.width - self.MARGIN_X * 2 - self.PAD * 2

        for speaker, text in self._entries:
            if speaker:
                content_h += lh
            for para in text.split("\n"):
                if not para:
                    content_h += lh
                else:
                    content_h += len(wrap_text(para, W, self._font_size)) * lh
            content_h += 8

        hdr_h = _font_render_h(self._font_size) + 4
        view_h = pyxel.height - self.MARGIN_Y * 2 - self.PAD * 2 - hdr_h - 2
        self._max_scroll = max(0, content_h - view_h)

    def update(self):
        if not self.active:
            return

        if pyxel.btnp(pyxel.KEY_ESCAPE) or pyxel.btnp(pyxel.KEY_BACKSPACE):
            self.active = False
            self.closed = True
            return

        mx, my = pyxel.mouse_x, pyxel.mouse_y
        lx, ly = self.MARGIN_X, self.MARGIN_Y
        lw = pyxel.width - self.MARGIN_X * 2
        lh = pyxel.height - self.MARGIN_Y * 2
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            if not (lx <= mx < lx + lw and ly <= my < ly + lh):
                self.active = False
                self.closed = True
                return

        wheel = pyxel.mouse_wheel
        if wheel != 0:
            self._scroll_by(-wheel * self.SCROLL_SPEED)

        c = self._controller
        if pyxel.btnp(pyxel.KEY_UP, hold=15, repeat=5) or (c and c.nav_up()):
            self._scroll_by(-self.SCROLL_SPEED)
        if pyxel.btnp(pyxel.KEY_DOWN, hold=15, repeat=5) or (c and c.nav_down()):
            self._scroll_by(self.SCROLL_SPEED)

    def _scroll_by(self, delta: int):
        self._scroll_y = max(0, min(self._scroll_y + delta, self._max_scroll))

    def draw(self):
        if not self.active:
            return

        W, H = pyxel.width, pyxel.height
        lx, ly = self.MARGIN_X, self.MARGIN_Y
        lw = W - self.MARGIN_X * 2
        lh = H - self.MARGIN_Y * 2

        # 半透明背景
        for y in range(0, H, 2):
            pyxel.line(0, y, W - 1, y, 0)

        # ログパネル
        pyxel.rect(lx, ly, lw, lh, 1)
        pyxel.rectb(lx, ly, lw, lh, 5)

        # ヘッダ
        hdr_h = _font_render_h(self._font_size) + 4
        pyxel.rect(lx + 1, ly + 1, lw - 2, hdr_h, 5)
        frh = _font_render_h(self._font_size)
        header = "LOG  UP/DOWN  B/ESC"
        self._draw_log_text(lx + 8, ly + max(2, (hdr_h - frh) // 2),
                            header, 7)

        # クリップ領域
        cx = lx + self.PAD
        cy = ly + hdr_h + 2
        cw = lw - self.PAD * 2
        ch = lh - hdr_h - 2 - self.PAD
        pyxel.clip(cx, cy, cw, ch)

        fh = _font_render_h(self._font_size)
        line_h = fh + 4

        draw_y = cy - self._scroll_y

        for speaker, text in self._entries:
            if speaker:
                if cy <= draw_y + fh and draw_y < cy + ch:
                    self._draw_log_text(cx, draw_y, f"[{speaker}]", 8)
                draw_y += line_h

            for para in text.split("\n"):
                if not para:
                    draw_y += line_h
                else:
                    for line in wrap_text(para, cw - 8, self._font_size):
                        if cy <= draw_y + fh and draw_y < cy + ch:
                            self._draw_log_text(cx + 8, draw_y, line, 7)
                        draw_y += line_h
            draw_y += 8

        pyxel.clip()

        # スクロールバー
        if self._max_scroll > 0:
            sb_x = lx + lw - 6
            sb_y = cy
            sb_h = ch
            thumb_h = max(10, int(sb_h * sb_h / (sb_h + self._max_scroll)))
            thumb_y = sb_y + int((sb_h - thumb_h) * self._scroll_y / self._max_scroll)
            pyxel.rect(sb_x, sb_y, 4, sb_h, 0)
            pyxel.rect(sb_x, thumb_y, 4, thumb_h, 5)

    def _draw_log_text(self, x, y, text, col):
        draw_unicode(x, y, text, col, size=self._font_size)
