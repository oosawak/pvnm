"""EXTRA TEXT full-screen viewer."""
from __future__ import annotations

import pyxel

from engine import palette as _palette_mod
from engine import image_cache as _image_cache_mod
from engine.extra_text_config import normalize_extra_text_config
from engine.extra_text_config import normalize_extra_text_size
from engine.extra_text_colors import extra_text_color_index
from engine.text_wrap import wrap_text
from ui.widgets import draw_unicode, text_px_w, _font_render_h, is_hover


_TITLE_SIZE = 18
_TEXT_SIZE = 18
_SMALL_SIZE = 14
_PANEL_X = 8
_PANEL_Y = 8
_PANEL_W = 704
_PANEL_H = 404
_PAD = 10
_BODY_LETTER_SPACING = 1


def extra_text_visible_line_limit(text_size: int | None = None) -> int:
    """Return the number of wrapped body lines that fit in the panel."""
    size = normalize_extra_text_size(
        _TEXT_SIZE if text_size is None else text_size)
    return _extra_text_body_line_slots(size)


def _extra_text_body_line_slots(size: int) -> int:
    line_h = _font_render_h(size) + 6
    top_y = _PANEL_Y + _PAD
    max_y = _PANEL_Y + _PANEL_H - _PAD
    return max(1, (max_y - top_y) // line_h)


def extra_text_body_lines(text: str, text_size: int | None = None) -> list[str]:
    """Wrap text exactly as the EXTRA TEXT viewer does."""
    size = normalize_extra_text_size(
        _TEXT_SIZE if text_size is None else text_size)
    max_w = _PANEL_W - _PAD * 2
    return wrap_text(text or "", max_w, size, _BODY_LETTER_SPACING)


class ExtraTextViewer:
    """Read EXTRA TEXT pages. Click advances, ESC closes/goes back."""

    def __init__(self):
        self.active = False
        self.closed = False
        self._cfg = normalize_extra_text_config({})
        self._page = 0
        self._text_size = _TEXT_SIZE
        self._controller = None

    def open(self, extra_text_config: dict | None = None,
             initial_page: int = 0,
             controller=None):
        self.active = True
        self.closed = False
        self._cfg = normalize_extra_text_config(extra_text_config)
        self._text_size = normalize_extra_text_size(
            self._cfg.get("text_size", _TEXT_SIZE))
        self._controller = controller
        pages = self._cfg.get("pages", []) or []
        self._page = max(0, min(int(initial_page or 0), len(pages) - 1))
        self._apply_master_palette()

    def close(self):
        self.active = False
        self.closed = True

    def update(self):
        if not self.active:
            return
        c = self._controller
        back = pyxel.btnp(pyxel.KEY_ESCAPE) or (c and c.pressed("back"))
        if back:
            self.close()
            return
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        if pyxel.btnp(pyxel.KEY_LEFT, hold=15, repeat=5) or (c and c.nav_left()):
            self._page = max(0, self._page - 1)
        if (pyxel.btnp(pyxel.KEY_RIGHT, hold=15, repeat=5)
                or (c and c.nav_right())
                or pyxel.btnp(pyxel.KEY_RETURN)
                or pyxel.btnp(pyxel.KEY_SPACE)
                or (c and c.pressed("confirm"))):
            self._next_or_close()
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            if self._hit_back(mx, my):
                self._page = max(0, self._page - 1)
            elif self._hit_close(mx, my):
                self.close()
            elif self._hit_next(mx, my):
                self._next_or_close()
            else:
                self._next_or_close()

    def draw(self):
        if not self.active:
            return
        self._apply_master_palette()
        colors = self._colors()
        bg = extra_text_color_index(colors, "bg")
        panel = extra_text_color_index(colors, "panel_bg")
        border = extra_text_color_index(colors, "border")
        text = extra_text_color_index(colors, "text")
        text_dim = extra_text_color_index(colors, "text_dim")
        accent = extra_text_color_index(colors, "accent")

        pyxel.cls(bg)
        pyxel.rect(_PANEL_X, _PANEL_Y, _PANEL_W, _PANEL_H, panel)
        pyxel.rectb(_PANEL_X, _PANEL_Y, _PANEL_W, _PANEL_H, border)

        pages = self._pages()
        if not pages:
            label = "No EXTRA TEXT pages"
            draw_unicode((pyxel.width - text_px_w(label, _TITLE_SIZE)) // 2,
                         220, label, text_dim, size=_TITLE_SIZE)
            self._draw_buttons()
            return

        self._page = max(0, min(self._page, len(pages) - 1))
        page = pages[self._page]
        title = str(page.get("title") or f"PAGE {self._page + 1}")
        body = str(page.get("text") or "")

        page_label = f"{self._page + 1} / {len(pages)}"

        y = _PANEL_Y + _PAD
        line_h = _font_render_h(self._text_size) + 6
        line_slots = extra_text_visible_line_limit(self._text_size)
        lines = extra_text_body_lines(body, self._text_size)
        show_ellipsis = len(lines) > line_slots
        draw_count = max(1, line_slots - 1) if show_ellipsis else line_slots
        for line in lines[:draw_count]:
            draw_unicode(_PANEL_X + _PAD, y, line, text,
                         size=self._text_size,
                         letter_spacing=_BODY_LETTER_SPACING)
            y += line_h
        if show_ellipsis:
            draw_unicode(_PANEL_X + _PAD, y, "...", text_dim,
                         size=self._text_size)

        meta_y = _PANEL_Y + _PANEL_H + 5
        title_label = _fit_text(title, 210, _SMALL_SIZE)
        draw_unicode(_PANEL_X + _PAD, meta_y, title_label, accent,
                     size=_SMALL_SIZE)
        hint = "Click: next / ESC: close"
        draw_unicode(246, meta_y, hint, text_dim, size=_SMALL_SIZE)
        draw_unicode(
            _PANEL_X + _PANEL_W - _PAD - text_px_w(page_label, _SMALL_SIZE),
            meta_y, page_label, text_dim, size=_SMALL_SIZE)
        self._draw_buttons()

    def _pages(self) -> list:
        return self._cfg.get("pages", []) or []

    def _colors(self) -> dict:
        return self._cfg.get("colors", {}) or {}

    def _next_or_close(self):
        pages = self._pages()
        if self._page < len(pages) - 1:
            self._page += 1
        else:
            self.close()

    def _draw_buttons(self):
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        colors = self._colors()
        for label, rect in (
            ("BACK", self._back_rect()),
            ("NEXT", self._next_rect()),
            ("CLOSE", self._close_rect()),
        ):
            x, y, w, h = rect
            hover = is_hover(mx, my, x, y, w, h)
            bg = extra_text_color_index(colors, "button_hover" if hover else "button_bg")
            fg = extra_text_color_index(colors, "button_text")
            border = extra_text_color_index(colors, "border")
            pyxel.rect(x, y, w, h, bg)
            pyxel.rectb(x, y, w, h, border)
            draw_unicode(x + (w - text_px_w(label, _SMALL_SIZE)) // 2,
                         y + (h - _font_render_h(_SMALL_SIZE)) // 2,
                         label, fg, size=_SMALL_SIZE)

    def _back_rect(self):
        return 14, 440, 96, 30

    def _next_rect(self):
        return 118, 440, 96, 30

    def _close_rect(self):
        return 608, 440, 96, 30

    def _hit_back(self, mx: int, my: int) -> bool:
        x, y, w, h = self._back_rect()
        return is_hover(mx, my, x, y, w, h)

    def _hit_next(self, mx: int, my: int) -> bool:
        x, y, w, h = self._next_rect()
        return is_hover(mx, my, x, y, w, h)

    def _hit_close(self, mx: int, my: int) -> bool:
        x, y, w, h = self._close_rect()
        return is_hover(mx, my, x, y, w, h)

    def _apply_master_palette(self):
        try:
            _palette_mod.load()
            _image_cache_mod.set_default_palette(
                _palette_mod.snapshot_pyxel_colors())
        except Exception:
            pass


def _fit_text(text: str, max_w: int, size: int) -> str:
    if text_px_w(text, size) <= max_w:
        return text
    suffix = ".."
    out = ""
    for ch in text:
        if text_px_w(out + ch + suffix, size) > max_w:
            break
        out += ch
    return (out or text[:1]) + suffix
