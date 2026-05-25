"""Color Config (720×480 フルスクリーン)

役割 (EDIT_*, PLAY_*) に対して 256色マスターパレットのインデックスを割り当てる
統合エディタ。エディタUI と プレイ画面UI の両方の即時プレビューを左側に表示する。

レイアウト:
  [LEFT  PREVIEW]  x=0,   w=380, h=448  (エディタ + プレイ画面の即時プレビュー)
  [RIGHT ROLES]    x=380, w=340, h=190  (役割一覧)
  [RIGHT DETAIL]   x=380, w=340, h=82   (現在選択中の色見本 + 説明)
  [RIGHT GRID]     x=380, w=340, h=176  (256色グリッドから index を選択)
  [BOTTOM BAR]     x=0,   w=720, h=32

保存先: settings.json["dialog_role_indices"] (role名 → 0-255 の int)
"""
import pyxel
from ui.colors import (
    EDIT_BG, EDIT_PANEL, EDIT_BORDER, EDIT_TEXT, EDIT_TEXT_DIM, EDIT_ACCENT,
    EDIT_BTN_HOVER, EDIT_HIGHLIGHT, EDIT_TITLE_BG,
)
from ui.colors import role_names, default_index
from ui.widgets import (
    draw_panel, draw_titlebar, draw_button, draw_unicode, draw_ui_text,
    ui_text_h, is_hover, is_clicked, title_bar_h, tab_h,
    text_px_w, _editor_render_h,
)
from ui.confirm_dialog import ConfirmDialog

_ROLE_DESC = {
    # ── EDIT (エディタ画面) ─────────────────────────────────
    "EDIT_BG":          "エディタ: 画面の背景",
    "EDIT_PANEL":       "エディタ: パネル背景",
    "EDIT_BTN_BG":      "エディタ: ボタン背景",
    "EDIT_PREVIEW_BG":  "エディタ: メインビュー / フローチャート背景",
    "EDIT_BORDER":      "エディタ: 枠線",
    "EDIT_TEXT_DIM":    "エディタ: 薄字",
    "EDIT_TEXT":        "エディタ: 通常字",
    "EDIT_BTN_HOVER":   "エディタ: ボタン ホバー色",
    "EDIT_ACCENT":      "エディタ: 強調 / アクティブ",
    "EDIT_HIGHLIGHT":   "エディタ: 選択行ハイライト",
    "EDIT_TITLE_BG":    "エディタ: タイトルバー背景",
    # ── PLAY (プレイ画面) ───────────────────────────────────
    "PLAY_BG":           "プレイ: 画面の背景",
    "PLAY_DIALOG_BG":    "プレイ: ダイアログボックス背景",
    "PLAY_BORDER":       "プレイ: 枠線",
    "PLAY_TEXT_DIM":     "プレイ: 薄字",
    "PLAY_TEXT":         "プレイ: 通常字 (デフォルトのセリフ色)",
    "PLAY_ACCENT":       "プレイ: 強調 / アクティブ",
    "PLAY_HIGHLIGHT":    "プレイ: ハイライト帯",
    "PLAY_SPEAKER_FG":   "プレイ: 話者バッジ文字色 (デフォルト)",
    "PLAY_SPEAKER_BG":   "プレイ: 話者バッジ背景 (デフォルト)",
    "PLAY_CHOICE_BG":    "プレイ: 選択肢ボタン背景",
    "PLAY_CHOICE_HOVER": "プレイ: 選択肢ホバー色",
}

_EDITOR_PRESETS = [
    ("DARK", {
        "EDIT_BG": 0, "EDIT_PANEL": 1, "EDIT_BTN_BG": 2,
        "EDIT_PREVIEW_BG": 0, "EDIT_BORDER": 5,
        "EDIT_TEXT_DIM": 8, "EDIT_TEXT": 119,
        "EDIT_BTN_HOVER": 115, "EDIT_ACCENT": 126,
        "EDIT_HIGHLIGHT": 36, "EDIT_TITLE_BG": 1,
    }),
    ("LIGHT", {
        "EDIT_BG": 119, "EDIT_PANEL": 71, "EDIT_BTN_BG": 52,
        "EDIT_PREVIEW_BG": 119, "EDIT_BORDER": 53,
        "EDIT_TEXT_DIM": 69, "EDIT_TEXT": 112,
        "EDIT_BTN_HOVER": 18, "EDIT_ACCENT": 126,
        "EDIT_HIGHLIGHT": 131, "EDIT_TITLE_BG": 71,
    }),
    ("SOFT", {
        "EDIT_BG": 22, "EDIT_PANEL": 23, "EDIT_BTN_BG": 54,
        "EDIT_PREVIEW_BG": 22, "EDIT_BORDER": 56,
        "EDIT_TEXT_DIM": 83, "EDIT_TEXT": 84,
        "EDIT_BTN_HOVER": 79, "EDIT_ACCENT": 40,
        "EDIT_HIGHLIGHT": 36, "EDIT_TITLE_BG": 55,
    }),
    ("NOIR", {
        "EDIT_BG": 112, "EDIT_PANEL": 147, "EDIT_BTN_BG": 111,
        "EDIT_PREVIEW_BG": 112, "EDIT_BORDER": 115,
        "EDIT_TEXT_DIM": 114, "EDIT_TEXT": 119,
        "EDIT_BTN_HOVER": 117, "EDIT_ACCENT": 113,
        "EDIT_HIGHLIGHT": 144, "EDIT_TITLE_BG": 123,
    }),
]

_PLAY_PRESETS = [
    ("DARK", {
        "PLAY_BG": 0, "PLAY_DIALOG_BG": 1, "PLAY_BORDER": 5,
        "PLAY_TEXT_DIM": 8, "PLAY_TEXT": 119,
        "PLAY_ACCENT": 126, "PLAY_HIGHLIGHT": 36,
        "PLAY_SPEAKER_FG": 119, "PLAY_SPEAKER_BG": 111,
        "PLAY_CHOICE_BG": 2, "PLAY_CHOICE_HOVER": 115,
    }),
    ("LIGHT", {
        "PLAY_BG": 119, "PLAY_DIALOG_BG": 71, "PLAY_BORDER": 53,
        "PLAY_TEXT_DIM": 69, "PLAY_TEXT": 112,
        "PLAY_ACCENT": 126, "PLAY_HIGHLIGHT": 131,
        "PLAY_SPEAKER_FG": 119, "PLAY_SPEAKER_BG": 111,
        "PLAY_CHOICE_BG": 52, "PLAY_CHOICE_HOVER": 18,
    }),
    ("CINEMA", {
        "PLAY_BG": 112, "PLAY_DIALOG_BG": 147, "PLAY_BORDER": 115,
        "PLAY_TEXT_DIM": 114, "PLAY_TEXT": 119,
        "PLAY_ACCENT": 113, "PLAY_HIGHLIGHT": 144,
        "PLAY_SPEAKER_FG": 119, "PLAY_SPEAKER_BG": 123,
        "PLAY_CHOICE_BG": 111, "PLAY_CHOICE_HOVER": 117,
    }),
    ("WARM", {
        "PLAY_BG": 22, "PLAY_DIALOG_BG": 23, "PLAY_BORDER": 56,
        "PLAY_TEXT_DIM": 83, "PLAY_TEXT": 84,
        "PLAY_ACCENT": 40, "PLAY_HIGHLIGHT": 36,
        "PLAY_SPEAKER_FG": 22, "PLAY_SPEAKER_BG": 77,
        "PLAY_CHOICE_BG": 54, "PLAY_CHOICE_HOVER": 79,
    }),
]

_SCREEN_W = 720
_SCREEN_H = 480
_BTN_H    = 32
_PANEL_H  = _SCREEN_H - _BTN_H

_LEFT_W  = 380
_RIGHT_X = _LEFT_W
_RIGHT_W = _SCREEN_W - _LEFT_W

_ROLES_H  = 190
_DETAIL_Y = _ROLES_H
_DETAIL_H = 82
_GRID_Y   = _DETAIL_Y + _DETAIL_H
_GRID_H   = _PANEL_H - _GRID_Y

_ROLE_PAD = 6
_ROLE_ROW_H = 28

_GRID_COLS = 16
_GRID_ROWS = 16


def _hex_for_idx(idx: int) -> str:
    """pyxel.colors[idx] の RGB を 6桁HEX で返す。範囲外は '------'。"""
    if not isinstance(idx, int) or idx < 0 or idx >= len(pyxel.colors):
        return "------"
    return f"{pyxel.colors[idx]:06X}"


def _compute_display_order() -> list:
    """マスターパレット 256 色を hex 値の昇順で並べ替えた
    「表示位置 → 実 index」のマッピングを返す。

    例: 0f4c5c → 1b4332 → 1e1e1e → … → ffffff
    6桁ゼロ埋め hex 文字列の辞書順と pyxel.colors[i] (0xRRGGBB の int) の
    数値順は等価なので、int の昇順でソートする。同色の場合は元 index 順。

    表示位置と実 index の対応は `_display_order[pos]` で引け、
    保存値 (settings.json) は実 index のままなので既存設定との互換性は壊れない。
    """
    items = [(i, pyxel.colors[i]) for i in range(256)]
    items.sort(key=lambda it: (it[1], it[0]))
    return [it[0] for it in items]


class ColorEditor:
    """Editor Color Config — 役割→マスターパレットIndex の編集。"""

    TITLE = "COLOR CONFIG"

    def __init__(self):
        self.active = False
        self.result = None
        self._roles = role_names()
        self._indices: dict = {}
        self._saved: dict = {}
        self._sel_role = self._roles[0] if self._roles else None
        self._role_scroll = 0
        self._scroll_y = 0
        self._content_h = 0
        self._preview_tab = "editor"  # "editor" | "play"
        self._display_order: list = list(range(256))
        self._right_view = "roles"  # "roles" | "presets"
        self._discard_confirm = ConfirmDialog()

    def open(self, role_indices: dict | None = None):
        """role_indices を読み込んで編集開始する。"""
        self.active = True
        self.result = None
        self._roles = role_names()
        self._indices = {r: default_index(r) for r in self._roles}
        if isinstance(role_indices, dict):
            for r in self._roles:
                v = role_indices.get(r)
                if isinstance(v, int) and 0 <= v <= 255:
                    self._indices[r] = v
        self._saved = dict(self._indices)
        self._sel_role = self._roles[0] if self._roles else None
        self._role_scroll = 0
        self._scroll_y = 0
        self._preview_tab = "editor"
        # マスターパレットは pyxel.init/load_pal 後に確定するので open() で計算
        self._display_order = _compute_display_order()

    def get_role_indices(self) -> dict:
        """SAVE 時に呼ばれる: 編集後の role → index dict を返す。"""
        return dict(self._indices)

    def _dirty(self) -> bool:
        return self._indices != self._saved

    def _finish_cancelled(self):
        self._indices = dict(self._saved)
        self.result = "cancelled"
        self.active = False

    def _request_cancel(self):
        if self._dirty():
            self._discard_confirm.open(
                "UNSAVED CHANGES",
                "Color config has unsaved edits.\n"
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

    def _idx(self, role: str) -> int:
        return self._indices.get(role, default_index(role))

    def _apply_preset(self, preset: dict):
        for role in self._roles:
            idx = preset.get(role)
            if isinstance(idx, int) and 0 <= idx <= 255:
                self._indices[role] = idx

    def _preset_active(self, preset: dict) -> bool:
        for role in self._roles:
            idx = preset.get(role)
            if isinstance(idx, int) and self._idx(role) != idx:
                return False
        return True

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

        # PREVIEW タブ切り替え
        tab_y = title_bar_h()
        tab_w = _LEFT_W // 2
        for i, name in enumerate(("editor", "play")):
            if is_clicked(mx, my, i * tab_w, tab_y, tab_w, tab_h()):
                if self._preview_tab != name:
                    self._preview_tab = name
                    self._scroll_y = 0

        # PREVIEW スクロール (タブ下のコンテンツ領域上のみ)
        content_top = title_bar_h() + tab_h()
        if is_hover(mx, my, 0, content_top, _LEFT_W, _PANEL_H - content_top):
            wheel = pyxel.mouse_wheel
            if wheel:
                visible_h = _PANEL_H - content_top - 8
                max_scroll = max(0, self._content_h - visible_h)
                self._scroll_y = max(0,
                                     min(max_scroll,
                                         self._scroll_y - wheel * 16))

        # 右上ペイン: ROLES / PRESET 切替
        tab_y = 0
        roles_w = 72
        preset_w = 82
        if is_clicked(mx, my, _RIGHT_X, tab_y, roles_w, title_bar_h()):
            self._right_view = "roles"
        if is_clicked(mx, my, _RIGHT_X + roles_w, tab_y,
                      preset_w, title_bar_h()):
            self._right_view = "presets"

        if self._right_view == "roles":
            # 役割リストのクリック
            for r, ry in self._visible_roles_with_y():
                if is_clicked(mx, my, _RIGHT_X + _ROLE_PAD, ry,
                              _RIGHT_W - _ROLE_PAD * 2, _ROLE_ROW_H):
                    self._sel_role = r

            # 役割リストのスクロール
            if is_hover(mx, my, _RIGHT_X, title_bar_h(),
                        _RIGHT_W, _ROLES_H - title_bar_h()):
                wheel = pyxel.mouse_wheel
                if wheel:
                    max_scroll = max(0, len(self._roles) * _ROLE_ROW_H
                                     - (_ROLES_H - title_bar_h()
                                        - _ROLE_PAD * 2))
                    self._role_scroll = max(
                        0, min(max_scroll,
                               self._role_scroll - wheel * _ROLE_ROW_H))
        else:
            self._handle_preset_clicks(mx, my)

        # 256色グリッドのクリック (display_order でセル位置→実indexを引く)
        gx0, gy0, cw, chh = self._grid_geom()
        if self._sel_role is not None:
            for pos in range(256):
                col = pos % _GRID_COLS
                row = pos // _GRID_COLS
                cx = gx0 + col * cw
                cy = gy0 + row * chh
                if is_clicked(mx, my, cx, cy, cw, chh):
                    self._indices[self._sel_role] = self._display_order[pos]

        # ツールバー
        bar_y = _PANEL_H + (_BTN_H - 20) // 2
        if is_clicked(mx, my, 4, bar_y, 82, 20):
            self.result = "saved"
            self.active = False
        if is_clicked(mx, my, 90, bar_y, 70, 20):
            self._indices = dict(self._saved)
        if is_clicked(mx, my, 164, bar_y, 88, 20):
            self._indices = {r: default_index(r) for r in self._roles}
        if is_clicked(mx, my, 256, bar_y, 60, 20):
            self._request_cancel()

    def _preset_button_geom(self, group: str, i: int) -> tuple:
        x = _RIGHT_X + _ROLE_PAD
        bw = (_RIGHT_W - _ROLE_PAD * 2 - 8) // 2
        bh = 22
        gap = 4

        edit_label_y = title_bar_h() + 8
        edit_y = edit_label_y + 16
        play_label_y = edit_y + 2 * (bh + gap) + 18
        play_y = play_label_y + 16
        base_y = play_y if group == "play" else edit_y
        bx = x + (i % 2) * (bw + 8)
        by = base_y + (i // 2) * (bh + gap)
        return bx, by, bw, bh

    def _handle_preset_clicks(self, mx, my):
        for i, (_name, preset) in enumerate(_EDITOR_PRESETS):
            bx, by, bw, bh = self._preset_button_geom("edit", i)
            if is_clicked(mx, my, bx, by, bw, bh):
                self._apply_preset(preset)

        for i, (_name, preset) in enumerate(_PLAY_PRESETS):
            bx, by, bw, bh = self._preset_button_geom("play", i)
            if is_clicked(mx, my, bx, by, bw, bh):
                self._apply_preset(preset)

    # ── draw ──────────────────────────────────────────────
    def draw(self):
        if not self.active:
            return
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        pyxel.cls(self._idx("EDIT_BG"))

        self._draw_preview_panel(mx, my)
        self._draw_roles_panel(mx, my)
        self._draw_role_detail_panel()
        self._draw_grid_panel(mx, my)
        self._draw_toolbar(mx, my)

        pyxel.line(mx - 4, my, mx + 4, my, 7)
        pyxel.line(mx, my - 4, mx, my + 4, 7)
        self._discard_confirm.draw()

    # ─── PREVIEW (LEFT, scrollable) ───────────────────────
    def _draw_preview_panel(self, mx, my):
        roles = {r: self._idx(r) for r in self._roles}

        pyxel.rect(0, 0, _LEFT_W, _PANEL_H, roles["EDIT_BG"])
        pyxel.rectb(0, 0, _LEFT_W, _PANEL_H, roles["EDIT_BORDER"])
        pyxel.rect(0, 0, _LEFT_W, title_bar_h(), roles["EDIT_TITLE_BG"])
        draw_unicode(8, (title_bar_h() - 12) // 2 + 1,
                     self.TITLE, roles["EDIT_TEXT"], size=12)
        pyxel.line(0, title_bar_h() - 1, _LEFT_W, title_bar_h() - 1,
                   roles["EDIT_BORDER"])

        # タブ行 (EDITOR UI / PLAY UI)
        tabs = [("EDITOR UI", "editor"), ("PLAY UI", "play")]
        tab_y = title_bar_h()
        tw = _LEFT_W // 2
        for i, (label, name) in enumerate(tabs):
            draw_button(i * tw, tab_y, tw, label,
                        h=tab_h(), active=(self._preview_tab == name),
                        hover=is_hover(mx, my, i * tw, tab_y, tw, tab_h()))

        view_x = 0
        view_y = tab_y + tab_h()
        view_w = _LEFT_W
        view_h = _PANEL_H - view_y

        pyxel.clip(view_x, view_y, view_w, view_h)
        cy = view_y + 8 - self._scroll_y
        if self._preview_tab == "editor":
            cy = self._draw_editor_preview(view_x + 8, cy, view_w - 16, roles)
        else:
            cy = self._draw_play_preview(view_x + 8, cy, view_w - 16, roles)
        pyxel.clip()

        self._content_h = cy - (view_y + 8 - self._scroll_y) + 8

        # スクロールバー (基本は不要だがフォントサイズ次第で出る)
        max_scroll = max(0, self._content_h - (view_h - 8))
        if max_scroll > 0:
            sb_x = _LEFT_W - 4
            sb_h = view_h
            ratio = (view_h - 8) / max(1, self._content_h)
            knob_h = max(20, int(sb_h * ratio))
            knob_y = view_y + int((sb_h - knob_h) * self._scroll_y / max_scroll)
            pyxel.rect(sb_x, view_y, 3, sb_h, roles["EDIT_PANEL"])
            pyxel.rect(sb_x, knob_y, 3, knob_h, roles["EDIT_ACCENT"])

    def _draw_editor_preview(self, px, py, pw, roles) -> int:
        """エディタUI のモックアップ。"""
        bg         = roles["EDIT_BG"]
        panel      = roles["EDIT_PANEL"]
        border     = roles["EDIT_BORDER"]
        text       = roles["EDIT_TEXT"]
        text_dim   = roles["EDIT_TEXT_DIM"]
        accent     = roles["EDIT_ACCENT"]
        btn_bg     = roles["EDIT_BTN_BG"]
        btn_hover  = roles["EDIT_BTN_HOVER"]
        title_bg   = roles["EDIT_TITLE_BG"]
        highlight  = roles["EDIT_HIGHLIGHT"]
        preview_bg = roles["EDIT_PREVIEW_BG"]

        # タイトルバー
        tb_h = 18
        pyxel.rect(px, py, pw, tb_h, title_bg)
        pyxel.rectb(px, py, pw, tb_h, border)
        draw_unicode(px + 6, py + (tb_h - 12) // 2 + 1,
                     "EDIT_TITLE_BG / タイトルバー", text, size=12)
        py += tb_h + 4

        # タブ
        ttab_h = 18
        for i, (lbl, fill, fg) in enumerate([
                ("[Active]", accent, bg),
                ("[Hover]",  btn_hover, text),
                ("[Normal]", btn_bg, text_dim),
        ]):
            tw = pw // 3 - 2
            tx = px + i * (tw + 2)
            pyxel.rect(tx, py, tw, ttab_h, fill)
            pyxel.rectb(tx, py, tw, ttab_h, border)
            draw_ui_text(tx + 4, py + (ttab_h - ui_text_h()) // 2, lbl, fg)
        py += ttab_h + 8

        # パネル + リスト
        pn_h = 96
        pyxel.rect(px, py, pw, pn_h, panel)
        pyxel.rectb(px, py, pw, pn_h, border)
        ly = py + 6
        rows = [
            ("Selected list row",  accent,    bg),
            ("Hover list row",     btn_hover, text),
            ("Highlight bar",      highlight, bg),
            ("Normal list row",    panel,     text),
            ("Dim row",            panel,     text_dim),
        ]
        for lbl, rbg, fg in rows:
            pyxel.rect(px + 4, ly, pw - 8, 16, rbg)
            draw_ui_text(px + 8, ly + (16 - ui_text_h()) // 2, lbl, fg)
            ly += 17
        py += pn_h + 8

        # ボタン
        bw = (pw - 8) // 3
        for i, (lbl, fill, fg) in enumerate([
                ("[NORMAL]", btn_bg,    text),
                ("[HOVER]",  btn_hover, text),
                ("[ACTIVE]", accent,    bg),
        ]):
            bx = px + i * (bw + 4)
            pyxel.rect(bx, py, bw, 22, fill)
            pyxel.rectb(bx, py, bw, 22, border)
            draw_ui_text(bx + 4, py + (22 - ui_text_h()) // 2, lbl, fg)
        py += 22 + 8

        # プレビュー領域
        prv_h = 56
        pyxel.rect(px, py, pw, prv_h, preview_bg)
        pyxel.rectb(px, py, pw, prv_h, border)
        draw_unicode(px + 6, py + 6, "EDIT_PREVIEW_BG", text_dim, size=12)
        draw_unicode(px + 6, py + prv_h - 20,
                     "（メインビュー / フローチャート背景）",
                     text_dim, size=12)
        py += prv_h + 8

        # テキストサンプル
        for lbl, fg in [
                ("EDIT_TEXT 通常字 ABC abc 0123", text),
                ("EDIT_TEXT_DIM 薄字 ABC abc",    text_dim),
                ("EDIT_ACCENT 強調 ABC abc",      accent),
        ]:
            draw_unicode(px + 4, py, lbl, fg, size=14)
            py += 22

        py = self._draw_editing_footer(px, py, roles)
        return py

    def _draw_play_preview(self, px, py, pw, roles) -> int:
        """プレイ画面UI のモックアップ。"""
        bg         = roles["PLAY_BG"]
        border     = roles["PLAY_BORDER"]
        text       = roles["PLAY_TEXT"]
        text_dim   = roles["PLAY_TEXT_DIM"]
        accent     = roles["PLAY_ACCENT"]
        highlight  = roles["PLAY_HIGHLIGHT"]
        dialog_bg  = roles["PLAY_DIALOG_BG"]
        speaker_fg = roles["PLAY_SPEAKER_FG"]
        speaker_bg = roles["PLAY_SPEAKER_BG"]
        choice_bg  = roles["PLAY_CHOICE_BG"]
        choice_hov = roles["PLAY_CHOICE_HOVER"]

        # 話者バッジ (枠と文字の間に余白を確保し中央配置)
        spk_label = "Alice"
        spk_h = max(22, _editor_render_h() + 6)
        spk_text_w = text_px_w(spk_label)
        spk_w = max(80, spk_text_w + 24)
        pyxel.rect(px, py, spk_w, spk_h, speaker_bg)
        pyxel.rectb(px, py, spk_w, spk_h, border)
        text_x = px + max(4, (spk_w - spk_text_w) // 2)
        text_y = py + max(1, (spk_h - _editor_render_h()) // 2)
        draw_unicode(text_x, text_y, spk_label, speaker_fg)
        py += spk_h - 1

        # ダイアログボックス
        dlg_h = 90
        pyxel.rect(px, py, pw, dlg_h, dialog_bg)
        pyxel.rectb(px, py, pw, dlg_h, border)
        draw_unicode(px + 8, py + 10,
                     "本文サンプル — PLAY_TEXT で表示",
                     text, size=12)
        draw_unicode(px + 8, py + 32,
                     "補足説明 — PLAY_TEXT_DIM の薄字",
                     text_dim, size=10)
        draw_unicode(px + 8, py + 54,
                     "強調語句 — PLAY_ACCENT カラー",
                     accent, size=12)
        py += dlg_h + 12

        # 選択肢ボタン
        ch_h = 24
        cbw = (pw - 8) // 3
        for i, (lbl, fill) in enumerate([
                ("[A] Normal", choice_bg),
                ("[B] Hover",  choice_hov),
                ("[C] Accent", accent),
        ]):
            bx = px + i * (cbw + 4)
            pyxel.rect(bx, py, cbw, ch_h, fill)
            pyxel.rectb(bx, py, cbw, ch_h, border)
            fg = bg if fill == accent else text
            draw_ui_text(bx + 4, py + (ch_h - ui_text_h()) // 2, lbl, fg)
        py += ch_h + 12

        # ハイライト帯
        hl_h = 16
        pyxel.rect(px, py, pw, hl_h, highlight)
        draw_ui_text(px + 6, py + (hl_h - ui_text_h()) // 2,
                     "HIGHLIGHT bar (selected log row 等)", bg)
        py += hl_h + 12

        py = self._draw_editing_footer(px, py, roles)
        return py

    def _draw_editing_footer(self, px, py, roles) -> int:
        """選択中の役割名と説明を表示。"""
        if not self._sel_role:
            return py
        # Editing フッタはエディタ chrome なので EDIT_* で固定
        accent   = roles["EDIT_ACCENT"]
        text_dim = roles["EDIT_TEXT_DIM"]
        sel_idx = self._idx(self._sel_role)
        py += 16  # 上のプレビュー要素との余白
        py = self._section_label(px, py, "Editing", accent)
        draw_unicode(px + 4, py,
                     f"{self._sel_role}  → #{sel_idx:03d}  {_hex_for_idx(sel_idx)}",
                     accent, size=14)
        py += 22
        draw_unicode(px + 4, py,
                     _ROLE_DESC.get(self._sel_role, ""),
                     text_dim, size=12)
        py += 20
        return py

    def _section_label(self, px, py, label, accent) -> int:
        draw_unicode(px, py, label, accent, size=14)
        py += 18
        return py

    # ─── ROLES (RIGHT-TOP) ────────────────────────────────
    def _visible_roles_with_y(self) -> list:
        out = []
        ry0 = title_bar_h() + _ROLE_PAD - self._role_scroll
        view_top = title_bar_h()
        view_bot = _ROLES_H
        for i, r in enumerate(self._roles):
            ry = ry0 + i * _ROLE_ROW_H
            if ry + _ROLE_ROW_H >= view_top and ry <= view_bot:
                out.append((r, ry))
        return out

    def _draw_roles_panel(self, mx, my):
        draw_panel(_RIGHT_X, 0, _RIGHT_W, _ROLES_H)
        self._draw_right_tabs(mx, my)
        if self._right_view == "presets":
            self._draw_presets_panel(mx, my)
            return

        sb_w = 5
        pyxel.clip(_RIGHT_X, title_bar_h(),
                   _RIGHT_W - sb_w, _ROLES_H - title_bar_h())
        for r, ry in self._visible_roles_with_y():
            sel = (r == self._sel_role)
            hov = is_hover(mx, my, _RIGHT_X + _ROLE_PAD, ry,
                           _RIGHT_W - _ROLE_PAD * 2 - sb_w, _ROLE_ROW_H) and not sel
            row_x = _RIGHT_X + _ROLE_PAD
            row_w = _RIGHT_W - _ROLE_PAD * 2 - sb_w
            if sel:
                pyxel.rect(row_x, ry, row_w, _ROLE_ROW_H, EDIT_ACCENT)
                fg = EDIT_BG
            elif hov:
                pyxel.rect(row_x, ry, row_w, _ROLE_ROW_H, EDIT_BTN_HOVER)
                fg = EDIT_TEXT
            else:
                fg = EDIT_TEXT
            idx = self._idx(r)
            sw = 18
            pyxel.rect(row_x + 2, ry + 4, sw, _ROLE_ROW_H - 8, idx)
            pyxel.rectb(row_x + 2, ry + 4, sw, _ROLE_ROW_H - 8, EDIT_BORDER)
            tx = row_x + 2 + sw + 6
            draw_unicode(tx, ry + 2, r, fg, size=12)
            draw_unicode(tx, ry + 16, f"#{idx:03d}  {_hex_for_idx(idx)}",
                         fg, size=10)
        pyxel.clip()

        content_h = len(self._roles) * _ROLE_ROW_H
        view_h = _ROLES_H - title_bar_h() - _ROLE_PAD * 2
        if content_h > view_h:
            track_x = _RIGHT_X + _RIGHT_W - 6
            track_y = title_bar_h() + _ROLE_PAD
            track_h = view_h
            max_scroll = max(1, content_h - view_h)
            thumb_h = max(18, int(track_h * view_h / content_h))
            thumb_y = track_y + int((track_h - thumb_h)
                                    * self._role_scroll / max_scroll)
            pyxel.rect(track_x, track_y, 3, track_h, EDIT_BORDER)
            pyxel.rect(track_x, thumb_y, 3, thumb_h, EDIT_ACCENT)

    def _draw_right_tabs(self, mx, my):
        h = title_bar_h()
        roles_w = 72
        preset_w = 82
        pyxel.rect(_RIGHT_X, 0, _RIGHT_W, h, EDIT_TITLE_BG)
        pyxel.line(_RIGHT_X, h - 1, _RIGHT_X + _RIGHT_W, h - 1,
                   EDIT_BORDER)
        draw_button(_RIGHT_X + 4, 1, roles_w - 8, "ROLES", h=h - 2,
                    active=self._right_view == "roles", size=10,
                    hover=is_hover(mx, my, _RIGHT_X, 0, roles_w, h))
        draw_button(_RIGHT_X + roles_w + 4, 1, preset_w - 8, "PRESET",
                    h=h - 2, active=self._right_view == "presets", size=10,
                    hover=is_hover(mx, my, _RIGHT_X + roles_w, 0,
                                   preset_w, h))

    def _draw_presets_panel(self, mx, my):
        x = _RIGHT_X + _ROLE_PAD
        y = title_bar_h() + 8

        draw_unicode(x, y, "EDIT", EDIT_ACCENT, size=12)
        for i, (name, preset) in enumerate(_EDITOR_PRESETS):
            bx, by, bw, bh = self._preset_button_geom("edit", i)
            draw_button(bx, by, bw, name, h=bh, size=12,
                        active=self._preset_active(preset),
                        hover=is_hover(mx, my, bx, by, bw, bh))

        bh = 22
        y += 16
        y += 2 * (bh + 4) + 18
        draw_unicode(x, y, "PLAY", EDIT_ACCENT, size=12)
        for i, (name, preset) in enumerate(_PLAY_PRESETS):
            bx, by, bw, bh = self._preset_button_geom("play", i)
            draw_button(bx, by, bw, name, h=bh, size=12,
                        active=self._preset_active(preset),
                        hover=is_hover(mx, my, bx, by, bw, bh))

    def _draw_role_detail_panel(self):
        draw_panel(_RIGHT_X, _DETAIL_Y, _RIGHT_W, _DETAIL_H)
        draw_titlebar(_RIGHT_X, _DETAIL_Y, _RIGHT_W, "SELECTED COLOR")
        if not self._sel_role:
            return

        idx = self._idx(self._sel_role)
        sw_x = _RIGHT_X + 10
        sw_y = _DETAIL_Y + title_bar_h() + 8
        sw_w = 52
        sw_h = 34
        pyxel.rect(sw_x, sw_y, sw_w, sw_h, idx)
        pyxel.rectb(sw_x, sw_y, sw_w, sw_h, EDIT_BORDER)
        pyxel.rectb(sw_x + 1, sw_y + 1, sw_w - 2, sw_h - 2, EDIT_ACCENT)

        tx = sw_x + sw_w + 10
        ty = sw_y
        draw_unicode(tx, ty, self._sel_role, EDIT_TEXT, size=12)
        draw_unicode(tx, ty + 15, f"#{idx:03d}  {_hex_for_idx(idx)}",
                     EDIT_ACCENT, size=12)
        desc = _ROLE_DESC.get(self._sel_role, "")
        draw_unicode(tx, ty + 31, desc[:28], EDIT_TEXT_DIM, size=10)

    # ─── 256色グリッド (RIGHT-BOTTOM) ──────────────────────
    def _grid_geom(self):
        area_x = _RIGHT_X + 8
        area_y = _GRID_Y + title_bar_h() + 8
        area_w = _RIGHT_W - 16
        area_h = _GRID_H - title_bar_h() - 16
        cw = area_w // _GRID_COLS
        ch = area_h // _GRID_ROWS
        return area_x, area_y, cw, ch

    def _draw_grid_panel(self, mx, my):
        draw_panel(_RIGHT_X, _GRID_Y, _RIGHT_W, _GRID_H)
        draw_titlebar(_RIGHT_X, _GRID_Y, _RIGHT_W,
                      "MASTER PALETTE (click to assign)")

        sel_idx = self._idx(self._sel_role) if self._sel_role else -1
        gx0, gy0, cw, chh = self._grid_geom()
        for pos in range(256):
            idx = self._display_order[pos]
            col = pos % _GRID_COLS
            row = pos // _GRID_COLS
            cx = gx0 + col * cw
            cy = gy0 + row * chh
            pyxel.rect(cx, cy, cw, chh, idx)
            if idx == sel_idx:
                pyxel.rectb(cx, cy, cw, chh, EDIT_ACCENT)
                pyxel.rectb(cx + 1, cy + 1, cw - 2, chh - 2, EDIT_ACCENT)
            elif is_hover(mx, my, cx, cy, cw, chh):
                pyxel.rectb(cx, cy, cw, chh, EDIT_TEXT)

    # ─── Toolbar ──────────────────────────────────────────
    def _draw_toolbar(self, mx, my):
        y = _PANEL_H
        pyxel.rect(0, y, _SCREEN_W, _BTN_H, EDIT_TITLE_BG)
        pyxel.line(0, y, _SCREEN_W, y, EDIT_BORDER)
        bar_y = y + (_BTN_H - 20) // 2
        draw_button(4,   bar_y, 82, "SAVE", h=20, size=10,
                    hover=is_hover(mx, my, 4,   bar_y, 82, 20))
        draw_button(90,  bar_y, 70, "REVERT", h=20, size=10,
                    hover=is_hover(mx, my, 90, bar_y, 70, 20))
        draw_button(164, bar_y, 88, "DEFAULT", h=20, size=10,
                    hover=is_hover(mx, my, 164, bar_y, 88, 20))
        draw_button(256, bar_y, 60, "CANCEL", h=20, size=10,
                    hover=is_hover(mx, my, 256, bar_y, 60, 20))
        draw_unicode(330, y + (_BTN_H - 10) // 2,
                     "PRESET: top-right panel",
                     EDIT_TEXT_DIM, size=10)
