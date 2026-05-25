"""CG gallery configuration editor."""
from __future__ import annotations

import os
import pyxel

from engine import gallery_palette as _gallery_palette
from engine import palette as _palette_mod
from engine.image_cache import set_default_palette as _set_image_cache_palette
from engine.gallery_config import (
    SLOTS_PER_GALLERY_PAGE,
    new_gallery_page,
    normalize_gallery_config,
)
from ui.colors import (
    EDIT_BG, EDIT_PANEL, EDIT_BORDER, EDIT_TEXT, EDIT_TEXT_DIM, EDIT_ACCENT,
    EDIT_BTN_HOVER, EDIT_TITLE_BG,
)
import ui.widgets as _w
from ui.widgets import (
    draw_panel, draw_titlebar, draw_button, draw_unicode,
    is_hover, is_clicked, title_bar_h, button_w,
)
from ui.confirm_dialog import ConfirmDialog


_BTN_H = 32
_PANEL_H = 480 - _BTN_H
_FONT_SIZE = 14
_SLOT_COLS = 3
_SLOT_ROWS = 3
_SLOT_W = 220
_SLOT_H = 100
_SLOT_GAP = 8
_GRID_X = 20
_GRID_Y = 88


class GalleryConfigEditor:
    """Configure CG gallery pages shown from title extras later."""

    def __init__(self):
        self.active = False
        self.result = None
        self._cfg = normalize_gallery_config({})
        self._saved = normalize_gallery_config({})
        self._page = 0
        self._slot = 0
        self._cache = None
        self._base_dir = ""
        self._settings = {}
        self._sepia_palette = None
        self._sepia_image_indices = set()
        self._discard_confirm = ConfirmDialog()
        self._import_overlay = False
        self._import_scope = "bg_ending"
        self._import_mode = "append"

    def open(self, gallery_config: dict | None = None, cache=None,
             base_dir: str = "", settings: dict | None = None):
        self.active = True
        self.result = None
        self._cfg = normalize_gallery_config(gallery_config)
        self._saved = normalize_gallery_config(self._cfg)
        self._page = 0
        self._slot = 0
        self._cache = cache
        self._base_dir = base_dir or os.getcwd()
        self._settings = settings or {}
        self._sepia_palette = _gallery_palette.build_sepia_palette(
            self._settings)
        self._sepia_image_indices = _gallery_palette.sepia_image_indices(
            self._settings)

    def get_config(self) -> dict:
        return normalize_gallery_config(self._cfg)

    def _dirty(self) -> bool:
        return normalize_gallery_config(self._cfg) != normalize_gallery_config(
            self._saved)

    def set_selected_image(self, path: str):
        if not self._has_page():
            return
        self._current_page()["slots"][self._slot]["image"] = path or ""

    def selected_image(self) -> str:
        if not self._has_page():
            return ""
        return self._current_page()["slots"][self._slot].get("image", "") or ""

    def update(self):
        if not self.active:
            return
        if self._update_discard_confirm():
            return
        if self._import_overlay:
            self._update_import_overlay()
            return
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        right_clicked = pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT)

        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self._request_cancel()
            return

        for key, x, y, w, h in self._top_button_rects():
            if is_clicked(mx, my, x, y, w, h):
                self._handle_top_action(key)
                return
        key, x, y, w, h = self._import_button_rect()
        if is_clicked(mx, my, x, y, w, h):
            self._handle_top_action(key)
            return

        if self._has_page():
            for idx in range(SLOTS_PER_GALLERY_PAGE):
                x, y, w, h = self._slot_rect(idx)
                if is_clicked(mx, my, x, y, w, h):
                    self._slot = idx
                    return
                if right_clicked and is_hover(mx, my, x, y, w, h):
                    self._slot = idx
                    self._current_page()["slots"][idx]["image"] = ""
                    return

        for key, x, y, w, h in self._bottom_button_rects():
            if is_clicked(mx, my, x, y, w, h):
                self._handle_bottom_action(key)
                return

    def draw(self):
        if not self.active:
            return
        self._apply_sepia_palette()
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        pyxel.cls(EDIT_BG)
        draw_panel(0, 0, 720, _PANEL_H)
        draw_titlebar(0, 0, 720, "CG GALLERY CONFIG")

        self._draw_top_bar(mx, my)
        if self._has_page():
            self._draw_slots(mx, my)
            self._draw_detail()
        else:
            self._draw_empty_state()
        self._draw_bottom_bar(mx, my)

        if self._import_overlay:
            self._draw_import_overlay(mx, my)

        pyxel.line(mx - 4, my, mx + 4, my, EDIT_TEXT)
        pyxel.line(mx, my - 4, mx, my + 4, EDIT_TEXT)
        self._discard_confirm.draw()

    def _has_page(self) -> bool:
        return bool(self._cfg.get("pages"))

    def _pages(self) -> list:
        return self._cfg.setdefault("pages", [])

    def _current_page(self) -> dict:
        pages = self._pages()
        self._page = max(0, min(self._page, len(pages) - 1))
        page = pages[self._page]
        norm = normalize_gallery_config({"pages": [page]})["pages"][0]
        pages[self._page] = norm
        return norm

    def _revert(self):
        self._cfg = normalize_gallery_config(self._saved)
        self._page = min(self._page, max(0, len(self._cfg.get("pages", [])) - 1))
        self._slot = min(self._slot, SLOTS_PER_GALLERY_PAGE - 1)

    def _finish_cancelled(self):
        self._revert()
        self.result = "cancelled"
        self.active = False

    def _request_cancel(self):
        if self._dirty():
            self._discard_confirm.open(
                "UNSAVED CHANGES",
                "CG gallery config has unsaved edits.\n"
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

    def _top_button_rects(self):
        y = title_bar_h() + 10
        x = 20
        buttons = [
            ("add", "ADD PAGE"),
            ("delete", "DELETE PAGE"),
            ("prev", "PREV"),
            ("next", "NEXT"),
            ("set_image", "SET IMAGE"),
            ("clear_slot", "CLEAR SLOT"),
        ]
        for key, label in buttons:
            w = max(70, button_w(label) + 14)
            yield key, x, y, w, 24
            x += w + 8

    def _import_button_rect(self):
        label = "IMPORT USED"
        w = max(112, button_w(label) + 14)
        return "import_used", 720 - w - 20, 58, w, 24

    def _bottom_button_rects(self):
        y = _PANEL_H + (_BTN_H - 22) // 2
        buttons = [
            ("save", "SAVE & CLOSE", 4),
            ("revert", "REVERT ALL", 134),
            ("cancel", "CANCEL", 264),
            ("preview", "PREVIEW", 394),
        ]
        for key, label, x in buttons:
            w = max(80, button_w(label) + 14)
            yield key, x, y, w, 22

    def _handle_top_action(self, key: str):
        pages = self._pages()
        if key == "add":
            pages.append(new_gallery_page(f"PAGE {len(pages) + 1}"))
            self._page = len(pages) - 1
            self._slot = 0
        elif key == "delete" and pages:
            pages.pop(self._page)
            self._page = max(0, min(self._page, len(pages) - 1))
            self._slot = 0
        elif key == "prev" and pages:
            self._page = max(0, self._page - 1)
            self._slot = 0
        elif key == "next" and pages:
            self._page = min(len(pages) - 1, self._page + 1)
            self._slot = 0
        elif key == "set_image" and pages:
            self.result = "image_pick"
        elif key == "clear_slot" and pages:
            self._current_page()["slots"][self._slot]["image"] = ""
        elif key == "import_used":
            self._import_overlay = True

    def _handle_bottom_action(self, key: str):
        if key == "save":
            self._cfg = normalize_gallery_config(self._cfg)
            self.result = "saved"
            self.active = False
        elif key == "revert":
            self._revert()
        elif key == "cancel":
            self._request_cancel()
        elif key == "preview" and self._has_page():
            self.result = "preview"

    def _slot_rect(self, idx: int) -> tuple[int, int, int, int]:
        col = idx % _SLOT_COLS
        row = idx // _SLOT_COLS
        return (
            _GRID_X + col * (_SLOT_W + _SLOT_GAP),
            _GRID_Y + row * (_SLOT_H + _SLOT_GAP),
            _SLOT_W,
            _SLOT_H,
        )

    def _draw_top_bar(self, mx: int, my: int):
        for key, x, y, w, h in self._top_button_rects():
            label = {
                "add": "ADD PAGE",
                "delete": "DELETE PAGE",
                "prev": "PREV",
                "next": "NEXT",
                "set_image": "SET IMAGE",
                "clear_slot": "CLEAR SLOT",
            }[key]
            active = not (key != "add" and not self._has_page())
            draw_button(x, y, w, label, h=h, active=active,
                        hover=active and is_hover(mx, my, x, y, w, h),
                        size=_FONT_SIZE)
        key, x, y, w, h = self._import_button_rect()
        draw_button(x, y, w, "IMPORT USED", h=h, active=True,
                    hover=is_hover(mx, my, x, y, w, h), size=12)
        page_info = "NO PAGES"
        if self._has_page():
            page_info = f"PAGE {self._page + 1} / {len(self._pages())}"
        draw_unicode(20, 64, page_info, EDIT_ACCENT, size=_FONT_SIZE)

    def _draw_empty_state(self):
        msg = "No CG gallery pages. Add a page, then save to show LOCKED on title."
        draw_unicode(40, 160, msg, EDIT_TEXT_DIM, size=_FONT_SIZE)

    def _draw_slots(self, mx: int, my: int):
        page = self._current_page()
        for idx, slot in enumerate(page.get("slots", [])):
            x, y, w, h = self._slot_rect(idx)
            selected = idx == self._slot
            hover = is_hover(mx, my, x, y, w, h)
            bg = EDIT_BTN_HOVER if hover and not selected else EDIT_BG
            if selected:
                bg = EDIT_ACCENT
            pyxel.rect(x, y, w, h, bg)
            pyxel.rectb(x, y, w, h, EDIT_TEXT if selected else EDIT_BORDER)
            image = slot.get("image", "") or ""
            if image:
                self._draw_slot_image(x, y, w, h, image)
            else:
                label = f"SLOT {idx + 1}"
                draw_unicode(x + 8, y + 8, label,
                             EDIT_BG if selected else EDIT_TEXT_DIM,
                             size=12)
                draw_unicode(x + 8, y + 42, "- Empty -",
                             EDIT_BG if selected else EDIT_TEXT_DIM,
                             size=12)

    def _draw_slot_image(self, x: int, y: int, w: int, h: int, path: str):
        tw, th = self._fit_image_size(path, w - 12, h - 34)
        img = None
        if self._cache and self._sepia_palette is not None and tw > 0 and th > 0:
            try:
                img = self._cache.get(
                    path, tw, th,
                    palette=self._sepia_palette,
                    allowed_indices=self._sepia_image_indices)
            except Exception:
                img = None
        if img is not None:
            ix = x + (w - img.width) // 2
            iy = y + 5
            pyxel.blt(ix, iy, img, 0, 0, img.width, img.height)
        name = os.path.basename(path)
        size = self._source_size_label(path)
        draw_unicode(x + 6, y + h - 28, _fit_text(name, w - 12, 10),
                     EDIT_TEXT, size=10)
        draw_unicode(x + 6, y + h - 14, size, EDIT_TEXT_DIM, size=10)

    def _draw_detail(self):
        x, y, w, h = 20, 416, 680, 24
        image = self.selected_image()
        label = f"SLOT {self._slot + 1}: "
        if image:
            label += f"{os.path.basename(image)}  {self._source_size_label(image)}"
        else:
            label += "empty"
        draw_unicode(x, y, _fit_text(label, w, _FONT_SIZE), EDIT_TEXT_DIM,
                     size=_FONT_SIZE)

    def _draw_bottom_bar(self, mx: int, my: int):
        pyxel.rect(0, _PANEL_H, 720, _BTN_H, EDIT_TITLE_BG)
        pyxel.line(0, _PANEL_H, 720, _PANEL_H, EDIT_BORDER)
        for key, x, y, w, h in self._bottom_button_rects():
            label = {
                "save": "SAVE & CLOSE",
                "revert": "REVERT ALL",
                "cancel": "CANCEL",
                "preview": "PREVIEW",
            }[key]
            active = key != "preview" or self._has_page()
            draw_button(x, y, w, label, h=h,
                        active=active,
                        hover=active and is_hover(mx, my, x, y, w, h),
                        size=_FONT_SIZE)
        draw_unicode(518, _PANEL_H + 10,
                     "1+ page = LOCKED",
                     EDIT_TEXT_DIM, size=10)

    def _apply_sepia_palette(self):
        if self._sepia_palette is None:
            return
        try:
            _palette_mod.apply_to_pyxel_colors(self._sepia_palette)
            _set_image_cache_palette(self._sepia_palette)
        except Exception:
            pass

    def _import_overlay_rects(self):
        x, y = 120, 122
        return {
            "scope_bg_ending": (x + 24, y + 58, 170, 26),
            "scope_all":       (x + 206, y + 58, 120, 26),
            "mode_append":     (x + 24, y + 112, 130, 26),
            "mode_replace":    (x + 166, y + 112, 130, 26),
            "run":             (x + 330, y + 160, 82, 26),
            "cancel":          (x + 424, y + 160, 82, 26),
        }

    def _update_import_overlay(self):
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self._import_overlay = False
            return
        if not pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            return
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        for key, (x, y, w, h) in self._import_overlay_rects().items():
            if not is_hover(mx, my, x, y, w, h):
                continue
            if key == "scope_bg_ending":
                self._import_scope = "bg_ending"
            elif key == "scope_all":
                self._import_scope = "all"
            elif key == "mode_append":
                self._import_mode = "append"
            elif key == "mode_replace":
                self._import_mode = "replace"
            elif key == "cancel":
                self._import_overlay = False
            elif key == "run":
                self._import_overlay = False
                self.result = (
                    f"import_used:{self._import_scope}:{self._import_mode}")
            return

    def _draw_import_overlay(self, mx: int, my: int):
        x, y, w, h = 110, 110, 520, 210
        pyxel.rect(0, 0, 720, 480, EDIT_BG)
        pyxel.rect(x, y, w, h, EDIT_PANEL)
        pyxel.rectb(x, y, w, h, EDIT_BORDER)
        draw_unicode(x + 18, y + 16, "IMPORT USED IMAGES",
                     EDIT_TEXT, size=_FONT_SIZE)
        draw_unicode(
            x + 18, y + 38,
            "APPEND keeps current slots. REPLACE rebuilds gallery pages.",
            EDIT_TEXT_DIM, size=10)

        rects = self._import_overlay_rects()
        draw_unicode(x + 18, y + 58 - 18, "Scope", EDIT_ACCENT, size=12)
        draw_unicode(x + 18, y + 112 - 18, "Mode", EDIT_ACCENT, size=12)
        specs = {
            "scope_bg_ending": ("BG+ENDING", self._import_scope == "bg_ending"),
            "scope_all":       ("ALL", self._import_scope == "all"),
            "mode_append":     ("APPEND", self._import_mode == "append"),
            "mode_replace":    ("REPLACE", self._import_mode == "replace"),
            "run":             ("IMPORT", False),
            "cancel":          ("CANCEL", False),
        }
        for key, (rx, ry, rw, rh) in rects.items():
            label, selected = specs[key]
            hover = is_hover(mx, my, rx, ry, rw, rh)
            active_col = EDIT_ACCENT if selected else EDIT_BTN_HOVER
            pyxel.rect(rx, ry, rw, rh,
                       active_col if selected or hover else EDIT_BG)
            pyxel.rectb(rx, ry, rw, rh, EDIT_TEXT if selected else EDIT_BORDER)
            fg = EDIT_BG if selected else EDIT_TEXT
            tw = _w.text_px_w(label, 12)
            draw_unicode(rx + (rw - tw) // 2, ry + 7, label, fg, size=12)

    def import_images(self, paths: list[str], replace: bool = False) -> tuple[int, int]:
        """Import image paths into 3x3 gallery pages.

        Returns ``(added, skipped)``. Existing paths are skipped in APPEND mode.
        """
        clean: list[str] = []
        seen: set[str] = set()
        for path in paths or []:
            text = str(path or "").strip()
            if not text or text in seen:
                continue
            clean.append(text)
            seen.add(text)
        if replace:
            self._cfg = normalize_gallery_config({})
            self._page = 0
            self._slot = 0

        pages = self._pages()
        existing = set()
        if not replace:
            for page in pages:
                for slot in page.get("slots", []) or []:
                    image = str(slot.get("image", "") or "").strip()
                    if image:
                        existing.add(image)

        added = 0
        skipped = 0
        first_added: tuple[int, int] | None = None
        for path in clean:
            if path in existing:
                skipped += 1
                continue
            p_idx, s_idx = self._first_empty_slot()
            if p_idx < 0:
                pages.append(new_gallery_page(f"PAGE {len(pages) + 1}"))
                p_idx, s_idx = len(pages) - 1, 0
            pages[p_idx]["slots"][s_idx]["image"] = path
            existing.add(path)
            added += 1
            if first_added is None:
                first_added = (p_idx, s_idx)

        self._cfg = normalize_gallery_config(self._cfg)
        if first_added is not None:
            self._page, self._slot = first_added
        elif self._has_page():
            self._page = min(self._page, len(self._pages()) - 1)
            self._slot = min(self._slot, SLOTS_PER_GALLERY_PAGE - 1)
        return added, skipped

    def _first_empty_slot(self) -> tuple[int, int]:
        for p_idx, page in enumerate(self._pages()):
            slots = page.get("slots", []) or []
            for s_idx, slot in enumerate(slots):
                if not str(slot.get("image", "") or "").strip():
                    return p_idx, s_idx
        return -1, -1

    def _fit_image_size(self, path: str, max_w: int, max_h: int) -> tuple[int, int]:
        ow, oh = self._source_size(path)
        if ow <= 0 or oh <= 0:
            return max_w, max_h
        scale = min(max_w / ow, max_h / oh, 1.0)
        return max(1, round(ow * scale)), max(1, round(oh * scale))

    def _source_size_label(self, path: str) -> str:
        ow, oh = self._source_size(path)
        return f"{ow}x{oh}" if ow > 0 and oh > 0 else "size unknown"

    def _source_size(self, path: str) -> tuple[int, int]:
        abs_path = path if os.path.isabs(path) else os.path.join(
            self._base_dir, path)
        try:
            from PIL import Image
            with Image.open(abs_path) as img:
                return img.size
        except Exception:
            return 0, 0


def _fit_text(text: str, max_w: int, size: int) -> str:
    if _w.text_px_w(text, size) <= max_w:
        return text
    suffix = ".."
    out = ""
    for ch in text:
        if _w.text_px_w(out + ch + suffix, size) > max_w:
            break
        out += ch
    return (out or text[:1]) + suffix
