"""エディタの各パネル (720×480)"""
import os
import sys
import subprocess
import threading
import unicodedata as _unicodedata
import pyxel
from ui.colors import *
import ui.widgets as _w
from ui.widgets import (
    draw_panel, draw_titlebar, draw_button,
    draw_list_item, draw_field, draw_unicode, draw_ui_text,
    is_hover, is_clicked,
    TITLE_BAR_H, NumericSlider,
    title_bar_h, tab_h, item_h, field_h, label_h, anim_fh,
    slider_h, slider_pitch,
    button_w, reset_btn_w, draw_reset_btn,
    text_px_w,
)
from ui.flow_view import FlowView
from ui.file_picker import FilePicker
from ui.native_dialogs import ask_text, ask_multiline, AsyncTextDialog
from editor_state import (
    display_name, normalize_character_position_memory, parse_scene_name,
)
from engine import image_cache as _image_cache_mod
from engine import palette as _palette_mod
from engine import player_prefs as _player_prefs
from engine.image_cache import (
    COLOR_KEY_AUTO,
    normalize_color_key,
    color_key_label,
)
from engine.animator import (
    prepare_char_config_for_next_scene,
    sprite_load_size_for_screen,
    sprite_top_left,
)
from engine.text_wrap import dialog_letter_spacing, wrap_text

# ── レイアウト定数 ──────────────────────────────────────────────
#   上段: MainView (Preview / Flow) — 全幅 720×240
#   中段: Toolbar                  — 全幅 720×26  (y=240)
#   下段左: SceneList w=160×214    (y=266)
#   下段右: Properties w=560×214   (y=266)
#   合計: 240+26+214 = 480

# 新レイアウト (BDF b12.bdf 統一):
#   Toolbar 720×26 (上): tabs + filename + 右端アクション
#   SceneList 200×454 (左、縦一杯): P/C 縦並び + シーン一覧 + ADD/COPY/DEL
#   MainView (preview) 520×180 (右上): キャラ配置プレビュー
#   Properties 520×274 (右中下): スクロール可能なフィールド領域
TB_X, TB_Y, TB_W, TB_H = 0,   0, 720,  26
SL_X, SL_Y, SL_W, SL_H = 0,  26, 200, 454
MV_X, MV_Y, MV_W, MV_H = 200, 26, 520, 180
PP_X, PP_Y, PP_W, PP_H = 200, 206, 520, 274

# 動的サイズ: widgets.py の item_h(), tab_h(), field_h(), label_h(), anim_fh() を使用

_BDF_SIZE_OPTIONS = (10, 12, 14, 16, 17, 18, 19, 20, 21, 22, 23, 24)

# ── スライダー仕様 ─────────────────────────────────────────────
# key → (min, max, step, is_float)
_SLIDER_SPECS = {
    # 背景
    "bg_x":                  (-720, 1440,  1, False),
    "bg_y":                  (-480,  960,  1, False),
    "bg_w":                  (   0, 1440,  1, False),  # 0=スクリーンサイズ
    "bg_h":                  (   0,  960,  1, False),  # 0=スクリーンサイズ
    # キャラクター
    "x":                     (-720, 1440,  1, False),
    "y":                     (-480,  960,  1, False),
    "w":                     (   0, 1440,  1, False),  # 0=元サイズ
    "h":                     (   0,  960,  1, False),  # 0=元サイズ
    "colkey":                (  -2,  255,  1, False),
    "scaling":               ( 0.1,  5.0, 0.01, True),  # CHARACTER SCALING (倍率)
    # アニメーション（全て step=1 に統一、右クリックで精密入力可）
    "anim_shake_amp":        (   0,   50,  1, False),
    "anim_shake_speed":      (   1,   60,  1, False),
    "anim_rot_speed":        ( -36,   36,  1, True),
    "anim_scale_start":      (   0,   10, 0.01, True),
    "anim_scale_end":        (   0,   10, 0.01, True),
    "anim_scale_frames":     (   0,  300,  1, False),
    "anim_motion_x":         (-720,  720,  1, False),
    "anim_motion_y":         (-480,  480,  1, False),
    "anim_motion_frames":    (   0,  300,  1, False),
    "anim_flipbook_interval":(   1,   60,  1, False),
    # フォントサイズ
    "font_size":             (   0,   11,  1, False),  # BDF size index
    # オーディオ
    "bgm_volume":            (   1,   10,  1, False),
    "bgm_fadeout_frames":    (   0,  300,  1, False),
    "se_volume":             (   1,   10,  1, False),
    "se_repeat":             (   0,   10,  1, False),
}

def _reset_w() -> int:
    """[↻] リセットボタンの必要幅 (TTF描画なので reset_btn_w() を使用)。"""
    return reset_btn_w()

# ANIMATION フィールド定義: (表示ラベル, キー, デフォルト値, float フラグ)
_ANIM_DEFS = [
    ("SHAKE AMPLITUDE",   "shake_amp",         0,    False),
    ("SHAKE SPEED",       "shake_speed",       4,    False),
    ("ROTATION SPEED",    "rot_speed",         0.0,  True),
    ("SCALE START",       "scale_start",       1.0,  True),
    ("SCALE END",         "scale_end",         1.0,  True),
    ("SCALE FRAMES",      "scale_frames",      0,    False),
    ("MOTION X",          "motion_x",          0,    False),
    ("MOTION Y",          "motion_y",          0,    False),
    ("MOTION FRAMES",     "motion_frames",     0,    False),
    ("FLIPBOOK INTERVAL", "flipbook_interval", 6,    False),
]


# ── SceneListPanel ───────────────────────────────────────────────

_CTX_ROW_H = 24   # Part/Chapter コンテキスト行の高さ

class SceneListPanel:
    """左パネル: シーン一覧 (Part/Chapter 縦並びドロップダウン付き)。

    レイアウト (上から):
      title bar      (タイトル "SCENES")
      P dropdown     (Part 名、全幅)
      P nav [<][>]   (Part 前/次、半分ずつ)
      C dropdown     (Chapter 名、全幅)
      C nav [<][>]   (Chapter 前/次、半分ずつ)
      scene list     (スクロール可)
      [+ADD][COPY][DEL]  (下部固定)

    P/C のラベルが幅に収まらない場合、ホバー中にホイールで横スクロール可能。
    """
    X, Y, W, H = SL_X, SL_Y, SL_W, SL_H
    _ROW_H = 24

    def __init__(self, state):
        self.state = state
        self._scroll_y = 0
        self._scroll_x = 0  # シーン名横スクロールオフセット
        self._hover_idx = -1
        # ドラッグ&ドロップ
        self._drag_src = -1
        self._drag_start_y = 0
        self._drag_active = False
        self._drag_threshold = 4
        # P/C ラベル横スクロールオフセット (px)
        self._p_scroll_x = 0
        self._c_scroll_x = 0
        # スクロールバードラッグ状態
        self._dragging_vbar = False
        self._dragging_hbar = False
        self._drag_bar_my0 = 0
        self._drag_bar_mx0 = 0
        self._drag_bar_scroll0 = 0
        # 横スクロールバーは縦スクロール領域の下端を 6px 取る
        self._HBAR_H = 6

    # ── 行の Y 座標 ─────────────────────────────────────────
    def _p_row_y(self):    return self.Y + title_bar_h()
    def _p_nav_y(self):    return self._p_row_y() + self._ROW_H
    def _c_row_y(self):    return self._p_nav_y() + self._ROW_H
    def _c_nav_y(self):    return self._c_row_y() + self._ROW_H

    def _list_top(self):
        return self._c_nav_y() + self._ROW_H + 2

    def _list_bot(self):
        # ADD/COPY/DEL ボタンの上、横スクロールバーの上を返す。
        _btn_h = max(20, _w._font_render_h(_w._ui_font_size) + 6)
        return self.Y + self.H - _btn_h - 2 - self._HBAR_H

    def _hbar_y(self):
        return self._list_bot()

    def _max_row_width(self) -> int:
        """フィルタ済みシーン名の最大描画幅 (横スクロール量算出用)。"""
        filtered = self.state.filtered_scenes()
        if not filtered:
            return 0
        fz = _w._ui_font_size
        return max(text_px_w(display_name(s), fz) for _, s in filtered)

    def _scroll_x_list_max(self) -> int:
        """シーン名横スクロールの上限。"""
        # 行内 padding 8px (左 4 + 右 4)
        return max(0, self._max_row_width() + 8 - self.W + 4)

    def _cap_scroll(self):
        filtered = self.state.filtered_scenes()
        total = len(filtered) * item_h()
        vis = self._list_bot() - self._list_top()
        self._scroll_y = max(0, min(max(0, total - vis), self._scroll_y))

    def scroll_selected_into_view(self):
        """外部から選択シーンが変わった時、選択行が見える位置へスクロールする。"""
        filtered = self.state.filtered_scenes()
        sel_fi = next((fi for fi, (gi, _s) in enumerate(filtered)
                       if gi == self.state.selected_scene), -1)
        if sel_fi < 0:
            self._scroll_y = 0
            self._cap_scroll()
            return
        ih = item_h()
        view_h = self._list_bot() - self._list_top()
        row_top = sel_fi * ih
        row_bot = row_top + ih
        if row_top < self._scroll_y:
            self._scroll_y = row_top
        elif row_bot > self._scroll_y + view_h:
            self._scroll_y = row_bot - view_h
        self._cap_scroll()

    def _scroll_x_max(self, label: str) -> int:
        """ラベル横スクロールの上限 (= text_w - 描画領域幅)。0 以下なら不要。"""
        avail = self.W - 8  # ボタン内側パディング
        tw = text_px_w(label, _w._ui_font_size)
        return max(0, tw - avail)

    def update(self):
        mx, my = pyxel.mouse_x, pyxel.mouse_y

        # ── スクロールバードラッグ処理 ─────────────────────────
        # マウスボタン押下中は scrollbar 追従、離されたらドラッグ終了。
        if self._dragging_vbar or self._dragging_hbar:
            if not pyxel.btn(pyxel.MOUSE_BUTTON_LEFT):
                self._dragging_vbar = False
                self._dragging_hbar = False
            else:
                self._apply_scrollbar_drag(mx, my)
                return  # 他のクリック・操作は無視

        # キーボード上下でシーン選択カーソルを移動
        if not _text_dialog.running:
            up   = pyxel.btnp(pyxel.KEY_UP,   hold=15, repeat=3)
            down = pyxel.btnp(pyxel.KEY_DOWN, hold=15, repeat=3)
            if up or down:
                self._move_selection(-1 if up else 1)

        # ── Part dropdown (全幅) ───────────────────────────────
        p_y = self._p_row_y()
        if is_clicked(mx, my, self.X, p_y, self.W, self._ROW_H):
            self.state.request_parts = True

        # P nav ([<][>] 半分ずつ)
        pn_y = self._p_nav_y()
        half = self.W // 2
        if is_clicked(mx, my, self.X, pn_y, half, self._ROW_H):
            self._prev_part()
        if is_clicked(mx, my, self.X + half, pn_y, self.W - half, self._ROW_H):
            self._next_part()

        # ── Chapter dropdown (全幅) ───────────────────────────
        c_y = self._c_row_y()
        if is_clicked(mx, my, self.X, c_y, self.W, self._ROW_H):
            self.state.request_chapters = True

        # C nav
        cn_y = self._c_nav_y()
        if is_clicked(mx, my, self.X, cn_y, half, self._ROW_H):
            self._prev_chapter()
        if is_clicked(mx, my, self.X + half, cn_y, self.W - half, self._ROW_H):
            self._next_chapter()

        # ── スクロールバードラッグ開始判定 ─────────────────────
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            vbar = self._vbar_rect()
            if vbar and is_hover(mx, my, *vbar):
                self._dragging_vbar = True
                self._drag_bar_my0 = my
                self._drag_bar_scroll0 = self._scroll_y
                return
            hbar = self._hbar_rect()
            if hbar and is_hover(mx, my, *hbar):
                self._dragging_hbar = True
                self._drag_bar_mx0 = mx
                self._drag_bar_scroll0 = self._scroll_x
                return

        # ── ホイールスクロール: 領域別ディスパッチ ─────────
        wheel = pyxel.mouse_wheel
        if wheel:
            part = self.state.get_part(self.state.current_part_id)
            chap = self.state.get_chapter(self.state.current_part_id,
                                          self.state.current_chapter_id)
            p_label = f"[P:{part['name']}]" if part else "[P:--]"
            c_label = f"[C:{chap['name']}]" if chap else "[C:--]"
            # P dropdown 行
            if is_hover(mx, my, self.X, p_y, self.W, self._ROW_H):
                mx_off = self._scroll_x_max(p_label)
                self._p_scroll_x = max(0, min(mx_off,
                                              self._p_scroll_x - wheel * 16))
            # C dropdown 行
            elif is_hover(mx, my, self.X, c_y, self.W, self._ROW_H):
                mx_off = self._scroll_x_max(c_label)
                self._c_scroll_x = max(0, min(mx_off,
                                              self._c_scroll_x - wheel * 16))
            # シーンリスト領域: Shift+ホイールで横、通常ホイールで縦
            else:
                list_top = self._list_top()
                list_bot = self._list_bot()
                if is_hover(mx, my, self.X, list_top,
                            self.W, list_bot - list_top):
                    shift = (pyxel.btn(pyxel.KEY_LSHIFT)
                             or pyxel.btn(pyxel.KEY_RSHIFT))
                    if shift:
                        max_x = self._scroll_x_list_max()
                        self._scroll_x = max(0, min(max_x,
                                                    self._scroll_x - wheel * 20))
                    else:
                        self._scroll_y -= wheel * 20
                        self._cap_scroll()

        # シーンリスト クリック / ドラッグ
        # (ホイールセクションでは hover 条件下でしか list_top/_bot を計算
        #  していないので、ここで明示的に取り直す)
        list_top = self._list_top()
        list_bot = self._list_bot()
        filtered = self.state.filtered_scenes()
        self._hover_idx = -1

        if self._drag_src >= 0:
            # ドラッグ中
            if pyxel.btn(pyxel.MOUSE_BUTTON_LEFT):
                if not self._drag_active and abs(my - self._drag_start_y) > self._drag_threshold:
                    self._drag_active = True
            else:
                # ドロップ
                if self._drag_active and filtered:
                    drop = self._drop_index(mx, my, filtered, list_top)
                    if drop is not None and drop != self._drag_src:
                        src_global = filtered[self._drag_src][0]
                        dst_global = (filtered[drop][0] if drop < len(filtered)
                                      else filtered[-1][0] + 1)
                        if dst_global > src_global:
                            dst_global -= 1
                        self.state.reorder_scenes(src_global, dst_global)
                self._drag_src = -1
                self._drag_active = False
        else:
            right_clicked = pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT)
            for fi, (gi, scene) in enumerate(filtered):
                iy = list_top + fi * item_h() - self._scroll_y
                if iy + item_h() <= list_top or iy >= list_bot:
                    continue
                if is_hover(mx, my, self.X + 2, iy, self.W - 4, item_h()):
                    self._hover_idx = fi
                    # 右クリックで名前変更
                    if right_clicked and not _text_dialog.running:
                        self.state.select_scene(gi)
                        cur_name = display_name(scene)
                        def _cb_rename(val, idx=gi):
                            if val:
                                self.state.rename_scene(idx, val)
                        _text_dialog.open("SCENE NAME", cur_name, _cb_rename)
                if is_clicked(mx, my, self.X + 2, iy, self.W - 4, item_h()):
                    self.state.select_scene(gi)
                    self._drag_src = fi
                    self._drag_start_y = my
                    self._drag_active = False

        # +ADD / COPY / DEL
        _btn_h = max(16, _w._font_render_h(_w._ui_font_size) + 4)
        btn_y  = self.Y + self.H - _btn_h - 2
        third_w = (self.W - 16) // 3
        bx1 = self.X + 4
        bx2 = bx1 + third_w + 4
        bx3 = bx2 + third_w + 4
        if is_clicked(mx, my, bx1, btn_y, third_w, _btn_h):
            self.state.add_scene()
            self.scroll_selected_into_view()
        if is_clicked(mx, my, bx2, btn_y, third_w, _btn_h):
            self.state.copy_scene()
            self.scroll_selected_into_view()
        if is_clicked(mx, my, bx3, btn_y, third_w, _btn_h):
            self.state.request_delete_scene = True

    def _vbar_rect(self):
        """縦スクロールバーの thumb 矩形 (= ドラッグ受付領域) を返す。
        スクロール不要なら None。"""
        filtered = self.state.filtered_scenes()
        total_h = len(filtered) * item_h()
        view_h = self._list_bot() - self._list_top()
        if total_h <= view_h:
            return None
        bar_x = self.X + self.W - 6
        bar_y = self._list_top()
        bar_h = view_h
        thumb_h = max(12, int(bar_h * view_h / total_h))
        max_scroll = total_h - view_h
        ratio = self._scroll_y / max_scroll if max_scroll > 0 else 0
        thumb_y = bar_y + int((bar_h - thumb_h) * ratio)
        return (bar_x, thumb_y, 6, thumb_h)

    def _hbar_rect(self):
        """横スクロールバーの thumb 矩形を返す。スクロール不要なら None。"""
        max_scroll = self._scroll_x_list_max()
        if max_scroll <= 0:
            return None
        bar_x = self.X
        bar_y = self._hbar_y()
        bar_w = self.W
        bar_h = self._HBAR_H
        view_w = self.W
        total_w = view_w + max_scroll
        thumb_w = max(12, int(bar_w * view_w / total_w))
        ratio = self._scroll_x / max_scroll if max_scroll > 0 else 0
        thumb_x = bar_x + int((bar_w - thumb_w) * ratio)
        return (thumb_x, bar_y, thumb_w, bar_h)

    def _apply_scrollbar_drag(self, mx: int, my: int):
        """ドラッグ中のスクロールバー位置に応じて _scroll_y / _scroll_x を更新。"""
        if self._dragging_vbar:
            filtered = self.state.filtered_scenes()
            total_h = len(filtered) * item_h()
            view_h = self._list_bot() - self._list_top()
            max_scroll = max(0, total_h - view_h)
            if max_scroll > 0 and view_h > 0:
                # マウス Y 移動分を thumb 移動分とみなして比例的に scroll に変換
                dy = my - self._drag_bar_my0
                thumb_h = max(12, int(view_h * view_h / total_h))
                travel = max(1, view_h - thumb_h)
                delta_scroll = int(dy * max_scroll / travel)
                self._scroll_y = max(0, min(max_scroll,
                                            self._drag_bar_scroll0 + delta_scroll))
        if self._dragging_hbar:
            max_scroll = self._scroll_x_list_max()
            bar_w = self.W
            if max_scroll > 0 and bar_w > 0:
                dx = mx - self._drag_bar_mx0
                total_w = bar_w + max_scroll
                thumb_w = max(12, int(bar_w * bar_w / total_w))
                travel = max(1, bar_w - thumb_w)
                delta_scroll = int(dx * max_scroll / travel)
                self._scroll_x = max(0, min(max_scroll,
                                            self._drag_bar_scroll0 + delta_scroll))

    def _draw_scroll_button(self, x: int, y: int, w: int, h: int,
                            label: str, scroll_x: int, hover: bool = False):
        """テキストを横スクロール (= 描画 x オフセット) させながらボタン枠内に
        クリップ描画する。Part / Chapter dropdown 用。
        """
        # ボタン枠 (通常の draw_button と同じ見た目)
        bg = EDIT_BTN_HOVER if hover else EDIT_BTN_BG
        pyxel.rect(x, y, w, h, bg)
        pyxel.rectb(x, y, w, h, EDIT_BORDER)
        # クリップして label を描画
        fsz = _w._ui_font_size
        rh = _w._font_render_h(fsz)
        pad_x = 4
        ty = y + max(0, (h - rh) // 2)
        pyxel.clip(x + 2, y + 1, w - 4, h - 2)
        draw_unicode(x + pad_x - scroll_x, ty, label, EDIT_TEXT, size=fsz,
                     bg_col=bg)
        pyxel.clip()
        # スクロール可能インジケータ (右端に小さい三角)
        if scroll_x > 0 or self._scroll_x_max(label) > 0:
            ix = x + w - 4
            # 左へスクロール余地あれば左印
            if scroll_x > 0:
                pyxel.text(x + 2, y + h // 2 - 3, "<", EDIT_ACCENT)
            # 右へスクロール余地あれば右印
            if scroll_x < self._scroll_x_max(label):
                pyxel.text(ix - 4, y + h // 2 - 3, ">", EDIT_ACCENT)

    def _move_selection(self, delta: int):
        """フィルタ済みリスト内で選択を delta 行ぶん移動し、可視範囲へスクロール。"""
        filtered = self.state.filtered_scenes()
        if not filtered:
            return
        cur_global = self.state.selected_scene
        cur_fi = next((fi for fi, (gi, _s) in enumerate(filtered)
                       if gi == cur_global), -1)
        if cur_fi < 0:
            new_fi = 0 if delta > 0 else len(filtered) - 1
        else:
            new_fi = max(0, min(len(filtered) - 1, cur_fi + delta))
        if new_fi == cur_fi:
            return
        new_gi = filtered[new_fi][0]
        self.state.select_scene(new_gi)
        # 自動スクロール: 選択行が可視範囲内に収まるよう調整
        list_top = self._list_top()
        list_bot = self._list_bot()
        ih = item_h()
        row_top = new_fi * ih - self._scroll_y
        row_bot = row_top + ih
        view_h = list_bot - list_top
        if row_top < 0:
            self._scroll_y += row_top
        elif row_bot > view_h:
            self._scroll_y += row_bot - view_h
        self._cap_scroll()

    def _drop_index(self, mx, my, filtered, list_top):
        """ドロップ先のフィルタ済みインデックスを返す"""
        rel_y = my - list_top + self._scroll_y
        idx = int(rel_y / item_h() + 0.5)
        return max(0, min(len(filtered) - 1, idx))

    def _prev_part(self):
        parts = self.state.parts
        if not parts:
            return
        ids = [p["id"] for p in parts]
        try:
            ci = ids.index(self.state.current_part_id)
        except ValueError:
            ci = 0
        ci = (ci - 1) % len(ids)
        self.state.current_part_id = ids[ci]
        chs = self.state.chapters_for_part(self.state.current_part_id)
        self.state.current_chapter_id = chs[0]["id"] if chs else 0
        self._scroll_y = 0

    def _next_part(self):
        parts = self.state.parts
        if not parts:
            return
        ids = [p["id"] for p in parts]
        try:
            ci = ids.index(self.state.current_part_id)
        except ValueError:
            ci = -1
        ci = (ci + 1) % len(ids)
        self.state.current_part_id = ids[ci]
        chs = self.state.chapters_for_part(self.state.current_part_id)
        self.state.current_chapter_id = chs[0]["id"] if chs else 0
        self._scroll_y = 0

    def _prev_chapter(self):
        chs = self.state.chapters_for_part(self.state.current_part_id)
        if not chs:
            return
        ids = [c["id"] for c in chs]
        try:
            ci = ids.index(self.state.current_chapter_id)
        except ValueError:
            ci = 0
        ci = (ci - 1) % len(ids)
        self.state.current_chapter_id = ids[ci]
        self._scroll_y = 0

    def _next_chapter(self):
        chs = self.state.chapters_for_part(self.state.current_part_id)
        if not chs:
            return
        ids = [c["id"] for c in chs]
        try:
            ci = ids.index(self.state.current_chapter_id)
        except ValueError:
            ci = -1
        ci = (ci + 1) % len(ids)
        self.state.current_chapter_id = ids[ci]
        self._scroll_y = 0

    def draw(self):
        draw_panel(self.X, self.Y, self.W, self.H)
        draw_titlebar(self.X, self.Y, self.W, "SCENES")
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        half = self.W // 2

        part = self.state.get_part(self.state.current_part_id)
        chap = self.state.get_chapter(self.state.current_part_id,
                                      self.state.current_chapter_id)
        p_label = f"[P:{part['name']}]" if part else "[P:--]"
        c_label = f"[C:{chap['name']}]" if chap else "[C:--]"

        # ── P dropdown (全幅) ─────────────────────────────────
        p_y = self._p_row_y()
        self._draw_scroll_button(self.X, p_y, self.W, self._ROW_H,
                                 p_label, self._p_scroll_x,
                                 hover=is_hover(mx, my, self.X, p_y,
                                                self.W, self._ROW_H))
        # P nav [<][>]
        pn_y = self._p_nav_y()
        draw_button(self.X, pn_y, half, "<", h=self._ROW_H,
                    hover=is_hover(mx, my, self.X, pn_y, half, self._ROW_H))
        draw_button(self.X + half, pn_y, self.W - half, ">", h=self._ROW_H,
                    hover=is_hover(mx, my, self.X + half, pn_y,
                                   self.W - half, self._ROW_H))

        # ── C dropdown (全幅) ─────────────────────────────────
        c_y = self._c_row_y()
        self._draw_scroll_button(self.X, c_y, self.W, self._ROW_H,
                                 c_label, self._c_scroll_x,
                                 hover=is_hover(mx, my, self.X, c_y,
                                                self.W, self._ROW_H))
        # C nav [<][>]
        cn_y = self._c_nav_y()
        draw_button(self.X, cn_y, half, "<", h=self._ROW_H,
                    hover=is_hover(mx, my, self.X, cn_y, half, self._ROW_H))
        draw_button(self.X + half, cn_y, self.W - half, ">", h=self._ROW_H,
                    hover=is_hover(mx, my, self.X + half, cn_y,
                                   self.W - half, self._ROW_H))

        # シーンリスト
        list_top = self._list_top()
        list_bot = self._list_bot()
        filtered = self.state.filtered_scenes()

        pyxel.clip(self.X, list_top, self.W, list_bot - list_top)
        # 全行が同じ _scroll_x オフセットで描画される (= リスト全体が一斉に
        # 左右スクロールするので、行間で文字位置がズレない)。
        sx_off = self._scroll_x
        fz = _w._ui_font_size
        rh = _w._font_render_h(fz)
        ih = item_h()
        for fi, (gi, scene) in enumerate(filtered):
            iy = list_top + fi * ih - self._scroll_y
            if iy + ih < list_top or iy > list_bot:
                continue
            # ドラッグ中の元アイテムは薄く
            if self._drag_active and fi == self._drag_src:
                pyxel.rect(self.X + 2, iy, self.W - 4, ih, EDIT_PANEL)
                continue
            selected = (gi == self.state.selected_scene)
            hover = is_hover(mx, my, self.X + 2, iy, self.W - 4, ih)
            # 背景 + テキスト (横スクロール対応)
            if selected:
                pyxel.rect(self.X + 2, iy, self.W - 4, ih, EDIT_ACCENT)
                fg = EDIT_BG
                row_bg = EDIT_ACCENT
            elif hover:
                pyxel.rect(self.X + 2, iy, self.W - 4, ih, EDIT_BTN_HOVER)
                fg = EDIT_TEXT
                row_bg = EDIT_BTN_HOVER
            else:
                fg = EDIT_TEXT_DIM
                row_bg = EDIT_BG
            ty = iy + max(0, (ih - rh) // 2)
            draw_unicode(self.X + 4 - sx_off, ty,
                         display_name(scene), fg, size=fz, bg_col=row_bg)

        # ドラッグ中: 挿入位置マーカー + ゴースト
        if self._drag_active and self._drag_src >= 0 and filtered:
            drop_idx = self._drop_index(mx, my, filtered, list_top)
            if drop_idx is not None:
                marker_y = list_top + drop_idx * item_h() - self._scroll_y
                pyxel.rect(self.X + 2, marker_y - 1, self.W - 4, 2, EDIT_ACCENT)
            # ゴースト
            if 0 <= self._drag_src < len(filtered):
                ghost_name = display_name(filtered[self._drag_src][1])
                gy = my - item_h() // 2
                pyxel.rect(self.X + 4, gy, self.W - 8, item_h(), EDIT_ACCENT)
                draw_unicode(self.X + 6, gy + 2, ghost_name, EDIT_BG,
                             size=_w._ui_font_size, bg_col=EDIT_ACCENT)

        pyxel.clip()

        # 縦スクロールバー (ドラッグ可)
        vbar = self._vbar_rect()
        if vbar:
            bar_x = self.X + self.W - 6
            bar_y = list_top
            bar_h = list_bot - list_top
            pyxel.rect(bar_x, bar_y, 6, bar_h, EDIT_BORDER)
            tx, ty, tw, th = vbar
            color = EDIT_HIGHLIGHT if self._dragging_vbar else EDIT_ACCENT
            pyxel.rect(tx, ty, tw, th, color)
        # 横スクロールバー (ドラッグ可)
        hbar = self._hbar_rect()
        if hbar:
            bar_x = self.X
            bar_y = self._hbar_y()
            bar_w = self.W
            pyxel.rect(bar_x, bar_y, bar_w, self._HBAR_H, EDIT_BORDER)
            tx, ty, tw, th = hbar
            color = EDIT_HIGHLIGHT if self._dragging_hbar else EDIT_ACCENT
            pyxel.rect(tx, ty, tw, th, color)

        # +ADD / COPY / DEL ボタン
        _btn_h = max(16, _w._font_render_h(_w._ui_font_size) + 4)
        btn_y  = self.Y + self.H - _btn_h - 2
        third_w = (self.W - 16) // 3
        bx1 = self.X + 4
        bx2 = bx1 + third_w + 4
        bx3 = bx2 + third_w + 4
        draw_button(bx1, btn_y, third_w, "+ADD", h=_btn_h,
                    hover=is_hover(mx, my, bx1, btn_y, third_w, _btn_h))
        draw_button(bx2, btn_y, third_w, "COPY", h=_btn_h,
                    hover=is_hover(mx, my, bx2, btn_y, third_w, _btn_h))
        draw_button(bx3, btn_y, third_w, "DEL", h=_btn_h,
                    hover=is_hover(mx, my, bx3, btn_y, third_w, _btn_h))

        # ツールチップ（長い名前のホバー表示、clip外）
        if (self._hover_idx >= 0 and self._hover_idx < len(filtered)
                and not self._drag_active):
            name = display_name(filtered[self._hover_idx][1])
            if len(name) > max(2, (self.W - 8) // 4):
                tw = len(name) * 4 + 8
                tx = min(mx + 8, 720 - tw - 4)
                ty = my - 14
                pyxel.rect(tx - 1, ty - 1, tw + 2, 14, EDIT_BORDER)
                pyxel.rect(tx, ty, tw, 12, EDIT_PANEL)
                pyxel.text(tx + 2, ty + 2, name, EDIT_TEXT)


# ── MainViewPanel ────────────────────────────────────────────────

class MainViewPanel:
    """右上パネル: シーンのスナップショットプレビュー or FLOW チャート"""
    X, Y, W, H = MV_X, MV_Y, MV_W, MV_H

    # スナップショットは 720x480 のオフスクリーン pyxel.Image。プレビューには
    # アスペクト比を保ったまま縮小 blit。クリックで実物大に拡大トグル。
    _SCREEN_W = 720
    _SCREEN_H = 480

    def __init__(self, state):
        self.state = state
        self.flow_view = FlowView(state)
        self._props = None
        self._settings = None
        self._cache = None     # ImageCache (set by App)
        # スナップショット用 offscreen
        self._snapshot_img: "pyxel.Image | None" = None
        self._snapshot_key: tuple = ()
        self._snapshot_palette = None
        # 縮小表示時の領域 (W, H に 3:2 のスナップを収める)
        self._scale = min(self.W / self._SCREEN_W, self.H / self._SCREEN_H)
        self._draw_w = int(self._SCREEN_W * self._scale)
        self._draw_h = int(self._SCREEN_H * self._scale)
        self._draw_x = self.X + (self.W - self._draw_w) // 2
        self._draw_y = self.Y + (self.H - self._draw_h) // 2

    def set_props_panel(self, props):
        self._props = props

    def set_settings(self, settings: dict):
        self._settings = settings

    def set_cache(self, cache):
        self._cache = cache

    def update(self):
        if self.state.active_tab == 1:
            self.flow_view.update()
            return
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        # 拡大モード中: どこをクリックしても元に戻す。ESC でも戻す。
        if self.state.preview_expanded:
            if (pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT)
                    or pyxel.btnp(pyxel.KEY_ESCAPE)):
                self.state.preview_expanded = False
            return
        # 縮小プレビュー領域クリックで拡大モードへ
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            if is_hover(mx, my, self._draw_x, self._draw_y,
                        self._draw_w, self._draw_h):
                self.state.preview_expanded = True

    def draw(self):
        if self.state.active_tab == 1:
            self.flow_view.draw()
            return
        self._draw_preview()

    def _resolve_preview_palette(self, scene) -> list | None:
        """マスターパレット導入後はシーン別/play別の上書きを行わないため常に None。

        プレビューはエディタの pyxel.colors[] (= 起動時に load されたマスター
        パレット) をそのまま使う。
        """
        return None

    def _build_color_map(self, preview_pal) -> dict:
        """preview_pal の各インデックス → 現エディタ pyxel.colors[] で
        最も近い色のインデックス、にマップ。

        pyxel は pyxel.colors[] を 1 フレームに 1 つしか持てないため、
        プレビュー領域だけ別パレットで描くには「色を近似して既存パレットの
        該当インデックスへ差し替える」しかない。
        """
        mapping = {}
        for src_i, h in enumerate(preview_pal):
            try:
                target = int(str(h).lstrip("#"), 16)
            except (ValueError, AttributeError):
                mapping[src_i] = src_i
                continue
            tr = (target >> 16) & 0xFF
            tg = (target >> 8) & 0xFF
            tb = target & 0xFF
            best, best_d = src_i, 1 << 30
            for ei in range(16):
                c = pyxel.colors[ei]
                r = (c >> 16) & 0xFF
                g = (c >> 8) & 0xFF
                b = c & 0xFF
                d = (r - tr) ** 2 + (g - tg) ** 2 + (b - tb) ** 2
                if d < best_d:
                    best, best_d = ei, d
            mapping[src_i] = best
        return mapping

    def _draw_preview(self):
        # 外枠
        pyxel.rect(self.X, self.Y, self.W, self.H, EDIT_BG)
        pyxel.rectb(self.X, self.Y, self.W, self.H, EDIT_BORDER)

        scene = self.state.current_scene()
        if scene is None:
            draw_unicode(self.X + 8, self.Y + 8,
                         "No scene selected", EDIT_TEXT_DIM,
                         size=_w._ui_font_size)
            return

        # スナップショットを必要に応じて再描画
        self._ensure_snapshot(scene)
        if self._snapshot_img is None:
            return
        self._activate_snapshot_palette()

        # 拡大モード: 画面全体に等倍 blt
        if self.state.preview_expanded:
            pyxel.blt(0, 0, self._snapshot_img, 0, 0,
                      self._SCREEN_W, self._SCREEN_H)
            # 右下に閉じ方ヒント
            hint = "ESC / CLICK TO CLOSE"
            fz = 12
            hw = _w.text_px_w(hint, fz)
            hh = _w._font_render_h(fz)
            hx = self._SCREEN_W - hw - 12
            hy = self._SCREEN_H - hh - 10
            pyxel.rect(hx - 4, hy - 3, hw + 8, hh + 6, PLAY_DIALOG_BG)
            pyxel.rectb(hx - 4, hy - 3, hw + 8, hh + 6, PLAY_BORDER)
            draw_unicode(hx, hy, hint, PLAY_TEXT_DIM, size=fz)
            return

        # 縮小表示: アスペクト比保持、preview 領域中央
        # pyxel.blt の scale は中央基準なのでオフセット補正が必要
        dw, dh = self._draw_w, self._draw_h
        dx, dy = self._draw_x, self._draw_y
        if abs(self._scale - 1.0) < 0.001:
            pyxel.blt(dx, dy, self._snapshot_img, 0, 0,
                      self._SCREEN_W, self._SCREEN_H)
        else:
            # 中央基準スケーリング補正
            bx = dx + int(self._SCREEN_W * (self._scale - 1) / 2)
            by = dy + int(self._SCREEN_H * (self._scale - 1) / 2)
            pyxel.blt(bx, by, self._snapshot_img, 0, 0,
                      self._SCREEN_W, self._SCREEN_H,
                      scale=self._scale)
        # スナップ枠
        pyxel.rectb(dx, dy, dw, dh, EDIT_BORDER)
        # シーン名と倍率表示
        disp_name = display_name(scene)
        if disp_name:
            draw_unicode(self.X + 4, self.Y + 4, disp_name, EDIT_TEXT,
                         size=_w._ui_font_size)
        pct = int(self._scale * 100 + 0.5)
        draw_unicode(dx + 4, dy + dh - 14,
                     f"PREVIEW {pct}%  (click to expand)",
                     EDIT_TEXT_DIM, size=_w._ui_font_size)

    # ── スナップショットレンダリング ───────────────────────

    def _scene_snapshot_key(self, scene_idx: int) -> tuple:
        """シーン内容を一意に表すキー (キャッシュ不変条件)。"""
        import json
        scenes = self.state.scenes[:scene_idx + 1]
        # 継承解決に効くフィールドだけ抽出
        parts = []
        for s in scenes:
            parts.append((
                s.get("name", ""),
                s.get("bg", ""), bool(s.get("bg_hide", False)),
                bool(s.get("bg_fullscreen", False)),
                bool(s.get("bg_above_dialog", False)),
                json.dumps(s.get("bg_anim", {}), sort_keys=True),
                json.dumps(s.get("char_l", {}), sort_keys=True),
                json.dumps(s.get("char_c", {}), sort_keys=True),
                json.dumps(s.get("char_r", {}), sort_keys=True),
            ))
        # 現シーンのダイアログ関連
        cur = scenes[-1] if scenes else {}
        dialog_size = 16
        if isinstance(self._settings, dict):
            dialog_size = int(self._settings.get("dialog_font_size", 16) or 16)
            role_indices = self._settings.get("dialog_role_indices") or {}
            if isinstance(role_indices, dict):
                parts.append(tuple(sorted(
                    (str(k), int(v)) for k, v in role_indices.items()
                    if isinstance(v, int)
                )))
            speaker_colors = self._settings.get("speaker_colors") or {}
            if isinstance(speaker_colors, dict):
                import json as _json
                parts.append(_json.dumps(speaker_colors, sort_keys=True))
        text_size_override = _player_prefs.normalize_text_size(
            _player_prefs.load_text_size_override())
        parts.append((cur.get("speaker", ""), cur.get("text", ""),
                      bool(cur.get("hide_dialog", False)),
                      int(cur.get("font_size", 0) or 0), dialog_size,
                      text_size_override))
        return tuple(parts)

    def _effective_snapshot_text_size(self, scene) -> int:
        """Match VNPlayer's dialog text-size selection for snapshots."""
        override = _player_prefs.normalize_text_size(
            _player_prefs.load_text_size_override())
        if override is not None:
            return override
        fallback_size = 16
        if isinstance(self._settings, dict):
            fallback_size = int(self._settings.get("dialog_font_size", 16) or 16)
        return int(scene.get("font_size", 0) or fallback_size)

    @staticmethod
    def _coerce_color(v, default: int) -> int:
        if isinstance(v, int) and 0 <= v <= 255:
            return v
        return default

    def _resolve_snapshot_text_color(self, speaker: str) -> int:
        cfg = self._settings.get("speaker_colors") if isinstance(
            self._settings, dict) else {}
        cfg = cfg or {}
        if not speaker:
            return self._coerce_color(
                cfg.get("narration_text_color"), PLAY_TEXT)
        speakers = cfg.get("speakers", {}) or {}
        entry = speakers.get(speaker) or {}
        return self._coerce_color(entry.get("text_color"), PLAY_TEXT)

    def _resolve_snapshot_speaker_colors(self, speaker: str) -> tuple:
        cfg = self._settings.get("speaker_colors") if isinstance(
            self._settings, dict) else {}
        cfg = cfg or {}
        speakers = cfg.get("speakers", {}) or {}
        entry = speakers.get(speaker) or {}
        bg = self._coerce_color(entry.get("name_bg_color"), PLAY_SPEAKER_BG)
        fg = self._coerce_color(entry.get("name_color"), PLAY_SPEAKER_FG)
        return bg, fg

    def _ensure_snapshot(self, scene):
        """scene のスナップショットが最新でなければ再描画する。"""
        scenes = self.state.scenes
        try:
            scene_idx = scenes.index(scene)
        except ValueError:
            scene_idx = self.state.selected_scene
        key = self._scene_snapshot_key(scene_idx)
        if key == self._snapshot_key and self._snapshot_img is not None:
            return
        if self._snapshot_img is None:
            try:
                self._snapshot_img = pyxel.Image(
                    self._SCREEN_W, self._SCREEN_H)
            except Exception as e:
                print(f"[preview] Image alloc failed: {e}")
                return
        self._render_snapshot(scene_idx)
        self._snapshot_key = key

    def _resolve_persistent_for(self, scene_idx: int) -> tuple:
        """指定シーンに到達した時点の persistent_bg / persistent_chars を
        VNPlayer と同じロジックで返す。"""
        persistent_bg = None
        persistent_chars: dict = {}
        scenes = self.state.scenes[:scene_idx + 1]
        import copy as _copy
        for s in scenes:
            for cfg in persistent_chars.values():
                prepare_char_config_for_next_scene(cfg)
            # BG
            if s.get("bg_hide"):
                persistent_bg = None
            else:
                bp = s.get("bg", "") or ""
                if bp:
                        persistent_bg = {
                            "path":         bp,
                            "fullscreen":   bool(s.get("bg_fullscreen", False)),
                            "above_dialog": bool(s.get("bg_above_dialog", False)),
                            "anim":         s.get("bg_anim", {}) or {},
                        }
            # キャラ
            for key in ("char_l", "char_c", "char_r"):
                cfg = s.get(key, {})
                if not isinstance(cfg, dict):
                    cfg = {}
                if cfg.get("hide"):
                    persistent_chars[key] = None
                else:
                    f = cfg.get("file", "") or ""
                    if f:
                        persistent_chars[key] = _copy.deepcopy(cfg)
        return persistent_bg, persistent_chars

    @staticmethod
    def _snapshot_image_paths(persistent_bg, persistent_chars: dict) -> list:
        paths: list = []
        if persistent_bg:
            bp = persistent_bg.get("path", "")
            if bp:
                paths.append(bp)
            for fb in (persistent_bg.get("anim", {}) or {}).get(
                    "flipbook_files", []) or []:
                if fb:
                    paths.append(fb)
        for cfg in persistent_chars.values():
            if not cfg:
                continue
            f = cfg.get("file", "")
            if f:
                paths.append(f)
            for fb in (cfg.get("anim", {}) or {}).get(
                    "flipbook_files", []) or []:
                if fb:
                    paths.append(fb)
        return paths

    def _activate_snapshot_palette(self) -> None:
        if self._snapshot_palette is None:
            return
        try:
            _palette_mod.apply_to_pyxel_colors(self._snapshot_palette)
            _image_cache_mod.set_default_palette(self._snapshot_palette)
        except Exception:
            pass

    def _apply_snapshot_palette(self, paths: list) -> None:
        self._snapshot_palette = None
        if not self._cache:
            return
        try:
            reserved = _palette_mod.reserved_from_settings(
                self._settings if isinstance(self._settings, dict) else {})
            if not reserved:
                return
            pal = _palette_mod.build_scene_palette(
                paths, reserved, base_dir=self._cache.base_dir)
            self._snapshot_palette = pal
            self._activate_snapshot_palette()
        except Exception as e:
            print(f"[preview] palette failed: {e}")

    def _draw_snapshot_sprite(self, target, cfg: dict,
                              default_w: int = 0,
                              default_h: int = 0) -> bool:
        """Draw one sprite into the snapshot with VNPlayer/AnimSprite math."""
        if not cfg or not self._cache:
            return False
        file_path = cfg.get("file", "") or cfg.get("path", "") or ""
        if not file_path:
            return False

        load_w = int(cfg.get("w") or default_w or 0)
        load_h = int(cfg.get("h") or default_h or 0)
        load_w, load_h, source_scale = sprite_load_size_for_screen(
            self._cache, file_path, load_w, load_h,
            self._SCREEN_W, self._SCREEN_H)

        ck_setting = normalize_color_key(cfg.get("colkey", COLOR_KEY_AUTO))
        auto_ck = ck_setting == COLOR_KEY_AUTO

        anim = cfg.get("anim", {}) or {}
        flipbook = [file_path] + [
            f for f in (anim.get("flipbook_files", []) or []) if f
        ]
        interval = max(1, int(anim.get("flipbook_interval", 6) or 6))
        frame = 1  # VNPlayer updates sprites once before the first draw.
        fb_idx = (frame // interval) % len(flipbook)
        draw_path = flipbook[fb_idx]

        main_src = self._cache.get(file_path, load_w, load_h,
                                   alpha_colkey=auto_ck)
        if main_src is None:
            return False
        base_w, base_h = main_src.width, main_src.height
        if draw_path == file_path:
            src = main_src
        else:
            src = self._cache.get(draw_path, base_w, base_h,
                                  alpha_colkey=auto_ck)
            if src is None:
                return False
        iw, ih = src.width, src.height

        static_scale = float(cfg.get("scale", 1.0) or 1.0)
        scale_start = float(anim.get("scale_start", 1.0))
        scale_end = float(anim.get("scale_end", 1.0))
        scale_frames = int(anim.get("scale_frames", 0) or 0)
        if scale_frames > 0:
            t = min(1.0, frame / scale_frames)
            anim_scale = scale_start + (scale_end - scale_start) * t
        else:
            anim_scale = scale_end
        draw_scale = max(0.01, static_scale * anim_scale) * source_scale

        x = float(cfg.get("x", 0))
        y = float(cfg.get("y", 0))
        motion_frames = int(anim.get("motion_frames", 0) or 0)
        if motion_frames > 0:
            t = min(1.0, frame / motion_frames)
            x += int(anim.get("motion_x", 0) or 0) * t
            y += int(anim.get("motion_y", 0) or 0) * t

        tl_x, tl_y = sprite_top_left(
            x, y, ih, draw_scale, screen_h=self._SCREEN_H)

        bw = -iw if bool(cfg.get("flip_h", False)) else iw
        bh = -ih if bool(cfg.get("flip_v", False)) else ih
        if auto_ck:
            colkey = self._cache.get_auto_colkey(draw_path, iw, ih)
        else:
            colkey = ck_setting if ck_setting >= 0 else None

        rot = (float(anim.get("rot_speed", 0.0) or 0.0) * frame) % 360
        if rot == 0.0 and abs(draw_scale - 1.0) < 0.001:
            target.blt(tl_x, tl_y, src, 0, 0, bw, bh, colkey)
        else:
            target.blt(tl_x, tl_y, src, 0, 0, bw, bh, colkey,
                       rotate=rot, scale=draw_scale)

        border_w = int(cfg.get("border_w", 0) or 0)
        if border_w > 0:
            border_col = int(cfg.get("border_col", 7) or 7)
            rw = round(iw * draw_scale)
            rh = round(ih * draw_scale)
            for bwi in range(border_w):
                target.rectb(tl_x - bwi, tl_y - bwi,
                             rw + bwi * 2, rh + bwi * 2,
                             border_col)
        return True

    def _render_snapshot(self, scene_idx: int):
        """720x480 スナップショット画像を描画する。"""
        img = self._snapshot_img
        if img is None:
            return
        from engine.player import (DIALOG_X, DIALOG_Y, DIALOG_W, DIALOG_H,
                                   DIALOG_PAD_X, DIALOG_PAD_Y)
        scenes = self.state.scenes
        if not (0 <= scene_idx < len(scenes)):
            return
        scene = scenes[scene_idx]

        # 背景クリア
        img.rect(0, 0, self._SCREEN_W, self._SCREEN_H, PLAY_BG)

        persistent_bg, persistent_chars = self._resolve_persistent_for(scene_idx)
        hide_dialog = bool(scene.get("hide_dialog", False))
        self._apply_snapshot_palette(
            self._snapshot_image_paths(persistent_bg, persistent_chars))

        # ── BG 描画 ────────────────────────────────────────
        if persistent_bg and self._cache:
            bg_path = persistent_bg.get("path", "")
            if bg_path:
                iw, ih = self._cache.source_size(bg_path)
                if iw > 0 and ih > 0:
                    above_dialog = (persistent_bg.get("above_dialog")
                                    and not hide_dialog)
                    H_eff = DIALOG_Y if above_dialog else self._SCREEN_H
                    fit_scale = min(self._SCREEN_W / iw, H_eff / ih)
                    if persistent_bg.get("fullscreen") or above_dialog:
                        s = fit_scale
                    else:
                        s = min(1.0, fit_scale)
                    sw = max(1, round(iw * s))
                    sh = max(1, round(ih * s))
                    tl_x = (self._SCREEN_W - sw) // 2
                    tl_y = ((H_eff - sh) // 2 if above_dialog
                            else (self._SCREEN_H - sh) // 2)
                    ay = self._SCREEN_H - tl_y - sh
                    bg_cfg = {
                        "file":   bg_path,
                        "x":      tl_x,
                        "y":      ay,
                        "w":      sw,
                        "h":      sh,
                        "colkey": -1,
                        "anim":   persistent_bg.get("anim", {}) or {},
                    }
                    self._draw_snapshot_sprite(img, bg_cfg, sw, sh)

        # ── キャラクター描画 ────────────────────────────────
        for slot_key in ("char_l", "char_r", "char_c"):
            cfg = persistent_chars.get(slot_key)
            if not cfg:
                continue
            self._draw_snapshot_sprite(img, cfg)

        # ── ダイアログ ─────────────────────────────────────
        if not hide_dialog:
            self._render_dialog_to_image(img, scene,
                                         DIALOG_X, DIALOG_Y,
                                         DIALOG_W, DIALOG_H,
                                         DIALOG_PAD_X, DIALOG_PAD_Y)

    def _render_dialog_to_image(self, img, scene, bx, by, bw, bh,
                                pad_x, pad_y):
        """ダイアログボックス + 話者バッジ + テキストを image へ描画。"""
        # ダイアログ枠
        img.rect(bx, by, bw, bh, PLAY_DIALOG_BG)
        img.rectb(bx, by, bw, bh, PLAY_ACCENT)
        img.rectb(bx + 2, by + 2, bw - 4, bh - 4, PLAY_BORDER)
        # フォント (プレイ時と同じ player override / scene font_size / dialog_font_size)
        fz = self._effective_snapshot_text_size(scene)
        bdf, actual = _w._get_bdf(fz)
        rh = _w._font_render_h(fz)
        lh = rh + 4
        text_spacing = dialog_letter_spacing(fz)
        # 話者バッジ
        speaker = scene.get("speaker", "")
        if speaker and bdf:
            spk_bg, spk_fg = self._resolve_snapshot_speaker_colors(speaker)
            tw = _w.text_px_w(speaker, fz)
            badge_w = tw + 20
            badge_h = rh + 8
            badge_x = bx + 12
            badge_y = by - badge_h + 2
            img.rect(badge_x, badge_y, badge_w, badge_h, spk_bg)
            img.rectb(badge_x, badge_y, badge_w, badge_h, PLAY_BORDER)
            img.text(badge_x + 10, badge_y + (badge_h - rh) // 2, speaker,
                     spk_fg, bdf)
        # 本文 (\n 改行対応、超長文は枠内まで)
        text = scene.get("text", "")
        if text and bdf:
            text_col = self._resolve_snapshot_text_color(speaker)
            tx = bx + pad_x
            ty = by + pad_y
            max_y = by + bh - rh - 4
            for line in wrap_text(text, max(1, bw - pad_x * 2), fz,
                                  text_spacing):
                if ty > max_y:
                    break
                if line:
                    if text_spacing:
                        cx = tx
                        last_x = cx
                        for ch in line:
                            if _unicodedata.combining(ch):
                                img.text(last_x, ty, ch, text_col, bdf)
                            else:
                                last_x = cx
                                img.text(cx, ty, ch, text_col, bdf)
                                cx += _w.text_px_w(ch, fz) + text_spacing
                    else:
                        img.text(tx, ty, line, text_col, bdf)
                ty += lh

        # プレイヤーUIボタンもsnapshotへ含める。
        if bdf:
            buttons = ("SAVE", "AUTO", "SKIP", "LOG", "OPT")
            btn_w, btn_h, gap = 36, 14, 2
            total_w = len(buttons) * btn_w + (len(buttons) - 1) * gap
            px0 = bx + bw - total_w - 8
            py0 = by + 4
            for i, label in enumerate(buttons):
                x = px0 + i * (btn_w + gap)
                img.rect(x, py0, btn_w, btn_h, PLAY_CHOICE_BG)
                img.rectb(x, py0, btn_w, btn_h, PLAY_BORDER)
                tw = _w.text_px_w(label, 10)
                btn_font, btn_actual = _w._get_bdf(10)
                if btn_font:
                    img.text(x + (btn_w - tw) // 2,
                             py0 + (btn_h - btn_actual) // 2,
                             label, PLAY_TEXT, btn_font)

    def _c(self, cmap, idx):
        """プレビュー描画時に色インデックスを変換するヘルパー。"""
        if cmap is None:
            return idx
        return cmap.get(idx, idx)

    def _draw_preview_body(self, scene, cmap=None):

        # VN (720×480) を 50% スケール → 360×240 で中央表示
        pw = self.H * 3 // 2   # = 360
        ph = self.H             # = 240
        px = self.X + (self.W - pw) // 2  # 水平中央: (720-360)//2 = 180
        py = self.Y

        # プレビュー用色 (cmap 経由で play/scene パレットの近似インデックス)
        c_preview_bg = self._c(cmap, EDIT_PREVIEW_BG)
        c_dialog_bg  = self._c(cmap, PLAY_DIALOG_BG)
        c_border     = self._c(cmap, EDIT_BORDER)
        c_accent     = self._c(cmap, EDIT_ACCENT)
        c_text       = self._c(cmap, EDIT_TEXT)
        c_text_dim   = self._c(cmap, EDIT_TEXT_DIM)
        c_bg         = self._c(cmap, EDIT_BG)
        c_highlight  = self._c(cmap, EDIT_HIGHLIGHT)

        pyxel.rect(px, py, pw, ph, c_preview_bg)
        pyxel.rectb(px, py, pw, ph, c_border)

        bg = scene.get("bg", "")
        if scene.get("bg_hide"):
            bg_label = "(hide)"
        elif bg:
            bg_label = os.path.basename(bg)
        else:
            bg_label = "(inherit)"
        pyxel.text(px + 4, py + 3,
                   f"BACKGROUND:{bg_label}"[: (pw // 4)], c_text_dim)

        # キャラクタースロット (50% スケール: 20×40)
        cw, ch_char = 20, 40
        scale_x = pw / 720   # 0.5
        scale_y = ph / 480   # 0.5

        # CHARSタブで選択中のスロットを強調表示
        sel_slot = None
        if self._props and self._props.view == "chars":
            sel_slot = self._props.char_tab

        slot_keys = [("char_l", "l", "L"), ("char_c", "c", "C"), ("char_r", "r", "R")]
        for key, slot, lbl in slot_keys:
            cfg = scene.get(key, {})
            if not isinstance(cfg, dict):
                cfg = {}
            file_   = cfg.get("file", "")
            hide_   = bool(cfg.get("hide", False))
            char_ux = cfg.get("x", 0)
            char_uy = cfg.get("y", 0)
            cx = px + int(char_ux * scale_x)
            cy_s = py + ph - int(char_uy * scale_y) - ch_char
            cx   = max(px, min(px + pw - cw,     cx))
            cy_s = max(py, min(py + ph - ch_char, cy_s))

            is_sel = (slot == sel_slot)
            if hide_:
                # 明示的に非表示: 選択中なら枠だけ表示、それ以外は何も描かない
                if is_sel:
                    pyxel.rectb(cx - 1, cy_s - 1, cw + 2, ch_char + 2, c_text)
                    pyxel.rectb(cx, cy_s, cw, ch_char, c_text_dim)
                    pyxel.text(cx + cw // 2 - 4, cy_s + ch_char // 2 - 3,
                               "X", c_text_dim)
            elif file_:
                pyxel.rect(cx, cy_s, cw, ch_char, c_accent)
                if is_sel:
                    pyxel.rectb(cx - 1, cy_s - 1, cw + 2, ch_char + 2, c_text)
                pyxel.rectb(cx, cy_s, cw, ch_char, c_border)
                pyxel.text(cx + 1, cy_s + 2, os.path.basename(file_)[:4], c_bg)
            else:
                # INHERIT: スロット枠を破線風 (細枠) で薄く表示
                if is_sel:
                    pyxel.rect(cx, cy_s, cw, ch_char, c_highlight)
                    pyxel.rectb(cx - 1, cy_s - 1, cw + 2, ch_char + 2, c_text)
                pyxel.rectb(cx, cy_s, cw, ch_char,
                            c_accent if is_sel else c_text_dim)
                pyxel.text(cx + cw // 2 - 2, cy_s + ch_char // 2 - 3, lbl,
                           c_accent if is_sel else c_text_dim)

        # ダイアログボックス (PLAY_DIALOG_BG はプレイ専用色 — cmap で正しく解決される)
        # プレビュー外枠と密着しないよう左右下に 4px のマージンを取る
        d_margin = 4
        dh = ph // 3 - d_margin
        dy = py + ph - dh - d_margin
        dx = px + d_margin
        dw = pw - d_margin * 2
        pyxel.rect(dx, dy, dw, dh, c_dialog_bg)
        # 枠が背景色と被って見えなくなるのを防ぐため、テキスト色と
        # アクセント色が異なる場合は両方で二重枠を描く。
        if c_text != c_accent:
            pyxel.rectb(dx, dy, dw, dh, c_text)
            pyxel.rectb(dx + 1, dy + 1, dw - 2, dh - 2, c_accent)
        else:
            pyxel.rectb(dx, dy, dw, dh, c_accent)

        _psz = 10
        _prh = _w._font_render_h(_psz)
        speaker = scene.get("speaker", "")
        if speaker:
            sw = min(dw - 20, _w.text_px_w(speaker, _psz) + 8)
            pyxel.rect(dx + 4, dy - _prh - 2, sw, _prh + 2, c_accent)
            draw_unicode(dx + 6, dy - _prh - 1, speaker, c_bg, size=_psz)

        text = scene.get("text", "")
        lh  = _prh + 2
        ty  = dy + 4
        for line in wrap_text(text, max(1, dw - 16), _psz):
            if ty + _prh > dy + dh - 2:
                break
            if line:
                draw_unicode(dx + 6, ty, line, c_text, size=_psz)
            ty  += lh

        # 左マージン (プレビュー枠外なのでエディタパレットを使用)
        disp_name = display_name(scene)
        if disp_name and px > 8:
            # シーン名: TTF (大きめ) / PREVIEW 50%: デフォルトフォント scale=1 (小さめ)
            draw_unicode(self.X + 4, py + 4, disp_name, EDIT_TEXT)
            sn_h = _w._editor_render_h()
            draw_ui_text(self.X + 4, py + 4 + sn_h + 2,
                         "PREVIEW 50%", EDIT_TEXT_DIM, scale=1)


# ── PropertiesPanel ──────────────────────────────────────────────

class PropertiesPanel:
    """右パネル: SCENE / CHARS / CHOICES タブ切り替え (スクロール対応)"""
    X, Y, W, H = PP_X, PP_Y, PP_W, PP_H

    _CHOICE_MAX    = 8
    # SCENE タブでスライダー行のインデックス。これらの行の下にもう1行分の余白を入れる。
    # 履歴: マスターパレット導入で旧 SCENE PALETTE 行(-2)、BACKGROUND SCALING/
    #       水平軸/垂直軸 (-3) を撤去後、画像継承 (HIDE BACKGROUND) 行を新設 (+1)、
    #       さらに BG SAFE AREA 行を新設 (+1)。BDF統一で FONT 行を削除 (-1)。
    _SCENE_SLIDER_ROWS = frozenset({2, 11, 12, 14, 15})
    _SCENE_TOTAL_ROWS  = 19
    _SCENE_SECTION_BEFORE = (
        (0, "TEXT"),
        (3, "BACKGROUND"),
        (8, "AUDIO"),
        (16, "FLOW"),
    )

    @classmethod
    def _scene_section_h(cls) -> int:
        return _w._font_render_h(10) + 6

    @classmethod
    def _scene_sections_before(cls, idx: int) -> int:
        return sum(1 for row, _label in cls._SCENE_SECTION_BEFORE if row <= idx)

    @classmethod
    def _scene_extra_below(cls, idx: int) -> int:
        """idx 行より上にあるスライダー行の数（= idx までに追加された下余白の段数）"""
        return sum(1 for r in cls._SCENE_SLIDER_ROWS if r < idx)

    def __init__(self, state):
        self.state         = state
        self.view          = "scene"   # "scene" | "chars" | "choices"
        self.char_tab      = "l"       # "l" | "c" | "r"
        self.choice_sel    = -1
        self._dialog_field = None      # ダイアログが開いているフィールドの識別子
        self._scroll_y     = 0         # スクロールオフセット
        self._sliders: dict = {}       # NumericSlider インスタンスのキャッシュ

    # ── 内部ヘルパー ─────────────────────────────────────────

    def _content_height(self) -> int:
        """現在のタブのコンテンツ全高さ"""
        rh  = self._scene_row_h()
        gap = 2
        sh  = slider_h()
        if self.view == "scene":
            # 通常行: rh+gap, スライダー行はその後に sh+gap の余白を追加
            extras = len(self._SCENE_SLIDER_ROWS)
            return (self._SCENE_TOTAL_ROWS * (rh + gap)
                    + extras * (sh + gap)
                    + len(self._SCENE_SECTION_BEFORE) * self._scene_section_h()
                    + 4)
        elif self.view == "chars":
            # L/C/Rサブタブは固定表示なのでここには含めない
            # FILE(field_h) + HIDE CHAR(20) + POS MEM(36)
            #   + 4スライダー(各 2*sh) + flip(22)
            #   + ANIM ヘッダ(anim_fh) + anim options(60) + 10スライダー(各 2*sh)
            # ※ 4スライダー = CHARACTER SCALING + horizontal/vertical axis position + COLOR KEY
            return (field_h() + 20 + 36 + 4 * 2 * sh + 22
                    + anim_fh() + 60 + 10 * 2 * sh + 4)
        else:
            return 24 + self._CHOICE_MAX * (_w._font_render_h(_w._ui_font_size) + 4) + 4 + 2 * (rh + gap)

    def _visible_h(self) -> int:
        if self.view == "chars":
            # L/C/Rサブタブ固定分を追加で引く
            return self.H - tab_h() - tab_h() - 4
        return self.H - tab_h() - 4

    def _cap_scroll(self):
        max_s = max(0, self._content_height() - self._visible_h())
        self._scroll_y = max(0, min(max_s, self._scroll_y))

    def _get_slider(self, slot_key: str, field: str) -> NumericSlider:
        """スロット+フィールドのスライダーを取得（なければ作成）。"""
        k = f"{slot_key}.{field}"
        if k not in self._sliders:
            spec = _SLIDER_SPECS.get(field, (0, 100, 1, False))
            self._sliders[k] = NumericSlider(*spec)
        return self._sliders[k]

    def _open_numeric_dialog(self, label: str, container: dict,
                              container_key: str, spec_key: str, default):
        """右クリックで数値を手動入力するダイアログを開く。"""
        if _text_dialog.running:
            return
        spec = _SLIDER_SPECS.get(spec_key, (0, 100, 1, False))
        is_float = spec[3]
        fid = ("numeric", id(container), container_key)
        self._dialog_field = fid
        def _cb(val, k=container_key, f=fid, c=container, is_f=is_float):
            try:
                v = float(val) if is_f else int(float(val))
                c[k] = v
                self.state.dirty = True
            except ValueError:
                pass
            if self._dialog_field == f:
                self._dialog_field = None
        _text_dialog.open(label, str(container.get(container_key, default)), _cb)

    # ── 公開 ─────────────────────────────────────────────────

    def update(self):
        _text_dialog.poll()

        # ファイル/シーン/エンディングピッカーがアクティブな場合はそちらを優先
        if _file_picker.active:
            _file_picker.update()
            return
        if _scene_picker.active:
            _scene_picker.update()
            return
        if _ending_picker.active:
            _ending_picker.update()
            return

        mx, my = pyxel.mouse_x, pyxel.mouse_y

        # スクロール (コンテンツエリア上でのみ)
        scroll_top = self.Y + tab_h() + (tab_h() if self.view == "chars" else 0)
        if is_hover(mx, my, self.X, scroll_top, self.W, self.H - (scroll_top - self.Y)):
            wheel = pyxel.mouse_wheel
            if wheel:
                self._scroll_y -= wheel * 20
                self._cap_scroll()

        # タブ切り替え（ダイアログが開いていない時のみ）
        if not _text_dialog.running:
            tab_w = self.W // 3
            for i, name in enumerate(("scene", "chars", "choices")):
                if is_clicked(mx, my, self.X + i * tab_w, self.Y, tab_w, tab_h()):
                    if self.view != name:
                        self.view = name
                        self._scroll_y = 0
                        self._dialog_field = None
        scene = self.state.current_scene()
        if scene is None:
            return
        if not _text_dialog.running:
            if self.view == "scene":
                self._update_scene(mx, my, scene)
            elif self.view == "chars":
                self._update_chars(mx, my, scene)
            else:
                self._update_choices(mx, my, scene)

    def draw(self):
        draw_panel(self.X, self.Y, self.W, self.H)
        tab_w = self.W // 3
        tabs  = [("SCENE", "scene"), ("CHARACTERS", "chars"), ("CHOICES", "choices")]
        for i, (label, name) in enumerate(tabs):
            draw_button(self.X + i * tab_w, self.Y, tab_w, label,
                        h=tab_h(), active=(self.view == name))

        # CHARS タブ: L/C/R サブタブをスクロール外に固定表示 (テキスト幅に合わせて左詰め)
        if self.view == "chars":
            stab_y = self.Y + tab_h()
            stab_x = self.X + 6
            stab_gap = 8
            mx, my = pyxel.mouse_x, pyxel.mouse_y
            for (t, lbl) in (("l", "LEFT"), ("c", "CENTER"), ("r", "RIGHT")):
                w = button_w(lbl)
                draw_button(stab_x, stab_y, w, lbl, h=tab_h(),
                            active=(self.char_tab == t),
                            hover=is_hover(mx, my, stab_x, stab_y, w, tab_h()))
                stab_x += w + stab_gap
            clip_y = self.Y + tab_h() + tab_h()
            clip_h = self.H - tab_h() - tab_h()
        else:
            clip_y = self.Y + tab_h()
            clip_h = self.H - tab_h()

        # コンテンツエリアをクリップしてスクロール描画
        pyxel.clip(self.X, clip_y, self.W, clip_h)

        scene = self.state.current_scene()
        cy = clip_y + 4 - self._scroll_y
        if scene is None:
            draw_ui_text(self.X + 4, cy, "No scene", EDIT_TEXT_DIM)
        elif self.view == "scene":
            self._draw_scene(scene, cy)
        elif self.view == "chars":
            self._draw_chars(scene, cy)
        else:
            self._draw_choices(scene, cy)

        pyxel.clip()
        self._draw_scrollbar()

    def _draw_scrollbar(self):
        vis_h  = self._visible_h()
        cont_h = self._content_height()
        if cont_h <= vis_h:
            return
        if self.view == "chars":
            bar_start = self.Y + tab_h() + tab_h() + 2
            bar_area  = self.H - tab_h() - tab_h() - 4
        else:
            bar_start = self.Y + tab_h() + 2
            bar_area  = self.H - tab_h() - 4
        bar_h = max(16, bar_area * vis_h // cont_h)
        bar_y = (bar_start +
                 (bar_area - bar_h) * self._scroll_y // max(1, cont_h - vis_h))
        sx = self.X + self.W - 5
        pyxel.rect(sx, bar_start, 3, bar_area, EDIT_BORDER)
        pyxel.rect(sx, bar_y, 3, bar_h, EDIT_ACCENT)

    # ── SCENE タブ ───────────────────────────────────────────

    def _scene_row_h(self) -> int:
        """SCENE タブの 1 行の高さ（ボタン/スライダー共通）"""
        return max(20, _w._font_render_h(_w._ui_font_size) + 4)

    def _compact_btn_w(self, label: str) -> int:
        """コンパクトチェックボックス用の幅（ラベル + 余白）"""
        return max(40, _w.text_px_w(label, _w._ui_font_size) + 14)

    def _char_pos_memory(self) -> dict:
        mem = normalize_character_position_memory(
            getattr(self.state, "character_position_memory", {}))
        self.state.character_position_memory = mem
        return mem

    def _store_char_pos(self, slot: str, cfg: dict) -> None:
        mem = self._char_pos_memory()
        mem[slot] = {
            "x": int(cfg.get("x", 0) or 0),
            "y": int(cfg.get("y", 0) or 0),
            "scale": float(cfg.get("scale", 1.0) or 1.0),
        }
        self.state.character_position_memory = mem
        self.state.dirty = True

    def _apply_char_pos(self, slot: str, cfg: dict) -> bool:
        pos = self._char_pos_memory().get(slot)
        if not isinstance(pos, dict):
            return False
        cfg["x"] = int(pos.get("x", 0))
        cfg["y"] = int(pos.get("y", 0))
        cfg["scale"] = float(pos.get("scale", 1.0))
        self.state.dirty = True
        return True

    def _char_pos_memory_label(self, slot: str) -> str:
        pos = self._char_pos_memory().get(slot)
        if not isinstance(pos, dict):
            return "POS MEM: none"
        return (f"POS MEM: x={int(pos.get('x', 0))} "
                f"y={int(pos.get('y', 0))} "
                f"s={float(pos.get('scale', 1.0)):.2f}")

    def _bdf_size_index(self, size: int) -> int:
        """BDFサイズをスライダー用インデックスへ変換する。0 は既定値扱い。"""
        try:
            n = int(size)
        except Exception:
            n = 0
        if n <= 0:
            n = 16
        nearest = min(_BDF_SIZE_OPTIONS, key=lambda v: abs(v - n))
        return _BDF_SIZE_OPTIONS.index(nearest)

    def _bdf_size_from_index(self, idx: int) -> int:
        idx = max(0, min(len(_BDF_SIZE_OPTIONS) - 1, int(idx)))
        return _BDF_SIZE_OPTIONS[idx]

    def _btn_val_label(self, prefix: str, value: str, max_chars: int = 96) -> str:
        """[PREFIX]:value 形式のボタンラベルを生成"""
        if not value:
            return f"[{prefix}]"
        # パスの場合はベース名のみ
        shown = os.path.basename(value) if ("/" in value or "\\" in value) else value
        if len(shown) > max_chars:
            shown = shown[:max_chars - 1] + "…"
        return f"[{prefix}]:{shown}"

    def _img_field_label(self, prefix: str, value: str, hide: bool,
                         max_chars: int = 80) -> str:
        """画像フィールド (BG / キャラ FILE) 用ラベル。

        トライステート (HIDE / SET / INHERIT) を可視化する:
          - hide=True            → [PREFIX]:(hide)    明示クリア
          - value あり           → [PREFIX]:filename  SET
          - 上記以外             → [PREFIX]:(inherit) 前シーンから継承
        """
        if hide:
            return f"[{prefix}]:(hide)"
        if not value:
            return f"[{prefix}]:(inherit)"
        shown = os.path.basename(value) if ("/" in value or "\\" in value) else value
        if len(shown) > max_chars:
            shown = shown[:max_chars - 1] + "…"
        return f"[{prefix}]:{shown}"

    def _audio_field_label(self, prefix: str, value: str, stop: bool,
                           max_chars: int = 80) -> str:
        """BGM用ラベル。BGM は SET / INHERIT / STOP の3状態を持つ。"""
        if stop:
            return f"[{prefix}]:(stop)"
        if not value:
            return f"[{prefix}]:(inherit)"
        shown = os.path.basename(value) if ("/" in value or "\\" in value) else value
        if len(shown) > max_chars:
            shown = shown[:max_chars - 1] + "…"
        return f"[{prefix}]:{shown}"

    def _scene_goto_display(self, goto_name: str) -> str:
        """goto 値 (scene name) から表示名を返す"""
        if not goto_name:
            return ""
        for s in self.state.scenes:
            if s.get("name") == goto_name:
                return display_name(s)
        return goto_name

    def _update_scene(self, mx, my, scene):
        cy0  = self.Y + tab_h() + 4
        ctop = self.Y + tab_h()
        cbot = self.Y + self.H
        # スクロールでタブの下に潜り込んだ UI に対するクリックを無効化。
        # （SCENE/CHARS/CHOICES タブ自体は呼び出し元で処理済み）
        if my < ctop:
            return
        s    = self._scroll_y
        rh   = self._scene_row_h()
        gap  = 2
        lh   = label_h()
        sh   = slider_h()      # 全スライダー共通の描画高さ
        extra_unit = sh + gap  # スライダー行の下に「もう1スライダー分」の余白

        sl_w = self.W - 6 - _reset_w() - 2
        rb_x = self.X + 2 + sl_w + 2
        right_clicked = pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT) and not _text_dialog.running
        is_fs = bool(scene.get("bg_fullscreen", False))

        def row_y(idx: int) -> int:
            extra = self._scene_extra_below(idx) * extra_unit
            sections = self._scene_sections_before(idx) * self._scene_section_h()
            return cy0 + idx * (rh + gap) + extra + sections - s

        def in_view(y: int, h: int) -> bool:
            return not (y + h <= ctop or y >= cbot)

        # 行 0: [SPEAKER]
        y0 = row_y(0)
        if in_view(y0, rh) and is_clicked(mx, my, self.X + 2, y0, self.W - 4, rh):
            fid = ("scene", "speaker")
            self._dialog_field = fid
            def _cb_sp(val, f=fid):
                scene["speaker"] = val
                self.state.dirty = True
                if self._dialog_field == f:
                    self._dialog_field = None
            _text_dialog.open("SPEAKER", str(scene.get("speaker", "")), _cb_sp)

        # 行 1: [EDIT_TEXT]
        y1 = row_y(1)
        if in_view(y1, rh) and is_clicked(mx, my, self.X + 2, y1, self.W - 4, rh):
            fid = ("scene", "text")
            self._dialog_field = fid
            def _cb_tx(val, f=fid):
                scene["text"] = val
                self.state.dirty = True
                if self._dialog_field == f:
                    self._dialog_field = None
            _text_dialog.open("EDIT_TEXT", str(scene.get("text", "")), _cb_tx, multiline=True)

        # 行 2: TEXT SIZE スライダー
        y2 = row_y(2)
        sl_fs = self._get_slider("scene", "font_size")
        cur_fs_idx = self._bdf_size_index(scene.get("font_size", 0))
        nv_fs = sl_fs.handle(self.X + 2, y2, sl_w, sh,
                             mx, my, cur_fs_idx)
        if nv_fs is not None:
            scene["font_size"] = self._bdf_size_from_index(nv_fs)
            self.state.dirty = True
        if is_clicked(mx, my, rb_x, y2 + lh, _reset_w(), sh - lh):
            scene["font_size"] = 0
            self.state.dirty = True

        # 行 3: [BACKGROUND IMAGE]:filename
        # 左クリック: ファイルピッカーを開く
        # 右クリック: 値をクリア (= INHERIT 状態に戻す)。誤選択のリカバリ用。
        y3 = row_y(3)
        if in_view(y3, rh):
            if is_clicked(mx, my, self.X + 2, y3, self.W - 4, rh):
                fid = ("scene", "bg")
                self._dialog_field = fid
                def _cb_bg(val, f=fid):
                    scene["bg"] = "./assets/images/bg/" + val
                    self.state.dirty = True
                    if self._dialog_field == f:
                        self._dialog_field = None
                _file_picker.open("BACKGROUND IMAGE", "./assets/images/bg/",
                                  mode="image", callback=_cb_bg,
                                  initial_path=str(scene.get("bg", "") or ""))
            elif right_clicked and is_hover(mx, my, self.X + 2, y3,
                                            self.W - 4, rh):
                if scene.get("bg", ""):
                    scene["bg"] = ""
                    self.state.dirty = True

        # 行 4: コンパクト BACKGROUND FULLSCREEN チェックボックス
        y4 = row_y(4)
        cb_lbl5 = ("[X] BACKGROUND FULLSCREEN" if is_fs
                   else "[ ] BACKGROUND FULLSCREEN")
        cb_w5 = self._compact_btn_w(cb_lbl5)
        if in_view(y4, rh) and is_clicked(mx, my, self.X + 2, y4, cb_w5, rh):
            scene["bg_fullscreen"] = not is_fs
            self.state.dirty = True

        # 行 5: コンパクト BG SAFE AREA チェックボックス
        # 立てると BG をダイアログ上の領域 (720x324) に収めて拡縮する。横に
        # 黒帯が出る代わりに画像下部 (キャラの足元等) がダイアログで隠れない。
        # hide_dialog=True のシーンでは無視され通常スケーリングに戻る。
        y5 = row_y(5)
        bad_on = bool(scene.get("bg_above_dialog", False))
        bad_lbl = "[X] BG SAFE AREA" if bad_on else "[ ] BG SAFE AREA"
        bad_w = self._compact_btn_w(bad_lbl)
        if in_view(y5, rh) and is_clicked(mx, my, self.X + 2, y5, bad_w, rh):
            scene["bg_above_dialog"] = not bad_on
            self.state.dirty = True

        # 行 6: コンパクト HIDE BACKGROUND チェックボックス
        # 立てると bg / bg_fullscreen の値に関わらず BG が表示されない (前シーン
        # からの継承を断つ明示クリア)。立てない場合 bg="" は INHERIT を意味する。
        y6 = row_y(6)
        bh_on = bool(scene.get("bg_hide", False))
        bh_lbl = "[X] HIDE BACKGROUND" if bh_on else "[ ] HIDE BACKGROUND"
        bh_w = self._compact_btn_w(bh_lbl)
        if in_view(y6, rh) and is_clicked(mx, my, self.X + 2, y6, bh_w, rh):
            scene["bg_hide"] = not bh_on
            self.state.dirty = True

        # 行 7: コンパクト HIDE DIALOG チェックボックス
        y7 = row_y(7)
        hd_on = bool(scene.get("hide_dialog", False))
        hd_lbl = "[X] HIDE DIALOG" if hd_on else "[ ] HIDE DIALOG"
        hd_w = self._compact_btn_w(hd_lbl)
        if in_view(y7, rh) and is_clicked(mx, my, self.X + 2, y7, hd_w, rh):
            scene["hide_dialog"] = not hd_on
            self.state.dirty = True

        # 行 8: コンパクト TRANSITION チェックボックス (OFF="", ON="fade")
        y8 = row_y(8)
        tr_on = (scene.get("transition", "") == "fade")
        tr_lbl = "[X] TRANSITION (fade)" if tr_on else "[ ] TRANSITION"
        tr_w = self._compact_btn_w(tr_lbl)
        if in_view(y8, rh) and is_clicked(mx, my, self.X + 2, y8, tr_w, rh):
            scene["transition"] = "" if tr_on else "fade"
            self.state.dirty = True

        # 行 9: [BACKGROUND MUSIC FILE]:filename
        y9 = row_y(9)
        if in_view(y9, rh) and is_clicked(mx, my, self.X + 2, y9, self.W - 4, rh):
            fid = ("scene", "bgm_file")
            self._dialog_field = fid
            def _cb_bgm(val, f=fid):
                scene["bgm_file"] = "./assets/sounds/bgm/" + val
                scene["bgm_stop"] = False
                self.state.dirty = True
                if self._dialog_field == f:
                    self._dialog_field = None
            _file_picker.open("BACKGROUND MUSIC FILE",
                              "./assets/sounds/bgm/",
                              mode="audio", callback=_cb_bgm,
                              initial_path=str(scene.get("bgm_file", "") or ""))
        elif (in_view(y9, rh) and right_clicked
              and is_hover(mx, my, self.X + 2, y9, self.W - 4, rh)):
            if scene.get("bgm_file", ""):
                scene["bgm_file"] = ""
                self.state.dirty = True

        # 行 10: コンパクト STOP BGM チェックボックス
        y10 = row_y(10)
        bs_on = bool(scene.get("bgm_stop", False))
        bs_lbl = "[X] STOP BGM" if bs_on else "[ ] STOP BGM"
        bs_w = self._compact_btn_w(bs_lbl)
        if in_view(y10, rh) and is_clicked(mx, my, self.X + 2, y10, bs_w, rh):
            scene["bgm_stop"] = not bs_on
            self.state.dirty = True

        once_on = not bool(scene.get("bgm_loop", True))
        once_lbl = "[X] PLAY BGM ONCE" if once_on else "[ ] PLAY BGM ONCE"
        once_x = self.X + 2 + bs_w + 8
        once_w = self._compact_btn_w(once_lbl)
        if (in_view(y10, rh)
                and is_clicked(mx, my, once_x, y10, once_w, rh)):
            scene["bgm_loop"] = once_on
            self.state.dirty = True

        # 行 11: BACKGROUND MUSIC VOLUME スライダー
        y11 = row_y(11)
        sl_bv = self._get_slider("scene", "bgm_volume")
        nv_bv = sl_bv.handle(self.X + 2, y11, sl_w, sh,
                             mx, my, scene.get("bgm_volume", 7))
        if nv_bv is not None:
            scene["bgm_volume"] = nv_bv
            self.state.dirty = True
        if right_clicked and is_hover(mx, my, self.X + 2, y11, sl_w, sh):
            self._open_numeric_dialog("BACKGROUND MUSIC VOLUME",
                                      scene, "bgm_volume", "bgm_volume", 7)
        if is_clicked(mx, my, rb_x, y11 + lh, _reset_w(), sh - lh):
            scene["bgm_volume"] = 7
            self.state.dirty = True

        # 行 12: BGM FADE OUT FRAMES スライダー
        y12 = row_y(12)
        sl_bf = self._get_slider("scene", "bgm_fadeout_frames")
        nv_bf = sl_bf.handle(self.X + 2, y12, sl_w, sh,
                             mx, my, scene.get("bgm_fadeout_frames", 0))
        if nv_bf is not None:
            scene["bgm_fadeout_frames"] = nv_bf
            self.state.dirty = True
        if right_clicked and is_hover(mx, my, self.X + 2, y12, sl_w, sh):
            self._open_numeric_dialog("BGM FADE OUT FRAMES",
                                      scene, "bgm_fadeout_frames",
                                      "bgm_fadeout_frames", 0)
        if is_clicked(mx, my, rb_x, y12 + lh, _reset_w(), sh - lh):
            scene["bgm_fadeout_frames"] = 0
            self.state.dirty = True

        # 行 13: [SOUND EFFECT FILE]:filename
        y13 = row_y(13)
        if in_view(y13, rh) and is_clicked(mx, my, self.X + 2, y13, self.W - 4, rh):
            fid = ("scene", "se_file")
            self._dialog_field = fid
            def _cb_se(val, f=fid):
                scene["se_file"] = "./assets/sounds/se/" + val
                self.state.dirty = True
                if self._dialog_field == f:
                    self._dialog_field = None
            _file_picker.open("SOUND EFFECT FILE",
                              "./assets/sounds/se/",
                              mode="audio", callback=_cb_se,
                              initial_path=str(scene.get("se_file", "") or ""))
        elif (in_view(y13, rh) and right_clicked
              and is_hover(mx, my, self.X + 2, y13, self.W - 4, rh)):
            if scene.get("se_file", ""):
                scene["se_file"] = ""
                self.state.dirty = True

        # 行 14: SOUND EFFECT VOLUME スライダー
        y14 = row_y(14)
        sl_sv = self._get_slider("scene", "se_volume")
        nv_sv = sl_sv.handle(self.X + 2, y14, sl_w, sh,
                             mx, my, scene.get("se_volume", 7))
        if nv_sv is not None:
            scene["se_volume"] = nv_sv
            self.state.dirty = True
        if right_clicked and is_hover(mx, my, self.X + 2, y14, sl_w, sh):
            self._open_numeric_dialog("SOUND EFFECT VOLUME",
                                      scene, "se_volume", "se_volume", 7)
        if is_clicked(mx, my, rb_x, y14 + lh, _reset_w(), sh - lh):
            scene["se_volume"] = 7
            self.state.dirty = True

        # 行 15: SOUND EFFECT REPEAT スライダー
        y15 = row_y(15)
        sl_sr = self._get_slider("scene", "se_repeat")
        nv_sr = sl_sr.handle(self.X + 2, y15, sl_w, sh,
                             mx, my, scene.get("se_repeat", 0))
        if nv_sr is not None:
            scene["se_repeat"] = nv_sr
            self.state.dirty = True
        if right_clicked and is_hover(mx, my, self.X + 2, y15, sl_w, sh):
            self._open_numeric_dialog("SOUND EFFECT REPEAT",
                                      scene, "se_repeat", "se_repeat", 0)
        if is_clicked(mx, my, rb_x, y15 + lh, _reset_w(), sh - lh):
            scene["se_repeat"] = 0
            self.state.dirty = True

        # 行 16: [GOTO]:scene-name (scene picker)
        y16 = row_y(16)
        if in_view(y16, rh) and is_clicked(mx, my, self.X + 2, y16, self.W - 4, rh):
            def _cb_goto(val):
                scene["goto"] = val
                self.state.dirty = True
            _scene_picker.open("GOTO SCENE", self.state,
                               scene.get("goto", ""), _cb_goto)

        # 行 17: [GOTO ENDING]:name (ending picker)
        y17 = row_y(17)
        if in_view(y17, rh) and is_clicked(mx, my, self.X + 2, y17, self.W - 4, rh):
            items = [("(none)", "")]
            for e in (self.state.endings or []):
                nm = e.get("name", "")
                if nm:
                    items.append((nm, nm))
            def _cb_end(val):
                scene["goto_ending"] = val
                self.state.dirty = True
            _ending_picker.open("GOTO ENDING", items,
                                scene.get("goto_ending", ""), _cb_end)

        # 行 18: コンパクト PAUSE AUTO チェックボックス
        y18 = row_y(18)
        ap_on = bool(scene.get("auto_pause", False))
        ap_lbl = "[X] PAUSE AUTO" if ap_on else "[ ] PAUSE AUTO"
        ap_w = self._compact_btn_w(ap_lbl)
        if in_view(y18, rh) and is_clicked(mx, my, self.X + 2, y18, ap_w, rh):
            scene["auto_pause"] = not ap_on
            self.state.dirty = True

    def _draw_scene(self, scene, cy):
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        rh  = self._scene_row_h()
        gap = 2
        lh  = label_h()
        sh  = slider_h()       # 全スライダー共通の描画高さ (ノブ揃え)
        extra_unit = sh + gap  # スライダー行の下に「もう1スライダー分」の余白
        sl_w = self.W - 6 - _reset_w() - 2
        rb_x = self.X + 2 + sl_w + 2
        is_fs = bool(scene.get("bg_fullscreen", False))

        def row_y(idx: int) -> int:
            extra = self._scene_extra_below(idx) * extra_unit
            sections = self._scene_sections_before(idx) * self._scene_section_h()
            return cy + idx * (rh + gap) + extra + sections

        def _draw_section(before_idx: int, label: str):
            sy = row_y(before_idx) - self._scene_section_h()
            pyxel.line(self.X + 2, sy + 2, self.X + self.W - 8, sy + 2,
                       EDIT_BORDER)
            draw_unicode(self.X + 4, sy + 5, label, EDIT_ACCENT, size=10)

        def _draw_reset(y: int):
            rb_y = y + lh
            rb_h = sh - lh
            draw_reset_btn(rb_x, rb_y, rb_h,
                           hover=is_hover(mx, my, rb_x, rb_y, _reset_w(), rb_h))

        for _idx, _label in self._SCENE_SECTION_BEFORE:
            _draw_section(_idx, _label)

        # 行 0: [SPEAKER]
        y0 = row_y(0)
        draw_button(self.X + 2, y0, self.W - 4, "[SPEAKER]", h=rh,
                    hover=is_hover(mx, my, self.X + 2, y0, self.W - 4, rh))

        # 行 1: [EDIT_TEXT]
        y1 = row_y(1)
        draw_button(self.X + 2, y1, self.W - 4, "[EDIT_TEXT]", h=rh,
                    hover=is_hover(mx, my, self.X + 2, y1, self.W - 4, rh))

        # 行 2: TEXT SIZE スライダー
        y2 = row_y(2)
        sl_fs = self._get_slider("scene", "font_size")
        cur_fs = int(scene.get("font_size", 0) or 0)
        cur_fs_idx = self._bdf_size_index(cur_fs)
        cur_fs_text = str(self._bdf_size_from_index(cur_fs_idx))
        sl_fs.draw(self.X + 2, y2, sl_w, sh,
                   "TEXT SIZE", cur_fs_idx,
                   label_h=lh, value_text=cur_fs_text)
        _draw_reset(y2)

        # 行 3: [BACKGROUND IMAGE]:filename / (inherit) / (hide)
        y3 = row_y(3)
        bh_on = bool(scene.get("bg_hide", False))
        draw_button(self.X + 2, y3, self.W - 4,
                    self._img_field_label("BACKGROUND IMAGE",
                                          scene.get("bg", ""), bh_on),
                    h=rh,
                    hover=is_hover(mx, my, self.X + 2, y3, self.W - 4, rh))

        # 行 4: コンパクト BACKGROUND FULLSCREEN チェックボックス
        y4 = row_y(4)
        cb_lbl5 = ("[X] BACKGROUND FULLSCREEN" if is_fs
                   else "[ ] BACKGROUND FULLSCREEN")
        cb_w5 = self._compact_btn_w(cb_lbl5)
        draw_button(self.X + 2, y4, cb_w5, cb_lbl5, h=rh, active=is_fs,
                    hover=is_hover(mx, my, self.X + 2, y4, cb_w5, rh))

        # 行 5: コンパクト BG SAFE AREA チェックボックス
        y5 = row_y(5)
        bad_on = bool(scene.get("bg_above_dialog", False))
        bad_lbl = "[X] BG SAFE AREA" if bad_on else "[ ] BG SAFE AREA"
        bad_w = self._compact_btn_w(bad_lbl)
        draw_button(self.X + 2, y5, bad_w, bad_lbl, h=rh, active=bad_on,
                    hover=is_hover(mx, my, self.X + 2, y5, bad_w, rh))

        # 行 6: コンパクト HIDE BACKGROUND チェックボックス (明示クリア)
        y6 = row_y(6)
        bh_lbl = "[X] HIDE BACKGROUND" if bh_on else "[ ] HIDE BACKGROUND"
        bh_w = self._compact_btn_w(bh_lbl)
        draw_button(self.X + 2, y6, bh_w, bh_lbl, h=rh, active=bh_on,
                    hover=is_hover(mx, my, self.X + 2, y6, bh_w, rh))

        # 行 7: コンパクト HIDE DIALOG チェックボックス
        y7 = row_y(7)
        hd_on = bool(scene.get("hide_dialog", False))
        hd_lbl = "[X] HIDE DIALOG" if hd_on else "[ ] HIDE DIALOG"
        hd_w = self._compact_btn_w(hd_lbl)
        draw_button(self.X + 2, y7, hd_w, hd_lbl, h=rh, active=hd_on,
                    hover=is_hover(mx, my, self.X + 2, y7, hd_w, rh))

        # 行 8: コンパクト TRANSITION チェックボックス
        y8 = row_y(8)
        tr_on = (scene.get("transition", "") == "fade")
        tr_lbl = "[X] TRANSITION (fade)" if tr_on else "[ ] TRANSITION"
        tr_w = self._compact_btn_w(tr_lbl)
        draw_button(self.X + 2, y8, tr_w, tr_lbl, h=rh, active=tr_on,
                    hover=is_hover(mx, my, self.X + 2, y8, tr_w, rh))

        # 行 9: [BACKGROUND MUSIC FILE]:filename
        y9 = row_y(9)
        draw_button(self.X + 2, y9, self.W - 4,
                    self._audio_field_label("BACKGROUND MUSIC FILE",
                                            scene.get("bgm_file", ""),
                                            bool(scene.get("bgm_stop", False))),
                    h=rh,
                    hover=is_hover(mx, my, self.X + 2, y9, self.W - 4, rh))

        # 行 10: コンパクト STOP BGM チェックボックス
        y10 = row_y(10)
        bs_on = bool(scene.get("bgm_stop", False))
        bs_lbl = "[X] STOP BGM" if bs_on else "[ ] STOP BGM"
        bs_w = self._compact_btn_w(bs_lbl)
        draw_button(self.X + 2, y10, bs_w, bs_lbl, h=rh, active=bs_on,
                    hover=is_hover(mx, my, self.X + 2, y10, bs_w, rh))
        once_on = not bool(scene.get("bgm_loop", True))
        once_lbl = "[X] PLAY BGM ONCE" if once_on else "[ ] PLAY BGM ONCE"
        once_x = self.X + 2 + bs_w + 8
        once_w = self._compact_btn_w(once_lbl)
        draw_button(once_x, y10, once_w, once_lbl, h=rh, active=once_on,
                    hover=is_hover(mx, my, once_x, y10, once_w, rh))

        # 行 11: BACKGROUND MUSIC VOLUME スライダー
        y11 = row_y(11)
        sl_bv = self._get_slider("scene", "bgm_volume")
        sl_bv.draw(self.X + 2, y11, sl_w, sh,
                   "BACKGROUND MUSIC VOLUME",
                   scene.get("bgm_volume", 7), label_h=lh)
        _draw_reset(y11)

        # 行 12: BGM FADE OUT FRAMES スライダー
        y12 = row_y(12)
        sl_bf = self._get_slider("scene", "bgm_fadeout_frames")
        bgm_fadeout_frames = int(scene.get("bgm_fadeout_frames", 0) or 0)
        bgm_fadeout_text = (
            "OFF" if bgm_fadeout_frames <= 0 else f"{bgm_fadeout_frames}f")
        sl_bf.draw(self.X + 2, y12, sl_w, sh,
                   "BGM FADE OUT",
                   bgm_fadeout_frames,
                   label_h=lh, value_text=bgm_fadeout_text)
        _draw_reset(y12)

        # 行 13: [SOUND EFFECT FILE]:filename
        y13 = row_y(13)
        draw_button(self.X + 2, y13, self.W - 4,
                    self._btn_val_label("SOUND EFFECT FILE",
                                        scene.get("se_file", "")),
                    h=rh,
                    hover=is_hover(mx, my, self.X + 2, y13, self.W - 4, rh))

        # 行 14: SOUND EFFECT VOLUME スライダー
        y14 = row_y(14)
        sl_sv = self._get_slider("scene", "se_volume")
        sl_sv.draw(self.X + 2, y14, sl_w, sh,
                   "SOUND EFFECT VOLUME",
                   scene.get("se_volume", 7), label_h=lh)
        _draw_reset(y14)

        # 行 15: SOUND EFFECT REPEAT スライダー
        y15 = row_y(15)
        sl_sr = self._get_slider("scene", "se_repeat")
        sl_sr.draw(self.X + 2, y15, sl_w, sh,
                   "SOUND EFFECT REPEAT (0=once)",
                   scene.get("se_repeat", 0), label_h=lh)
        _draw_reset(y15)

        # 行 16: [GOTO]:scene-name
        y16 = row_y(16)
        goto_disp = self._scene_goto_display(scene.get("goto", ""))
        draw_button(self.X + 2, y16, self.W - 4,
                    self._btn_val_label("GOTO", goto_disp), h=rh,
                    hover=is_hover(mx, my, self.X + 2, y16, self.W - 4, rh))

        # 行 17: [GOTO ENDING]:name
        y17 = row_y(17)
        draw_button(self.X + 2, y17, self.W - 4,
                    self._btn_val_label("GOTO ENDING",
                                        scene.get("goto_ending", "")),
                    h=rh,
                    hover=is_hover(mx, my, self.X + 2, y17, self.W - 4, rh))

        # 行 18: コンパクト PAUSE AUTO チェックボックス
        y18 = row_y(18)
        ap_on = bool(scene.get("auto_pause", False))
        ap_lbl = "[X] PAUSE AUTO" if ap_on else "[ ] PAUSE AUTO"
        ap_w = self._compact_btn_w(ap_lbl)
        draw_button(self.X + 2, y18, ap_w, ap_lbl, h=rh, active=ap_on,
                    hover=is_hover(mx, my, self.X + 2, y18, ap_w, rh))

    # ── CHARS タブ ───────────────────────────────────────────

    def _update_chars(self, mx, my, scene):
        # L/C/R サブタブは固定位置（スクロール外）: テキスト幅に合わせて左詰め
        stab_y = self.Y + tab_h()
        stab_x = self.X + 6
        stab_gap = 8
        for (t, lbl) in (("l", "LEFT"), ("c", "CENTER"), ("r", "RIGHT")):
            w = button_w(lbl)
            if is_clicked(mx, my, stab_x, stab_y, w, tab_h()):
                self.char_tab = t
                self._dialog_field = None
            stab_x += w + stab_gap

        # コンテンツはL/C/Rタブの下から始まる
        cy0  = self.Y + tab_h() + tab_h() + 4   # コンテンツ開始位置（絶対座標）
        s    = self._scroll_y
        ctop = self.Y + tab_h() + tab_h()        # スクロール領域の上端 (= L/C/R タブの直下)
        cbot = self.Y + self.H

        # スクロール領域の外にあるクリックは L/C/R タブで吸収済み — 以降は無視。
        # 「タブの下に潜り込んだUI」もこの判定で全てクリック不可になる。
        if my < ctop:
            return

        slot_key = f"char_{self.char_tab}"
        cfg = scene.setdefault(slot_key, {})

        sl_w = self.W - 6 - _reset_w() - 2   # スライダー幅（リセットボタン分を確保）
        rb_x = self.X + 2 + sl_w + 2        # リセットボタン X 座標

        lh = label_h()
        sh = slider_h()         # 全スライダー共通の描画高さ
        sp = slider_pitch()     # 全スライダー共通の行ピッチ (= 2*sh)

        right_clicked = pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT) and not _text_dialog.running

        # FILE ボタン
        # 左クリック: ファイルピッカーを開く
        # 右クリック: 値をクリア (= INHERIT 状態に戻す)。誤選択のリカバリ用。
        fy = cy0 - s
        if ctop <= fy + field_h() and fy < cbot:
            if is_clicked(mx, my, self.X + 2, fy, self.W - 4, field_h()):
                fid = ("chars", slot_key, "file")
                self._dialog_field = fid
                def _cb(val, f=fid, c=cfg):
                    c["file"] = "./assets/images/chars/" + val
                    self.state.dirty = True
                    if self._dialog_field == f:
                        self._dialog_field = None
                _file_picker.open("CHARACTER FILE", "./assets/images/chars/",
                                  mode="image", callback=_cb,
                                  initial_path=str(cfg.get("file", "") or ""))
            elif right_clicked and is_hover(mx, my, self.X + 2, fy,
                                            self.W - 4, field_h()):
                if cfg.get("file", ""):
                    cfg["file"] = ""
                    self.state.dirty = True
        fy += field_h()

        # HIDE CHARACTER チェックボックス (明示的にこのスロットを非表示にする)。
        # file が空のときは前シーンから継承するが、HIDE が立つと継承を断ち切る。
        ch_hide_h = 18
        ch_hide_on = bool(cfg.get("hide", False))
        ch_hide_lbl = ("[X] HIDE CHARACTER" if ch_hide_on
                       else "[ ] HIDE CHARACTER")
        ch_hide_w = self._compact_btn_w(ch_hide_lbl)
        if ctop <= fy + ch_hide_h and fy < cbot:
            if is_clicked(mx, my, self.X + 2, fy, ch_hide_w, ch_hide_h):
                cfg["hide"] = not ch_hide_on
                self.state.dirty = True
        fy += ch_hide_h + 2

        # 現在スロット専用の立ち位置メモ。画像を差し替えた後でも、
        # x/y/scale だけを素早く復元できるようにする。
        pos_y = fy
        pos_h = 18
        pos_bw = (self.W - 8) // 2
        if ctop <= pos_y + pos_h and pos_y < cbot:
            if is_clicked(mx, my, self.X + 2, pos_y, pos_bw, pos_h):
                self._store_char_pos(self.char_tab, cfg)
            if is_clicked(mx, my, self.X + 4 + pos_bw, pos_y, pos_bw, pos_h):
                self._apply_char_pos(self.char_tab, cfg)
        fy += 36

        # CHARACTER SCALING (倍率)。vertical axis position を基準にスケールする。
        tab_label = {"l": "LEFT", "c": "CENTER", "r": "RIGHT"}.get(self.char_tab, "")
        scaling_label = f"{tab_label} CHARACTER SCALING"
        sl_sc = self._get_slider(slot_key, "scaling")
        nv_sc = sl_sc.handle(self.X + 2, fy, sl_w, sh,
                             mx, my, float(cfg.get("scale", 1.0)))
        if nv_sc is not None:
            cfg["scale"] = float(nv_sc)
            self.state.dirty = True
        if right_clicked and is_hover(mx, my, self.X + 2, fy, sl_w, sh):
            self._open_numeric_dialog(scaling_label, cfg, "scale", "scaling", 1.0)
        if is_clicked(mx, my, rb_x, fy + lh, _reset_w(), sh - lh):
            cfg["scale"] = 1.0
            self.state.dirty = True
        fy += sp

        # horizontal axis position (旧 X), vertical axis position (旧 Y), COLOR KEY
        for fkey, default in (
                ("x", 0), ("y", 0), ("colkey", COLOR_KEY_AUTO)):
            field_y = fy
            sl = self._get_slider(slot_key, fkey)
            cur_val = (normalize_color_key(cfg.get(fkey, default))
                       if fkey == "colkey" else cfg.get(fkey, default))
            nv = sl.handle(self.X + 2, field_y, sl_w, sh,
                           mx, my, cur_val)
            if nv is not None:
                cfg[fkey] = normalize_color_key(nv) if fkey == "colkey" else nv
                self.state.dirty = True
            if right_clicked and is_hover(mx, my, self.X + 2, field_y, sl_w, sh):
                self._open_numeric_dialog(fkey.upper(), cfg, fkey, fkey, default)
            if is_clicked(mx, my, rb_x, field_y + lh, _reset_w(), sh - lh):
                cfg[fkey] = default
                self.state.dirty = True
            fy += sp

        # Flip ボタン
        flip_y = fy + 4
        bw = (self.W - 8) // 2
        if ctop <= flip_y < cbot:
            if is_clicked(mx, my, self.X + 2, flip_y, bw, 18):
                cfg["flip_h"] = not cfg.get("flip_h", False)
                self.state.dirty = True
            if is_clicked(mx, my, self.X + 4 + bw, flip_y, bw, 18):
                cfg["flip_v"] = not cfg.get("flip_v", False)
                self.state.dirty = True

        # ANIMATION ヘッダー + スライダー
        ay = flip_y + 22 + anim_fh()  # ヘッダー高さ分も確保
        anim = cfg.setdefault("anim", {})
        opt_h = 18
        opt_w = (self.W - 8) // 2
        if ctop <= ay + opt_h and ay < cbot:
            if is_clicked(mx, my, self.X + 2, ay, opt_w, opt_h):
                cfg["keep_anim"] = not bool(cfg.get("keep_anim", False))
                self.state.dirty = True
            if is_clicked(mx, my, self.X + 4 + opt_w, ay, opt_w, opt_h):
                cfg["hold_motion_end"] = not bool(cfg.get("hold_motion_end", False))
                self.state.dirty = True
        ay += opt_h + 2
        if ctop <= ay + opt_h and ay < cbot:
            if is_clicked(mx, my, self.X + 2, ay,
                          self._compact_btn_w("[CLEAR ANIM]"), opt_h):
                cfg["anim"] = {}
                cfg["keep_anim"] = False
                cfg["hold_motion_end"] = False
                anim = cfg["anim"]
                self.state.dirty = True
        ay += opt_h + 4
        for _, akey, default, _ in _ANIM_DEFS:
            sl = self._get_slider(slot_key, f"anim_{akey}")
            nv = sl.handle(self.X + 2, ay, sl_w, sh,
                           mx, my, anim.get(akey, default))
            if nv is not None:
                anim[akey] = nv
                self.state.dirty = True
            if right_clicked and is_hover(mx, my, self.X + 2, ay, sl_w, sh):
                self._open_numeric_dialog(
                    f"anim_{akey}".upper(), anim, akey, f"anim_{akey}", default)
            if is_clicked(mx, my, rb_x, ay + lh, _reset_w(), sh - lh):
                anim[akey] = default
                self.state.dirty = True
            ay += sp

    def _char_fields(self, cfg):
        return [
            ("FILE",      "file",   cfg.get("file",    "")),
            ("X",         "x",      str(cfg.get("x",   0))),
            ("Y",         "y",      str(cfg.get("y",   0))),
            ("W",         "w",      str(cfg.get("w",   0))),
            ("H",         "h",      str(cfg.get("h",   0))),
            ("COLOR KEY", "colkey", color_key_label(
                cfg.get("colkey", COLOR_KEY_AUTO))),
        ]

    def _anim_items(self, anim):
        return [
            ("SHAKE AMPLITUDE",   "shake_amp",         str(anim.get("shake_amp", 0))),
            ("SHAKE SPEED",       "shake_speed",       str(anim.get("shake_speed", 4))),
            ("ROTATION SPEED",    "rot_speed",         str(anim.get("rot_speed", 0.0))),
            ("SCALE START",       "scale_start",       str(anim.get("scale_start", 1.0))),
            ("SCALE END",         "scale_end",         str(anim.get("scale_end", 1.0))),
            ("SCALE FRAMES",      "scale_frames",      str(anim.get("scale_frames", 0))),
            ("MOTION X",          "motion_x",          str(anim.get("motion_x", 0))),
            ("MOTION Y",          "motion_y",          str(anim.get("motion_y", 0))),
            ("MOTION FRAMES",     "motion_frames",     str(anim.get("motion_frames", 0))),
            ("FLIPBOOK INTERVAL", "flipbook_interval", str(anim.get("flipbook_interval", 6))),
        ]

    def _draw_chars(self, scene, cy):
        slot_key = f"char_{self.char_tab}"
        cfg = scene.get(slot_key, {})
        if not isinstance(cfg, dict):
            cfg = {}

        mx, my = pyxel.mouse_x, pyxel.mouse_y
        sl_w = self.W - 6 - _reset_w() - 2   # スライダー幅
        rb_x = self.X + 2 + sl_w + 2        # リセットボタン X 座標

        lh = label_h()
        sh = slider_h()         # 全スライダー共通の描画高さ
        sp = slider_pitch()     # 全スライダー共通の行ピッチ (= 2*sh)

        # FILE ボタン (全幅)。トライステート (HIDE / SET / INHERIT) を可視化。
        ch_hide_on = bool(cfg.get("hide", False))
        file_lbl = self._img_field_label("FILE", cfg.get("file", ""), ch_hide_on)
        draw_button(self.X + 2, cy, self.W - 4, file_lbl, h=field_h(),
                    hover=is_hover(mx, my, self.X + 2, cy, self.W - 4, field_h()))
        fy = cy + field_h()

        # HIDE CHARACTER コンパクトチェックボックス
        ch_hide_h = 18
        ch_hide_lbl = ("[X] HIDE CHARACTER" if ch_hide_on
                       else "[ ] HIDE CHARACTER")
        ch_hide_w = self._compact_btn_w(ch_hide_lbl)
        draw_button(self.X + 2, fy, ch_hide_w, ch_hide_lbl, h=ch_hide_h,
                    active=ch_hide_on,
                    hover=is_hover(mx, my, self.X + 2, fy, ch_hide_w, ch_hide_h))
        fy += ch_hide_h + 2

        pos_h = 18
        pos_bw = (self.W - 8) // 2
        apply_has_pos = isinstance(
            self._char_pos_memory().get(self.char_tab), dict)
        draw_button(self.X + 2, fy, pos_bw, "[STORE POS]", h=pos_h,
                    hover=is_hover(mx, my, self.X + 2, fy, pos_bw, pos_h))
        draw_button(self.X + 4 + pos_bw, fy, pos_bw, "[APPLY POS]",
                    h=pos_h, active=apply_has_pos,
                    hover=is_hover(mx, my, self.X + 4 + pos_bw, fy,
                                   pos_bw, pos_h))
        draw_ui_text(self.X + 4, fy + pos_h + 2,
                     self._char_pos_memory_label(self.char_tab),
                     EDIT_TEXT_DIM)
        fy += 36

        # CHARACTER SCALING (file の直下)
        tab_label = {"l": "LEFT", "c": "CENTER", "r": "RIGHT"}.get(self.char_tab, "")
        scaling_label = f"{tab_label} CHARACTER SCALING"
        sl_sc = self._get_slider(slot_key, "scaling")
        sl_sc.draw(self.X + 2, fy, sl_w, sh,
                   scaling_label, float(cfg.get("scale", 1.0)), label_h=lh)
        rb_y = fy + lh
        rb_h = sh - lh
        draw_reset_btn(rb_x, rb_y, rb_h,
                       hover=is_hover(mx, my, rb_x, rb_y, _reset_w(), rb_h))
        fy += sp

        # horizontal / vertical axis position + COLOR KEY
        for fkey, label, default in (
                ("x", "horizontal axis position", 0),
                ("y", "vertical axis position",   0),
                ("colkey", "COLOR KEY", COLOR_KEY_AUTO)):
            sl = self._get_slider(slot_key, fkey)
            cur_val = (normalize_color_key(cfg.get(fkey, default))
                       if fkey == "colkey" else cfg.get(fkey, default))
            value_text = color_key_label(cur_val) if fkey == "colkey" else None
            sl.draw(self.X + 2, fy, sl_w, sh,
                    label, cur_val, label_h=lh, value_text=value_text)
            rb_y = fy + lh
            rb_h = sh - lh
            draw_reset_btn(rb_x, rb_y, rb_h, hover=is_hover(mx, my, rb_x, rb_y, _reset_w(), rb_h))
            fy += sp

        flip_y = fy + 4
        bw = (self.W - 8) // 2
        flip_h = bool(cfg.get("flip_h", False))
        flip_v = bool(cfg.get("flip_v", False))
        draw_button(self.X + 2, flip_y, bw,
                    "[X] FLIP HORIZONTAL" if flip_h else "[ ] FLIP HORIZONTAL",
                    h=18, active=flip_h)
        draw_button(self.X + 4 + bw, flip_y, bw,
                    "[X] FLIP VERTICAL" if flip_v else "[ ] FLIP VERTICAL",
                    h=18, active=flip_v)

        # ANIMATION ヘッダー (UIスケール対応の高さで余白確保)
        ay = flip_y + 22
        draw_ui_text(self.X + 2, ay, "-- ANIMATION --", EDIT_TEXT_DIM)
        ay += anim_fh()

        opt_h = 18
        opt_w = (self.W - 8) // 2
        keep_on = bool(cfg.get("keep_anim", False))
        hold_on = bool(cfg.get("hold_motion_end", False))
        keep_lbl = "[X] KEEP ANIM NEXT" if keep_on else "[ ] KEEP ANIM NEXT"
        hold_lbl = "[X] HOLD MOTION END" if hold_on else "[ ] HOLD MOTION END"
        draw_button(self.X + 2, ay, opt_w, keep_lbl, h=opt_h,
                    active=keep_on,
                    hover=is_hover(mx, my, self.X + 2, ay, opt_w, opt_h))
        draw_button(self.X + 4 + opt_w, ay, opt_w, hold_lbl, h=opt_h,
                    active=hold_on,
                    hover=is_hover(mx, my, self.X + 4 + opt_w, ay,
                                   opt_w, opt_h))
        ay += opt_h + 2
        clear_w = self._compact_btn_w("[CLEAR ANIM]")
        draw_button(self.X + 2, ay, clear_w, "[CLEAR ANIM]", h=opt_h,
                    hover=is_hover(mx, my, self.X + 2, ay, clear_w, opt_h))
        ay += opt_h + 4

        anim = cfg.get("anim", {})
        for label, akey, default, _ in _ANIM_DEFS:
            sl = self._get_slider(slot_key, f"anim_{akey}")
            sl.draw(self.X + 2, ay, sl_w, sh,
                    label, anim.get(akey, default), label_h=lh)
            rb_y = ay + lh
            rb_h = sh - lh
            draw_reset_btn(rb_x, rb_y, rb_h, hover=is_hover(mx, my, rb_x, rb_y, _reset_w(), rb_h))
            ay += sp

    # ── CHOICES タブ ─────────────────────────────────────────

    def _update_choices(self, mx, my, scene):
        s    = self._scroll_y
        ctop = self.Y + tab_h()
        cbot = self.Y + self.H
        # タブ下に潜り込んだ UI へのクリックを無効化
        if my < ctop:
            return
        cy   = self.Y + tab_h() + 4 - s
        choices = scene.setdefault("choices", [])

        if ctop <= cy < cbot:
            if is_clicked(mx, my, self.X + 2, cy, self.W - 4, 20):
                choices.append({"label": "new", "goto": ""})
                self.choice_sel = len(choices) - 1
                self.state.dirty = True
                return
        cy += 24

        for i in range(min(len(choices), self._CHOICE_MAX)):
            iy = cy + i * (_w._font_render_h(_w._ui_font_size) + 4)
            if iy + (_w._font_render_h(_w._ui_font_size) + 4) <= ctop or iy >= cbot:
                continue
            if is_clicked(mx, my, self.X + 2, iy, self.W - 20, (_w._font_render_h(_w._ui_font_size) + 4)):
                self.choice_sel = i
            if is_clicked(mx, my, self.X + self.W - 18, iy, 16, (_w._font_render_h(_w._ui_font_size) + 4)):
                choices.pop(i)
                self.choice_sel = min(self.choice_sel, len(choices) - 1)
                self.state.dirty = True
                return

        if 0 <= self.choice_sel < len(choices):
            ey = cy + self._CHOICE_MAX * (_w._font_render_h(_w._ui_font_size) + 4) + 4
            ch = choices[self.choice_sel]
            rh = self._scene_row_h()

            # LABEL ボタン (テキストダイアログ)
            lb_y = ey
            if ctop <= lb_y + rh and lb_y < cbot:
                if is_clicked(mx, my, self.X + 2, lb_y, self.W - 4, rh):
                    fid = ("choices", self.choice_sel, "label")
                    self._dialog_field = fid
                    def _cb_lbl(val, f=fid, c=ch):
                        c["label"] = val
                        self.state.dirty = True
                        if self._dialog_field == f:
                            self._dialog_field = None
                    _text_dialog.open("LABEL", ch.get("label", ""), _cb_lbl)

            # GOTO ボタン (シーンピッカー)
            gt_y = ey + rh + 2
            if ctop <= gt_y + rh and gt_y < cbot:
                if is_clicked(mx, my, self.X + 2, gt_y, self.W - 4, rh):
                    def _cb_goto(val, c=ch):
                        c["goto"] = val
                        self.state.dirty = True
                    _scene_picker.open("CHOICE GOTO", self.state,
                                       ch.get("goto", ""), _cb_goto)

    def _draw_choices(self, scene, cy):
        choices = scene.get("choices", [])
        mx, my  = pyxel.mouse_x, pyxel.mouse_y

        draw_button(self.X + 2, cy, self.W - 4, "+ ADD CHOICE", h=20,
                    hover=is_hover(mx, my, self.X + 2, cy, self.W - 4, 20))
        cy += 24

        for i, ch in enumerate(choices[:self._CHOICE_MAX]):
            iy  = cy + i * (_w._font_render_h(_w._ui_font_size) + 4)
            sel = (i == self.choice_sel)
            pyxel.rect(self.X + 2, iy, self.W - 22, (_w._font_render_h(_w._ui_font_size) + 4),
                       EDIT_ACCENT if sel else EDIT_PANEL)
            _rh = _w._font_render_h(_w._ui_font_size)
            ty = iy + max(0, ((_rh + 4) - _rh) // 2)
            draw_unicode(self.X + 5, ty,
                         ch.get("label", ""),
                         EDIT_BG if sel else EDIT_TEXT_DIM, size=_w._ui_font_size)
            bx = self.X + self.W - 18
            hover_x = is_hover(mx, my, bx, iy, 16, (_w._font_render_h(_w._ui_font_size) + 4))
            pyxel.rect(bx, iy, 16, (_w._font_render_h(_w._ui_font_size) + 4), EDIT_BTN_BG if hover_x else EDIT_PANEL)
            draw_ui_text(bx + 4, iy + 4, "x", EDIT_TEXT)

        if not choices:
            draw_ui_text(self.X + 4, cy + 4, "no choices", EDIT_TEXT_DIM)

        ey = cy + self._CHOICE_MAX * (_w._font_render_h(_w._ui_font_size) + 4) + 4
        pyxel.line(self.X + 2, ey - 2, self.X + self.W - 2, ey - 2, EDIT_BORDER)

        if 0 <= self.choice_sel < len(choices):
            ch = choices[self.choice_sel]
            rh = self._scene_row_h()
            lb_y = ey
            gt_y = ey + rh + 2
            draw_button(self.X + 2, lb_y, self.W - 4,
                        self._btn_val_label("LABEL", ch.get("label", "")),
                        h=rh,
                        hover=is_hover(mx, my, self.X + 2, lb_y, self.W - 4, rh))
            goto_disp = self._scene_goto_display(ch.get("goto", ""))
            draw_button(self.X + 2, gt_y, self.W - 4,
                        self._btn_val_label("GOTO", goto_disp),
                        h=rh,
                        hover=is_hover(mx, my, self.X + 2, gt_y, self.W - 4, rh))
        else:
            draw_ui_text(self.X + 4, ey + 4, "select to edit", EDIT_TEXT_DIM)


# ── Toolbar ──────────────────────────────────────────────────────

class Toolbar:
    """下部ツールバー: タブ切り替え + SETTINGS + OPEN + QUIT + PLAY"""
    X, Y, W, H = TB_X, TB_Y, TB_W, TB_H

    TABS = ["SCENE", "FLOW"]

    def __init__(self, state):
        self.state = state

    _BTN_H = 24
    _GAP = 6

    def _layout(self):
        """各ボタンの矩形を返す。
        (tabs, qy, play, quit, open, settings, import_md)
        """
        tab_w = max(58, button_w("SCENE"), button_w("FLOW"))
        tabs = []
        for i, tab in enumerate(self.TABS):
            tx = self.X + 4 + i * (tab_w + 2)
            tabs.append((tx, tab_w, tab))

        play_w = max(58, button_w("PLAY"))
        quit_w = max(38, button_w("QUIT"))
        open_w = max(38, button_w("OPEN"))
        set_w  = max(40, button_w("SETTINGS"))
        imp_w  = max(56, button_w("IMPORT MD"))

        play_x = self.W - 4 - play_w
        qy = self.Y + (self.H - self._BTN_H) // 2
        qx = play_x - self._GAP - quit_w
        ox = qx - self._GAP - open_w
        sx = ox - self._GAP - set_w
        ix = sx - self._GAP - imp_w
        return (tabs, qy, (play_x, play_w), (qx, quit_w),
                (ox, open_w), (sx, set_w), (ix, imp_w))

    def update(self):
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        (tabs, qy, (play_x, play_w), (qx, quit_w),
         (ox, open_w), (sx, set_w), (ix, imp_w)) = self._layout()
        for i, (tx, tw, _) in enumerate(tabs):
            if is_clicked(mx, my, tx, self.Y, tw, self.H):
                self.state.active_tab = i
        if is_clicked(mx, my, play_x, self.Y, play_w, self.H):
            self.state.request_play = True
        if is_clicked(mx, my, qx, qy, quit_w, self._BTN_H):
            self.state.request_quit = True
        if is_clicked(mx, my, ox, qy, open_w, self._BTN_H):
            self.state.request_open = True
        if is_clicked(mx, my, sx, qy, set_w, self._BTN_H):
            self.state.request_settings = True
        if is_clicked(mx, my, ix, qy, imp_w, self._BTN_H):
            self.state.request_import_md = True

    def draw(self):
        pyxel.rect(self.X, self.Y, self.W, self.H, EDIT_TITLE_BG)
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        (tabs, qy, (play_x, play_w), (qx, quit_w),
         (ox, open_w), (sx, set_w), (ix, imp_w)) = self._layout()

        for i, (tx, tw, tab) in enumerate(tabs):
            active = (self.state.active_tab == i)
            hover  = is_hover(mx, my, tx, self.Y, tw, self.H)
            draw_button(tx, self.Y, tw, tab, h=self.H,
                        active=active, hover=hover and not active)

        # ファイル名表示領域はタブ右端〜IMPORT左端の間。BDF (b12) で描画。
        # 長すぎる時は末尾省略。
        name_x = tabs[-1][0] + tabs[-1][1] + 8
        name_w = max(0, ix - name_x - 4)
        path = self.state.file_path
        name = os.path.basename(path) if path else "untitled"
        if self.state.dirty:
            name += " *"
        # text_px_w で実描画幅を計りつつ収まるまで末尾削る
        fz = _w._ui_font_size
        # 中央寄せ用に幅を測る
        full_w = text_px_w(name, fz)
        if full_w > name_w:
            # 末尾を "…" にしつつ削る
            while name and text_px_w(name + "…", fz) > name_w:
                name = name[:-1]
            if name:
                name = name + "…"
        disp_w = text_px_w(name, fz)
        # name_w 領域内で中央寄せ
        tx = name_x + max(0, (name_w - disp_w) // 2)
        ty = self.Y + max(0, (self.H - _w._font_render_h(fz)) // 2)
        col = EDIT_ACCENT if self.state.dirty else EDIT_TEXT_DIM
        draw_unicode(tx, ty, name, col, size=fz)

        ph_ = is_hover(mx, my, play_x, self.Y, play_w, self.H)
        draw_button(play_x, self.Y, play_w, "PLAY", h=self.H, hover=ph_)

        qh_ = is_hover(mx, my, qx, qy, quit_w, self._BTN_H)
        draw_button(qx, qy, quit_w, "QUIT", h=self._BTN_H, hover=qh_)

        oh_ = is_hover(mx, my, ox, qy, open_w, self._BTN_H)
        draw_button(ox, qy, open_w, "OPEN", h=self._BTN_H, hover=oh_)

        sh_ = is_hover(mx, my, sx, qy, set_w, self._BTN_H)
        draw_button(sx, qy, set_w, "SETTINGS", h=self._BTN_H, hover=sh_)

        ih_ = is_hover(mx, my, ix, qy, imp_w, self._BTN_H)
        draw_button(ix, qy, imp_w, "IMPORT MD", h=self._BTN_H, hover=ih_)


# ─── ネイティブテキスト入力ダイアログ ─────────────────────────

def _native_ask(label: str, initial: str) -> str | None:
    """ネイティブダイアログでテキスト入力。キャンセル時は None を返す。"""
    return ask_text(label, initial)


def _native_ask_multiline(label: str, initial: str) -> str | None:
    """複数行テキスト入力ダイアログ (tkinter Text ウィジェット)。"""
    return ask_multiline(label, initial)


_text_dialog = AsyncTextDialog()
_file_picker = FilePicker()


class _ListPicker:
    """汎用リスト選択モーダル（シーン/エンディング共通）"""

    def __init__(self):
        self.active = False
        self._title = ""
        self._items: list[tuple[str, str]] = []  # [(display, value)]
        self._callback = None
        self._scroll = 0
        self._selected = -1

    def open(self, title: str, items: list[tuple[str, str]],
             current_value: str, callback):
        self.active   = True
        self._title   = title
        self._items   = list(items)
        self._callback = callback
        self._scroll  = 0
        self._selected = -1
        for i, (_, v) in enumerate(self._items):
            if v == current_value:
                self._selected = i
                break

    def close(self):
        self.active = False
        self._callback = None
        self._items = []

    @property
    def _rect(self):
        w = 360
        h = 300
        x = (720 - w) // 2
        y = (480 - h) // 2
        return x, y, w, h

    def _row_h(self):
        return max(18, _w._font_render_h(_w._ui_font_size) + 2)

    def update(self):
        if not self.active:
            return
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        x, y, w, h = self._rect
        # ESC で閉じる
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self.close()
            return
        # ホイール
        if is_hover(mx, my, x, y, w, h):
            wheel = pyxel.mouse_wheel
            if wheel:
                self._scroll -= wheel * 20
                self._scroll = max(0, self._scroll)
        # キャンセルボタン
        btn_h = 22
        cancel_x = x + w - 80 - 4
        btn_y    = y + h - btn_h - 4
        if is_clicked(mx, my, cancel_x, btn_y, 80, btn_h):
            self.close()
            return
        # 選択
        list_top = y + title_bar_h() + 4
        list_bot = btn_y - 4
        rh = self._row_h()
        for i, (_, _) in enumerate(self._items):
            iy = list_top + i * rh - self._scroll
            if iy + rh <= list_top or iy >= list_bot:
                continue
            if is_clicked(mx, my, x + 4, iy, w - 8, rh):
                cb = self._callback
                val = self._items[i][1]
                self.close()
                if cb:
                    cb(val)
                return

    def draw(self):
        if not self.active:
            return
        x, y, w, h = self._rect
        # 影
        pyxel.rect(x + 3, y + 3, w, h, EDIT_BORDER)
        draw_panel(x, y, w, h)
        draw_titlebar(x, y, w, self._title)
        # リスト
        btn_h = 22
        btn_y = y + h - btn_h - 4
        list_top = y + title_bar_h() + 4
        list_bot = btn_y - 4
        rh = self._row_h()
        pyxel.clip(x, list_top, w, list_bot - list_top)
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        for i, (disp, _) in enumerate(self._items):
            iy = list_top + i * rh - self._scroll
            if iy + rh <= list_top or iy >= list_bot:
                continue
            sel   = (i == self._selected)
            hover = is_hover(mx, my, x + 4, iy, w - 8, rh)
            draw_list_item(x + 4, iy, w - 8, disp,
                           h=rh, selected=sel, hover=hover and not sel)
        pyxel.clip()
        # Cancel ボタン
        cancel_x = x + w - 80 - 4
        draw_button(cancel_x, btn_y, 80, "Cancel", h=btn_h,
                    hover=is_hover(mx, my, cancel_x, btn_y, 80, btn_h))


class _ScenePicker:
    """Part/Chapterで絞り込めるGOTO用シーンピッカー。"""

    def __init__(self):
        self.active = False
        self._title = ""
        self._state = None
        self._callback = None
        self._current_value = ""
        self._part_filter: int | None = None
        self._chapter_filter: tuple[int, int] | None = None
        self._scroll = 0
        self._selected = -1

    def open(self, title: str, state, current_value: str, callback):
        self.active = True
        self._title = title
        self._state = state
        self._callback = callback
        self._current_value = current_value or ""
        self._scroll = 0
        parsed = parse_scene_name(self._current_value)
        if parsed:
            pid, cid, _disp = parsed
            self._part_filter = pid
            self._chapter_filter = (pid, cid)
        else:
            self._part_filter = int(getattr(state, "current_part_id", 0) or 0) or None
            cid = int(getattr(state, "current_chapter_id", 0) or 0)
            self._chapter_filter = (
                (self._part_filter, cid) if self._part_filter and cid else None)
        self._sync_selected()

    def close(self):
        self.active = False
        self._state = None
        self._callback = None

    @property
    def _rect(self):
        w = 520
        h = 360
        x = (720 - w) // 2
        y = (480 - h) // 2
        return x, y, w, h

    def _row_h(self):
        return max(18, _w._font_render_h(_w._ui_font_size) + 3)

    def _parts(self) -> list[tuple[int | None, str]]:
        state = self._state
        out = [(None, "ALL PARTS")]
        if state:
            for part in state.parts:
                out.append((int(part.get("id", 0)), str(part.get("name", ""))))
        return out

    def _chapters(self) -> list[tuple[tuple[int, int] | None, str]]:
        state = self._state
        out: list[tuple[tuple[int, int] | None, str]] = [(None, "ALL CHAPTERS")]
        if not state:
            return out
        if self._part_filter is not None:
            for chapter in state.chapters_for_part(self._part_filter):
                cid = int(chapter.get("id", 0))
                name = str(chapter.get("name", ""))
                out.append(((self._part_filter, cid), name or f"Chapter {cid}"))
        else:
            for chapter in state.chapters:
                pid = int(chapter.get("part_id", 0))
                cid = int(chapter.get("id", 0))
                part_name = self._part_label(pid)
                name = str(chapter.get("name", ""))
                out.append(((pid, cid), f"{part_name} / {name or f'Chapter {cid}'}"))
        return out

    def _part_label(self, part_id: int | None) -> str:
        if part_id is None:
            return "ALL PARTS"
        state = self._state
        if state:
            part = state.get_part(part_id)
            if part:
                return str(part.get("name", f"Part {part_id}"))
        return f"Part {part_id}"

    def _chapter_label(self, chapter_key: tuple[int, int] | None) -> str:
        if chapter_key is None:
            return "ALL CHAPTERS"
        pid, cid = chapter_key
        state = self._state
        if state:
            chapter = state.get_chapter(pid, cid)
            if chapter:
                return str(chapter.get("name", f"Chapter {cid}"))
        return f"Chapter {cid}"

    def _scene_items(self) -> list[tuple[str, str]]:
        state = self._state
        if not state:
            return [("(none)", "")]
        items = [("(none)", "")]
        for scene in state.scenes:
            name = scene.get("name", "")
            parsed = parse_scene_name(name)
            if self._part_filter is not None:
                if not parsed or parsed[0] != self._part_filter:
                    continue
            if self._chapter_filter is not None:
                if not parsed or (parsed[0], parsed[1]) != self._chapter_filter:
                    continue
            items.append((self._scene_display(scene, parsed), name))
        return items

    def _scene_display(self, scene: dict, parsed) -> str:
        state = self._state
        disp = display_name(scene)
        if not parsed or not state:
            return disp
        pid, cid, _name = parsed
        if self._part_filter is not None and self._chapter_filter is not None:
            return disp
        if self._part_filter is not None:
            return f"{self._chapter_label((pid, cid))} / {disp}"
        return f"{self._part_label(pid)} / {self._chapter_label((pid, cid))} / {disp}"

    def _sync_selected(self):
        items = self._scene_items()
        self._selected = 0 if items else -1
        for i, (_disp, value) in enumerate(items):
            if value == self._current_value:
                self._selected = i
                break
        self._ensure_selected_visible()

    def _cycle_part(self, delta: int):
        parts = self._parts()
        ids = [p[0] for p in parts]
        try:
            idx = ids.index(self._part_filter)
        except ValueError:
            idx = 0
        self._part_filter = ids[(idx + delta) % len(ids)]
        self._chapter_filter = None
        self._scroll = 0
        self._sync_selected()

    def _cycle_chapter(self, delta: int):
        chapters = self._chapters()
        ids = [c[0] for c in chapters]
        try:
            idx = ids.index(self._chapter_filter)
        except ValueError:
            idx = 0
        self._chapter_filter = ids[(idx + delta) % len(ids)]
        if self._chapter_filter is not None:
            self._part_filter = self._chapter_filter[0]
        self._scroll = 0
        self._sync_selected()

    def _list_geom(self):
        x, y, w, h = self._rect
        btn_h = 22
        btn_y = y + h - btn_h - 4
        filter_h = 24
        part_y = y + title_bar_h() + 6
        chap_y = part_y + filter_h + 4
        list_top = chap_y + filter_h + 6
        list_bot = btn_y - 4
        return btn_y, part_y, chap_y, list_top, list_bot

    def _filter_row(self, row_y: int):
        x, _y, w, _h = self._rect
        arrow_w = 30
        gap = 4
        return (
            (x + 6, row_y, arrow_w, 22),
            (x + 6 + arrow_w + gap, row_y,
             w - 12 - (arrow_w + gap) * 2, 22),
            (x + w - 6 - arrow_w, row_y, arrow_w, 22),
        )

    def _fit_label(self, text: str, max_w: int) -> str:
        if text_px_w(text, size=_w._ui_font_size) <= max_w:
            return text
        suffix = "..."
        out = text
        while out and text_px_w(out + suffix, size=_w._ui_font_size) > max_w:
            out = out[:-1]
        return (out + suffix) if out else suffix

    def _cap_scroll(self):
        _btn_y, _part_y, _chap_y, list_top, list_bot = self._list_geom()
        total = len(self._scene_items()) * self._row_h()
        self._scroll = max(0, min(max(0, total - (list_bot - list_top)),
                                  self._scroll))

    def _ensure_selected_visible(self):
        if self._selected < 0:
            self._scroll = 0
            return
        _btn_y, _part_y, _chap_y, list_top, list_bot = self._list_geom()
        rh = self._row_h()
        view_h = list_bot - list_top
        row_top = self._selected * rh
        row_bot = row_top + rh
        if row_top < self._scroll:
            self._scroll = row_top
        elif row_bot > self._scroll + view_h:
            self._scroll = row_bot - view_h
        self._cap_scroll()

    def _move_selection(self, delta: int):
        items = self._scene_items()
        if not items:
            self._selected = -1
            return
        if self._selected < 0:
            self._selected = 0
        else:
            self._selected = max(0, min(len(items) - 1,
                                        self._selected + delta))
        self._ensure_selected_visible()

    def _choose_selected(self):
        items = self._scene_items()
        if not (0 <= self._selected < len(items)):
            return
        cb = self._callback
        val = items[self._selected][1]
        self.close()
        if cb:
            cb(val)

    def update(self):
        if not self.active:
            return
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        x, y, w, h = self._rect
        btn_y, part_y, chap_y, list_top, list_bot = self._list_geom()

        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self.close()
            return
        if pyxel.btnp(pyxel.KEY_UP, hold=15, repeat=4):
            self._move_selection(-1)
        if pyxel.btnp(pyxel.KEY_DOWN, hold=15, repeat=4):
            self._move_selection(1)
        if pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE):
            self._choose_selected()
            return

        p_prev, p_mid, p_next = self._filter_row(part_y)
        c_prev, c_mid, c_next = self._filter_row(chap_y)
        if is_clicked(mx, my, *p_prev):
            self._cycle_part(-1)
            return
        if is_clicked(mx, my, *p_next) or is_clicked(mx, my, *p_mid):
            self._cycle_part(1)
            return
        if is_clicked(mx, my, *c_prev):
            self._cycle_chapter(-1)
            return
        if is_clicked(mx, my, *c_next) or is_clicked(mx, my, *c_mid):
            self._cycle_chapter(1)
            return

        if is_hover(mx, my, x, list_top, w, list_bot - list_top):
            wheel = pyxel.mouse_wheel
            if wheel:
                self._scroll -= wheel * 20
                self._cap_scroll()

        btn_h = 22
        none_x = x + 4
        cancel_x = x + w - 80 - 4
        if is_clicked(mx, my, none_x, btn_y, 80, btn_h):
            cb = self._callback
            self.close()
            if cb:
                cb("")
            return
        if is_clicked(mx, my, cancel_x, btn_y, 80, btn_h):
            self.close()
            return

        items = self._scene_items()
        rh = self._row_h()
        for i, (_disp, _value) in enumerate(items):
            iy = list_top + i * rh - self._scroll
            if iy + rh <= list_top or iy >= list_bot:
                continue
            if is_clicked(mx, my, x + 4, iy, w - 8, rh):
                self._selected = i
                self._choose_selected()
                return

    def draw(self):
        if not self.active:
            return
        x, y, w, h = self._rect
        pyxel.rect(x + 3, y + 3, w, h, EDIT_BORDER)
        draw_panel(x, y, w, h)
        draw_titlebar(x, y, w, self._title)

        btn_y, part_y, chap_y, list_top, list_bot = self._list_geom()
        mx, my = pyxel.mouse_x, pyxel.mouse_y

        p_prev, p_mid, p_next = self._filter_row(part_y)
        c_prev, c_mid, c_next = self._filter_row(chap_y)
        draw_button(*p_prev[:3], "<", h=p_prev[3],
                    hover=is_hover(mx, my, *p_prev))
        part_label = self._fit_label(
            f"PART: {self._part_label(self._part_filter)}", p_mid[2] - 12)
        draw_button(*p_mid[:3], part_label,
                    h=p_mid[3], hover=is_hover(mx, my, *p_mid))
        draw_button(*p_next[:3], ">", h=p_next[3],
                    hover=is_hover(mx, my, *p_next))
        draw_button(*c_prev[:3], "<", h=c_prev[3],
                    hover=is_hover(mx, my, *c_prev))
        chapter_label = self._fit_label(
            f"CHAPTER: {self._chapter_label(self._chapter_filter)}",
            c_mid[2] - 12)
        draw_button(*c_mid[:3], chapter_label,
                    h=c_mid[3], hover=is_hover(mx, my, *c_mid))
        draw_button(*c_next[:3], ">", h=c_next[3],
                    hover=is_hover(mx, my, *c_next))

        items = self._scene_items()
        rh = self._row_h()
        pyxel.clip(x, list_top, w, list_bot - list_top)
        for i, (disp, _value) in enumerate(items):
            iy = list_top + i * rh - self._scroll
            if iy + rh <= list_top or iy >= list_bot:
                continue
            sel = i == self._selected
            hover = is_hover(mx, my, x + 4, iy, w - 8, rh)
            draw_list_item(x + 4, iy, w - 8, disp,
                           h=rh, selected=sel, hover=hover and not sel)
        pyxel.clip()

        btn_h = 22
        none_x = x + 4
        cancel_x = x + w - 80 - 4
        count = max(0, len(items) - 1)
        draw_unicode(x + 94, btn_y + 5, f"{count} scenes",
                     EDIT_TEXT_DIM, size=10)
        draw_button(none_x, btn_y, 80, "None", h=btn_h,
                    hover=is_hover(mx, my, none_x, btn_y, 80, btn_h))
        draw_button(cancel_x, btn_y, 80, "Cancel", h=btn_h,
                    hover=is_hover(mx, my, cancel_x, btn_y, 80, btn_h))


_scene_picker   = _ScenePicker()
_ending_picker  = _ListPicker()


def set_file_picker_cache(cache):
    """App から ImageCache を渡す"""
    _file_picker._cache = cache


def set_file_picker_base(base_dir: str):
    """プロジェクトベースディレクトリを設定する"""
    _file_picker._project_base = base_dir


def set_file_picker_settings(settings: dict):
    """画像プレビュー用 per-image palette 構築に必要な settings を注入する。
    `dialog_role_indices` / `speaker_colors` の予約 index を保護するために使う。"""
    _file_picker.set_settings(settings)


def get_file_picker_base() -> str:
    """プロジェクトベースディレクトリを取得する"""
    return _file_picker._project_base or "."


def is_file_picker_active() -> bool:
    """ファイルピッカーまたはシーン/エンディングピッカーがアクティブかどうかを返す"""
    return _file_picker.active or _scene_picker.active or _ending_picker.active


def draw_file_picker():
    """モーダル群を描画する（全パネルの上に重ねて描画）"""
    if _file_picker.active:
        _file_picker.draw()
    if _scene_picker.active:
        _scene_picker.draw()
    if _ending_picker.active:
        _ending_picker.draw()


def open_file_picker(title: str, base_dir: str, mode: str, callback,
                     project_base: str = "", initial_path: str = ""):
    """外部からファイルピッカーを開く。initial_path で既存選択値を渡すと、
    そのファイルにカーソルが合った状態で開く。"""
    _file_picker.open(title, base_dir, mode, callback,
                      project_base=project_base, initial_path=initial_path)


def update_file_picker():
    """外部からアクティブなモーダルを更新する"""
    if _file_picker.active:
        _file_picker.update()
    elif _scene_picker.active:
        _scene_picker.update()
    elif _ending_picker.active:
        _ending_picker.update()
