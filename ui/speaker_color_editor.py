"""SPEAKER COLORS Config (720×480 フルスクリーン)

スピーカーごとに「名前バッジの文字色」「名前バッジの背景色」「セリフ本文色」を、
さらに地の文 (スピーカー名空) のセリフ色を、256 色マスターパレットから
割り当てる。プレビューはプレイ画面のダイアログボックスを縮尺なしで再現し、
選択したスピーカーで「吾輩は猫である。」サンプルを描画する。

レイアウト:
  [LEFT  SPEAKERS]  x=0,   w=200, h=324  (Narration + Speaker list + ADD/DEL)
  [MID   SLOTS]     x=200, w=180, h=324  (現在選択中エントリの色スロット)
  [RIGHT GRID]      x=380, w=340, h=324  (256色グリッド)
  [PREVIEW]         x=0,   w=720, h=140  (ダイアログボックスのライブプレビュー)
  [TOOLBAR]         x=0,   w=720, h=16   (SAVE / CANCEL)

保存先: settings.json["speaker_colors"]
"""
import copy
import pyxel
from ui.colors import (
    EDIT_BG, EDIT_PANEL, EDIT_BORDER, EDIT_TEXT, EDIT_TEXT_DIM, EDIT_ACCENT,
    EDIT_BTN_HOVER, EDIT_TITLE_BG,
    PLAY_BG, PLAY_BORDER, PLAY_TEXT, PLAY_DIALOG_BG, PLAY_ACCENT,
    PLAY_SPEAKER_BG, PLAY_SPEAKER_FG,
)
from ui.widgets import (
    draw_button, draw_unicode, draw_ui_text,
    ui_text_h, is_hover, is_clicked, title_bar_h,
    text_px_w, _editor_render_h,
)
from ui.color_editor import _compute_display_order, _hex_for_idx
from ui.confirm_dialog import ConfirmDialog

_SCREEN_W = 720
_SCREEN_H = 480

_TOP_H    = 324           # 上段 (3ペイン) の高さ
_PREVIEW_H = 140          # ダイアログプレビューの高さ
_TOOL_H   = _SCREEN_H - _TOP_H - _PREVIEW_H  # 残り 16px

_LEFT_W   = 200
_MID_W    = 180
_RIGHT_X  = _LEFT_W + _MID_W
_RIGHT_W  = _SCREEN_W - _RIGHT_X

_LIST_ITEM_H = 20

_GRID_COLS = 16
_GRID_ROWS = 16

# スロット種別
_SLOT_NARR_TEXT = "narration_text_color"
_SLOT_NAME_FG   = "name_color"
_SLOT_NAME_BG   = "name_bg_color"
_SLOT_TEXT      = "text_color"

# 地の文サンプル
_SAMPLE_TEXT = "吾輩は猫である。名前はまだ無い。"


class SpeakerColorEditor:
    """SPEAKER COLORS — スピーカーごとのテキスト/バッジ色を編集する。

    result:
        None        — まだ操作中
        "saved"     — SAVE & CLOSE
        "cancelled" — ESC / CANCEL
    """

    TITLE = "SPEAKER COLORS"

    def __init__(self):
        self.active = False
        self.result = None
        self._cfg = {"narration_text_color": None, "speakers": {}}
        self._saved = copy.deepcopy(self._cfg)
        # 現在選択中: ("narration", None) か ("speaker", name)
        self._sel_kind = "narration"
        self._sel_name: str | None = None
        # 編集中スロット (palette クリック → このスロットへ反映)
        self._sel_slot: str | None = _SLOT_NARR_TEXT
        self._list_scroll = 0
        self._display_order: list = []
        self._discard_confirm = ConfirmDialog()

    # ── lifecycle ─────────────────────────────────────────
    def open(self, cfg: dict | None = None):
        self.active = True
        self.result = None
        if isinstance(cfg, dict):
            self._cfg = copy.deepcopy(cfg)
        else:
            self._cfg = {"narration_text_color": None, "speakers": {}}
        self._cfg.setdefault("narration_text_color", None)
        self._cfg.setdefault("speakers", {})
        self._saved = copy.deepcopy(self._cfg)
        self._sel_kind = "narration"
        self._sel_name = None
        self._sel_slot = _SLOT_NARR_TEXT
        self._list_scroll = 0
        self._display_order = _compute_display_order()

    def get_config(self) -> dict:
        return copy.deepcopy(self._cfg)

    def _dirty(self) -> bool:
        return self._cfg != self._saved

    def _finish_cancelled(self):
        self._cfg = copy.deepcopy(self._saved)
        self.result = "cancelled"
        self.active = False

    def _request_cancel(self):
        if self._dirty():
            self._discard_confirm.open(
                "UNSAVED CHANGES",
                "Speaker color config has unsaved edits.\n"
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

    # ── helpers ───────────────────────────────────────────
    def _speaker_names(self) -> list:
        return list(self._cfg.get("speakers", {}).keys())

    def _entries(self) -> list:
        """リスト表示順: Narration が先頭、続いてスピーカー (登録順)。"""
        out = [("narration", None)]
        for name in self._speaker_names():
            out.append(("speaker", name))
        return out

    def _current_entry(self) -> dict:
        if self._sel_kind == "narration":
            return self._cfg
        speakers = self._cfg.get("speakers", {})
        return speakers.get(self._sel_name, {}) if self._sel_name else {}

    def _slot_value(self, slot: str) -> int | None:
        v = self._current_entry().get(slot)
        return v if (isinstance(v, int) and 0 <= v <= 255) else None

    def _slot_default(self, slot: str) -> int:
        if slot == _SLOT_NARR_TEXT:  return PLAY_TEXT
        if slot == _SLOT_NAME_FG:    return PLAY_SPEAKER_FG
        if slot == _SLOT_NAME_BG:    return PLAY_SPEAKER_BG
        if slot == _SLOT_TEXT:       return PLAY_TEXT
        return PLAY_TEXT

    def _slot_color(self, slot: str) -> int:
        """スロットの効果色 (None ならデフォルト)。"""
        v = self._slot_value(slot)
        return v if v is not None else self._slot_default(slot)

    def _set_slot(self, slot: str, idx: int) -> None:
        if self._sel_kind == "narration":
            if slot == _SLOT_NARR_TEXT:
                self._cfg["narration_text_color"] = int(idx)
        elif self._sel_kind == "speaker" and self._sel_name:
            speakers = self._cfg.setdefault("speakers", {})
            entry = speakers.setdefault(self._sel_name, {})
            entry[slot] = int(idx)

    def _slots_for_selection(self) -> list:
        """選択中エントリで操作可能なスロット一覧 (描画/操作両方で使う)。"""
        if self._sel_kind == "narration":
            return [(_SLOT_NARR_TEXT, "TEXT (地の文)")]
        return [
            (_SLOT_NAME_FG, "NAME COLOR"),
            (_SLOT_NAME_BG, "NAME BG COLOR"),
            (_SLOT_TEXT,    "TEXT COLOR"),
        ]

    # ── update ────────────────────────────────────────────
    def update(self):
        if not self.active:
            return
        if self._update_discard_confirm():
            return
        mx, my = pyxel.mouse_x, pyxel.mouse_y

        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self._request_cancel()
            return

        self._update_left(mx, my)
        self._update_mid(mx, my)
        self._update_grid(mx, my)
        self._update_toolbar(mx, my)

    def _update_left(self, mx, my):
        # エントリ行クリック
        list_y = title_bar_h() + 4
        for i, (kind, name) in enumerate(self._entries()):
            iy = list_y + i * _LIST_ITEM_H - self._list_scroll
            if iy < title_bar_h() or iy + _LIST_ITEM_H > _TOP_H - 24:
                continue
            if is_clicked(mx, my, 4, iy, _LEFT_W - 8, _LIST_ITEM_H):
                self._sel_kind = kind
                self._sel_name = name
                # 選択時のデフォルトスロット
                if kind == "narration":
                    self._sel_slot = _SLOT_NARR_TEXT
                else:
                    self._sel_slot = _SLOT_NAME_FG

        # ホイールスクロール
        if is_hover(mx, my, 0, title_bar_h(), _LEFT_W,
                    _TOP_H - title_bar_h() - 24):
            wheel = pyxel.mouse_wheel
            if wheel:
                content_h = len(self._entries()) * _LIST_ITEM_H
                view_h = _TOP_H - title_bar_h() - 24
                max_scroll = max(0, content_h - view_h)
                self._list_scroll = max(
                    0, min(max_scroll, self._list_scroll - wheel * _LIST_ITEM_H))

        # ADD / DEL ボタン
        bw = (_LEFT_W - 12) // 2
        by = _TOP_H - 22
        if is_clicked(mx, my, 4, by, bw, 18):
            self._add_speaker()
        if is_clicked(mx, my, 8 + bw, by, bw, 18):
            self._del_speaker()

    def _update_mid(self, mx, my):
        # スロット行のクリック (パレット選択先を切替)
        sy = title_bar_h() + 8
        slots = self._slots_for_selection()
        row_h = 32
        for slot, _label in slots:
            if is_clicked(mx, my, _LEFT_W + 4, sy, _MID_W - 8, row_h):
                self._sel_slot = slot
            sy += row_h + 4

        # 「Reset」ボタン (現在のスロットを未指定に戻す)
        if self._sel_slot is not None:
            ry = _TOP_H - 22
            if is_clicked(mx, my, _LEFT_W + 4, ry, _MID_W - 8, 18):
                self._reset_current_slot()

    def _update_grid(self, mx, my):
        if self._sel_slot is None:
            return
        gx, gy, cw, chh = self._grid_geom()
        for pos in range(256):
            col = pos % _GRID_COLS
            row = pos // _GRID_COLS
            cx = gx + col * cw
            cy = gy + row * chh
            if is_clicked(mx, my, cx, cy, cw, chh):
                self._set_slot(self._sel_slot, self._display_order[pos])
                return

    def _update_toolbar(self, mx, my):
        ty = _TOP_H + _PREVIEW_H
        if is_clicked(mx, my, 4, ty, 90, _TOOL_H):
            self.result = "saved"
            self.active = False
        if is_clicked(mx, my, 100, ty, 60, _TOOL_H):
            self._cfg = copy.deepcopy(self._saved)
        if is_clicked(mx, my, 166, ty, 70, _TOOL_H):
            self._request_cancel()

    # ── data ops ──────────────────────────────────────────
    def _add_speaker(self):
        from ui.native_dialogs import ask_text
        name = ask_text("SPEAKER NAME", "")
        if not name:
            return
        speakers = self._cfg.setdefault("speakers", {})
        if name in speakers:
            return
        speakers[name] = {
            "name_color": None,
            "name_bg_color": None,
            "text_color": None,
        }
        self._sel_kind = "speaker"
        self._sel_name = name
        self._sel_slot = _SLOT_NAME_FG

    def _del_speaker(self):
        if self._sel_kind != "speaker" or not self._sel_name:
            return
        speakers = self._cfg.get("speakers", {})
        speakers.pop(self._sel_name, None)
        self._sel_kind = "narration"
        self._sel_name = None
        self._sel_slot = _SLOT_NARR_TEXT

    def _reset_current_slot(self):
        if not self._sel_slot:
            return
        if self._sel_kind == "narration":
            self._cfg["narration_text_color"] = None
        elif self._sel_kind == "speaker" and self._sel_name:
            speakers = self._cfg.get("speakers", {})
            entry = speakers.get(self._sel_name)
            if entry is not None and self._sel_slot in entry:
                entry[self._sel_slot] = None

    # ── draw ──────────────────────────────────────────────
    def draw(self):
        if not self.active:
            return
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        pyxel.cls(EDIT_BG)
        self._draw_left(mx, my)
        self._draw_mid(mx, my)
        self._draw_grid(mx, my)
        self._draw_preview()
        self._draw_toolbar(mx, my)
        self._discard_confirm.draw()

    def _draw_left(self, mx, my):
        # 枠 + タイトル
        pyxel.rect(0, 0, _LEFT_W, _TOP_H, EDIT_PANEL)
        pyxel.rectb(0, 0, _LEFT_W, _TOP_H, EDIT_BORDER)
        pyxel.rect(0, 0, _LEFT_W, title_bar_h(), EDIT_TITLE_BG)
        draw_unicode(8, (title_bar_h() - 12) // 2 + 1,
                     "SPEAKERS", EDIT_TEXT, size=12)

        # リスト本体 (clip)
        list_top = title_bar_h()
        list_bot = _TOP_H - 24
        pyxel.clip(0, list_top, _LEFT_W, list_bot - list_top)
        list_y = list_top + 4
        for i, (kind, name) in enumerate(self._entries()):
            iy = list_y + i * _LIST_ITEM_H - self._list_scroll
            sel = (self._sel_kind == kind and
                   (kind == "narration" or self._sel_name == name))
            hov = is_hover(mx, my, 4, iy, _LEFT_W - 8, _LIST_ITEM_H) and not sel
            if sel:
                pyxel.rect(4, iy, _LEFT_W - 8, _LIST_ITEM_H, EDIT_ACCENT)
                fg = EDIT_BG
            elif hov:
                pyxel.rect(4, iy, _LEFT_W - 8, _LIST_ITEM_H, EDIT_BTN_HOVER)
                fg = EDIT_TEXT
            else:
                fg = EDIT_TEXT
            label = "[Narration]" if kind == "narration" else (name or "")
            draw_unicode(8, iy + 4, label, fg, size=12)
        pyxel.clip()

        # ADD / DEL
        bw = (_LEFT_W - 12) // 2
        by = _TOP_H - 22
        ah = is_hover(mx, my, 4, by, bw, 18)
        draw_button(4, by, bw, "ADD", h=18, hover=ah)
        dh = is_hover(mx, my, 8 + bw, by, bw, 18)
        # Narration を選択中は DEL 無効
        active_del = (self._sel_kind == "speaker" and self._sel_name is not None)
        draw_button(8 + bw, by, bw, "DEL", h=18, hover=(dh and active_del))

    def _draw_mid(self, mx, my):
        pyxel.rect(_LEFT_W, 0, _MID_W, _TOP_H, EDIT_PANEL)
        pyxel.rectb(_LEFT_W, 0, _MID_W, _TOP_H, EDIT_BORDER)
        pyxel.rect(_LEFT_W, 0, _MID_W, title_bar_h(), EDIT_TITLE_BG)
        title = ("[Narration]" if self._sel_kind == "narration"
                 else (self._sel_name or ""))
        draw_unicode(_LEFT_W + 8, (title_bar_h() - 12) // 2 + 1,
                     title, EDIT_TEXT, size=12)

        # スロット一覧
        sy = title_bar_h() + 8
        row_h = 32
        for slot, label in self._slots_for_selection():
            sel = (self._sel_slot == slot)
            hov = is_hover(mx, my, _LEFT_W + 4, sy, _MID_W - 8, row_h) and not sel
            box_bg = EDIT_ACCENT if sel else (EDIT_BTN_HOVER if hov else EDIT_BG)
            fg = EDIT_BG if sel else EDIT_TEXT
            pyxel.rect(_LEFT_W + 4, sy, _MID_W - 8, row_h, box_bg)
            pyxel.rectb(_LEFT_W + 4, sy, _MID_W - 8, row_h, EDIT_BORDER)
            # 色見本
            sw_w, sw_h = 28, 16
            sw_x = _LEFT_W + 8
            sw_y = sy + (row_h - sw_h) // 2
            pyxel.rect(sw_x, sw_y, sw_w, sw_h, self._slot_color(slot))
            pyxel.rectb(sw_x, sw_y, sw_w, sw_h, EDIT_BORDER)
            # ラベル + index + HEX 表示
            v = self._slot_value(slot)
            if v is not None:
                idx_str = f"#{v:03d} {_hex_for_idx(v)}"
            else:
                eff = self._slot_color(slot)
                idx_str = f"(default #{eff:03d} {_hex_for_idx(eff)})"
            draw_unicode(sw_x + sw_w + 6, sy + 4,
                         label, fg, size=12)
            draw_unicode(sw_x + sw_w + 6, sy + 18,
                         idx_str, fg, size=10)
            sy += row_h + 4

        # Reset ボタン
        if self._sel_slot is not None:
            ry = _TOP_H - 22
            rh = is_hover(mx, my, _LEFT_W + 4, ry, _MID_W - 8, 18)
            draw_button(_LEFT_W + 4, ry, _MID_W - 8,
                        "RESET SLOT (use default)", h=18, hover=rh)

    def _grid_geom(self):
        gx = _RIGHT_X + 8
        gy = title_bar_h() + 8
        area_w = _RIGHT_W - 16
        area_h = _TOP_H - title_bar_h() - 16
        cw = area_w // _GRID_COLS
        chh = area_h // _GRID_ROWS
        return gx, gy, cw, chh

    def _draw_grid(self, mx, my):
        pyxel.rect(_RIGHT_X, 0, _RIGHT_W, _TOP_H, EDIT_PANEL)
        pyxel.rectb(_RIGHT_X, 0, _RIGHT_W, _TOP_H, EDIT_BORDER)
        pyxel.rect(_RIGHT_X, 0, _RIGHT_W, title_bar_h(), EDIT_TITLE_BG)
        draw_unicode(_RIGHT_X + 8, (title_bar_h() - 12) // 2 + 1,
                     "MASTER PALETTE (click to assign)",
                     EDIT_TEXT, size=12)

        sel_idx = -1
        if self._sel_slot is not None:
            sel_idx = self._slot_value(self._sel_slot)
            if sel_idx is None:
                sel_idx = -1

        gx, gy, cw, chh = self._grid_geom()
        for pos in range(256):
            idx = self._display_order[pos]
            col = pos % _GRID_COLS
            row = pos // _GRID_COLS
            cx = gx + col * cw
            cy = gy + row * chh
            pyxel.rect(cx, cy, cw, chh, idx)
            if idx == sel_idx:
                pyxel.rectb(cx, cy, cw, chh, EDIT_ACCENT)
                pyxel.rectb(cx + 1, cy + 1, cw - 2, chh - 2, EDIT_ACCENT)
            elif is_hover(mx, my, cx, cy, cw, chh):
                pyxel.rectb(cx, cy, cw, chh, EDIT_TEXT)

    def _draw_preview(self):
        """プレイ画面ダイアログのライブプレビュー (吾輩は猫である)。"""
        py0 = _TOP_H
        # 背景塗り (PLAY_BG)
        pyxel.rect(0, py0, _SCREEN_W, _PREVIEW_H, PLAY_BG)
        pyxel.line(0, py0, _SCREEN_W, py0, EDIT_BORDER)

        # ダイアログボックス本体
        dlg_x = 16
        dlg_w = _SCREEN_W - 32
        dlg_y = py0 + 24
        dlg_h = _PREVIEW_H - 32

        # 話者バッジ (Narration の場合は省略)
        speaker = "" if self._sel_kind == "narration" else (self._sel_name or "")
        fsz = _editor_render_h()
        if speaker:
            sp_h = max(20, fsz + 6)
            sp_text_w = text_px_w(speaker)
            sp_w = max(60, sp_text_w + 24)
            sp_x = dlg_x + 12
            sp_y = dlg_y - sp_h + 2
            spk_bg = self._slot_color(_SLOT_NAME_BG)
            spk_fg = self._slot_color(_SLOT_NAME_FG)
            pyxel.rect(sp_x, sp_y, sp_w, sp_h, spk_bg)
            pyxel.rectb(sp_x, sp_y, sp_w, sp_h, PLAY_BORDER)
            text_x = sp_x + max(4, (sp_w - sp_text_w) // 2)
            text_y = sp_y + max(1, (sp_h - fsz) // 2)
            draw_unicode(text_x, text_y, speaker, spk_fg)

        pyxel.rect(dlg_x, dlg_y, dlg_w, dlg_h, PLAY_DIALOG_BG)
        pyxel.rectb(dlg_x, dlg_y, dlg_w, dlg_h, PLAY_ACCENT)
        pyxel.rectb(dlg_x + 2, dlg_y + 2, dlg_w - 4, dlg_h - 4, PLAY_BORDER)

        # 本文 (Narration なら narration_text_color、それ以外は speaker text_color)
        if self._sel_kind == "narration":
            text_col = self._slot_color(_SLOT_NARR_TEXT)
        else:
            text_col = self._slot_color(_SLOT_TEXT)
        draw_unicode(dlg_x + 14, dlg_y + 14, _SAMPLE_TEXT, text_col, size=12)
        draw_unicode(dlg_x + 14, dlg_y + 36,
                     "ABCDEFG abcdefg 0123456789",
                     text_col, size=12)

    def _draw_toolbar(self, mx, my):
        ty = _TOP_H + _PREVIEW_H
        pyxel.rect(0, ty, _SCREEN_W, _TOOL_H, EDIT_TITLE_BG)
        pyxel.line(0, ty, _SCREEN_W, ty, EDIT_BORDER)
        sh = is_hover(mx, my, 4, ty, 90, _TOOL_H)
        draw_button(4, ty, 90, "SAVE & CLOSE", h=_TOOL_H, hover=sh)
        rh = is_hover(mx, my, 100, ty, 60, _TOOL_H)
        draw_button(100, ty, 60, "REVERT", h=_TOOL_H, hover=rh)
        ch = is_hover(mx, my, 166, ty, 70, _TOOL_H)
        draw_button(166, ty, 70, "CANCEL", h=_TOOL_H, hover=ch)
        draw_unicode(244, ty + (_TOOL_H - 10) // 2,
                     "ESC = CANCEL", EDIT_TEXT_DIM, size=10)
