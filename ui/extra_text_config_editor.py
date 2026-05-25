"""EXTRA TEXT configuration editor."""
from __future__ import annotations

import pyxel

from engine.extra_text_config import (
    EXTRA_TEXT_SIZE_OPTIONS,
    new_extra_text_page,
    normalize_extra_text_config,
    normalize_extra_text_size,
)
from engine.extra_text_colors import (
    EXTRA_TEXT_COLOR_ROLES,
    normalize_extra_text_colors,
)
from engine.text_wrap import wrap_text
from ui.extra_text_viewer import (
    extra_text_body_lines,
    extra_text_visible_line_limit,
)
from ui.colors import (
    EDIT_BG, EDIT_PANEL, EDIT_BORDER, EDIT_TEXT, EDIT_TEXT_DIM, EDIT_ACCENT,
    EDIT_BTN_HOVER, EDIT_TITLE_BG,
)
from ui.native_dialogs import AsyncTextDialog
import ui.widgets as _w
from ui.widgets import (
    draw_panel, draw_titlebar, draw_button, draw_unicode,
    is_hover, is_clicked, title_bar_h, button_w,
)
from ui.confirm_dialog import ConfirmDialog


_BTN_H = 32
_PANEL_H = 480 - _BTN_H
_FONT_SIZE = 14
_SMALL_SIZE = 12
_COLOR_ROLE_ROW_H = 22
_COLOR_GRID_CELL = 10
_COLOR_GRID_COLS = 16
_COLOR_GRID_ROWS = 16


def _hex_for_idx(idx: int) -> str:
    if not isinstance(idx, int) or idx < 0 or idx >= len(pyxel.colors):
        return "------"
    return f"{pyxel.colors[idx]:06X}"


def _compute_display_order() -> list[int]:
    items = [(i, pyxel.colors[i]) for i in range(256)]
    items.sort(key=lambda it: (it[1], it[0]))
    return [it[0] for it in items]


class ExtraTextConfigEditor:
    """Configure pages and colors for title EXTRAS / EXTRA TEXT."""

    def __init__(self):
        self.active = False
        self.result = None
        self._cfg = normalize_extra_text_config({})
        self._saved = normalize_extra_text_config({})
        self._page = 0
        self._color_roles = list(EXTRA_TEXT_COLOR_ROLES)
        self._sel_color_role = self._color_roles[0][0]
        self._display_order = list(range(256))
        self._text_dialog = AsyncTextDialog()
        self._discard_confirm = ConfirmDialog()

    def open(self, extra_text_config: dict | None = None):
        self.active = True
        self.result = None
        self._cfg = normalize_extra_text_config(extra_text_config)
        self._saved = normalize_extra_text_config(self._cfg)
        self._page = 0
        self._sel_color_role = self._color_roles[0][0]
        self._display_order = _compute_display_order()

    def get_config(self) -> dict:
        return normalize_extra_text_config(self._cfg)

    def current_page_index(self) -> int:
        pages = self._pages()
        if not pages:
            return 0
        return max(0, min(self._page, len(pages) - 1))

    def _dirty(self) -> bool:
        return normalize_extra_text_config(self._cfg) != normalize_extra_text_config(
            self._saved)

    def update(self):
        if not self.active:
            return
        if self._update_discard_confirm():
            return
        if self._text_dialog.poll():
            return
        if self._text_dialog.running:
            return

        mx, my = pyxel.mouse_x, pyxel.mouse_y
        right_clicked = pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT)
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self._request_cancel()
            return

        for key, x, y, w, h in self._top_button_rects():
            if right_clicked and key == "text_size" and is_hover(mx, my, x, y, w, h):
                self._adjust_text_size(-1)
                return
            if is_clicked(mx, my, x, y, w, h):
                self._handle_top_action(key)
                return

        self._update_colors(mx, my)

        for key, x, y, w, h in self._bottom_button_rects():
            if is_clicked(mx, my, x, y, w, h):
                self._handle_bottom_action(key)
                return

    def draw(self):
        if not self.active:
            return
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        pyxel.cls(EDIT_BG)
        draw_panel(0, 0, 720, _PANEL_H)
        draw_titlebar(0, 0, 720, "EXTRA TEXT CONFIG")
        self._draw_top_bar(mx, my)
        self._draw_page_preview()
        self._draw_color_panel(mx, my)
        self._draw_bottom_bar(mx, my)
        pyxel.line(mx - 4, my, mx + 4, my, EDIT_TEXT)
        pyxel.line(mx, my - 4, mx, my + 4, EDIT_TEXT)
        self._discard_confirm.draw()

    def _pages(self) -> list:
        return self._cfg.setdefault("pages", [])

    def _has_page(self) -> bool:
        return bool(self._pages())

    def _current_page(self) -> dict:
        pages = self._pages()
        self._page = max(0, min(self._page, len(pages) - 1))
        page = pages[self._page]
        if not isinstance(page, dict):
            page = new_extra_text_page(f"PAGE {self._page + 1}")
        page.setdefault("title", f"PAGE {self._page + 1}")
        page.setdefault("text", "")
        pages[self._page] = page
        return page

    def _colors(self) -> dict:
        colors = self._cfg.get("colors")
        if not isinstance(colors, dict):
            colors = normalize_extra_text_colors(colors)
            self._cfg["colors"] = colors
        return colors

    def _revert(self):
        self._cfg = normalize_extra_text_config(self._saved)
        self._page = min(self._page, max(0, len(self._pages()) - 1))

    def _finish_cancelled(self):
        self._revert()
        self.result = "cancelled"
        self.active = False

    def _request_cancel(self):
        if self._dirty():
            self._discard_confirm.open(
                "UNSAVED CHANGES",
                "Extra text config has unsaved edits.\n"
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
            ("edit", "EDIT TEXT"),
            ("text_size", f"TEXT SIZE:{self._text_size()}"),
        ]
        for key, label in buttons:
            w = max(70, button_w(label) + 14)
            yield key, x, y, w, 24
            x += w + 8

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
            pages.append(new_extra_text_page(f"PAGE {len(pages) + 1}"))
            self._page = len(pages) - 1
        elif key == "delete" and pages:
            pages.pop(self._page)
            self._page = max(0, min(self._page, len(pages) - 1))
        elif key == "prev" and pages:
            self._page = max(0, self._page - 1)
        elif key == "next" and pages:
            self._page = min(len(pages) - 1, self._page + 1)
        elif key == "edit" and pages:
            page = self._current_page()
            limit = extra_text_visible_line_limit(self._text_size())
            self._text_dialog.open(
                f"EXTRA TEXT - MAX {limit} WRAPPED LINES",
                str(page.get("text", "")),
                self._set_current_text,
                multiline=True,
            )
        elif key == "text_size":
            self._adjust_text_size(1)

    def _handle_bottom_action(self, key: str):
        if key == "save":
            self._cfg = normalize_extra_text_config(self._cfg)
            self.result = "saved"
            self.active = False
        elif key == "revert":
            self._revert()
        elif key == "cancel":
            self._request_cancel()
        elif key == "preview" and self._has_page():
            self.result = "preview"

    def _set_current_text(self, text: str):
        if not self._has_page():
            return
        self._current_page()["text"] = text or ""

    def _update_colors(self, mx: int, my: int):
        x, y, w, h = self._color_rect()
        role_x, role_y, role_w = x + 8, y + 24, 250
        for i, (key, _label, _desc, _default) in enumerate(self._color_roles):
            ry = role_y + i * _COLOR_ROLE_ROW_H
            if is_clicked(mx, my, role_x, ry, role_w, _COLOR_ROLE_ROW_H):
                self._sel_color_role = key
                return
        gx, gy = self._palette_grid_origin()
        grid_w = _COLOR_GRID_COLS * _COLOR_GRID_CELL
        grid_h = _COLOR_GRID_ROWS * _COLOR_GRID_CELL
        if is_clicked(mx, my, gx, gy, grid_w, grid_h):
            col = (mx - gx) // _COLOR_GRID_CELL
            row = (my - gy) // _COLOR_GRID_CELL
            pos = row * _COLOR_GRID_COLS + col
            if 0 <= pos < len(self._display_order):
                self._colors()[self._sel_color_role] = self._display_order[pos]

    def _draw_top_bar(self, mx: int, my: int):
        for key, x, y, w, h in self._top_button_rects():
            labels = {
                "add": "ADD PAGE",
                "delete": "DELETE PAGE",
                "prev": "PREV",
                "next": "NEXT",
                "edit": "EDIT TEXT",
                "text_size": f"TEXT SIZE:{self._text_size()}",
            }
            active = not (key not in ("add", "text_size") and not self._has_page())
            draw_button(x, y, w, labels[key], h=h, active=active,
                        hover=active and is_hover(mx, my, x, y, w, h),
                        size=_FONT_SIZE)
        info = "NO PAGES"
        if self._has_page():
            info = f"PAGE {self._page + 1} / {len(self._pages())}"
        draw_unicode(20, 64, info, EDIT_ACCENT, size=_FONT_SIZE)
        note = (
            f"DISPLAY MAX {extra_text_visible_line_limit(self._text_size())}"
            " WRAPPED LINES")
        draw_unicode(170, 66, note, EDIT_TEXT_DIM, size=_SMALL_SIZE)

    def _draw_page_preview(self):
        x, y, w, h = 20, 88, 680, 92
        pyxel.rect(x, y, w, h, EDIT_BG)
        pyxel.rectb(x, y, w, h, EDIT_BORDER)
        if not self._has_page():
            draw_unicode(x + 12, y + 34,
                         "No EXTRA TEXT pages. Add a page to show EXTRAS.",
                         EDIT_TEXT_DIM, size=_FONT_SIZE)
            return
        page = self._current_page()
        draw_unicode(x + 10, y + 8, str(page.get("title", "")),
                     EDIT_TEXT, size=_FONT_SIZE)
        body = str(page.get("text", ""))
        text_size = self._text_size()
        body_lines = extra_text_body_lines(body, text_size)
        line_limit = extra_text_visible_line_limit(text_size)
        count_label = f"{len(body_lines)} / {line_limit} DISPLAY LINES"
        count_col = EDIT_ACCENT if len(body_lines) > line_limit else EDIT_TEXT_DIM
        draw_unicode(x + w - 10 - _w.text_px_w(count_label, _SMALL_SIZE),
                     y + 10, count_label, count_col, size=_SMALL_SIZE)
        yy = y + 34
        for line in wrap_text(body or "(empty)", w - 20, _SMALL_SIZE, 0)[:3]:
            draw_unicode(x + 10, yy, line, EDIT_TEXT_DIM, size=_SMALL_SIZE)
            yy += _w._font_render_h(_SMALL_SIZE) + 2
        if len(body_lines) > line_limit:
            warning = "OVER LIMIT: SPLIT INTO PAGES"
            draw_unicode(x + w - 10 - _w.text_px_w(warning, _SMALL_SIZE),
                         y + h - 18, warning, EDIT_ACCENT,
                         size=_SMALL_SIZE)

    def _draw_color_panel(self, mx: int, my: int):
        x, y, w, h = self._color_rect()
        pyxel.rect(x, y, w, h, EDIT_PANEL)
        pyxel.rectb(x, y, w, h, EDIT_BORDER)
        draw_unicode(x + 8, y + 5, "EXTRA TEXT COLORS", EDIT_ACCENT,
                     size=_FONT_SIZE)

        role_x, role_y, role_w = x + 8, y + 24, 250
        for i, (key, label, _desc, _default) in enumerate(self._color_roles):
            ry = role_y + i * _COLOR_ROLE_ROW_H
            selected = key == self._sel_color_role
            hover = is_hover(mx, my, role_x, ry, role_w, _COLOR_ROLE_ROW_H)
            bg = EDIT_ACCENT if selected else (EDIT_BTN_HOVER if hover else EDIT_BG)
            fg = EDIT_BG if selected else EDIT_TEXT
            pyxel.rect(role_x, ry, role_w, _COLOR_ROLE_ROW_H - 1, bg)
            pyxel.rectb(role_x, ry, role_w, _COLOR_ROLE_ROW_H - 1, EDIT_BORDER)
            idx = self._color_idx(key)
            pyxel.rect(role_x + 6, ry + 5, 12, 12, idx)
            pyxel.rectb(role_x + 6, ry + 5, 12, 12, EDIT_BORDER)
            draw_unicode(role_x + 24, ry + 3, label, fg, size=_SMALL_SIZE)
            draw_unicode(role_x + role_w - 48, ry + 3, str(idx), fg,
                         size=_SMALL_SIZE)

        gx, gy = self._palette_grid_origin()
        pyxel.rectb(gx - 1, gy - 1,
                    _COLOR_GRID_COLS * _COLOR_GRID_CELL + 2,
                    _COLOR_GRID_ROWS * _COLOR_GRID_CELL + 2,
                    EDIT_BORDER)
        sel_idx = self._color_idx(self._sel_color_role)
        for pos, idx in enumerate(self._display_order[:256]):
            cx = gx + (pos % _COLOR_GRID_COLS) * _COLOR_GRID_CELL
            cy = gy + (pos // _COLOR_GRID_COLS) * _COLOR_GRID_CELL
            pyxel.rect(cx, cy, _COLOR_GRID_CELL, _COLOR_GRID_CELL, idx)
            if idx == sel_idx:
                pyxel.rectb(cx, cy, _COLOR_GRID_CELL, _COLOR_GRID_CELL,
                            EDIT_TEXT)

        detail_x, detail_y = x + 452, y + 44
        detail_w = w - (detail_x - x) - 8
        pyxel.rect(detail_x, detail_y, detail_w, 66, EDIT_BG)
        pyxel.rectb(detail_x, detail_y, detail_w, 66, EDIT_BORDER)
        pyxel.rect(detail_x + 8, detail_y + 8, 36, 36, sel_idx)
        pyxel.rectb(detail_x + 8, detail_y + 8, 36, 36, EDIT_BORDER)
        label, desc = self._selected_role_text()
        draw_unicode(detail_x + 52, detail_y + 6, label, EDIT_TEXT,
                     size=_SMALL_SIZE)
        draw_unicode(detail_x + 52, detail_y + 26,
                     f"IDX {sel_idx}  #{_hex_for_idx(sel_idx)}",
                     EDIT_TEXT_DIM, size=_SMALL_SIZE)
        draw_unicode(detail_x + 8, detail_y + 48, desc, EDIT_TEXT_DIM,
                     size=10)

    def _draw_bottom_bar(self, mx: int, my: int):
        pyxel.rect(0, _PANEL_H, 720, _BTN_H, EDIT_TITLE_BG)
        pyxel.line(0, _PANEL_H, 720, _PANEL_H, EDIT_BORDER)
        labels = {
            "save": "SAVE & CLOSE",
            "revert": "REVERT ALL",
            "cancel": "CANCEL",
            "preview": "PREVIEW",
        }
        for key, x, y, w, h in self._bottom_button_rects():
            active = key != "preview" or self._has_page()
            draw_button(x, y, w, labels[key], h=h, active=active,
                        hover=active and is_hover(mx, my, x, y, w, h),
                        size=_FONT_SIZE)
        draw_unicode(520, _PANEL_H + 10, "1+ page = EXTRAS",
                     EDIT_TEXT_DIM, size=10)

    def _color_rect(self):
        return 20, 190, 680, 248

    def _palette_grid_origin(self):
        x, y, _w, _h = self._color_rect()
        return x + 278, y + 50

    def _color_idx(self, role: str) -> int:
        return normalize_extra_text_colors(self._colors()).get(role, 0)

    def _text_size(self) -> int:
        size = normalize_extra_text_size(self._cfg.get("text_size"))
        self._cfg["text_size"] = size
        return size

    def _adjust_text_size(self, delta: int):
        options = list(EXTRA_TEXT_SIZE_OPTIONS)
        cur = self._text_size()
        try:
            idx = options.index(cur)
        except ValueError:
            idx = options.index(normalize_extra_text_size(cur))
        idx = max(0, min(len(options) - 1, idx + int(delta)))
        self._cfg["text_size"] = options[idx]

    def _selected_role_text(self) -> tuple[str, str]:
        for key, label, desc, _default in self._color_roles:
            if key == self._sel_color_role:
                return label, desc
        return "", ""
