"""フォント設定画面 (720×480 フルスクリーン)

エディタフォント、UIフォントサイズ、ダイアログフォントを設定できる。
リアルタイムプレビュー付き。
"""
import os
import pyxel
from ui.colors import (
    EDIT_BG, EDIT_PANEL, EDIT_BORDER, EDIT_TEXT, EDIT_TEXT_DIM, EDIT_ACCENT,
    EDIT_BTN_BG, EDIT_BTN_HOVER, EDIT_PREVIEW_BG, EDIT_HIGHLIGHT, EDIT_TITLE_BG,
    PLAY_BG, PLAY_BORDER, PLAY_TEXT, PLAY_DIALOG_BG, PLAY_ACCENT,
    PLAY_SPEAKER_BG, PLAY_SPEAKER_FG, PLAY_CHOICE_BG, PLAY_CHOICE_HOVER,
)
import ui.widgets as _w
from ui.widgets import (
    draw_panel, draw_titlebar, draw_button, draw_unicode,
    draw_list_item, draw_field,
    is_hover, is_clicked, NumericSlider,
    title_bar_h, tab_h, item_h, field_h, label_h,
    set_editor_font, set_ui_font_size, set_ui_scale, text_px_w,
)
from ui.confirm_dialog import ConfirmDialog

# レイアウト
_LEFT_W  = 340
_RIGHT_W = 380   # 720 - 340
_BTN_H   = 32
_PANEL_H = 480 - _BTN_H   # = 448

_LIST_VISIBLE = 4   # フォントリスト表示行数
_LIST_ITEM_H  = 24  # フォントリストアイテム高さ


class FontSettingsEditor:
    """フォント設定画面。active=True の間は update/draw を呼ぶ。"""

    def __init__(self):
        self.active = False
        self.result = None   # "saved" | "cancelled"

        # 設定値
        self.editor_font      = ""
        self.editor_font_size = 16
        self.ui_font_size     = 16
        self.ui_scale         = 1
        self.dialog_font      = ""
        self.dialog_font_size = 16

        # バックアップ (REVERT / CANCEL 用)
        self._saved = {}

        # フォントファイル一覧
        self._font_files = []

        # スクロール
        self._editor_scroll = 0
        self._dialog_scroll = 0

        # スライダー
        self._sl_editor_sz = NumericSlider(8, 25, 1, False)
        self._sl_ui_sz     = NumericSlider(8, 25, 1, False)
        self._sl_ui_scale  = NumericSlider(1, 4, 1, False)
        self._sl_dialog_sz = NumericSlider(8, 25, 1, False)

        # ライター キャッシュ
        self._writer_cache = {}
        self._base_dir     = ""
        self._discard_confirm = ConfirmDialog()

    # ── 公開 API ────────────────────────────────────────────────

    def open(self, settings: dict, base_dir: str):
        self.active = True
        self.result = None
        self._base_dir = base_dir

        self.editor_font      = settings.get("editor_font", "IPA_Gothic.ttf")
        self.editor_font_size = int(settings.get("editor_font_size", 16))
        self.ui_font_size     = int(settings.get("ui_font_size", 16))
        self.ui_scale         = max(1, min(4, int(settings.get("ui_scale", 1))))
        self.dialog_font      = settings.get("dialog_font", "IPA_Gothic.ttf")
        self.dialog_font_size = int(settings.get("dialog_font_size", 16))

        self._saved = {
            "editor_font":      self.editor_font,
            "editor_font_size": self.editor_font_size,
            "ui_font_size":     self.ui_font_size,
            "ui_scale":         self.ui_scale,
            "dialog_font":      self.dialog_font,
            "dialog_font_size": self.dialog_font_size,
        }

        self._editor_scroll = 0
        self._dialog_scroll = 0

        # フォントファイル一覧をスキャン
        self._scan_fonts(base_dir)
        self._apply_live()

    def get_settings(self) -> dict:
        return {
            "editor_font":      self.editor_font,
            "editor_font_size": self.editor_font_size,
            "ui_font_size":     self.ui_font_size,
            "ui_scale":         self.ui_scale,
            "dialog_font":      self.dialog_font,
            "dialog_font_size": self.dialog_font_size,
        }

    def _dirty(self) -> bool:
        return self.get_settings() != self._saved

    # ── 内部 ────────────────────────────────────────────────────

    def _scan_fonts(self, base_dir: str):
        """assets/fonts/ から .ttf/.otf を収集"""
        fonts_dir = os.path.join(base_dir, "assets", "fonts")
        self._font_files = []
        if os.path.isdir(fonts_dir):
            for f in sorted(os.listdir(fonts_dir)):
                if f.lower().endswith((".ttf", ".otf")) and not f.startswith("."):
                    self._font_files.append(f)

    def _make_font(self, font_file: str, size: int = 16):
        """フォントファイルから pyxel.Font を作成 (キャッシュ付き)"""
        key = (font_file, size)
        if key in self._writer_cache:
            return self._writer_cache[key]
        from ui.widgets import load_pyxel_font, set_font_base_dir
        set_font_base_dir(self._base_dir)
        font = load_pyxel_font(font_file, size)
        self._writer_cache[key] = font
        return font

    def _apply_live(self):
        """現在の設定をリアルタイムに適用"""
        # エディタフォント
        f = self._make_font(self.editor_font, self.editor_font_size)
        if f:
            set_editor_font(f, self.editor_font_size, path=self.editor_font)
        # UIフォントサイズ
        set_ui_font_size(self.ui_font_size)
        # UI Scale (pyxel デフォルトフォントの倍率)
        set_ui_scale(self.ui_scale)
        # ダイアログはBDF統一。フォントファイル指定は互換保存のみで、
        # 実際の描画にはサイズだけを反映する。
        from engine.player import set_dialog_font_size
        set_dialog_font_size(self.dialog_font_size)

    def _revert(self):
        """設定を開いた時点に戻す"""
        self.editor_font      = self._saved["editor_font"]
        self.editor_font_size = self._saved["editor_font_size"]
        self.ui_font_size     = self._saved["ui_font_size"]
        self.ui_scale         = self._saved["ui_scale"]
        self.dialog_font      = self._saved["dialog_font"]
        self.dialog_font_size = self._saved["dialog_font_size"]
        self._apply_live()

    def _finish_cancelled(self):
        self._revert()
        self.result = "cancelled"
        self.active = False

    def _request_cancel(self):
        if self._dirty():
            self._discard_confirm.open(
                "UNSAVED CHANGES",
                "Font settings have unsaved edits.\n"
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

    # ── update ────────────────────────────────────────────────────

    def update(self):
        if not self.active:
            return
        if self._update_discard_confirm():
            return
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        changed = False

        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self._request_cancel()
            return

        # ── 左パネル: 設定 ──
        cy = title_bar_h() + 4

        # EDITOR FONT リスト
        cy += 10  # ラベル高さ
        for i in range(self._editor_scroll,
                       min(len(self._font_files),
                           self._editor_scroll + _LIST_VISIBLE)):
            vi = i - self._editor_scroll
            iy = cy + vi * _LIST_ITEM_H
            if is_clicked(mx, my, 4, iy, _LEFT_W - 8, _LIST_ITEM_H):
                self.editor_font = self._font_files[i]
                changed = True
        list_area_y = cy
        list_area_h = _LIST_VISIBLE * _LIST_ITEM_H
        if is_hover(mx, my, 0, list_area_y, _LEFT_W, list_area_h):
            wheel = pyxel.mouse_wheel
            if wheel:
                self._editor_scroll = max(
                    0, min(len(self._font_files) - _LIST_VISIBLE,
                           self._editor_scroll - wheel))
        cy += list_area_h + 4

        # EDITOR FONT SIZE slider
        cy += 2  # gap
        nv = self._sl_editor_sz.handle(4, cy, _LEFT_W - 8, 32,
                                        mx, my, self.editor_font_size)
        if nv is not None:
            self.editor_font_size = nv
            changed = True
        cy += 36

        # UI FONT SIZE slider
        nv = self._sl_ui_sz.handle(4, cy, _LEFT_W - 8, 32,
                                   mx, my, self.ui_font_size)
        if nv is not None:
            self.ui_font_size = nv
            changed = True
        cy += 36

        # UI SCALE slider (pyxel デフォルトフォントの倍率 1〜4)
        nv = self._sl_ui_scale.handle(4, cy, _LEFT_W - 8, 32,
                                       mx, my, self.ui_scale)
        if nv is not None:
            self.ui_scale = nv
            changed = True
        cy += 36

        # DIALOG FONT リスト
        cy += 10
        for i in range(self._dialog_scroll,
                       min(len(self._font_files),
                           self._dialog_scroll + _LIST_VISIBLE)):
            vi = i - self._dialog_scroll
            iy = cy + vi * _LIST_ITEM_H
            if is_clicked(mx, my, 4, iy, _LEFT_W - 8, _LIST_ITEM_H):
                self.dialog_font = self._font_files[i]
                changed = True
        dlist_area_y = cy
        dlist_area_h = _LIST_VISIBLE * _LIST_ITEM_H
        if is_hover(mx, my, 0, dlist_area_y, _LEFT_W, dlist_area_h):
            wheel = pyxel.mouse_wheel
            if wheel:
                self._dialog_scroll = max(
                    0, min(len(self._font_files) - _LIST_VISIBLE,
                           self._dialog_scroll - wheel))
        cy += dlist_area_h + 4

        # DIALOG FONT SIZE slider
        cy += 2
        nv = self._sl_dialog_sz.handle(4, cy, _LEFT_W - 8, 32,
                                        mx, my, self.dialog_font_size)
        if nv is not None:
            self.dialog_font_size = nv
            changed = True

        if changed:
            self._apply_live()

        # ── 下部ボタンバー ──
        bar_y = _PANEL_H + (_BTN_H - 20) // 2
        bw = 126
        if is_clicked(mx, my, 4, bar_y, bw, 20):
            # SAVE & CLOSE
            self.result = "saved"
            self.active = False
        if is_clicked(mx, my, 134, bar_y, bw, 20):
            # REVERT ALL
            self._revert()
        if is_clicked(mx, my, 264, bar_y, 80, 20):
            # CANCEL
            self._request_cancel()

    # ── draw ──────────────────────────────────────────────────────

    def draw(self):
        if not self.active:
            return
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        pyxel.cls(EDIT_BG)

        # ── 左パネル: 設定 ──
        draw_panel(0, 0, _LEFT_W, _PANEL_H)
        draw_titlebar(0, 0, _LEFT_W, "FONT CONFIG")

        cy = title_bar_h() + 4

        # EDITOR FONT
        pyxel.text(4, cy, "EDITOR FONT", EDIT_ACCENT)
        cy += 10
        for i in range(self._editor_scroll,
                       min(len(self._font_files),
                           self._editor_scroll + _LIST_VISIBLE)):
            vi = i - self._editor_scroll
            iy = cy + vi * _LIST_ITEM_H
            sel = (self._font_files[i] == self.editor_font)
            hov = is_hover(mx, my, 4, iy, _LEFT_W - 8, _LIST_ITEM_H)
            if sel:
                pyxel.rect(4, iy, _LEFT_W - 8, _LIST_ITEM_H, EDIT_ACCENT)
            elif hov:
                pyxel.rect(4, iy, _LEFT_W - 8, _LIST_ITEM_H, EDIT_BTN_HOVER)
            draw_unicode(6, iy + 2, self._font_files[i],
                         EDIT_BG if sel else EDIT_TEXT, size=10)
        cy += _LIST_VISIBLE * _LIST_ITEM_H + 4

        # EDITOR FONT SIZE
        cy += 2
        self._sl_editor_sz.draw(4, cy, _LEFT_W - 8, 32,
                                "EDITOR FONT SIZE",
                                self.editor_font_size, label_h=10)
        cy += 36

        # UI FONT SIZE
        self._sl_ui_sz.draw(4, cy, _LEFT_W - 8, 32,
                            "UI FONT SIZE",
                            self.ui_font_size, label_h=10)
        cy += 36

        # UI SCALE (pyxel default font multiplier)
        self._sl_ui_scale.draw(4, cy, _LEFT_W - 8, 32,
                                "UI SCALE (default font x N)",
                                self.ui_scale, label_h=10)
        cy += 36

        # DIALOG FONT (BDF固定。旧TTF選択は互換表示のみ)
        draw_unicode(4, cy, "DIALOG FONT (BDF)", EDIT_ACCENT, size=10)
        cy += 10
        for i in range(self._dialog_scroll,
                       min(len(self._font_files),
                           self._dialog_scroll + _LIST_VISIBLE)):
            vi = i - self._dialog_scroll
            iy = cy + vi * _LIST_ITEM_H
            sel = (self._font_files[i] == self.dialog_font)
            hov = is_hover(mx, my, 4, iy, _LEFT_W - 8, _LIST_ITEM_H)
            if sel:
                pyxel.rect(4, iy, _LEFT_W - 8, _LIST_ITEM_H, EDIT_ACCENT)
            elif hov:
                pyxel.rect(4, iy, _LEFT_W - 8, _LIST_ITEM_H, EDIT_BTN_HOVER)
            draw_unicode(6, iy + 2, self._font_files[i],
                         EDIT_BG if sel else EDIT_TEXT, size=10)
        cy += _LIST_VISIBLE * _LIST_ITEM_H + 4

        # DIALOG FONT SIZE
        cy += 2
        self._sl_dialog_sz.draw(4, cy, _LEFT_W - 8, 32,
                                "DIALOG FONT SIZE",
                                self.dialog_font_size, label_h=10)

        # ── 右パネル: プレビュー ──
        rx = _LEFT_W
        draw_panel(rx, 0, _RIGHT_W, _PANEL_H)
        draw_titlebar(rx, 0, _RIGHT_W, "PREVIEW")
        self._draw_preview(rx, mx, my)

        # ── 下部ツールバー ──
        pyxel.rect(0, _PANEL_H, 720, _BTN_H, EDIT_TITLE_BG)
        pyxel.line(0, _PANEL_H, 720, _PANEL_H, EDIT_BORDER)

        bar_y = _PANEL_H + (_BTN_H - 20) // 2
        bw = 126
        draw_button(4,   bar_y, bw, "SAVE & CLOSE", h=20,
                    hover=is_hover(mx, my, 4,   bar_y, bw, 20))
        draw_button(134, bar_y, bw, "REVERT ALL",   h=20,
                    hover=is_hover(mx, my, 134, bar_y, bw, 20))
        draw_button(264, bar_y, 80, "CANCEL",        h=20,
                    hover=is_hover(mx, my, 264, bar_y, 80, 20))
        draw_unicode(360, _PANEL_H + (_BTN_H - 8) // 2,
                     "ESC = CANCEL", EDIT_TEXT_DIM, size=9)

        # カーソル
        pyxel.line(mx - 4, my, mx + 4, my, 7)
        pyxel.line(mx, my - 4, mx, my + 4, 7)
        self._discard_confirm.draw()

    def _draw_preview(self, rx, mx, my):
        """右パネル: UIプレビュー"""
        px = rx + 8
        py = title_bar_h() + 8
        pw = _RIGHT_W - 16

        _GAP = 4  # 各プレビュー要素間の共通間隔

        # ダイアログサンプルに十分な高さを確保するため上部は固定の小さい高さで表示
        ui_rh = _w._ui_render_h()
        tbh = ui_rh + 4  # タイトルバー
        th  = ui_rh + 4  # タブ
        ih  = ui_rh + 4  # リスト
        lh  = label_h()

        # -- タイトルバーサンプル --
        pyxel.rect(px, py, pw, tbh, EDIT_TITLE_BG)
        draw_unicode(px + 4, py + (tbh - ui_rh) // 2,
                     "TITLE BAR", EDIT_TEXT, size=_w._ui_font_size)
        py += tbh + _GAP

        # -- タブ行サンプル --
        tw = pw // 3
        for i, lbl in enumerate(("SCENE", "CHARS", "CHOICES")):
            draw_button(px + i * tw, py, tw, lbl,
                        h=th, active=(i == 0))
        py += th + _GAP

        # -- リストアイテム (選択 / 通常) サンプル --
        pyxel.rect(px, py, pw, ih, EDIT_ACCENT)
        draw_unicode(px + 4, py + (ih - ui_rh) // 2,
                     "Selected Item", EDIT_BG, size=_w._ui_font_size)
        py += ih
        draw_unicode(px + 4, py + (ih - ui_rh) // 2,
                     "Normal Item", EDIT_TEXT_DIM, size=_w._ui_font_size)
        py += ih + _GAP

        # -- ダイアログボックスサンプル (残り領域を全て使う) --
        dsz = self.dialog_font_size
        drh = _w._font_render_h(dsz)
        line_h_d = drh + 4
        badge_h = drh + 8
        # バッジが上に伸びる分の余白を確保
        py += badge_h
        remaining = _PANEL_H - py - 8
        min_dlg_h = line_h_d * 5 + 20  # 5行分 + 上下余白
        dlg_h = max(min_dlg_h, remaining)
        # 下端をはみ出す場合は Choice ボタンをスキップ（後段で判定）

        pyxel.rect(px, py, pw, dlg_h, PLAY_DIALOG_BG)
        pyxel.rectb(px, py, pw, dlg_h, PLAY_ACCENT)
        pyxel.rectb(px + 2, py + 2, pw - 4, dlg_h - 4, PLAY_BORDER)

        # スピーカーバッジ
        speaker = "Alice"
        badge_w = len(speaker) * (dsz // 2 + 1) + 20
        badge_x = px + 12
        badge_y = py - badge_h + 2
        pyxel.rect(badge_x, badge_y, badge_w, badge_h, PLAY_SPEAKER_BG)
        pyxel.rectb(badge_x, badge_y, badge_w, badge_h, PLAY_BORDER)
        draw_unicode(badge_x + 10, badge_y + (badge_h - drh) // 2,
                     speaker, PLAY_SPEAKER_FG, size=dsz)

        # ダイアログテキスト（日英サンプル）
        _samples = [
            "ABCDEFGabcdefg",
            "0123456789!?@#",
            "あいうえおかきくけこ",
            "The quick brown fox",
            "吾輩は猫である。",
        ]
        tx = px + 12
        ty = py + 10
        line_h = drh + 4
        for line in _samples:
            if ty + drh > py + dlg_h - 4:
                break
            draw_unicode(tx, ty, line, PLAY_TEXT, size=dsz)
            ty += line_h

        py += dlg_h + 8

        # -- 選択肢ボタンサンプル --
        choice_h = drh + 12
        choice_w = min(pw - 16, 260)
        cx = px + (pw - choice_w) // 2
        if py + choice_h * 2 + 6 < _PANEL_H:
            for i, lbl in enumerate(("Choice A", "Choice B")):
                cy = py + i * (choice_h + 6)
                hov = (i == 0)
                bg_ = PLAY_CHOICE_HOVER if hov else PLAY_CHOICE_BG
                fg_ = PLAY_BG if hov else PLAY_TEXT
                pyxel.rect(cx, cy, choice_w, choice_h, bg_)
                pyxel.rectb(cx, cy, choice_w, choice_h, PLAY_ACCENT)
                lw = text_px_w(lbl, dsz)
                draw_unicode(cx + (choice_w - lw) // 2,
                             cy + (choice_h - drh) // 2,
                             lbl, fg_, size=dsz)
