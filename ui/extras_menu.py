"""Title EXTRAS submenu."""
from __future__ import annotations

import pyxel

from engine.title_colors import normalize_button_colors, button_color_index
from ui.widgets import (
    draw_unicode, text_px_w, _font_render_h, pointer_intent_active,
)


_BTN_W = 260
_BTN_H = 40
_BTN_GAP = 10
_FONT_SIZE = 16


class ExtrasMenu:
    """Title-side page for extra content."""

    def __init__(self):
        self.active = False
        self.result = None
        self._hover = -1
        self._selected = 0
        self._controller = None
        self._button_colors = normalize_button_colors()
        self._show_gallery = False
        self._show_extra_text = False

    def open(self, button_colors: dict | None = None,
             show_gallery: bool = False,
             show_extra_text: bool = False,
             controller=None):
        self.active = True
        self.result = None
        self._hover = -1
        self._selected = 0
        self._controller = controller
        self._button_colors = normalize_button_colors(button_colors)
        self._show_gallery = bool(show_gallery)
        self._show_extra_text = bool(show_extra_text)

    def update(self):
        if not self.active:
            return
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self.result = "closed"
            self.active = False
            return
        items = self._items()
        if items:
            c = self._controller
            nav_up = pyxel.btnp(pyxel.KEY_UP, hold=15, repeat=5)
            nav_down = pyxel.btnp(pyxel.KEY_DOWN, hold=15, repeat=5)
            confirm = pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE)
            back = pyxel.btnp(pyxel.KEY_BACKSPACE)
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
                self.result = "closed"
                self.active = False
                return
            if confirm:
                self.result = items[self._selected][0]
                self.active = False
                return
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        self._hover = -1
        if pointer_intent_active():
            for i, (key, _label) in enumerate(items):
                x, y, w, h = self._button_rect(i)
                if x <= mx < x + w and y <= my < y + h:
                    self._hover = i
                    self._selected = i
                    if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
                        self.result = key
                        self.active = False
                    return

    def draw(self):
        if not self.active:
            return
        colors = self._button_colors
        bg = button_color_index(colors, "normal_bg")
        border = button_color_index(colors, "normal_border")
        text = button_color_index(colors, "normal_text")
        pyxel.cls(bg)
        pyxel.rectb(18, 18, pyxel.width - 36, pyxel.height - 36, border)

        title = "EXTRAS"
        title_size = 20
        title_w = text_px_w(title, title_size)
        title_h = _font_render_h(title_size)
        title_x = (pyxel.width - title_w) // 2
        title_y = 92
        pad_x, pad_y = 18, 8
        pyxel.rect(title_x - pad_x, title_y - pad_y,
                   title_w + pad_x * 2, title_h + pad_y * 2, bg)
        pyxel.rectb(title_x - pad_x, title_y - pad_y,
                    title_w + pad_x * 2, title_h + pad_y * 2, border)
        draw_unicode(title_x, title_y, title, text, size=title_size)

        for i, (key, label) in enumerate(self._items()):
            self._draw_button(i, label)

    def _items(self) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
        if self._show_gallery:
            items.append(("gallery", "CG GALLERY"))
        if self._show_extra_text:
            items.append(("extra_text", "EXTRA TEXT"))
        items.append(("closed", "BACK"))
        return items

    def _button_rect(self, idx: int) -> tuple[int, int, int, int]:
        items = self._items()
        total_h = len(items) * _BTN_H + max(0, len(items) - 1) * _BTN_GAP
        x = (pyxel.width - _BTN_W) // 2
        y = 172 + idx * (_BTN_H + _BTN_GAP)
        if total_h > 0:
            y = max(150, (pyxel.height - total_h) // 2 + 26)
            y += idx * (_BTN_H + _BTN_GAP)
        return x, y, _BTN_W, _BTN_H

    def _draw_button(self, idx: int, label: str):
        x, y, w, h = self._button_rect(idx)
        hover = idx == self._hover or (self._hover < 0 and idx == self._selected)
        colors = self._button_colors
        bg = button_color_index(colors, "hover_bg" if hover else "normal_bg")
        border = button_color_index(
            colors, "hover_border" if hover else "normal_border")
        text = button_color_index(colors, "hover_text" if hover else "normal_text")
        pyxel.rect(x, y, w, h, bg)
        pyxel.rectb(x, y, w, h, border)
        draw_unicode(x + (w - text_px_w(label, _FONT_SIZE)) // 2,
                     y + (h - _font_render_h(_FONT_SIZE)) // 2,
                     label, text, size=_FONT_SIZE)
