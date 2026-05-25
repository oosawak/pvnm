"""タイトル画面: 背景画像＋メニューボタン"""
import pyxel
from ui.widgets import (
    draw_unicode, text_px_w, _font_render_h, pointer_intent_active,
)
from engine.title_colors import normalize_button_colors, button_color_index


# メニュー項目
_MENU_ITEMS = [
    ("start",    "Start Game"),
    ("continue", "Continue"),
    ("options",  "Options"),
    ("quit",     "Quit"),
]

BTN_W = 200
BTN_H = 36
BTN_GAP = 8


class TitleScreen:
    """フルスクリーンタイトル画面。"""

    def __init__(self):
        self.active = False
        self.result: str | None = None
        self._bg_image = None
        self._bg_fullscreen = False
        self._button_colors = normalize_button_colors()
        self._extras_available = False
        self._extras_unlocked = False
        self._hover = -1
        self._selected = 0
        self._controller = None
        self._size_logged = False

    def open(self, bg_image=None, bg_fullscreen: bool = False,
             button_colors: dict | None = None,
             extras_locked: bool = False,
             extras_available: bool | None = None,
             extras_unlocked: bool | None = None,
             controller=None):
        self.active = True
        self.result = None
        self._bg_image = bg_image
        self._bg_fullscreen = bool(bg_fullscreen)
        self._controller = controller
        available = (
            bool(extras_locked) if extras_available is None
            else bool(extras_available)
        )
        self._extras_available = available
        if extras_unlocked is None:
            self._extras_unlocked = available and not bool(extras_locked)
        else:
            self._extras_unlocked = available and bool(extras_unlocked)
        if button_colors is not None:
            self._button_colors = normalize_button_colors(button_colors)
        self._hover = -1
        self._selected = 0
        self._size_logged = False

    def update(self):
        if not self.active:
            return

        mx, my = pyxel.mouse_x, pyxel.mouse_y
        self._hover = -1
        menu_x = self._menu_x()
        menu_y = self._menu_y()

        items = self._menu_items()
        if items:
            nav_up = pyxel.btnp(pyxel.KEY_UP, hold=15, repeat=5)
            nav_down = pyxel.btnp(pyxel.KEY_DOWN, hold=15, repeat=5)
            confirm = pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE)
            back = pyxel.btnp(pyxel.KEY_ESCAPE)
            c = self._controller
            if c is not None:
                nav_up = nav_up or c.nav_up()
                nav_down = nav_down or c.nav_down()
                confirm = confirm or c.pressed("confirm")
                back = back or c.pressed("back")
            if nav_up:
                self._selected = (self._selected - 1) % len(items)
            if nav_down:
                self._selected = (self._selected + 1) % len(items)
            if back:
                self.result = "quit"
                self.active = False
                return
            if confirm:
                key = items[self._selected][0]
                if key == "extras_locked":
                    self.result = None
                    return
                self.result = key
                self.active = False
                return

        if pointer_intent_active():
            for i in range(len(items)):
                bx = menu_x
                by = menu_y + i * (BTN_H + BTN_GAP)
                if bx <= mx < bx + BTN_W and by <= my < by + BTN_H:
                    self._hover = i
                    self._selected = i
                    if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
                        if items[i][0] == "extras_locked":
                            self.result = None
                            return
                        self.result = items[i][0]
                        self.active = False
                    break

    def draw(self):
        if not self.active:
            return

        W, H = pyxel.width, pyxel.height
        if not self._size_logged:
            self._size_logged = True
            print(f"[PVNM] title_draw_pyxel_size={W}x{H}")

        # 背景
        # - デフォルト: 原寸 (等倍) でセンタリング。画面より大きい場合のみ
        #   アスペクト比を維持したまま画面に収まるよう縮小。
        # - フルスクリーン: アスペクト比を維持したまま画面一杯に拡大縮小。
        #
        # 注意: pyxel.blt(..., scale=s) はソース矩形の中央を基準に拡大縮小する
        # ため、そのまま (dx, dy) を渡すと描画位置が iw*(1-s)/2 だけずれる。
        # ここで補正して、描画後の左上が (dx, dy) に来るようにする。
        if self._bg_image:
            pyxel.cls(0)
            try:
                iw = self._bg_image.width
                ih = self._bg_image.height
            except Exception:
                iw, ih = 0, 0
            if iw > 0 and ih > 0:
                fit_scale = min(W / iw, H / ih)
                if self._bg_fullscreen:
                    scale = fit_scale
                else:
                    # 原寸表示。ただし画面をはみ出すなら縮小してフィット。
                    scale = min(1.0, fit_scale)
                dw = int(iw * scale)
                dh = int(ih * scale)
                dx = (W - dw) // 2
                dy = (H - dh) // 2
                if abs(scale - 1.0) < 0.001:
                    pyxel.blt(dx, dy, self._bg_image, 0, 0, iw, ih)
                else:
                    # 中央基準スケーリングへの位置補正
                    bx = dx + int(iw * (scale - 1) / 2)
                    by = dy + int(ih * (scale - 1) / 2)
                    pyxel.blt(bx, by, self._bg_image, 0, 0, iw, ih,
                              scale=scale)
        else:
            pyxel.cls(1)
            for i in range(0, W, 40):
                pyxel.line(i, 0, i, H, 13)
            for i in range(0, H, 40):
                pyxel.line(0, i, W, i, 13)

        # メニューボタン
        menu_x = self._menu_x()
        menu_y = self._menu_y()

        for i, (key, label) in enumerate(self._menu_items()):
            bx = menu_x
            by = menu_y + i * (BTN_H + BTN_GAP)
            hover = (
                ((self._hover == i) or (self._hover < 0 and self._selected == i))
                and key != "extras_locked"
            )

            if hover:
                pyxel.rect(
                    bx, by, BTN_W, BTN_H,
                    button_color_index(self._button_colors, "hover_bg"))
                pyxel.rectb(
                    bx, by, BTN_W, BTN_H,
                    button_color_index(self._button_colors, "hover_border"))
                fg = button_color_index(self._button_colors, "hover_text")
            else:
                pyxel.rect(
                    bx, by, BTN_W, BTN_H,
                    button_color_index(self._button_colors, "normal_bg"))
                pyxel.rectb(
                    bx, by, BTN_W, BTN_H,
                    button_color_index(self._button_colors, "normal_border"))
                fg = button_color_index(self._button_colors, "normal_text")

            fsz_btn = 14
            tw_btn = text_px_w(label, fsz_btn)
            rh_btn = _font_render_h(fsz_btn)
            lx = bx + (BTN_W - tw_btn) // 2
            ly = by + (BTN_H - rh_btn) // 2
            draw_unicode(lx, ly, label, fg, size=fsz_btn)

    def _menu_x(self) -> int:
        return (pyxel.width - BTN_W) // 2

    def _menu_y(self) -> int:
        return pyxel.height // 2 + (2 if self._extras_available else 20)

    def _menu_items(self) -> list[tuple[str, str]]:
        if not self._extras_available:
            return list(_MENU_ITEMS)
        extras_key = "extras" if self._extras_unlocked else "extras_locked"
        extras_label = "EXTRAS" if self._extras_unlocked else "???"
        return [
            ("start", "Start Game"),
            ("continue", "Continue"),
            ("options", "Options"),
            (extras_key, extras_label),
            ("quit", "Quit"),
        ]
