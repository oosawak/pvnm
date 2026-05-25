"""セーブ/ロード画面: 3×3グリッド (9スロット) のモーダルUI"""
import pyxel
from datetime import datetime
from engine import storage as _storage
from ui.widgets import (
    draw_unicode, text_px_w, _font_render_h, pointer_intent_active,
)

# レイアウト
MARGIN_X = 20
MARGIN_Y = 18
COLS = 3
ROWS = 3
SLOT_W = 220
SLOT_H = 126
GAP = 8
HEADER_H = 38
FONT_SIZE = 16


class SaveLoadScreen:
    """モーダルセーブ/ロード画面。"""

    def __init__(self):
        self.active = False
        self.closed = False
        self.mode = "save"
        self._slots: list[dict | None] = [None] * 9
        self._save_path = ""
        self._hover = -1
        self._on_save = None
        self._on_load = None
        self._result: dict | None = None
        self._selected = 0
        self._controller = None

    @property
    def load_result(self) -> dict | None:
        r = self._result
        self._result = None
        return r

    def open(self, mode: str, on_save=None, on_load=None,
             save_path: str = "", controller=None):
        self.mode = mode
        self.active = True
        self.closed = False
        self._on_save = on_save
        self._on_load = on_load
        self._save_path = save_path or "pvnm_saves.json"
        self._hover = -1
        self._result = None
        self._selected = 0
        self._controller = controller
        self._load_slots()

    def _load_slots(self):
        self._slots = [None] * 9
        if not self._save_path:
            return
        try:
            data = _storage.read_json(self._save_path, default=None)
            if not isinstance(data, dict):
                return
            slots = data.get("slots", [])
            for i, s in enumerate(slots[:9]):
                self._slots[i] = s
        except Exception:
            pass

    def _save_slots(self):
        data = {"slots": self._slots}
        try:
            if not _storage.write_json(self._save_path, data):
                raise RuntimeError("storage backend returned false")
        except Exception as e:
            print(f"[SaveLoad] save failed: {e}")

    def _slot_rect(self, idx: int) -> tuple[int, int, int, int]:
        col = idx % COLS
        row = idx // COLS
        grid_w = COLS * SLOT_W + (COLS - 1) * GAP
        ox = (pyxel.width - grid_w) // 2
        oy = MARGIN_Y + HEADER_H + 8
        x = ox + col * (SLOT_W + GAP)
        y = oy + row * (SLOT_H + GAP)
        return x, y, SLOT_W, SLOT_H

    def update(self):
        if not self.active:
            return

        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self.active = False
            self.closed = True
            return

        mx, my = pyxel.mouse_x, pyxel.mouse_y
        W, H = pyxel.width, pyxel.height
        px, py = MARGIN_X, MARGIN_Y
        pw, ph = W - MARGIN_X * 2, H - MARGIN_Y * 2
        self._hover = -1

        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) and not (
            px <= mx < px + pw and py <= my < py + ph
        ):
            self.active = False
            self.closed = True
            return

        pointer_active = pointer_intent_active()
        if pointer_active:
            for i in range(9):
                sx, sy, sw, sh = self._slot_rect(i)
                if sx <= mx < sx + sw and sy <= my < sy + sh:
                    self._hover = i
                    self._selected = i
                    break

        self._update_selection()

        clicked = pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) and self._hover >= 0
        confirm = (clicked or pyxel.btnp(pyxel.KEY_RETURN)
                   or pyxel.btnp(pyxel.KEY_SPACE)
                   or (self._controller
                       and self._controller.pressed("confirm")))
        if confirm and 0 <= self._selected < 9:
            idx = self._selected
            if self.mode == "save":
                self._do_save(idx)
            else:
                self._do_load(idx)

    def _update_selection(self):
        c = self._controller
        if pyxel.btnp(pyxel.KEY_LEFT, hold=15, repeat=5) or (c and c.nav_left()):
            self._selected = max(0, self._selected - 1)
        if pyxel.btnp(pyxel.KEY_RIGHT, hold=15, repeat=5) or (c and c.nav_right()):
            self._selected = min(8, self._selected + 1)
        if pyxel.btnp(pyxel.KEY_UP, hold=15, repeat=5) or (c and c.nav_up()):
            self._selected = max(0, self._selected - COLS)
        if pyxel.btnp(pyxel.KEY_DOWN, hold=15, repeat=5) or (c and c.nav_down()):
            self._selected = min(8, self._selected + COLS)

    def _do_save(self, idx: int):
        if not self._on_save:
            return
        state = self._on_save()
        if state is None:
            return
        state["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        self._slots[idx] = state
        self._save_slots()

    def _do_load(self, idx: int):
        slot = self._slots[idx]
        if slot is None:
            return
        self._result = slot
        if self._on_load:
            self._on_load(slot)
        self.active = False
        self.closed = True

    def draw(self):
        if not self.active:
            return

        W, H = pyxel.width, pyxel.height

        # 半透明背景
        for y in range(0, H, 2):
            pyxel.line(0, y, W - 1, y, 0)

        pw = W - MARGIN_X * 2
        ph = H - MARGIN_Y * 2
        px, py = MARGIN_X, MARGIN_Y
        pyxel.rect(px, py, pw, ph, 1)
        pyxel.rectb(px, py, pw, ph, 5)

        # ヘッダ
        title = "SAVE" if self.mode == "save" else "LOAD"
        pyxel.rect(px + 1, py + 1, pw - 2, HEADER_H - 2, 5)
        frh = _font_render_h(FONT_SIZE)
        draw_unicode(px + 10, py + max(4, (HEADER_H - frh) // 2),
                     f"{title}  B/ESC: CLOSE", 7, size=FONT_SIZE)

        for i in range(9):
            self._draw_slot(i)

    def _draw_slot(self, idx: int):
        sx, sy, sw, sh = self._slot_rect(idx)
        slot = self._slots[idx]
        hover = (self._hover == idx) or (self._selected == idx)

        bg = 2 if hover else 0
        pyxel.rect(sx, sy, sw, sh, bg)
        pyxel.rectb(sx, sy, sw, sh, 5 if hover else 13)

        draw_unicode(sx + 6, sy + 5, f"SLOT {idx + 1}", 6, size=FONT_SIZE)

        if slot is None:
            label = "- Empty -"
            draw_unicode(sx + (sw - text_px_w(label, FONT_SIZE)) // 2,
                         sy + sh // 2 - 8, label, 13, size=FONT_SIZE)
        else:
            lh = _font_render_h(FONT_SIZE)
            y = sy + lh + 6
            part = slot.get("part_name", "")
            chap = slot.get("chapter_name", "")

            if part:
                self._draw_slot_text(sx + 6, y, _truncate_px(part, sw - 12), 7)
                y += lh
            if chap:
                self._draw_slot_text(sx + 6, y, _truncate_px(chap, sw - 12), 7)
                y += lh
            # Keep scene_name/scene_display private. They may be internal IDs
            # or draft labels that should not be shown to players.
            y += lh

            speaker = slot.get("speaker", "")
            text_prev = slot.get("text_preview", "")
            if speaker and y + lh < sy + sh - lh:
                self._draw_slot_text(sx + 6, y, _truncate_px(f"[{speaker}]", sw - 12), 8)
                y += lh
            if text_prev and y + lh < sy + sh - lh:
                self._draw_slot_text(sx + 6, y, _truncate_px(text_prev, sw - 12), 7)

            ts = slot.get("timestamp", "")
            if ts:
                draw_unicode(sx + 6, sy + sh - lh - 3, ts, 6, size=FONT_SIZE)

    def _draw_slot_text(self, x, y, text, col):
        """日本語対応テキスト描画"""
        draw_unicode(x, y, text, col, size=FONT_SIZE)


def _truncate_px(text: str, max_w: int) -> str:
    if text_px_w(text, FONT_SIZE) <= max_w:
        return text
    suffix = ".."
    out = ""
    for ch in text:
        if text_px_w(out + ch + suffix, FONT_SIZE) > max_w:
            break
        out += ch
    return (out or text[:1]) + suffix
