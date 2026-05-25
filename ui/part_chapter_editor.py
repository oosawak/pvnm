"""Part / Chapter 編集モーダル (720×480 フルスクリーン)

Part 一覧または Chapter 一覧を表示し、追加・コピー・削除・名前変更・
ドラッグ&ドロップによる並べ替えができる。
"""
import copy
import pyxel
from ui.colors import (
    EDIT_BG, EDIT_PANEL, EDIT_BORDER, EDIT_TEXT, EDIT_TEXT_DIM, EDIT_ACCENT,
    EDIT_BTN_BG, EDIT_BTN_HOVER, EDIT_PREVIEW_BG, EDIT_HIGHLIGHT, EDIT_TITLE_BG,
)
import ui.widgets as _w
from ui.widgets import (
    draw_panel, draw_titlebar, draw_button, draw_unicode,
    draw_list_item,
    is_hover, is_clicked,
    title_bar_h, item_h,
)
from ui.native_dialogs import ask_text, AsyncTextDialog
from ui.confirm_dialog import ConfirmDialog

# レイアウト
_BTN_BAR_H = 32
_PANEL_H   = 480 - _BTN_BAR_H
_LIST_W    = 360
_DETAIL_W  = 720 - _LIST_W  # = 360

_DRAG_THRESHOLD = 4


def _native_ask(label: str, initial: str) -> str | None:
    """ネイティブダイアログでテキスト入力"""
    return ask_text(label, initial)


class _AsyncDialog(AsyncTextDialog):
    """Backward-compatible async text dialog."""


class PartChapterEditor:
    """Part または Chapter の編集モーダル。

    mode="parts": Part 一覧を編集
    mode="chapters": 指定 Part 内の Chapter 一覧を編集
    """

    def __init__(self):
        self.active = False
        self.result = None  # "saved" | "cancelled"
        self._mode  = "parts"
        self._state = None
        self._part_id = 0  # chapters モードで使用
        self._sel   = 0
        self._scroll = 0
        self._dialog = _AsyncDialog()
        # ドラッグ&ドロップ
        self._drag_src = -1
        self._drag_start_y = 0
        self._drag_active = False
        self._snapshot = None
        self._pending_delete_item = None
        self._discard_confirm = ConfirmDialog()

    def open_parts(self, state):
        self.active  = True
        self.result  = None
        self._mode   = "parts"
        self._state  = state
        self._sel    = 0
        self._scroll = 0
        self._drag_src = -1
        self._drag_active = False
        self._pending_delete_item = None
        self._discard_confirm.result = None
        self._discard_confirm.active = False
        self._take_snapshot()

    def open_chapters(self, state, part_id: int):
        self.active   = True
        self.result   = None
        self._mode    = "chapters"
        self._state   = state
        self._part_id = part_id
        self._sel     = 0
        self._scroll  = 0
        self._drag_src = -1
        self._drag_active = False
        self._pending_delete_item = None
        self._discard_confirm.result = None
        self._discard_confirm.active = False
        self._take_snapshot()

    def _take_snapshot(self):
        self._snapshot = {
            "parts": copy.deepcopy(self._state.parts),
            "chapters": copy.deepcopy(self._state.chapters),
            "scenes": copy.deepcopy(self._state.scenes),
            "current_part_id": self._state.current_part_id,
            "current_chapter_id": self._state.current_chapter_id,
            "selected_scene": self._state.selected_scene,
            "selected_special": self._state.selected_special,
            "dirty": self._state.dirty,
            "scene_gen": self._state.scene_gen,
        }

    def _restore_snapshot(self):
        if not self._snapshot:
            return
        self._state.parts = copy.deepcopy(self._snapshot["parts"])
        self._state.chapters = copy.deepcopy(self._snapshot["chapters"])
        self._state.scenes = copy.deepcopy(self._snapshot["scenes"])
        self._state.current_part_id = self._snapshot["current_part_id"]
        self._state.current_chapter_id = self._snapshot["current_chapter_id"]
        self._state.selected_scene = self._snapshot["selected_scene"]
        self._state.selected_special = self._snapshot["selected_special"]
        self._state.dirty = self._snapshot["dirty"]
        self._state.scene_gen = self._snapshot["scene_gen"] + 1

    def _finish_saved(self):
        self._state.normalize_scene_order()
        self.result = "saved"
        self.active = False
        self._snapshot = None
        self._pending_delete_item = None

    def _finish_cancelled(self):
        self._restore_snapshot()
        self.result = "cancelled"
        self.active = False
        self._snapshot = None
        self._pending_delete_item = None

    def _dirty(self) -> bool:
        if not self._snapshot or self._state is None:
            return False
        return (
            self._state.parts != self._snapshot["parts"]
            or self._state.chapters != self._snapshot["chapters"]
            or self._state.scenes != self._snapshot["scenes"]
            or self._state.current_part_id != self._snapshot["current_part_id"]
            or self._state.current_chapter_id != self._snapshot["current_chapter_id"]
            or self._state.selected_scene != self._snapshot["selected_scene"]
            or self._state.selected_special != self._snapshot["selected_special"]
        )

    def _request_cancel(self):
        if self._dirty():
            self._discard_confirm.open(
                "UNSAVED CHANGES",
                "Part/Chapter edits are not saved.\n"
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

    # ── リストデータ取得 ────────────────────────────────────

    def _items(self) -> list:
        if self._mode == "parts":
            return self._state.parts
        else:
            return self._state.chapters_for_part(self._part_id)

    def _item_label(self, item: dict) -> str:
        if self._mode == "parts":
            return f"{item['id']:04d}: {item['name']}"
        else:
            return f"{item['id']:04d}: {item['name']}"

    # ── update ────────────────────────────────────────────────

    def update(self):
        if not self.active:
            return
        self._dialog.poll()
        if self._dialog.running:
            return
        if self._update_discard_confirm():
            return
        if self._pending_delete_item is not None:
            self._update_delete_confirm()
            return

        mx, my = pyxel.mouse_x, pyxel.mouse_y
        items = self._items()

        # リスト領域
        list_x, list_y = 4, title_bar_h() + 4
        list_w, list_h = _LIST_W - 8, _PANEL_H - title_bar_h() - 8
        ih = item_h()

        # スクロール
        if is_hover(mx, my, list_x, list_y, list_w, list_h):
            wheel = pyxel.mouse_wheel
            if wheel:
                total = len(items) * ih
                self._scroll -= wheel * 20
                self._scroll = max(0, min(max(0, total - list_h), self._scroll))

        # ドラッグ&ドロップ
        if self._drag_src >= 0:
            if pyxel.btn(pyxel.MOUSE_BUTTON_LEFT):
                if not self._drag_active and abs(my - self._drag_start_y) > _DRAG_THRESHOLD:
                    self._drag_active = True
            else:
                if self._drag_active and items:
                    drop = self._drop_index(my, list_y, items, ih)
                    if drop is not None and drop != self._drag_src:
                        self._do_reorder(self._drag_src, drop)
                        self._sel = drop
                self._drag_src = -1
                self._drag_active = False
        else:
            for i, item in enumerate(items):
                iy = list_y + i * ih - self._scroll
                if iy + ih <= list_y or iy >= list_y + list_h:
                    continue
                if is_clicked(mx, my, list_x, iy, list_w, ih):
                    self._sel = i
                    self._drag_src = i
                    self._drag_start_y = my
                    self._drag_active = False

        # 右パネル: 名前編集ボタン
        if items and 0 <= self._sel < len(items):
            rename_x = _LIST_W + 8
            rename_y = title_bar_h() + 40
            rename_w = _DETAIL_W - 16
            if is_clicked(mx, my, rename_x, rename_y, rename_w, 24):
                current_name = items[self._sel]["name"]
                label = "PART NAME" if self._mode == "parts" else "CHAPTER NAME"
                sel_item = items[self._sel]
                def _cb(val, it=sel_item):
                    if val:
                        it["name"] = val
                        self._state.dirty = True
                self._dialog.open(label, current_name, _cb)

        # ボタンバー
        bar_y = _PANEL_H + (_BTN_BAR_H - 20) // 2
        bw = 80
        gap = 6
        bx = 4

        if is_clicked(mx, my, bx, bar_y, bw, 20):
            self._do_add()
        bx += bw + gap
        if is_clicked(mx, my, bx, bar_y, bw, 20):
            self._do_copy()
        bx += bw + gap
        if is_clicked(mx, my, bx, bar_y, bw, 20):
            self._request_delete()
        bx += bw + gap + 20
        if is_clicked(mx, my, bx, bar_y, bw, 20):
            self._finish_saved()
        bx += bw + gap
        if is_clicked(mx, my, bx, bar_y, bw, 20):
            self._request_cancel()

        # ESC
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self._request_cancel()

    def _drop_index(self, my, list_y, items, ih):
        rel = my - list_y + self._scroll
        idx = int(rel / ih + 0.5)
        return max(0, min(len(items) - 1, idx))

    def _do_reorder(self, from_idx, to_idx):
        if self._mode == "parts":
            self._state.reorder_parts(from_idx, to_idx)
        else:
            self._state.reorder_chapters(self._part_id, from_idx, to_idx)

    def _do_add(self):
        if self._mode == "parts":
            self._state.add_part()
        else:
            self._state.add_chapter(self._part_id)
        self._sel = len(self._items()) - 1

    def _do_copy(self):
        items = self._items()
        if not items or self._sel < 0 or self._sel >= len(items):
            return
        item = items[self._sel]
        if self._mode == "parts":
            self._state.copy_part(item["id"])
        else:
            self._state.copy_chapter(self._part_id, item["id"])
        self._sel = len(self._items()) - 1

    def _request_delete(self):
        items = self._items()
        if not items or self._sel < 0 or self._sel >= len(items):
            return
        if len(items) <= 1:
            return  # 最後の1つは削除不可
        self._pending_delete_item = copy.deepcopy(items[self._sel])

    def _delete_scene_count(self, item):
        if self._mode == "parts":
            prefix = f"{item['id']:04d}_"
        else:
            prefix = f"{self._part_id:04d}_{item['id']:04d}_"
        return sum(1 for s in self._state.scenes
                   if s.get("name", "").startswith(prefix))

    def _update_delete_confirm(self):
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self._pending_delete_item = None
            return
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        dx, dy, dw, dh = self._delete_dialog_rect()
        ok_x, ok_y, bw, bh = self._delete_dialog_ok_rect(dx, dy, dw, dh)
        cancel_x = ok_x + bw + 8
        if is_clicked(mx, my, ok_x, ok_y, bw, bh):
            item = self._pending_delete_item
            if self._mode == "parts":
                self._state.delete_part(item["id"])
            else:
                self._state.delete_chapter(self._part_id, item["id"])
            self._sel = min(self._sel, len(self._items()) - 1)
            self._pending_delete_item = None
        elif is_clicked(mx, my, cancel_x, ok_y, bw, bh):
            self._pending_delete_item = None

    # ── draw ──────────────────────────────────────────────────

    def draw(self):
        if not self.active:
            return
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        pyxel.cls(EDIT_BG)

        title = "PARTS" if self._mode == "parts" else "CHAPTERS"
        items = self._items()
        ih = item_h()

        # 左パネル: リスト
        draw_panel(0, 0, _LIST_W, _PANEL_H)
        draw_titlebar(0, 0, _LIST_W, title)

        list_x, list_y = 4, title_bar_h() + 4
        list_w, list_h = _LIST_W - 8, _PANEL_H - title_bar_h() - 8

        pyxel.clip(list_x, list_y, list_w, list_h)
        for i, item in enumerate(items):
            iy = list_y + i * ih - self._scroll
            if iy + ih < list_y or iy > list_y + list_h:
                continue
            if self._drag_active and i == self._drag_src:
                pyxel.rect(list_x, iy, list_w, ih, EDIT_PANEL)
                continue
            sel = (i == self._sel)
            hov = is_hover(mx, my, list_x, iy, list_w, ih) and not self._drag_active
            label = self._item_label(item)
            draw_list_item(list_x, iy, list_w, label, h=ih, selected=sel, hover=hov)

        # ドラッグ中のゴースト + 挿入マーカー
        if self._drag_active and 0 <= self._drag_src < len(items):
            drop = self._drop_index(my, list_y, items, ih)
            if drop is not None:
                marker_y = list_y + drop * ih - self._scroll
                pyxel.rect(list_x, marker_y - 1, list_w, 2, EDIT_ACCENT)
            ghost_label = self._item_label(items[self._drag_src])
            gy = my - ih // 2
            pyxel.rect(list_x + 2, gy, list_w - 4, ih, EDIT_ACCENT)
            draw_unicode(list_x + 6, gy + 2, ghost_label, EDIT_BG, size=_w._ui_font_size)

        if not items:
            pyxel.text(list_x + 4, list_y + 4, "Empty", EDIT_TEXT_DIM)
        pyxel.clip()

        # スクロールバー
        total = len(items) * ih
        if total > list_h:
            bar_area = list_h - 4
            bar_h = max(12, bar_area * list_h // total)
            bar_y = list_y + 2 + (bar_area - bar_h) * self._scroll // max(1, total - list_h)
            sx = _LIST_W - 7
            pyxel.rect(sx, list_y + 2, 3, bar_area, EDIT_BORDER)
            pyxel.rect(sx, bar_y, 3, bar_h, EDIT_ACCENT)

        # 右パネル: 詳細
        draw_panel(_LIST_W, 0, _DETAIL_W, _PANEL_H)
        draw_titlebar(_LIST_W, 0, _DETAIL_W, "DETAIL")

        if items and 0 <= self._sel < len(items):
            item = items[self._sel]
            dy = title_bar_h() + 8
            pyxel.text(_LIST_W + 8, dy, "ID:", EDIT_TEXT_DIM)
            pyxel.text(_LIST_W + 30, dy, f"{item['id']:04d}", EDIT_ACCENT)
            dy += 16
            pyxel.text(_LIST_W + 8, dy, "NAME:", EDIT_TEXT_DIM)
            dy += 12
            # 名前表示 + 編集ボタン
            name_w = _DETAIL_W - 16
            pyxel.rect(_LIST_W + 8, dy, name_w, 24, EDIT_HIGHLIGHT)
            pyxel.rectb(_LIST_W + 8, dy, name_w, 24, EDIT_ACCENT)
            draw_unicode(_LIST_W + 12, dy + 4, item["name"], EDIT_TEXT, size=_w._ui_font_size)
            pyxel.text(_LIST_W + name_w - 30, dy + 8, "[EDIT]", EDIT_ACCENT)

            # 所属情報
            if self._mode == "parts":
                chs = self._state.chapters_for_part(item["id"])
                scenes = [s for s in self._state.scenes
                          if s["name"].startswith(f"{item['id']:04d}_")]
                dy += 36
                pyxel.text(_LIST_W + 8, dy, f"Chapters: {len(chs)}", EDIT_TEXT_DIM)
                dy += 12
                pyxel.text(_LIST_W + 8, dy, f"Scenes: {len(scenes)}", EDIT_TEXT_DIM)
            else:
                prefix = f"{self._part_id:04d}_{item['id']:04d}_"
                scenes = [s for s in self._state.scenes
                          if s["name"].startswith(prefix)]
                dy += 36
                pyxel.text(_LIST_W + 8, dy, f"Scenes: {len(scenes)}", EDIT_TEXT_DIM)
        else:
            pyxel.text(_LIST_W + 8, title_bar_h() + 8, "Select an item", EDIT_TEXT_DIM)

        # ボタンバー
        pyxel.rect(0, _PANEL_H, 720, _BTN_BAR_H, EDIT_TITLE_BG)
        pyxel.line(0, _PANEL_H, 720, _PANEL_H, EDIT_BORDER)

        bar_y = _PANEL_H + (_BTN_BAR_H - 20) // 2
        bw = 80
        gap = 6
        bx = 4

        buttons = ["+ADD", "COPY", "DELETE", "OK", "CANCEL"]
        for i, label in enumerate(buttons):
            if i == 3:
                bx += 20  # OK の前に余白
            draw_button(bx, bar_y, bw, label, h=20,
                        hover=is_hover(mx, my, bx, bar_y, bw, 20))
            bx += bw + gap

        # ESC ヒント
        pyxel.text(500, _PANEL_H + (_BTN_BAR_H - 8) // 2,
                   "ESC = CANCEL", EDIT_TEXT_DIM)

        if self._pending_delete_item is not None:
            self._draw_delete_confirm()

        # カーソル
        pyxel.line(mx - 4, my, mx + 4, my, 7)
        pyxel.line(mx, my - 4, mx, my + 4, 7)
        self._discard_confirm.draw()

    def _delete_dialog_rect(self):
        return 130, 150, 460, 160

    def _delete_dialog_ok_rect(self, dx, dy, dw, dh):
        bw = 120
        bh = max(24, _w._ui_render_h() + 4)
        total = bw * 2 + 8
        return dx + (dw - total) // 2, dy + dh - bh - 12, bw, bh

    def _draw_delete_confirm(self):
        item = self._pending_delete_item or {}
        scene_count = self._delete_scene_count(item)
        dx, dy, dw, dh = self._delete_dialog_rect()
        for y in range(0, 480, 2):
            pyxel.line(0, y, 719, y, EDIT_BG)
        pyxel.rect(dx - 3, dy - 3, dw + 6, dh + 6, EDIT_BORDER)
        draw_panel(dx, dy, dw, dh)
        title = "DELETE PART" if self._mode == "parts" else "DELETE CHAPTER"
        draw_titlebar(dx, dy, dw, title)
        y = dy + title_bar_h() + 10
        name = item.get("name", "")
        target = "Part" if self._mode == "parts" else "Chapter"
        lines = [
            f"{target}: {name}",
            f"This will delete {scene_count} scene(s).",
            "Images, BGM, SE, text, choices, and goto settings",
            "inside those scenes will be removed from this project.",
        ]
        for line in lines:
            draw_unicode(dx + 10, y, line, EDIT_TEXT_DIM,
                         size=_w._ui_font_size)
            y += _w._ui_render_h() + 4
        ok_x, ok_y, bw, bh = self._delete_dialog_ok_rect(dx, dy, dw, dh)
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        draw_button(ok_x, ok_y, bw, "DELETE", h=bh,
                    hover=is_hover(mx, my, ok_x, ok_y, bw, bh))
        draw_button(ok_x + bw + 8, ok_y, bw, "CANCEL", h=bh,
                    hover=is_hover(mx, my, ok_x + bw + 8, ok_y, bw, bh))
