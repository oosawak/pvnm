"""エンディング編集モーダル: エンディングの作成・編集・削除"""
import copy
import pyxel
import os
from ui.widgets import (
    draw_unicode, draw_field, draw_button, draw_panel,
    _ui_font_size, _font_render_h, is_clicked, is_hover,
    load_pyxel_font, field_h, label_h, title_bar_h, NumericSlider,
    button_w, text_px_w,
)
import ui.widgets as _w
from ui.colors import *
from ui.confirm_dialog import ConfirmDialog

# レイアウト
MARGIN_X = 40
MARGIN_Y = 24
LIST_W = 160
PAD = 8

_FONT_SZ = 12
_DETAIL_SCROLL_GUTTER = 14
_SLIDE_SELECT_W = 32
_SLIDE_SELECT_GAP = 6
_SLIDE_THUMB_W = 72
_SLIDE_THUMB_GAP = 6

# 詳細パネル: 行間/ブロック間の余白
_ROW_GAP   = 6   # 同種フィールド同士の隙間
_BLOCK_GAP = 12  # 概念ブロック (テキスト群 / BGM 群 / SLIDES 群) の境界


def _header_h():
    return _font_render_h(_FONT_SZ) + 6


def _item_h():
    return _font_render_h(_FONT_SZ) + 4


def _btn_h():
    return _font_render_h(_FONT_SZ) + 4


class EndingEditor:
    """エンディング一覧の編集モーダル。"""

    def __init__(self):
        self.active = False
        self.result = None  # "saved" | "cancelled" | None
        # PREVIEW ボタン押下時に「再生したいエンディング dict」をここに積む。
        # 外側 (main.py) が拾って _start_ending_play() を呼び、終了後に
        # エディタへ戻る (`active` は維持されたままなのでそのまま再開できる)。
        self.preview_request: "dict | None" = None
        # PREVIEW 開始秒 (BGM のシーク開始位置)。曲の途中から確認したい時に使う。
        self.preview_start_sec: float = 0.0
        # main.py が拾うべき値とペアにして送る用
        self.preview_start_for_request: float = 0.0
        self._endings: list[dict] = []
        self._selected = 0
        self._scroll = 0
        self._font = None
        self._detail_scroll = 0   # 右ペイン全体のスクロール量
        self._pending_slide_idx = -1
        self._selected_slide_idx = -1
        self._last_captured_time: float | None = None
        self._sliders: dict = {}   # キー → NumericSlider
        self._saved_endings: list[dict] = []
        self._discard_confirm = ConfirmDialog()
        self._cache = None

    def _get_slider(self, key: str, lo: float, hi: float,
                    step: float, is_float: bool = True) -> NumericSlider:
        if key not in self._sliders:
            self._sliders[key] = NumericSlider(lo, hi, step, is_float)
        return self._sliders[key]

    def set_cache(self, cache) -> None:
        self._cache = cache

    @staticmethod
    def _basename(p: str) -> str:
        if not p:
            return ""
        return os.path.basename(p)

    def open(self, endings: list[dict]):
        self.active = True
        self.result = None
        self._endings = copy.deepcopy(endings)
        self._sort_all_slides_by_time()
        self._saved_endings = copy.deepcopy(self._endings)
        self._selected = 0 if endings else -1
        self._scroll = 0
        self._detail_scroll = 0
        self._selected_slide_idx = self._initial_slide_index()
        self._last_captured_time = None

    def get_endings(self) -> list[dict]:
        self._sort_all_slides_by_time()
        return self._endings

    def find_ending_by_name(self, name: str) -> dict | None:
        """Return a copy of the current draft ending by name."""
        if not name:
            return None
        self._sort_all_slides_by_time()
        for ending in self._endings:
            if ending.get("name", "") == name:
                return copy.deepcopy(ending)
        return None

    def _dirty(self) -> bool:
        return self._endings != self._saved_endings

    def _finish_cancelled(self) -> None:
        self._endings = copy.deepcopy(self._saved_endings)
        self.result = "cancelled"
        self.active = False

    def _request_cancel(self) -> None:
        if self._dirty():
            self._discard_confirm.open(
                "UNSAVED CHANGES",
                "Ending config has unsaved edits.\n"
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

    def _initial_slide_index(self) -> int:
        if 0 <= self._selected < len(self._endings):
            slides = self._endings[self._selected].get("slides", [])
            if slides:
                return 0
        return -1

    def _clamp_selected_slide(self) -> None:
        if not (0 <= self._selected < len(self._endings)):
            self._selected_slide_idx = -1
            return
        slides = self._endings[self._selected].get("slides", [])
        if not slides:
            self._selected_slide_idx = -1
            return
        if not (0 <= self._selected_slide_idx < len(slides)):
            self._selected_slide_idx = min(max(0, self._selected_slide_idx),
                                           len(slides) - 1)

    @staticmethod
    def _slide_time(slide: dict) -> float:
        try:
            return max(0.0, float(slide.get("time", 0.0) or 0.0))
        except (TypeError, ValueError):
            return 0.0

    def _sort_slides_by_time(self, ending: dict | None = None,
                             selected_slide: dict | None = None) -> None:
        """Keep ending slides ordered by TIME while preserving selection."""
        if ending is None:
            if not (0 <= self._selected < len(self._endings)):
                return
            ending = self._endings[self._selected]
        slides = ending.get("slides", [])
        if len(slides) < 2:
            self._clamp_selected_slide()
            return
        selected_obj = selected_slide
        if selected_obj is None and 0 <= self._selected_slide_idx < len(slides):
            selected_obj = slides[self._selected_slide_idx]
        indexed = list(enumerate(slides))
        indexed.sort(key=lambda pair: (self._slide_time(pair[1]), pair[0]))
        slides[:] = [slide for _, slide in indexed]
        if selected_obj is not None:
            for i, slide in enumerate(slides):
                if slide is selected_obj:
                    self._selected_slide_idx = i
                    break
        self._clamp_selected_slide()

    def _sort_all_slides_by_time(self) -> None:
        for ending in self._endings:
            slides = ending.get("slides", [])
            if len(slides) < 2:
                continue
            indexed = list(enumerate(slides))
            indexed.sort(key=lambda pair: (self._slide_time(pair[1]), pair[0]))
            slides[:] = [slide for _, slide in indexed]

    def capture_preview_time(self, sec: float) -> bool:
        """PREVIEWをESCで抜けた時刻を一時確保する。"""
        t = round(max(0.0, float(sec)), 2)
        self._last_captured_time = t
        return True

    def apply_captured_time_to_slide(self) -> bool:
        """一時確保したPREVIEW時刻を、選択中スライドのTIMEへ反映する。"""
        if self._last_captured_time is None:
            return False
        if not (0 <= self._selected < len(self._endings)):
            return False
        slides = self._endings[self._selected].get("slides", [])
        if not (0 <= self._selected_slide_idx < len(slides)):
            return False
        slide = slides[self._selected_slide_idx]
        t = round(max(0.0, float(self._last_captured_time)), 2)
        slide["time"] = t
        self.preview_start_sec = t
        self._last_captured_time = None
        self._sort_slides_by_time(selected_slide=slide)
        return True

    def clear_captured_time(self) -> None:
        self._last_captured_time = None

    def _captured_time_label(self) -> str:
        if self._last_captured_time is None:
            return ""
        return f"CAP:{self._format_time(self._last_captured_time)}"

    def _request_preview(self, start_sec: float) -> None:
        """現在選択中エンディングのプレビューを指定秒から開始する。"""
        if not (0 <= self._selected < len(self._endings)):
            return
        start = max(0.0, float(start_sec or 0.0))
        self.preview_request = copy.deepcopy(self._endings[self._selected])
        self.preview_start_sec = start
        self.preview_start_for_request = start

    def _request_slide_preview(self, slide_idx: int) -> None:
        """指定スライドのTIMEからプレビューを開始する。"""
        if not (0 <= self._selected < len(self._endings)):
            return
        slides = self._endings[self._selected].get("slides", [])
        if not (0 <= slide_idx < len(slides)):
            return
        self._selected_slide_idx = slide_idx
        self._request_preview(float(slides[slide_idx].get("time", 0.0) or 0.0))

    def update(self):
        if not self.active:
            return
        if self._update_discard_confirm():
            return

        mx, my = pyxel.mouse_x, pyxel.mouse_y
        W, H = pyxel.width, pyxel.height
        px, py = MARGIN_X, MARGIN_Y
        pw = W - MARGIN_X * 2
        ph = H - MARGIN_Y * 2
        hh = _header_h()
        ih = _item_h()
        bh = _btn_h()

        # ESCでキャンセル
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self._request_cancel()
            return

        # Ctrl+Sで保存
        if (pyxel.btn(pyxel.KEY_CTRL) or pyxel.btn(pyxel.KEY_GUI)) and pyxel.btnp(pyxel.KEY_S):
            self.result = "saved"
            self.active = False
            return

        # リスト領域
        list_x = px + PAD
        list_y = py + hh + PAD
        list_h = ph - hh - PAD * 2 - bh - 6

        for i in range(len(self._endings)):
            iy = list_y + i * ih - self._scroll
            if list_y <= iy < list_y + list_h:
                if is_clicked(mx, my, list_x, iy, LIST_W - 10, ih):
                    self._selected = i
                    self._detail_scroll = 0
                    self._selected_slide_idx = self._initial_slide_index()
                    self._last_captured_time = None

        if list_x <= mx < list_x + LIST_W and list_y <= my < list_y + list_h:
            wheel = pyxel.mouse_wheel
            if wheel != 0:
                self._scroll -= wheel * 16
                max_scroll = max(0, len(self._endings) * ih - list_h)
                self._scroll = max(0, min(self._scroll, max_scroll))

        # ボタン行
        btn_y = py + ph - bh - 4
        add_w = max(42, button_w("ADD"))
        copy_w = max(52, button_w("COPY"))
        del_w = max(42, button_w("DEL"))
        save_w = max(58, button_w("SAVE"))
        cancel_w = max(58, button_w("CANCEL"))
        preview_w = max(72, button_w("PREVIEW"))
        # 「FROM:M:SS.ff」ボタン (PREVIEW の左、preview_start_sec を編集)
        pfrom_lbl = f"FROM:{self._format_time(self.preview_start_sec)}"
        pfrom_w = max(80, button_w(pfrom_lbl))
        if is_clicked(mx, my, list_x, btn_y, add_w, bh):
            self._add_ending()
        copy_x = list_x + add_w + 6
        del_x = copy_x + copy_w + 6
        if is_clicked(mx, my, copy_x, btn_y, copy_w, bh):
            self._copy_ending()
        if is_clicked(mx, my, del_x, btn_y, del_w, bh):
            self._del_ending()

        cancel_x = px + pw - PAD - cancel_w
        save_x = cancel_x - 4 - save_w
        preview_x = save_x - 8 - preview_w
        pfrom_x = preview_x - 4 - pfrom_w
        # PREVIEW FROM 時刻入力 (クリックで _native_ask)
        if is_clicked(mx, my, pfrom_x, btn_y, pfrom_w, bh):
            self._edit_preview_start()
            return
        # PREVIEW: 現在選択中のエンディングを再生 (エディタはそのまま維持)
        if is_clicked(mx, my, preview_x, btn_y, preview_w, bh):
            self._request_preview(self.preview_start_sec)
            return
        if is_clicked(mx, my, save_x, btn_y, save_w, bh):
            self.result = "saved"
            self.active = False
            return
        if is_clicked(mx, my, cancel_x, btn_y, cancel_w, bh):
            self._request_cancel()
            return

        # 右側: 詳細フィールド
        if 0 <= self._selected < len(self._endings):
            self._clamp_selected_slide()
            self._update_detail(px, py, pw, ph, list_y, mx, my)

    def _row_ys(self, fh: int, bh: int) -> dict:
        """詳細パネル各行のコンテンツ相対 y 座標 (上端=0)。

        スクリーン座標は呼び出し側で `list_y + ys[...] - _detail_scroll` に
        変換する。update / draw が同じレイアウトを共有するためのヘルパー。
        """
        ys: dict = {}
        y = 0
        ys["name"] = y;          y += fh + _ROW_GAP
        ys["credits"] = y;       y += fh + _ROW_GAP
        ys["font_size"] = y;     y += fh + _ROW_GAP
        ys["scroll_speed"] = y;  y += fh + _BLOCK_GAP
        ys["bgm_file"] = y;      y += bh + _ROW_GAP
        ys["bgm_volume"] = y;    y += fh + _ROW_GAP
        ys["bgm_loop"] = y;      y += bh + _ROW_GAP
        # 次のエンディングへの遷移先 (チェーン用、空文字=遷移なし)
        ys["goto_ending"] = y;   y += bh + _BLOCK_GAP
        ys["slides_label"] = y;  y += _font_render_h(_FONT_SZ) + 4
        ys["slides_buttons"] = y; y += bh + _ROW_GAP
        ys["slide_list"] = y
        return ys

    def _detail_geom(self, px, py, pw, ph):
        """右ペイン (詳細) の表示領域 (x, y, w, h) を返す。"""
        hh = _header_h()
        bh = _btn_h()
        detail_x = px + PAD + LIST_W + PAD
        detail_y = py + hh + PAD
        detail_w = pw - LIST_W - PAD * 3
        btn_y = py + ph - bh - 4
        detail_h = max(0, btn_y - detail_y - 4)
        return detail_x, detail_y, detail_w, detail_h

    @staticmethod
    def _detail_content_w(detail_w: int) -> int:
        """右ペイン内でスクロールバーと被らない実コンテンツ幅。"""
        return max(1, detail_w - _DETAIL_SCROLL_GUTTER)

    def _content_h(self, ending: dict, fh: int, bh: int) -> int:
        """詳細コンテンツ全体の高さ。スクロール上限計算に使う。"""
        ys = self._row_ys(fh, bh)
        slides = ending.get("slides", [])
        # スライド1件あたり 2 行 (画像+TIME、エフェクト+EFFECT_DUR+legacy DUR)
        slide_pitch = (fh * 2) + _ROW_GAP * 2
        return ys["slide_list"] + len(slides) * slide_pitch + 4

    def _update_detail(self, px, py, pw, ph, list_y, mx, my):
        fh = field_h()
        lh = label_h()
        bh = _btn_h()
        right_clicked = pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT)
        ending = self._endings[self._selected]
        ys = self._row_ys(fh, bh)

        detail_x, detail_y, detail_w, detail_h = self._detail_geom(
            px, py, pw, ph)
        content_w = self._detail_content_w(detail_w)

        # ホイールスクロール (ペイン全域)
        if (detail_x <= mx < detail_x + detail_w and
                detail_y <= my < detail_y + detail_h):
            wheel = pyxel.mouse_wheel
            if wheel != 0:
                self._detail_scroll -= wheel * 16
            content_h = self._content_h(ending, fh, bh)
            max_ss = max(0, content_h - detail_h)
            self._detail_scroll = max(0, min(self._detail_scroll, max_ss))

        off = -self._detail_scroll

        def _in_pane(y, h):
            return detail_y <= y + h and y < detail_y + detail_h

        # NAME / CREDITS / FONT SIZE: クリックでダイアログ
        for fname in ("name", "credits", "font_size"):
            fy = detail_y + ys[fname] + off
            if not _in_pane(fy, fh):
                continue
            if is_clicked(mx, my, detail_x, fy + lh, content_w, fh - lh):
                self._open_text_input(fname)

        # SCROLL SPEED: スライダー
        ss_y = detail_y + ys["scroll_speed"] + off
        if _in_pane(ss_y, fh):
            sl_ss = self._get_slider(f"ending:{self._selected}:scroll_speed",
                                     0.1, 10.0, 0.1, True)
            nv = sl_ss.handle(detail_x, ss_y, content_w, fh, mx, my,
                              float(ending.get("scroll_speed", 1.0)))
            if nv is not None:
                ending["scroll_speed"] = float(nv)

        # BGM FILE: ボタン
        bgm_y = detail_y + ys["bgm_file"] + off
        if _in_pane(bgm_y, bh):
            if is_clicked(mx, my, detail_x, bgm_y, content_w, bh):
                self._pick_bgm_file()
            elif right_clicked and is_hover(mx, my, detail_x, bgm_y,
                                            content_w, bh):
                ending["bgm_file"] = ""

        # BGM VOLUME: スライダー
        bv_y = detail_y + ys["bgm_volume"] + off
        if _in_pane(bv_y, fh):
            sl_bv = self._get_slider(f"ending:{self._selected}:bgm_volume",
                                     1, 10, 1, False)
            nv_bv = sl_bv.handle(detail_x, bv_y, content_w, fh,
                                 mx, my, int(ending.get("bgm_volume", 7)))
            if nv_bv is not None:
                ending["bgm_volume"] = int(nv_bv)

        # BGM LOOP: チェックボックス。デフォルトは False (ループしない)。
        loop_y = detail_y + ys["bgm_loop"] + off
        loop_on = bool(ending.get("bgm_loop", False))
        loop_lbl = ("[X] BGM LOOP" if loop_on else "[ ] BGM LOOP")
        loop_w = max(80, text_px_w(loop_lbl, _ui_font_size) + 14)
        if _in_pane(loop_y, bh):
            if is_clicked(mx, my, detail_x, loop_y, loop_w, bh):
                ending["bgm_loop"] = not loop_on

        # GOTO ENDING: 次のエンディングへ遷移する設定。
        # クリックで _ending_picker を開く (現在の ending を除いたリスト)。
        ge_y = detail_y + ys["goto_ending"] + off
        if _in_pane(ge_y, bh):
            if is_clicked(mx, my, detail_x, ge_y, content_w, bh):
                self._pick_goto_ending()

        # スライド操作ボタン (sticky 化: 詳細パネル上端へ吸着)
        # スライド数が多くて自然位置が画面外に流れても上端に張り付くので、
        # スクロール途中でも ADD/DEL に常時アクセスできる。
        slides_y_natural = detail_y + ys["slides_buttons"] + off
        slides_y = max(detail_y + 2, slides_y_natural)
        is_sticky = slides_y > slides_y_natural
        as_w = max(70, button_w("ADD SLIDE"))
        ds_w = max(70, button_w("DEL SLIDE"))
        # ADD/DEL は常時クリック可能 (詳細パネル内なので _in_pane 不要)
        if is_clicked(mx, my, detail_x, slides_y, as_w, bh):
            self._add_slide()
            return
        if is_clicked(mx, my, detail_x + as_w + 6, slides_y, ds_w, bh):
            self._del_slide()
            return
        apply_lbl = "APPLY TIME"
        apply_w = max(86, button_w(apply_lbl))
        clear_lbl = "CLEAR CAP"
        clear_w = max(80, button_w(clear_lbl))
        apply_x = detail_x + as_w + 6 + ds_w + 8
        clear_x = apply_x + apply_w + 6
        if (self._last_captured_time is not None
                and is_clicked(mx, my, apply_x, slides_y, apply_w, bh)):
            self.apply_captured_time_to_slide()
            return
        if (self._last_captured_time is not None
                and is_clicked(mx, my, clear_x, slides_y, clear_w, bh)):
            self.clear_captured_time()
            return
        # Sticky bar 内 (ボタンの隙間) への誤クリックは下のスライドリストへ
        # 届かせない (バー裏のスライド行が反応しないように)
        if is_sticky and slides_y <= my < slides_y + bh:
            return

        # スライドリスト (各スライド 2 行レイアウト)
        slide_list_y0 = detail_y + ys["slide_list"] + off
        slides = ending.get("slides", [])
        slide_pitch = (fh * 2) + _ROW_GAP * 2
        # 行内の幅配分 (content_w 基準。右端スクロールバー用の溝を残す)
        body_x = detail_x + _SLIDE_SELECT_W + _SLIDE_SELECT_GAP
        body_w = max(60, content_w - _SLIDE_SELECT_W - _SLIDE_SELECT_GAP)
        thumb_w = min(_SLIDE_THUMB_W, max(48, body_w // 5))
        controls_x = body_x + thumb_w + _SLIDE_THUMB_GAP
        controls_w = max(60, body_w - thumb_w - _SLIDE_THUMB_GAP)
        time_w  = 110
        preview_w = max(68, button_w("PREVIEW"))
        eff_w   = 70
        edur_w  = 104
        dur_w   = max(76, controls_w - preview_w - eff_w - edur_w - 12)
        for si, slide in enumerate(slides):
            sy_a = slide_list_y0 + si * slide_pitch          # 行 A
            sy_b = sy_a + fh + _ROW_GAP                       # 行 B
            row_h = fh * 2 + _ROW_GAP
            if (_in_pane(sy_a, row_h)
                    and (pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) or right_clicked)
                    and detail_x <= mx < detail_x + _SLIDE_SELECT_W
                    and sy_a <= my < sy_a + row_h):
                self._selected_slide_idx = si
                return
            if _in_pane(sy_a, row_h):
                if is_clicked(mx, my, body_x, sy_a, thumb_w, row_h):
                    self._edit_slide_image(si)
                    return
                elif right_clicked and is_hover(mx, my, body_x, sy_a,
                                                thumb_w, row_h):
                    slide["image"] = ""
                    return
            # 行 A: IMAGE | TIME (クリックで入力ダイアログ)
            if _in_pane(sy_a, fh):
                img_w = max(60, controls_w - time_w - 4)
                if is_clicked(mx, my, controls_x, sy_a, img_w, fh):
                    self._edit_slide_image(si)
                elif right_clicked and is_hover(mx, my, controls_x, sy_a,
                                                img_w, fh):
                    slide["image"] = ""
                # TIME (秒): タイムライン同期。クリックで _native_ask を開く。
                # スライダーだと小数点以下の細かい調整が辛いので入力式。
                time_x = controls_x + img_w + 4
                if is_clicked(mx, my, time_x, sy_a, time_w, fh):
                    self._edit_slide_time(si)
            # 行 B: PREVIEW | EFFECT | EFFECT_DUR | DUR
            if _in_pane(sy_b, fh):
                if is_clicked(mx, my, controls_x, sy_b, preview_w, fh):
                    self._request_slide_preview(si)
                    return
                eff_x = controls_x + preview_w + 4
                # EFFECT 切替ボタン (左クリックで cut→fade→zoom→cut の循環)
                if is_clicked(mx, my, eff_x, sy_b, eff_w, fh):
                    cur_eff = slide.get("effect", "fade")
                    cycle = ["cut", "fade", "zoom"]
                    nxt = cycle[(cycle.index(cur_eff) + 1) % len(cycle)] if cur_eff in cycle else "fade"
                    slide["effect"] = nxt
                # EFFECT_DURATION
                edur_x = eff_x + eff_w + 4
                if is_clicked(mx, my, edur_x, sy_b, edur_w, fh):
                    self._edit_slide_effect_duration(si)
                    return
                # DUR (legacy / time 未設定時のフォールバック)
                dur_x = edur_x + edur_w + 4
                if is_clicked(mx, my, dur_x, sy_b, dur_w, fh):
                    self._edit_slide_duration(si)
                    return

    def _add_ending(self):
        idx = len(self._endings) + 1
        self._endings.append({
            "name": f"Ending {idx}",
            "slides": [],
            "credits": "",
            "font_file": "",
            "font_size": 14,
            "scroll_speed": 1.0,
            "bgm_file": "",
            "bgm_volume": 7,
            # 既定はループ無し: エンディングは曲一回再生で終了するのが自然。
            # 連続再生やループを意図する場合は [X] BGM LOOP をオンにする。
            "bgm_loop": False,
            # 次のエンディングへの遷移先 (空=遷移なし)。
            # 例: キャラ回想 (E1) → スタッフロール (E2)
            "goto_ending": "",
        })
        self._selected = len(self._endings) - 1
        self._selected_slide_idx = self._initial_slide_index()

    def _copy_ending(self):
        if not (0 <= self._selected < len(self._endings)):
            return
        src = copy.deepcopy(self._endings[self._selected])
        src["name"] = self._unique_copy_name(str(src.get("name", "") or "Ending"))
        self._endings.insert(self._selected + 1, src)
        self._selected += 1
        self._detail_scroll = 0
        self._selected_slide_idx = self._initial_slide_index()
        self._last_captured_time = None

    def _del_ending(self):
        if 0 <= self._selected < len(self._endings):
            self._endings.pop(self._selected)
            if self._selected >= len(self._endings):
                self._selected = len(self._endings) - 1
            self._selected_slide_idx = self._initial_slide_index()

    def _unique_copy_name(self, base_name: str) -> str:
        names = {
            str(ending.get("name", "") or "")
            for ending in self._endings
        }
        base = base_name.strip() or "Ending"
        candidate = f"{base} Copy"
        if candidate not in names:
            return candidate
        i = 2
        while True:
            candidate = f"{base} Copy {i}"
            if candidate not in names:
                return candidate
            i += 1

    def _add_slide(self):
        if 0 <= self._selected < len(self._endings):
            slides = self._endings[self._selected].setdefault("slides", [])
            self._sort_slides_by_time()
            # 直前のスライドの time + effect_dur + duration を新スライドの time
            # にして自然なタイムライン初期値にする (= sequential 風)
            if slides:
                last = slides[-1]
                next_time = float(last.get("time", 0.0) or 0.0) \
                    + float(last.get("effect_duration", 1.0) or 1.0) \
                    + float(last.get("duration", 3.0) or 3.0)
            else:
                next_time = 0.0
            slides.append({
                "image": "",
                "time": float(next_time),
                "effect": "fade",
                "effect_duration": 1.0,
                "duration": 3.0,
            })
            self._sort_slides_by_time(selected_slide=slides[-1])

    def _del_slide(self):
        if 0 <= self._selected < len(self._endings):
            slides = self._endings[self._selected].get("slides", [])
            if slides:
                slides.pop()
                self._clamp_selected_slide()

    def _pick_bgm_file(self):
        if self._selected < 0 or self._selected >= len(self._endings):
            return
        from ui.panels import open_file_picker, get_file_picker_base
        import os as _os
        base = get_file_picker_base()
        scan_dir = _os.path.join(base, "assets", "sounds", "bgm")
        if not _os.path.isdir(scan_dir):
            scan_dir = base
        initial_path = self._endings[self._selected].get("bgm_file", "")
        open_file_picker("ENDING BGM", scan_dir, "audio",
                         self._on_bgm_selected, project_base=base,
                         initial_path=initial_path)

    def _pick_goto_ending(self):
        """このエンディング終了後に遷移する次のエンディングを選択する。"""
        if self._selected < 0 or self._selected >= len(self._endings):
            return
        cur = self._endings[self._selected]
        cur_name = cur.get("name", "")
        # 候補リスト = (none) + 自分以外の全エンディング
        items = [("(none)", "")]
        for e in self._endings:
            nm = e.get("name", "")
            if nm and nm != cur_name:
                items.append((nm, nm))
        from ui.panels import _ending_picker
        def _cb(val: str, e=cur):
            e["goto_ending"] = val
        _ending_picker.open("GOTO ENDING", items,
                            cur.get("goto_ending", ""), _cb)

    def _on_bgm_selected(self, path: str):
        if 0 <= self._selected < len(self._endings):
            stored = path
            if path and not os.path.isabs(path) and not path.startswith("."):
                stored = "./assets/sounds/bgm/" + path
            self._endings[self._selected]["bgm_file"] = stored

    def _edit_slide_image(self, slide_idx: int):
        if self._selected < 0:
            return
        ending = self._endings[self._selected]
        slides = ending.get("slides", [])
        if slide_idx >= len(slides):
            return
        self._pending_slide_idx = slide_idx
        from ui.panels import open_file_picker, get_file_picker_base
        base = get_file_picker_base()
        scan_dir = base
        open_file_picker("SLIDE IMAGE", scan_dir, "image",
                         self._on_slide_image_selected,
                         project_base=base,
                         initial_path=slides[slide_idx].get("image", ""))

    def _on_slide_image_selected(self, path: str):
        si = self._pending_slide_idx
        if 0 <= self._selected < len(self._endings):
            slides = self._endings[self._selected].get("slides", [])
            if 0 <= si < len(slides):
                slides[si]["image"] = path
        self._pending_slide_idx = -1

    @staticmethod
    def _format_time(sec: float) -> str:
        """秒数を "M:SS.ff" または "S.ff" 形式に整形 (表示用)。"""
        try:
            v = max(0.0, float(sec))
        except (TypeError, ValueError):
            v = 0.0
        m = int(v // 60)
        s = v - m * 60
        if m > 0:
            return f"{m}:{s:05.2f}"   # 例: "1:23.45"
        return f"{s:.2f}"             # 例: "10.50"

    @staticmethod
    def _parse_time(text: str) -> "float | None":
        """\"M:SS.ff\" / \"M:S\" / \"S.ff\" のいずれかを秒数に変換。
        パース不能なら None。"""
        if text is None:
            return None
        s = str(text).strip()
        if not s:
            return None
        try:
            if ":" in s:
                m_str, s_str = s.split(":", 1)
                return float(m_str) * 60.0 + float(s_str)
            return float(s)
        except ValueError:
            return None

    def _edit_preview_start(self):
        """PREVIEW FROM (秒) をテキスト入力ダイアログで編集する。"""
        from ui.native_dialogs import ask_text as _native_ask
        result = _native_ask("PREVIEW FROM  (M:SS.ff or seconds)",
                             self._format_time(self.preview_start_sec))
        if result is None:
            return
        parsed = self._parse_time(result)
        if parsed is None:
            return
        self.preview_start_sec = max(0.0, float(parsed))

    def _edit_slide_time(self, slide_idx: int):
        """スライドの TIME (タイムライン同期秒) をテキスト入力で編集。"""
        if self._selected < 0:
            return
        slides = self._endings[self._selected].get("slides", [])
        if not (0 <= slide_idx < len(slides)):
            return
        from ui.native_dialogs import ask_text as _native_ask
        cur_sec = float(slides[slide_idx].get("time", 0.0) or 0.0)
        result = _native_ask("TIME  (M:SS.ff or seconds)",
                             self._format_time(cur_sec))
        if result is None:
            return
        parsed = self._parse_time(result)
        if parsed is None:
            return
        slide = slides[slide_idx]
        slide["time"] = max(0.0, float(parsed))
        self._sort_slides_by_time(selected_slide=slide)

    def _edit_slide_float(self, slide_idx: int, key: str, title: str,
                          default: float = 0.0) -> None:
        if self._selected < 0:
            return
        slides = self._endings[self._selected].get("slides", [])
        if not (0 <= slide_idx < len(slides)):
            return
        from ui.native_dialogs import ask_text as _native_ask
        try:
            cur = float(slides[slide_idx].get(key, default) or default)
        except (TypeError, ValueError):
            cur = float(default)
        result = _native_ask(title, f"{cur:.2f}")
        if result is None:
            return
        try:
            slides[slide_idx][key] = max(0.0, float(str(result).strip()))
        except ValueError:
            pass

    def _edit_slide_effect_duration(self, slide_idx: int):
        self._edit_slide_float(slide_idx, "effect_duration",
                               "EFFECT DURATION (sec)", 1.0)

    def _edit_slide_duration(self, slide_idx: int):
        self._edit_slide_float(slide_idx, "duration", "DURATION (sec)", 3.0)

    def _open_text_input(self, field: str):
        if self._selected < 0 or self._selected >= len(self._endings):
            return
        ending = self._endings[self._selected]
        current = str(ending.get(field, ""))

        if field == "credits":
            from ui.native_dialogs import ask_multiline
            result = ask_multiline("CREDITS", current)
        else:
            from ui.native_dialogs import ask_text as _native_ask
            result = _native_ask(field.upper(), current)

        if result is not None:
            if field == "font_size":
                try:
                    ending[field] = int(result)
                except ValueError:
                    pass
            elif field == "scroll_speed":
                try:
                    ending[field] = float(result)
                except ValueError:
                    pass
            else:
                ending[field] = result

    def draw(self):
        if not self.active:
            return

        W, H = pyxel.width, pyxel.height
        px, py = MARGIN_X, MARGIN_Y
        pw = W - MARGIN_X * 2
        ph = H - MARGIN_Y * 2
        hh = _header_h()
        ih = _item_h()
        bh = _btn_h()
        frh = _font_render_h(_FONT_SZ)

        draw_panel(px, py, pw, ph, bg=EDIT_PANEL, border=EDIT_BORDER)

        # ヘッダ
        pyxel.rect(px + 1, py + 1, pw - 2, hh - 2, EDIT_TITLE_BG)
        self._draw_text(px + 8, py + max(1, (hh - frh) // 2),
                        "ENDING CONFIG  (Ctrl+S=Save, ESC=Cancel)", EDIT_TEXT)

        list_x = px + PAD
        list_y = py + hh + PAD
        list_h = ph - hh - PAD * 2 - bh - 6

        # リスト背景
        pyxel.rect(list_x, list_y, LIST_W, list_h, EDIT_BG)
        pyxel.rectb(list_x, list_y, LIST_W, list_h, EDIT_BORDER)

        # リスト項目
        pyxel.clip(list_x, list_y, LIST_W, list_h)
        for i, end in enumerate(self._endings):
            iy = list_y + i * ih - self._scroll
            if iy + ih < list_y or iy > list_y + list_h:
                continue
            sel = (i == self._selected)
            bg = EDIT_ACCENT if sel else EDIT_BG
            pyxel.rect(list_x + 1, iy, LIST_W - 2, ih - 1, bg)
            fg = EDIT_BG if sel else EDIT_TEXT_DIM
            name = end.get("name", f"Ending {i+1}")
            ty = iy + max(1, (ih - frh) // 2)
            self._draw_text(list_x + 6, ty, name[:18], fg)
        pyxel.clip()

        # ボタン行
        btn_y = py + ph - bh - 4
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        add_w = max(42, button_w("ADD"))
        copy_w = max(52, button_w("COPY"))
        del_w = max(42, button_w("DEL"))
        save_w = max(58, button_w("SAVE"))
        cancel_w = max(58, button_w("CANCEL"))

        ah = is_hover(mx, my, list_x, btn_y, add_w, bh)
        draw_button(list_x, btn_y, add_w, "ADD", h=bh, hover=ah)
        copy_x = list_x + add_w + 6
        cph = is_hover(mx, my, copy_x, btn_y, copy_w, bh)
        draw_button(copy_x, btn_y, copy_w, "COPY", h=bh, hover=cph)
        del_x = copy_x + copy_w + 6
        dh = is_hover(mx, my, del_x, btn_y, del_w, bh)
        draw_button(del_x, btn_y, del_w, "DEL", h=bh, hover=dh)

        cancel_x = px + pw - PAD - cancel_w
        save_x = cancel_x - 4 - save_w
        preview_w = max(72, button_w("PREVIEW"))
        preview_x = save_x - 8 - preview_w
        pfrom_lbl = f"FROM:{self._format_time(self.preview_start_sec)}"
        pfrom_w = max(80, button_w(pfrom_lbl))
        pfrom_x = preview_x - 4 - pfrom_w
        fmh = is_hover(mx, my, pfrom_x, btn_y, pfrom_w, bh)
        draw_button(pfrom_x, btn_y, pfrom_w, pfrom_lbl, h=bh, hover=fmh)
        pvh = is_hover(mx, my, preview_x, btn_y, preview_w, bh)
        # 選択中のエンディングがない時はディム表示にしたいところだが、
        # ボタン側は変更せず main 側で no-op として処理する。
        draw_button(preview_x, btn_y, preview_w, "PREVIEW", h=bh, hover=pvh)
        svh = is_hover(mx, my, save_x, btn_y, save_w, bh)
        draw_button(save_x, btn_y, save_w, "SAVE", h=bh, hover=svh)
        cnh = is_hover(mx, my, cancel_x, btn_y, cancel_w, bh)
        draw_button(cancel_x, btn_y, cancel_w, "CANCEL", h=bh, hover=cnh)

        # 右側: 詳細
        if 0 <= self._selected < len(self._endings):
            self._clamp_selected_slide()
            self._draw_detail(px, py, pw, ph, list_y, mx, my)
        self._discard_confirm.draw()

    def _draw_detail(self, px, py, pw, ph, list_y, mx, my):
        ending = self._endings[self._selected]
        fh = field_h()
        lh = label_h()
        bh = _btn_h()
        ys = self._row_ys(fh, bh)

        detail_x, detail_y, detail_w, detail_h = self._detail_geom(
            px, py, pw, ph)
        content_w = self._detail_content_w(detail_w)

        # スクロール上限を再クランプ (リサイズや項目数変化に追従)
        content_h = self._content_h(ending, fh, bh)
        max_ss = max(0, content_h - detail_h)
        self._detail_scroll = max(0, min(self._detail_scroll, max_ss))
        off = -self._detail_scroll

        pyxel.clip(detail_x, detail_y, detail_w, detail_h)

        # NAME / CREDITS / FONT SIZE
        for label, key in [("NAME", "name"),
                           ("CREDITS", "credits"),
                           ("FONT SIZE", "font_size")]:
            fy = detail_y + ys[key] + off
            val = str(ending.get(key, ""))
            if key == "credits":
                first_line = val.split("\n")[0]
                val = first_line[:30] + (
                    "..." if "\n" in val or len(first_line) > 30 else "")
            draw_field(detail_x, fy, content_w, label, val, h=fh, label_h=lh)

        # SCROLL SPEED (slider)
        sl_ss = self._get_slider(f"ending:{self._selected}:scroll_speed",
                                 0.1, 10.0, 0.1, True)
        sl_ss.draw(detail_x, detail_y + ys["scroll_speed"] + off,
                   content_w, fh, "SCROLL SPEED",
                   float(ending.get("scroll_speed", 1.0)),
                   label_h=lh)

        # BGM FILE ボタン
        bgm_y = detail_y + ys["bgm_file"] + off
        bgm_path = ending.get("bgm_file", "")
        bgm_name = self._basename(bgm_path) if bgm_path else ""
        bgm_lbl = (f"[BACKGROUND MUSIC]:{bgm_name}" if bgm_name
                   else "[BACKGROUND MUSIC]")
        draw_button(detail_x, bgm_y, content_w, bgm_lbl, h=bh,
                    hover=is_hover(mx, my, detail_x, bgm_y, content_w, bh))

        # BGM VOLUME スライダー
        sl_bv = self._get_slider(f"ending:{self._selected}:bgm_volume",
                                 1, 10, 1, False)
        sl_bv.draw(detail_x, detail_y + ys["bgm_volume"] + off,
                   content_w, fh, "BACKGROUND MUSIC VOLUME",
                   int(ending.get("bgm_volume", 7)),
                   label_h=lh)

        # BGM LOOP チェックボックス (デフォルト False)
        loop_y = detail_y + ys["bgm_loop"] + off
        loop_on = bool(ending.get("bgm_loop", False))
        loop_lbl = ("[X] BGM LOOP" if loop_on else "[ ] BGM LOOP")
        loop_w = max(80, text_px_w(loop_lbl, _ui_font_size) + 14)
        draw_button(detail_x, loop_y, loop_w, loop_lbl, h=bh,
                    active=loop_on,
                    hover=is_hover(mx, my, detail_x, loop_y, loop_w, bh))

        # GOTO ENDING: 自然終了時に次のエンディングへチェーンする (空=チェーン無し)
        ge_y = detail_y + ys["goto_ending"] + off
        ge_target = str(ending.get("goto_ending", "") or "")
        ge_label = (f"[GOTO ENDING]:{ge_target}" if ge_target
                    else "[GOTO ENDING]:(none)")
        draw_button(detail_x, ge_y, content_w, ge_label, h=bh,
                    hover=is_hover(mx, my, detail_x, ge_y, content_w, bh))

        # スライド (ラベル: スクロール対象。バッジ + 件数のみ)
        slides = ending.get("slides", [])
        sync_label = ""
        if 0 <= self._selected_slide_idx < len(slides):
            sync_label = f"  SYNC:{self._selected_slide_idx + 1}"
        if self._last_captured_time is not None:
            sync_label += f"  CAP:{self._format_time(self._last_captured_time)}"
        self._draw_text(detail_x, detail_y + ys["slides_label"] + off,
                        f"SLIDES ({len(slides)}){sync_label}", EDIT_TEXT_DIM)

        # ADD/DEL SLIDE ボタンは sticky 描画 (後でクリップ外に再描画する) ので
        # ここでは描かない。代わりに sticky 位置と sticky 中フラグを計算。
        slides_y_natural = detail_y + ys["slides_buttons"] + off
        slides_y = max(detail_y + 2, slides_y_natural)
        is_sticky = slides_y > slides_y_natural
        as_w = max(70, button_w("ADD SLIDE"))
        ds_w = max(70, button_w("DEL SLIDE"))

        # スライドリスト (各スライド 2 行レイアウト)
        slide_list_y0 = detail_y + ys["slide_list"] + off
        slide_pitch = (fh * 2) + _ROW_GAP * 2
        body_x = detail_x + _SLIDE_SELECT_W + _SLIDE_SELECT_GAP
        body_w = max(60, content_w - _SLIDE_SELECT_W - _SLIDE_SELECT_GAP)
        thumb_w = min(_SLIDE_THUMB_W, max(48, body_w // 5))
        controls_x = body_x + thumb_w + _SLIDE_THUMB_GAP
        controls_w = max(60, body_w - thumb_w - _SLIDE_THUMB_GAP)
        time_w  = 110
        preview_w = max(68, button_w("PREVIEW"))
        eff_w   = 70
        edur_w  = 104
        dur_w   = max(76, controls_w - preview_w - eff_w - edur_w - 12)
        for si_i, slide in enumerate(slides):
            sy_a = slide_list_y0 + si_i * slide_pitch
            sy_b = sy_a + fh + _ROW_GAP
            row_h = fh * 2 + _ROW_GAP
            if sy_b + fh < detail_y or sy_a > detail_y + detail_h:
                continue
            selected = (si_i == self._selected_slide_idx)
            if selected:
                pyxel.rectb(detail_x, sy_a - 2, content_w,
                            fh * 2 + _ROW_GAP + 4, EDIT_ACCENT)
            lane_hover = is_hover(mx, my, detail_x, sy_a,
                                  _SLIDE_SELECT_W, row_h)
            pyxel.rectb(detail_x, sy_a, _SLIDE_SELECT_W, row_h,
                        EDIT_ACCENT if selected else EDIT_BORDER)
            draw_button(detail_x + 2, sy_a, _SLIDE_SELECT_W - 4,
                        str(si_i + 1), h=row_h,
                        active=selected, hover=lane_hover)
            thumb_hover = is_hover(mx, my, body_x, sy_a, thumb_w, row_h)
            self._draw_slide_thumbnail(body_x, sy_a, thumb_w, row_h,
                                       slide.get("image", ""),
                                       selected=selected,
                                       hover=thumb_hover)
            # 行 A: IMAGE ボタン + TIME 入力ボタン
            img_path = slide.get("image", "")
            img_name = self._basename(img_path) if img_path else ""
            lbl = (f"[Image {si_i+1}]:{img_name}" if img_name
                   else f"[Image {si_i+1}]")
            img_w = max(60, controls_w - time_w - 4)
            draw_button(controls_x, sy_a, img_w, lbl, h=fh,
                        active=selected,
                        hover=is_hover(mx, my, controls_x, sy_a, img_w, fh))
            # TIME: クリックで入力ダイアログを開くボタン (M:SS.ff 表示)
            time_x = controls_x + img_w + 4
            time_lbl = f"[TIME]:{self._format_time(slide.get('time', 0.0) or 0.0)}"
            draw_button(time_x, sy_a, time_w, time_lbl, h=fh,
                        active=selected,
                        hover=is_hover(mx, my, time_x, sy_a, time_w, fh))
            # 行 B: EFFECT | EFFECT_DUR | DUR
            preview_hover = is_hover(mx, my, controls_x, sy_b, preview_w, fh)
            draw_button(controls_x, sy_b, preview_w, "PREVIEW", h=fh,
                        active=selected, hover=preview_hover)
            cur_eff = slide.get("effect", "fade")
            eff_label = f"[{cur_eff}]"
            eff_x = controls_x + preview_w + 4
            draw_button(eff_x, sy_b, eff_w, eff_label, h=fh,
                        hover=is_hover(mx, my, eff_x, sy_b, eff_w, fh))
            edur_x = eff_x + eff_w + 4
            try:
                edur_val = float(slide.get("effect_duration", 1.0) or 1.0)
            except (TypeError, ValueError):
                edur_val = 1.0
            edur_lbl = f"E-DUR:{edur_val:.2f}"
            draw_button(edur_x, sy_b, edur_w, edur_lbl, h=fh,
                        hover=is_hover(mx, my, edur_x, sy_b, edur_w, fh))
            dur_x = edur_x + edur_w + 4
            try:
                dur_val = float(slide.get("duration", 3.0) or 3.0)
            except (TypeError, ValueError):
                dur_val = 3.0
            dur_lbl = f"DUR:{dur_val:.2f}"
            draw_button(dur_x, sy_b, dur_w, dur_lbl, h=fh,
                        hover=is_hover(mx, my, dur_x, sy_b, dur_w, fh))
        pyxel.clip()

        # ADD/DEL SLIDE ボタンを最後に描画 (sticky で常に上端付近に張り付く)。
        # スクロール時に裏のスライド行が透けないよう背景マスクを敷く。
        if is_sticky:
            pyxel.rect(detail_x, slides_y - 2, content_w, bh + 4, EDIT_BG)
        ash = is_hover(mx, my, detail_x, slides_y, as_w, bh)
        draw_button(detail_x, slides_y, as_w, "ADD SLIDE", h=bh, hover=ash)
        dsh = is_hover(mx, my, detail_x + as_w + 6, slides_y, ds_w, bh)
        draw_button(detail_x + as_w + 6, slides_y, ds_w, "DEL SLIDE",
                    h=bh, hover=dsh)
        apply_lbl = "APPLY TIME"
        apply_w = max(86, button_w(apply_lbl))
        clear_lbl = "CLEAR CAP"
        clear_w = max(80, button_w(clear_lbl))
        apply_x = detail_x + as_w + 6 + ds_w + 8
        clear_x = apply_x + apply_w + 6
        cap_active = self._last_captured_time is not None
        aph = cap_active and is_hover(mx, my, apply_x, slides_y, apply_w, bh)
        draw_button(apply_x, slides_y, apply_w, apply_lbl, h=bh,
                    active=cap_active, hover=aph)
        clh = cap_active and is_hover(mx, my, clear_x, slides_y, clear_w, bh)
        draw_button(clear_x, slides_y, clear_w, clear_lbl, h=bh,
                    active=False, hover=clh)
        cap_lbl = self._captured_time_label()
        if cap_lbl:
            cap_w = text_px_w(cap_lbl, _FONT_SZ)
            cap_x = clear_x + clear_w + 8
            if cap_x + cap_w > detail_x + content_w:
                cap_x = detail_x + content_w - cap_w - 2
            if cap_x > clear_x + clear_w + 2:
                cap_y = slides_y + max(0, (bh - _font_render_h(_FONT_SZ)) // 2)
                self._draw_text(cap_x, cap_y, cap_lbl, EDIT_ACCENT)

        # スクロールバー (右端)
        if content_h > detail_h and detail_h > 0:
            bar_x = detail_x + detail_w - 3
            bar_h_total = detail_h
            thumb_h = max(12, int(bar_h_total * detail_h / content_h))
            thumb_y = detail_y + int(
                (bar_h_total - thumb_h) * self._detail_scroll / max_ss
            ) if max_ss > 0 else detail_y
            pyxel.rect(bar_x, detail_y, 2, bar_h_total, EDIT_BORDER)
            pyxel.rect(bar_x, thumb_y, 2, thumb_h, EDIT_ACCENT)

    def _draw_slide_thumbnail(self, x: int, y: int, w: int, h: int,
                              image_path: str, selected: bool = False,
                              hover: bool = False) -> None:
        """Draw a small editor thumbnail for an ending slide.

        The thumbnail intentionally uses the editor/master palette cache. The
        actual ending playback still applies each slide's optimized palette.
        """
        bg = EDIT_BTN_HOVER if hover else EDIT_BG
        pyxel.rect(x, y, w, h, bg)
        pyxel.rectb(x, y, w, h, EDIT_ACCENT if selected else EDIT_BORDER)
        if not image_path or self._cache is None:
            return
        pad = 2
        box_w = max(1, w - pad * 2)
        box_h = max(1, h - pad * 2)
        try:
            img = self._cache.get(image_path, height=box_h)
        except Exception:
            img = None
        if img is None or img.width <= 0 or img.height <= 0:
            return
        scale = min(1.0, box_w / img.width, box_h / img.height)
        dw = max(1, int(img.width * scale))
        dh = max(1, int(img.height * scale))
        dx = x + pad + (box_w - dw) // 2
        dy = y + pad + (box_h - dh) // 2
        if abs(scale - 1.0) < 0.001:
            pyxel.blt(dx, dy, img, 0, 0, img.width, img.height)
        else:
            # pyxel.blt(scale=...) scales around its destination point, so use
            # the same compensation as the main preview/ending renderer.
            bx = dx + int(img.width * (scale - 1.0) / 2)
            by = dy + int(img.height * (scale - 1.0) / 2)
            pyxel.blt(bx, by, img, 0, 0, img.width, img.height, scale=scale)

    def _draw_text(self, x, y, text, col):
        draw_unicode(x, y, text, col, size=_FONT_SZ)
