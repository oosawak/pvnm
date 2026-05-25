"""CG gallery preview screen."""
from __future__ import annotations

import os
import pyxel

from engine import gallery_palette as _gallery_palette
from engine import palette as _palette_mod
from engine.gallery_config import (
    SLOTS_PER_GALLERY_PAGE,
    normalize_gallery_config,
)
from engine.image_cache import set_default_palette as _set_image_cache_palette
from ui.colors import (
    EDIT_BG, EDIT_PANEL, EDIT_BORDER, EDIT_TEXT, EDIT_TEXT_DIM, EDIT_ACCENT,
    EDIT_BTN_HOVER, EDIT_TITLE_BG,
)
import ui.widgets as _w
from ui.widgets import (
    draw_unicode, text_px_w, _font_render_h, is_hover, pointer_intent_active,
)


_FONT_SIZE = 16
_SMALL_SIZE = 12
_COLS = 3
_ROWS = 3
_SLOT_W = 220
_SLOT_H = 112
_SLOT_PAD = 2
_GAP = 8
_HEADER_H = 42


class GalleryPreview:
    """Preview CG gallery list/detail behavior from the editor."""

    def __init__(self):
        self.active = False
        self.closed = False
        self._cfg = normalize_gallery_config({})
        self._cache = None
        self._base_dir = ""
        self._settings = {}
        self._page = 0
        self._hover = -1
        self._detail_image = ""
        self._sepia_palette = None
        self._sepia_image_indices = set()
        self._detail_palette = None
        self._detail_palette_path = ""
        self._selected = 0
        self._controller = None

    def open(self, gallery_config: dict | None = None, cache=None,
             base_dir: str = "", settings: dict | None = None,
             controller=None):
        self.active = True
        self.closed = False
        self._cfg = normalize_gallery_config(gallery_config)
        self._cache = cache
        self._base_dir = base_dir or os.getcwd()
        self._settings = settings or {}
        self._page = 0
        self._hover = -1
        self._selected = 0
        self._controller = controller
        self._detail_image = ""
        self._detail_palette = None
        self._detail_palette_path = ""
        self._sepia_palette = _gallery_palette.build_sepia_palette(
            self._settings)
        self._sepia_image_indices = _gallery_palette.sepia_image_indices(
            self._settings)

    def update(self):
        if not self.active:
            return
        c = self._controller
        back = pyxel.btnp(pyxel.KEY_ESCAPE) or (c and c.pressed("back"))
        confirm = (
            pyxel.btnp(pyxel.KEY_RETURN)
            or pyxel.btnp(pyxel.KEY_SPACE)
            or (c and c.pressed("confirm"))
        )
        if back:
            if self._detail_image:
                self._detail_image = ""
            else:
                self.close()
            return

        if self._detail_image:
            left = (pyxel.btnp(pyxel.KEY_LEFT, hold=15, repeat=5)
                    or (c and c.nav_left()))
            right = (pyxel.btnp(pyxel.KEY_RIGHT, hold=15, repeat=5)
                     or (c and c.nav_right()))
            if left:
                self._move_detail_image(-1)
                return
            if right:
                self._move_detail_image(1)
                return
            if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) or confirm:
                self._detail_image = ""
            return

        pages = self._pages()
        if not pages:
            if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) or confirm:
                self.close()
            return

        slots = self._page_slots()
        if slots:
            self._selected = max(0, min(self._selected, len(slots) - 1))
            left = pyxel.btnp(pyxel.KEY_LEFT, hold=15, repeat=5) or (c and c.nav_left())
            right = pyxel.btnp(pyxel.KEY_RIGHT, hold=15, repeat=5) or (c and c.nav_right())
            page_prev = bool(c and c.pressed("log"))
            page_next = bool(c and c.pressed("skip_hold"))
            if page_prev:
                if self._page > 0:
                    self._set_page(self._page - 1)
                return
            if page_next:
                if self._page < len(pages) - 1:
                    self._set_page(self._page + 1)
                return
            self._selected = max(0, min(self._selected, len(slots) - 1))
            if left:
                if self._selected % _COLS != 0:
                    self._selected = max(0, self._selected - 1)
            if right:
                if (self._selected % _COLS != _COLS - 1
                        and self._selected < len(slots) - 1):
                    self._selected = min(len(slots) - 1, self._selected + 1)
            if pyxel.btnp(pyxel.KEY_UP, hold=15, repeat=5) or (c and c.nav_up()):
                self._selected = max(0, self._selected - _COLS)
            if pyxel.btnp(pyxel.KEY_DOWN, hold=15, repeat=5) or (c and c.nav_down()):
                self._selected = min(len(slots) - 1, self._selected + _COLS)
            if confirm:
                image = slots[self._selected].get("image", "") or ""
                if image:
                    self._open_detail(image)
                return

        mx, my = pyxel.mouse_x, pyxel.mouse_y
        self._hover = -1
        pointer_active = pointer_intent_active()
        if pointer_active:
            for idx, slot in enumerate(slots):
                x, y, w, h = self._slot_rect(idx)
                if is_hover(mx, my, x, y, w, h):
                    self._hover = idx
                    self._selected = idx
                    if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
                        image = slot.get("image", "") or ""
                        if image:
                            self._open_detail(image)
                    return

        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            if self._hit_prev(mx, my):
                self._set_page(max(0, self._page - 1))
            elif self._hit_next(mx, my):
                self._set_page(min(len(pages) - 1, self._page + 1))
            elif self._hit_close(mx, my):
                self.close()

    def draw(self):
        if not self.active:
            return
        if self._detail_image:
            self._draw_detail()
        else:
            self._draw_list()

    def close(self):
        self.active = False
        self.closed = True

    def _pages(self) -> list:
        return self._cfg.get("pages", []) or []

    def _page_slots(self) -> list:
        pages = self._pages()
        if not pages:
            return []
        self._page = max(0, min(self._page, len(pages) - 1))
        slots = pages[self._page].get("slots", []) or []
        return slots[:SLOTS_PER_GALLERY_PAGE]

    def _set_page(self, page: int):
        pages = self._pages()
        if not pages:
            self._page = 0
            self._selected = 0
            return
        self._page = max(0, min(page, len(pages) - 1))
        self._selected = 0

    def _image_positions(self) -> list[tuple[int, int, str]]:
        positions: list[tuple[int, int, str]] = []
        for page_idx, page in enumerate(self._pages()):
            if not isinstance(page, dict):
                continue
            slots = (page.get("slots", []) or [])[:SLOTS_PER_GALLERY_PAGE]
            for slot_idx, slot in enumerate(slots):
                if not isinstance(slot, dict):
                    continue
                image = slot.get("image", "") or ""
                if image:
                    positions.append((page_idx, slot_idx, image))
        return positions

    def _move_detail_image(self, delta: int):
        positions = self._image_positions()
        if not positions:
            return
        current = None
        for idx, (page_idx, slot_idx, image) in enumerate(positions):
            if (page_idx == self._page and slot_idx == self._selected
                    and image == self._detail_image):
                current = idx
                break
        if current is None:
            for idx, (_page_idx, _slot_idx, image) in enumerate(positions):
                if image == self._detail_image:
                    current = idx
                    break
        if current is None:
            return
        next_idx = max(0, min(len(positions) - 1, current + int(delta)))
        if next_idx == current:
            return
        self._page, self._selected, self._detail_image = positions[next_idx]
        self._hover = -1
        self._detail_palette = None
        self._detail_palette_path = ""

    def _slot_rect(self, idx: int) -> tuple[int, int, int, int]:
        grid_w = _COLS * _SLOT_W + (_COLS - 1) * _GAP
        x0 = (pyxel.width - grid_w) // 2
        y0 = _HEADER_H + 10
        col = idx % _COLS
        row = idx // _COLS
        return (
            x0 + col * (_SLOT_W + _GAP),
            y0 + row * (_SLOT_H + _GAP),
            _SLOT_W,
            _SLOT_H,
        )

    def _draw_list(self):
        self._apply_sepia_palette()
        pyxel.cls(EDIT_BG)
        pyxel.rect(0, 0, pyxel.width, _HEADER_H, EDIT_TITLE_BG)
        pyxel.line(0, _HEADER_H, pyxel.width, _HEADER_H, EDIT_BORDER)

        pages = self._pages()
        page_label = "NO PAGES"
        if pages:
            page_label = f"CG GALLERY PREVIEW   PAGE {self._page + 1} / {len(pages)}"
        draw_unicode(16, 12, page_label, EDIT_TEXT, size=_FONT_SIZE)
        draw_unicode(500, 13, "ESC: BACK", EDIT_TEXT_DIM, size=_SMALL_SIZE)

        if not pages:
            msg = "No CG gallery pages"
            draw_unicode((pyxel.width - text_px_w(msg, _FONT_SIZE)) // 2,
                         220, msg, EDIT_TEXT_DIM, size=_FONT_SIZE)
            return

        for idx, slot in enumerate(self._page_slots()):
            self._draw_slot(idx, slot)
        self._draw_nav_buttons()

    def _draw_slot(self, idx: int, slot: dict):
        x, y, w, h = self._slot_rect(idx)
        hover = idx == self._hover or (self._hover < 0 and idx == self._selected)
        bg = EDIT_BTN_HOVER if hover else EDIT_PANEL
        pyxel.rect(x, y, w, h, bg)
        pyxel.rectb(x, y, w, h, EDIT_TEXT if hover else EDIT_BORDER)
        image = slot.get("image", "") or ""
        if image:
            self._draw_thumbnail(x, y, w, h, image)
        else:
            label = "LOCKED"
            draw_unicode(x + (w - text_px_w(label, _FONT_SIZE)) // 2,
                         y + (h - _font_render_h(_FONT_SIZE)) // 2,
                         label, EDIT_TEXT_DIM, size=_FONT_SIZE)

    def _draw_thumbnail(self, x: int, y: int, w: int, h: int, path: str):
        tw, th = self._fit_size(path, w - _SLOT_PAD * 2,
                                h - _SLOT_PAD * 2)
        img = None
        if self._cache and self._sepia_palette is not None:
            try:
                img = self._cache.get(
                    path, tw, th,
                    palette=self._sepia_palette,
                    allowed_indices=self._sepia_image_indices)
            except Exception:
                img = None
        if img is not None:
            pyxel.blt(x + (w - img.width) // 2,
                      y + (h - img.height) // 2,
                      img, 0, 0, img.width, img.height)

    def _draw_nav_buttons(self):
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        for label, x, y, w, h in (
            ("PREV", *self._prev_rect()),
            ("NEXT", *self._next_rect()),
            ("BACK", *self._close_rect()),
        ):
            hover = is_hover(mx, my, x, y, w, h)
            pyxel.rect(x, y, w, h, EDIT_BTN_HOVER if hover else EDIT_PANEL)
            pyxel.rectb(x, y, w, h, EDIT_TEXT if hover else EDIT_BORDER)
            draw_unicode(x + (w - text_px_w(label, _FONT_SIZE)) // 2,
                         y + (h - _font_render_h(_FONT_SIZE)) // 2,
                         label, EDIT_TEXT, size=_FONT_SIZE)

    def _draw_detail(self):
        pal = self._detail_palette_for(self._detail_image)
        if pal is not None:
            _palette_mod.apply_to_pyxel_colors(pal)
            _set_image_cache_palette(pal)
        pyxel.cls(0)
        image = self._detail_image
        img = None
        dw, dh = self._fit_size(image, pyxel.width, pyxel.height)
        if self._cache and pal is not None:
            try:
                img = self._cache.get(image, dw, dh, palette=pal)
            except Exception:
                img = None
        if img is not None:
            pyxel.blt((pyxel.width - img.width) // 2,
                      (pyxel.height - img.height) // 2,
                      img, 0, 0, img.width, img.height)

    def _detail_palette_for(self, path: str):
        if path == self._detail_palette_path and self._detail_palette is not None:
            return self._detail_palette
        self._detail_palette_path = path
        self._detail_palette = None
        try:
            reserved = _palette_mod.reserved_from_settings(self._settings)
            if self._cache and hasattr(self._cache, "get_prebuilt_palette"):
                self._detail_palette = self._cache.get_prebuilt_palette(
                    [path], reserved)
            if self._detail_palette is not None:
                return self._detail_palette
            self._detail_palette = _palette_mod.build_scene_palette(
                [path], reserved, base_dir=self._base_dir)
        except Exception:
            self._detail_palette = None
        return self._detail_palette

    def _open_detail(self, image: str):
        self._detail_image = image
        self._detail_palette = None
        self._detail_palette_path = ""

    def _apply_sepia_palette(self):
        if self._sepia_palette is None:
            return
        try:
            _palette_mod.apply_to_pyxel_colors(self._sepia_palette)
            _set_image_cache_palette(self._sepia_palette)
        except Exception:
            pass

    def _source_size(self, path: str) -> tuple[int, int]:
        if self._cache:
            try:
                return self._cache.source_size(path)
            except Exception:
                pass
        abs_path = path if os.path.isabs(path) else os.path.join(
            self._base_dir, path)
        try:
            from PIL import Image
            with Image.open(abs_path) as img:
                return int(img.width), int(img.height)
        except Exception:
            return 0, 0

    def _fit_size(self, path: str, max_w: int, max_h: int) -> tuple[int, int]:
        ow, oh = self._source_size(path)
        if ow <= 0 or oh <= 0:
            return max(1, max_w), max(1, max_h)
        scale = min(max_w / ow, max_h / oh, 1.0)
        return max(1, round(ow * scale)), max(1, round(oh * scale))

    def _size_label(self, path: str) -> str:
        ow, oh = self._source_size(path)
        return f"{ow}x{oh}" if ow > 0 and oh > 0 else "size unknown"

    def _prev_rect(self) -> tuple[int, int, int, int]:
        return 20, 442, 90, 28

    def _next_rect(self) -> tuple[int, int, int, int]:
        return 118, 442, 90, 28

    def _close_rect(self) -> tuple[int, int, int, int]:
        return 610, 442, 90, 28

    def _hit_prev(self, mx: int, my: int) -> bool:
        x, y, w, h = self._prev_rect()
        return is_hover(mx, my, x, y, w, h)

    def _hit_next(self, mx: int, my: int) -> bool:
        x, y, w, h = self._next_rect()
        return is_hover(mx, my, x, y, w, h)

    def _hit_close(self, mx: int, my: int) -> bool:
        x, y, w, h = self._close_rect()
        return is_hover(mx, my, x, y, w, h)


def _fit_text(text: str, max_w: int, size: int) -> str:
    text = str(text or "")
    if _w.text_px_w(text, size) <= max_w:
        return text
    suffix = ".."
    out = ""
    for ch in text:
        if _w.text_px_w(out + ch + suffix, size) > max_w:
            break
        out += ch
    return (out or text[:1]) + suffix
