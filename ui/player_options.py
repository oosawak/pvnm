"""Runtime OPT screen for player-facing settings."""
import pyxel
from engine.player_prefs import TEXT_SIZE_OPTIONS, normalize_text_size
from ui.colors import (
    PLAY_BG, PLAY_BORDER, PLAY_TEXT, PLAY_ACCENT,
    PLAY_CHOICE_BG, PLAY_CHOICE_HOVER,
)
from ui.widgets import draw_unicode, text_px_w


_WIZARD_ACTIONS = [
    ("confirm", "A / NEXT", "Press the button for OK / next page"),
    ("back", "B / BACK", "Press the button for back / close"),
    ("auto", "X / AUTO", "Press the button for autoplay"),
    ("opt", "Y / OPT", "Press the button for options"),
]

FONT_SIZE = 16
TITLE_SIZE = 24
ROW_H = 64
TOP_ROW_H = 56


class PlayerOptions:
    """Player OPT modal with a controller setup wizard."""

    def __init__(self):
        self.active = False
        self.closed = False
        self.title_requested = False
        self._controller = None
        self._view = "top"
        self._hover = -1
        self._selected = 0
        self._allow_title_return = False
        self._wizard_step = 0
        self._pending_map: dict[str, str] = {}
        self._message = ""
        self._last_mouse = (-1, -1)
        self._get_text_size = lambda: None
        self._get_effective_text_size = lambda: 16
        self._set_text_size = lambda _size: None

    def open(self, controller, text_size_getter=None,
             text_size_effective_getter=None, text_size_setter=None,
             allow_title_return=False):
        self._controller = controller
        self._get_text_size = text_size_getter or (lambda: None)
        self._get_effective_text_size = text_size_effective_getter or (lambda: 16)
        self._set_text_size = text_size_setter or (lambda _size: None)
        self.active = True
        self.closed = False
        self.title_requested = False
        self._view = "top"
        self._hover = -1
        self._selected = 0
        self._allow_title_return = bool(allow_title_return)
        self._wizard_step = 0
        self._pending_map = {}
        self._message = ""
        self._last_mouse = (pyxel.mouse_x, pyxel.mouse_y)

    def close(self):
        self.active = False
        self.closed = True
        self._view = "top"
        self._message = ""

    def handle_back(self):
        if not self.active:
            return
        if self._view == "wizard":
            self._view = "controller"
            self._selected = 0
            self._message = "Setup canceled"
        elif self._view in ("controller", "help", "text_size", "confirm_title"):
            self._view = "top"
            self._selected = 0
            self._message = ""
        else:
            self.close()
        self._last_mouse = (pyxel.mouse_x, pyxel.mouse_y)

    def update(self):
        if not self.active or self._controller is None:
            return
        if self._view == "controller":
            self._update_controller()
        elif self._view == "help":
            self._update_help()
        elif self._view == "text_size":
            self._update_text_size()
        elif self._view == "wizard":
            self._update_wizard()
        elif self._view == "confirm_title":
            self._update_confirm_title()
        else:
            self._update_top()

    def draw(self):
        if not self.active or self._controller is None:
            return

        W, H = pyxel.width, pyxel.height
        for y in range(0, H, 2):
            pyxel.line(0, y, W - 1, y, 0)

        px, py, pw, ph = 70, 42, W - 140, H - 84
        pyxel.rect(px, py, pw, ph, PLAY_BG)
        pyxel.rectb(px, py, pw, ph, PLAY_ACCENT)
        pyxel.rectb(px + 2, py + 2, pw - 4, ph - 4, PLAY_BORDER)

        draw_unicode(px + 14, py + 10, "OPTIONS", PLAY_TEXT, size=TITLE_SIZE)
        if self._view == "controller":
            self._draw_controller(px, py, pw, ph)
        elif self._view == "help":
            self._draw_help(px, py, pw, ph)
        elif self._view == "text_size":
            self._draw_text_size(px, py, pw, ph)
        elif self._view == "wizard":
            self._draw_wizard(px, py, pw, ph)
        elif self._view == "confirm_title":
            self._draw_confirm_title(px, py, pw, ph)
        else:
            self._draw_top(px, py, pw, ph)

    # ── Top view ────────────────────────────────────────────────

    def _update_top(self):
        items = self._top_items()
        self._handle_nav(len(items))
        self._handle_mouse_rows(len(items), 96, 124, pyxel.width - 192, TOP_ROW_H)
        if self._confirm_pressed() or self._face_pressed():
            action = items[self._selected][0]
            if action == "help":
                self._view = "help"
                self._selected = 0
                self._message = ""
                self._last_mouse = (pyxel.mouse_x, pyxel.mouse_y)
            elif action == "text_size":
                self._view = "text_size"
                self._selected = self._text_size_selected_index()
                self._message = ""
                self._last_mouse = (pyxel.mouse_x, pyxel.mouse_y)
            elif action == "controller":
                self._view = "controller"
                self._selected = 0
                self._message = ""
                self._last_mouse = (pyxel.mouse_x, pyxel.mouse_y)
            elif action == "title":
                self._view = "confirm_title"
                self._selected = 1
                self._message = ""
                self._last_mouse = (pyxel.mouse_x, pyxel.mouse_y)
            else:
                self.close()
            return
        if self._close_pressed():
            self.close()
            return

    def _draw_top(self, px, py, pw, ph):
        draw_unicode(px + 14, py + 48, "MENU", PLAY_ACCENT, size=FONT_SIZE)
        items = self._top_items()
        x, y, w, row_h = 96, 124, pyxel.width - 192, TOP_ROW_H
        for i, (_action, label, value, desc) in enumerate(items):
            self._draw_row(x, y + i * row_h, w, row_h, label, value, desc,
                           i == self._selected)
        draw_unicode(px + 14, py + ph - 24,
                     "A/ENTER: SELECT   B/ESC: CLOSE", PLAY_TEXT, size=FONT_SIZE)

    def _top_items(self):
        items = [
            ("help", "HELP", "", "Show current controls"),
            ("text_size", "TEXT SIZE", self._text_size_value_label(),
             "Change dialog text size"),
            ("controller", "CONTROLLER SETTING", "",
             "A/B/X/Y also open this item"),
        ]
        if self._allow_title_return:
            items.append(("title", "TITLE", "", "Return to title screen"))
        items.append(("close", "CLOSE", "", "Return to the game"))
        return items

    # ── Return to title confirm ─────────────────────────────────

    def _update_confirm_title(self):
        self._handle_nav(2)
        self._handle_mouse_rows(2, 96, 216, pyxel.width - 192, ROW_H)
        if self._close_pressed():
            self._view = "top"
            self._selected = 0
            self._message = ""
            self._last_mouse = (pyxel.mouse_x, pyxel.mouse_y)
            return
        if self._confirm_pressed() or self._face_pressed():
            if self._selected == 0:
                self.title_requested = True
                self.active = False
                self.closed = True
                self._view = "top"
            else:
                self._view = "top"
                self._selected = 0
                self._message = ""
            self._last_mouse = (pyxel.mouse_x, pyxel.mouse_y)

    def _draw_confirm_title(self, px, py, pw, ph):
        draw_unicode(px + 14, py + 48, "RETURN TO TITLE?",
                     PLAY_ACCENT, size=FONT_SIZE)
        draw_unicode(px + 28, py + 88,
                     "Unsaved progress since the last save will be lost.",
                     PLAY_TEXT, size=FONT_SIZE)
        rows = [
            ("YES", "", "Return to the title screen"),
            ("NO", "", "Go back to options"),
        ]
        x, y, w, row_h = 96, 216, pyxel.width - 192, ROW_H
        for i, (label, value, desc) in enumerate(rows):
            self._draw_row(x, y + i * row_h, w, row_h, label, value, desc,
                           i == self._selected)
        draw_unicode(px + 14, py + ph - 24,
                     "A/ENTER: SELECT   B/ESC: BACK", PLAY_TEXT, size=FONT_SIZE)

    # ── Help ────────────────────────────────────────────────────

    def _update_help(self):
        row_y = pyxel.height - 92
        self._handle_nav(1)
        self._handle_mouse_rows(1, 96, row_y, pyxel.width - 192, 38)
        if self._confirm_pressed() or self._close_pressed() or self._face_pressed():
            self._view = "top"
            self._selected = 0
            self._message = ""
            self._last_mouse = (pyxel.mouse_x, pyxel.mouse_y)

    def _draw_help(self, px, py, pw, ph):
        draw_unicode(px + 14, py + 48, "HELP", PLAY_ACCENT, size=FONT_SIZE)
        gamepad_controls = [
            (_button_label(self._controller, "confirm"), "NEXT / OK"),
            (_button_label(self._controller, "back"), "BACK / CLOSE"),
            (_button_label(self._controller, "auto"), "AUTO SPEED"),
            (_button_label(self._controller, "opt"), "OPTIONS"),
            (_button_label(self._controller, "save"), "SAVE"),
            (_button_label(self._controller, "hide_dialog"), "HIDE DIALOG"),
            (_button_label(self._controller, "log"), "LOG"),
            (f"HOLD {_button_label(self._controller, 'skip_hold')}", "SKIP"),
            ("BACK+START", "TITLE"),
            ("D-PAD", "MENU SELECT"),
        ]
        pc_controls = [
            ("ENTER / SPACE", "NEXT / OK"),
            ("CLICK DIALOG", "NEXT"),
            ("LEFT", "PREV SCENE"),
            ("ESC", "CLOSE / TITLE"),
            ("HOLD CTRL", "SKIP"),
            ("OPT > TITLE", "TITLE"),
            ("SCREEN BTNS", "UI BUTTONS"),
        ]
        left_x = px + 42
        right_x = px + 312
        top_y = py + 76
        row_h = 20
        draw_unicode(left_x, top_y, "GAMEPAD", PLAY_ACCENT, size=FONT_SIZE)
        draw_unicode(right_x, top_y, "PC / MAC", PLAY_ACCENT, size=FONT_SIZE)
        list_y = top_y + 24
        for i, (button, action) in enumerate(gamepad_controls):
            y = list_y + i * row_h
            draw_unicode(left_x, y, button, PLAY_ACCENT, size=FONT_SIZE)
            draw_unicode(left_x + 120, y, action, PLAY_TEXT, size=FONT_SIZE)
        for i, (button, action) in enumerate(pc_controls):
            y = list_y + i * row_h
            draw_unicode(right_x, y, button, PLAY_ACCENT, size=FONT_SIZE)
            draw_unicode(right_x + 128, y, action, PLAY_TEXT, size=FONT_SIZE)
        self._draw_help_back_button(96, pyxel.height - 92,
                                    pyxel.width - 192, 38)

    def _draw_help_back_button(self, x, y, w, h):
        pyxel.rect(x, y, w, h, PLAY_CHOICE_HOVER)
        pyxel.rectb(x, y, w, h, PLAY_BORDER)
        draw_unicode(x + 10, y + 8, "BACK", PLAY_BG, size=FONT_SIZE)
        draw_unicode(x + 112, y + 8, "Return to options menu",
                     PLAY_BG, size=FONT_SIZE)

    # ── Text size ───────────────────────────────────────────────

    def _update_text_size(self):
        self._handle_text_size_nav()
        self._handle_text_size_pointer()
        if self._close_pressed():
            self._view = "top"
            self._selected = 1
            self._message = ""
            self._last_mouse = (pyxel.mouse_x, pyxel.mouse_y)
            return
        if self._confirm_pressed() or self._face_pressed():
            self._activate_text_size_item()

    def _draw_text_size(self, px, py, pw, ph):
        draw_unicode(px + 14, py + 48, "TEXT SIZE", PLAY_ACCENT, size=FONT_SIZE)
        for idx, rect in enumerate(_text_size_rects()):
            x, y, w, h = rect
            selected = (idx == self._selected)
            active = self._is_text_size_item_active(idx)
            if idx == 0:
                label = "GAME DEFAULT"
                value = str(self._safe_effective_text_size())
            elif 1 <= idx <= len(TEXT_SIZE_OPTIONS):
                label = str(TEXT_SIZE_OPTIONS[idx - 1])
                value = "ON" if active else ""
            else:
                label = "BACK"
                value = ""
            self._draw_text_size_cell(x, y, w, h, label, value, selected, active)

    def _handle_text_size_nav(self):
        count = len(TEXT_SIZE_OPTIONS) + 2
        if pyxel.btnp(pyxel.KEY_UP, hold=15, repeat=5) or self._controller.nav_up():
            self._selected = _text_size_nav_up(self._selected)
        if pyxel.btnp(pyxel.KEY_DOWN, hold=15, repeat=5) or self._controller.nav_down():
            self._selected = _text_size_nav_down(self._selected)
        if pyxel.btnp(pyxel.KEY_LEFT, hold=15, repeat=5) or self._controller.nav_left():
            self._selected = max(0, self._selected - 1)
        if pyxel.btnp(pyxel.KEY_RIGHT, hold=15, repeat=5) or self._controller.nav_right():
            self._selected = min(count - 1, self._selected + 1)

    def _handle_text_size_pointer(self):
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        clicked = pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT)
        moved = (mx, my) != self._last_mouse
        self._last_mouse = (mx, my)
        if not (moved or clicked):
            self._hover = -1
            return
        self._hover = -1
        for idx, (x, y, w, h) in enumerate(_text_size_rects()):
            if x <= mx < x + w and y <= my < y + h:
                self._hover = idx
                self._selected = idx
                break

    def _activate_text_size_item(self):
        if self._selected == 0:
            self._set_text_size(None)
            self._message = "Text size: game default"
            return
        if 1 <= self._selected <= len(TEXT_SIZE_OPTIONS):
            size = TEXT_SIZE_OPTIONS[self._selected - 1]
            self._set_text_size(size)
            self._message = f"Text size: {size}"
            return
        self._view = "top"
        self._selected = 1
        self._message = ""
        self._last_mouse = (pyxel.mouse_x, pyxel.mouse_y)

    def _text_size_selected_index(self) -> int:
        override = normalize_text_size(self._safe_text_size_override())
        if override is None:
            return 0
        return TEXT_SIZE_OPTIONS.index(override) + 1

    def _is_text_size_item_active(self, idx: int) -> bool:
        override = normalize_text_size(self._safe_text_size_override())
        if idx == 0:
            return override is None
        if 1 <= idx <= len(TEXT_SIZE_OPTIONS):
            return override == TEXT_SIZE_OPTIONS[idx - 1]
        return False

    def _text_size_value_label(self) -> str:
        override = normalize_text_size(self._safe_text_size_override())
        if override is None:
            return f"DEFAULT {self._safe_effective_text_size()}"
        return str(override)

    def _safe_text_size_override(self):
        try:
            return self._get_text_size()
        except Exception:
            return None

    def _safe_effective_text_size(self) -> int:
        try:
            return int(self._get_effective_text_size())
        except Exception:
            return 16

    def _draw_text_size_cell(self, x, y, w, h, label, value, selected, active):
        bg = PLAY_CHOICE_HOVER if selected else PLAY_CHOICE_BG
        fg = PLAY_BG if selected else PLAY_TEXT
        border = PLAY_ACCENT if active else PLAY_BORDER
        pyxel.rect(x, y, w, h, bg)
        pyxel.rectb(x, y, w, h, border)
        label_w = text_px_w(label, FONT_SIZE)
        draw_unicode(x + (w - label_w) // 2, y + 8, label, fg, size=FONT_SIZE)
        if value:
            val_w = text_px_w(value, FONT_SIZE)
            draw_unicode(x + w - val_w - 8, y + h - 20, value, fg, size=FONT_SIZE)

    # ── Controller list ─────────────────────────────────────────

    def _update_controller(self):
        items = 2  # setup wizard, back
        self._handle_nav(items)
        self._handle_mouse_rows(items, 96, 124, pyxel.width - 192, ROW_H)
        if self._confirm_pressed() or self._face_pressed():
            if self._selected == 0:
                self._start_wizard()
            elif self._selected == items - 1:
                self._view = "top"
                self._selected = 0
                self._message = ""
                self._last_mouse = (pyxel.mouse_x, pyxel.mouse_y)
            return
        if self._close_pressed():
            self._view = "top"
            self._selected = 0
            self._message = ""
            self._last_mouse = (pyxel.mouse_x, pyxel.mouse_y)
            return

    def _draw_controller(self, px, py, pw, ph):
        draw_unicode(px + 14, py + 48, "CONTROLLER SETTING",
                     PLAY_ACCENT, size=FONT_SIZE)
        x, y, w, row_h = 96, 124, pyxel.width - 192, ROW_H
        self._draw_row(x, y, w, row_h, "SETUP WIZARD", "",
                       "Configure A/B/X/Y buttons",
                       self._selected == 0)
        self._draw_row(x, y + row_h, w, row_h, "BACK", "",
                       "Return to options menu", self._selected == 1)
        hint = self._message or "A/Enter: select   B/Esc: back"
        draw_unicode(px + 14, py + ph - 28, hint.upper(), PLAY_TEXT, size=FONT_SIZE)

    # ── Wizard ──────────────────────────────────────────────────

    def _start_wizard(self):
        self._view = "wizard"
        self._wizard_step = 0
        self._pending_map = {}
        self._message = ""

    def _update_wizard(self):
        if self._close_pressed():
            self.handle_back()
            return
        action = _WIZARD_ACTIONS[self._wizard_step][0]
        name = self._controller.any_pressed_face_button()
        if not name:
            return
        if name in self._pending_map.values():
            self._message = "Already used. Press a different button."
            return
        self._pending_map[action] = name
        self._wizard_step += 1
        self._message = ""
        if self._wizard_step >= len(_WIZARD_ACTIONS):
            for key, value in self._pending_map.items():
                self._controller.mapping[key] = value
            self._controller.save_user_mapping()
            self._view = "controller"
            self._selected = 0
            self._message = "Controller mapping saved"
            self._last_mouse = (pyxel.mouse_x, pyxel.mouse_y)

    def _draw_wizard(self, px, py, pw, ph):
        draw_unicode(px + 14, py + 36, "CONTROLLER SETUP WIZARD",
                     PLAY_ACCENT, size=FONT_SIZE)
        _action, label, desc = _WIZARD_ACTIONS[self._wizard_step]
        step = f"STEP {self._wizard_step + 1} / {len(_WIZARD_ACTIONS)}"
        draw_unicode(px + 14, py + 72, step, PLAY_TEXT, size=FONT_SIZE)

        box_x, box_y, box_w, box_h = px + 44, py + 118, pw - 88, 128
        pyxel.rect(box_x, box_y, box_w, box_h, PLAY_CHOICE_BG)
        pyxel.rectb(box_x, box_y, box_w, box_h, PLAY_ACCENT)
        msg = f"PRESS: {label}"
        draw_unicode(box_x + (box_w - text_px_w(msg, 24)) // 2,
                     box_y + 32, msg, PLAY_TEXT, size=24)
        draw_unicode(box_x + (box_w - text_px_w(desc, FONT_SIZE)) // 2,
                     box_y + 84, desc, PLAY_TEXT, size=FONT_SIZE)

        y = py + 270
        for i, (key, done_label, _done_desc) in enumerate(_WIZARD_ACTIONS):
            value = self._pending_map.get(key)
            col = PLAY_ACCENT if value else PLAY_TEXT
            suffix = _short_button(value) if value else "-"
            draw_unicode(px + 64 + (i % 2) * 250,
                         y + (i // 2) * 28,
                         f"{done_label}: {suffix}", col, size=FONT_SIZE)

        hint = self._message or "Esc cancels. Duplicate buttons are ignored."
        draw_unicode(px + 14, py + ph - 28, hint, PLAY_TEXT, size=FONT_SIZE)

    # ── Shared helpers ──────────────────────────────────────────

    def _handle_nav(self, count: int):
        if pyxel.btnp(pyxel.KEY_UP, hold=15, repeat=5) or self._controller.nav_up():
            self._selected = (self._selected - 1) % count
        if pyxel.btnp(pyxel.KEY_DOWN, hold=15, repeat=5) or self._controller.nav_down():
            self._selected = (self._selected + 1) % count

    def _handle_mouse_rows(self, count: int, x: int, y: int,
                           w: int, row_h: int):
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        clicked = pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT)
        moved = (mx, my) != self._last_mouse
        self._last_mouse = (mx, my)
        if not (moved or clicked):
            self._hover = -1
            return
        self._hover = -1
        for i in range(count):
            ry = y + i * row_h
            if x <= mx < x + w and ry <= my < ry + row_h:
                self._hover = i
                self._selected = i
                break

    def _confirm_pressed(self) -> bool:
        clicked = pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) and self._hover >= 0
        return (clicked or pyxel.btnp(pyxel.KEY_RETURN)
                or pyxel.btnp(pyxel.KEY_SPACE)
                or self._controller.pressed("confirm"))

    def _close_pressed(self) -> bool:
        return (pyxel.btnp(pyxel.KEY_ESCAPE)
                or pyxel.btnp(pyxel.KEY_BACKSPACE)
                or self._controller.pressed("back"))

    def _face_pressed(self) -> bool:
        for name in (
            "GAMEPAD1_BUTTON_A", "GAMEPAD1_BUTTON_B",
            "GAMEPAD1_BUTTON_X", "GAMEPAD1_BUTTON_Y",
            "GAMEPAD2_BUTTON_A", "GAMEPAD2_BUTTON_B",
            "GAMEPAD2_BUTTON_X", "GAMEPAD2_BUTTON_Y",
        ):
            code = getattr(pyxel, name, None)
            if isinstance(code, int) and pyxel.btnp(code):
                return True
        return False

    def _draw_row(self, x, y, w, h, label, value, desc, selected):
        bg = PLAY_CHOICE_HOVER if selected else PLAY_CHOICE_BG
        fg = PLAY_BG if selected else PLAY_TEXT
        pyxel.rect(x, y, w, h - 4, bg)
        pyxel.rectb(x, y, w, h - 4, PLAY_BORDER)
        label_y = y + 7
        desc_y = y + (30 if h <= 56 else 36)
        if value:
            value_w = text_px_w(value, FONT_SIZE)
            draw_unicode(x + w - value_w - 12, label_y, value, fg, size=FONT_SIZE)
        draw_unicode(x + 10, label_y, label, fg, size=FONT_SIZE)
        draw_unicode(x + 10, desc_y, desc, fg, size=FONT_SIZE)


def _short_button(name: str | None) -> str:
    if not name:
        return "-"
    label = name.replace("GAMEPAD1_BUTTON_", "").replace(
        "GAMEPAD2_BUTTON_", "P2 "
    ).replace("GAMEPAD3_BUTTON_", "P3 ").replace("GAMEPAD4_BUTTON_", "P4 ")
    return _friendly_button(label)


def _button_label(controller, action: str) -> str:
    return _friendly_button(controller.button_label(action))


def _friendly_button(label: str) -> str:
    return label.replace("LEFTSHOULDER", "L1").replace(
        "RIGHTSHOULDER", "R1"
    ).replace("DPAD_", "D-")


def _text_size_rects() -> list[tuple[int, int, int, int]]:
    x, w = 96, pyxel.width - 192
    rects: list[tuple[int, int, int, int]] = [(x, 112, w, 42)]
    gap = 8
    cell_w = (w - gap * 2) // 3
    cell_h = 48
    y0 = 166
    for i in range(len(TEXT_SIZE_OPTIONS)):
        col = i % 3
        row = i // 3
        rects.append((x + col * (cell_w + gap),
                      y0 + row * (cell_h + gap),
                      cell_w, cell_h))
    rects.append((x, 348, w, 42))
    return rects


def _text_size_nav_up(idx: int) -> int:
    if idx == 0:
        return len(TEXT_SIZE_OPTIONS) + 1
    if 1 <= idx <= 3:
        return 0
    if 4 <= idx <= len(TEXT_SIZE_OPTIONS):
        return idx - 3
    return 7


def _text_size_nav_down(idx: int) -> int:
    back_idx = len(TEXT_SIZE_OPTIONS) + 1
    if idx == 0:
        return 1
    if 1 <= idx <= 6:
        return idx + 3
    if 7 <= idx <= len(TEXT_SIZE_OPTIONS):
        return back_idx
    return 0
