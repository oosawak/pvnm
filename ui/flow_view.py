"""フローチャートビュー (720×480 対応)"""
import math
import re
import pyxel
from ui.colors import *
from ui.widgets import (draw_panel, draw_titlebar, draw_unicode, is_hover,
                        title_bar_h, _font_render_h, _ui_font_size)

_PREFIX_RE = re.compile(r"^\d{4}_\d{4}_")

# MainViewPanel と同じ領域。
# 以前の上部全幅レイアウトでは 0,0,720,232 だったが、現在のメイン
# エディタは左に SceneListPanel を常設するため、FLOW も右上プレビュー
# 領域内に収める。
MV_X, MV_Y, MV_W, MV_H = 200, 26, 520, 180

NODE_W_MIN = 80
X_GAP  = 16


def _node_h():
    """ノードの高さ（フォントサイズに応じて動的）。

    text_renderer の実描画高さ (`_font_render_h`) 以上を確保し、Japanese
    descender (例: "め") がノード枠下からハミ出ない (sc41 の現象を回避)。
    """
    # フォント高さに 4px の余白を足す (枠線とのギャップ)
    fh = _font_render_h(_ui_font_size)
    return max(20, fh + 4)


def _y_gap():
    """ノード間の縦ステップ。ノード同士が重ならず、アロー+チョイス
    ラベルを描画する空間を確保する。"""
    return _node_h() + max(24, _ui_font_size + 10)


def _text_px_w(text: str) -> int:
    """テキストの描画幅を概算（全角=size, 半角=size//2+1）"""
    sz = _ui_font_size
    half = sz // 2 + 1
    return sum(sz if ord(c) > 0x7F else half for c in text)


def _calc_node_w(name: str) -> int:
    """ノード名から必要なノード幅を計算"""
    disp = _PREFIX_RE.sub("", name)
    tw = _text_px_w(disp)
    return max(NODE_W_MIN, tw + 16)


class FlowView:
    X, Y, W, H = MV_X, MV_Y, MV_W, MV_H

    # 特殊ノード ID プレフィックス (通常のシーン名と衝突しないように __ を使う)
    _TITLE_ID = "__title__"
    _ENDING_PREFIX = "__ending__:"

    def __init__(self, state):
        self.state = state
        self._pos: dict[str, list[int]] = {}
        self._dragging:   str | None = None
        self._drag_ox = 0
        self._drag_oy = 0
        self._connecting: str | None = None
        self._connect_mx = 0
        self._connect_my = 0
        self._known_gen  = -1
        # scroll / pan
        self._scroll_x = 0
        self._scroll_y = 0
        self._panning   = False
        self._pan_ox    = 0
        self._pan_oy    = 0
        # 選択変更を検知してノードを可視範囲に収めるための前回選択名
        self._last_focused_name: str | None = None

    def update(self):
        self._sync_positions()
        # 選択シーンが変わったら可視範囲に収める (キーボード操作からの呼び出しに追従)
        sc = self.state.current_scene()
        cur_name = sc["name"] if sc else None
        if cur_name and cur_name != self._last_focused_name:
            self._ensure_visible(cur_name)
            self._last_focused_name = cur_name
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        pressed  = pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT)
        held     = pyxel.btn(pyxel.MOUSE_BUTTON_LEFT)
        released = pyxel.btnr(pyxel.MOUSE_BUTTON_LEFT)

        if pyxel.btnp(pyxel.KEY_R):
            self._pos.clear()
            self._scroll_x = 0
            self._scroll_y = 0
            self._tree_layout()
            return

        # ── scroll (wheel) ──
        if self._in_panel(mx, my):
            wheel = pyxel.mouse_wheel
            if wheel != 0:
                if pyxel.btn(pyxel.KEY_SHIFT):
                    self._scroll_x += wheel * 20
                else:
                    self._scroll_y += wheel * 20

        # ── pan (middle or right drag) ──
        mid_pressed  = pyxel.btnp(pyxel.MOUSE_BUTTON_MIDDLE)
        mid_held     = pyxel.btn(pyxel.MOUSE_BUTTON_MIDDLE)
        right_pressed = pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT)
        right_held    = pyxel.btn(pyxel.MOUSE_BUTTON_RIGHT)

        if self._panning:
            if mid_held or right_held:
                self._scroll_x += mx - self._pan_ox
                self._scroll_y += my - self._pan_oy
                self._pan_ox = mx
                self._pan_oy = my
            else:
                self._panning = False
            return

        if (mid_pressed or right_pressed) and self._in_panel(mx, my):
            self._panning = True
            self._pan_ox = mx
            self._pan_oy = my
            return

        if self._connecting is not None:
            self._connect_mx, self._connect_my = mx, my
            if released:
                target = self._node_at(mx, my)
                if target and target != self._connecting:
                    src_i = self._scene_index(self._connecting)
                    if src_i is not None:
                        self.state.scenes[src_i]["goto"] = target
                        self.state.dirty = True
                self._connecting = None
            return

        if self._dragging is not None:
            if held:
                sx, sy = self._scroll_x, self._scroll_y
                self._pos[self._dragging] = [mx - self._drag_ox - sx,
                                              my - self._drag_oy - sy]
            else:
                self._dragging = None
            return

        if pressed and self._in_panel(mx, my):
            # 特殊ノード（タイトル/エンディング）を先にチェック
            sp = self._special_node_at(mx, my)
            if sp is not None:
                self.state.selected_special = sp
                return
            port = self._port_at(mx, my)
            if port:
                self._connecting = port
                self._connect_mx, self._connect_my = mx, my
                return
            name = self._node_at(mx, my)
            if name:
                i = self._scene_index(name)
                if i is not None:
                    self.state.select_scene(i)
                self._dragging = name
                sx, sy = self._scroll_x, self._scroll_y
                nx, ny = self._pos[name]
                self._drag_ox = mx - (nx + sx)
                self._drag_oy = my - (ny + sy)

    def draw(self):
        draw_panel(self.X, self.Y, self.W, self.H)
        draw_titlebar(self.X, self.Y, self.W, "FLOW   R=reset  wheel=scroll  RMB=pan")

        sx, sy = self._scroll_x, self._scroll_y
        nh = _node_h()
        tbh = title_bar_h()
        # clip to panel interior (below titlebar, above hint)
        pyxel.clip(self.X, self.Y + tbh, self.W, self.H - tbh - 12)

        self._draw_edges(sx, sy, nh)

        if self._connecting is not None:
            sp = self._pos.get(self._connecting)
            if sp:
                nw = _calc_node_w(self._connecting)
                x1, y1 = _port_out(sp[0] + sx, sp[1] + sy, nw, nh)
                _draw_arrow(x1, y1, self._connect_mx, self._connect_my, EDIT_HIGHLIGHT)

        selected_name = ""
        sc = self.state.current_scene()
        if sc:
            selected_name = sc["name"]

        for scene in self.state.scenes:
            name = scene["name"]
            pos  = self._pos.get(name)
            if pos is None:
                continue
            has_choices = bool(scene.get("choices"))
            self._draw_node(pos[0] + sx, pos[1] + sy, name,
                            name == selected_name, has_choices, nh)

        # 特殊ノード（タイトル・エンディング）
        self._draw_special_nodes(nh)

        pyxel.clip()  # reset clip
        pyxel.text(self.X + 4, self.Y + self.H - 10,
                   "drag=move  port->connect  wheel=scroll  RMB=pan  R=reset", EDIT_TEXT_DIM)

    # ── 位置管理 ──────────────────────────────────────────────

    def _ensure_visible(self, name: str):
        """指定ノードが画面外なら _scroll_x/_scroll_y を補正して可視範囲に収める。"""
        pos = self._pos.get(name)
        if pos is None:
            return
        nw = _calc_node_w(name)
        nh = _node_h()
        # FlowView の描画クリップ範囲と一致させる
        view_top    = self.Y + title_bar_h()
        view_bot    = self.Y + self.H - 12
        view_left   = self.X
        view_right  = self.X + self.W
        margin = 16
        # ノードの画面座標
        node_left = pos[0] + self._scroll_x
        node_top  = pos[1] + self._scroll_y
        node_right = node_left + nw
        node_bot   = node_top + nh
        # 縦
        if node_top < view_top + margin:
            self._scroll_y += (view_top + margin) - node_top
        elif node_bot > view_bot - margin:
            self._scroll_y -= node_bot - (view_bot - margin)
        # 横
        if node_left < view_left + margin:
            self._scroll_x += (view_left + margin) - node_left
        elif node_right > view_right - margin:
            self._scroll_x -= node_right - (view_right - margin)

    def _sync_positions(self):
        if self._known_gen != self.state.scene_gen:
            self._pos.clear()
            self._known_gen = self.state.scene_gen

        names = {s["name"] for s in self.state.scenes}
        for k in list(self._pos):
            if k not in names:
                del self._pos[k]

        new_scenes = [s for s in self.state.scenes if s["name"] not in self._pos]
        if not new_scenes:
            return

        if not self._pos:
            self._tree_layout()
        else:
            bot_y = max(p[1] for p in self._pos.values())
            cx = self.X + self.W // 2
            yg = _y_gap()
            for scene in new_scenes:
                nw = _calc_node_w(scene["name"])
                bot_y += yg
                self._pos[scene["name"]] = [cx - nw // 2, bot_y]

    def _tree_layout(self):
        scenes = self.state.scenes
        if not scenes:
            return

        scene_names   = [s["name"] for s in scenes]
        name_to_scene = {s["name"]: s for s in scenes}

        def get_children(name):
            s = name_to_scene.get(name)
            if not s:
                return []
            choices = s.get("choices", [])
            if choices:
                return [c["goto"] for c in choices
                        if c.get("goto") and c["goto"] in name_to_scene]
            goto = s.get("goto", "")
            if goto and goto in name_to_scene:
                return [goto]
            idx = scene_names.index(name)
            return [scene_names[idx + 1]] if idx + 1 < len(scene_names) else []

        counted: set[str] = set()
        subtree_w: dict[str, int] = {}
        # シーン数が多い (293+) と再帰版は RecursionError になるため反復で実装
        parent_kids: dict[str, list] = {}

        def compute_w(root):
            if root not in name_to_scene or root in counted:
                return
            # 各エントリ: (name, finalize_flag)
            stack: list = [(root, False)]
            while stack:
                name, finalize = stack.pop()
                if finalize:
                    nw = _calc_node_w(name)
                    kids = parent_kids.get(name, [])
                    if not kids:
                        subtree_w[name] = nw
                        continue
                    valid = [subtree_w[k] for k in kids
                             if subtree_w.get(k, 0) > 0]
                    total = sum(valid) + X_GAP * max(0, len(valid) - 1)
                    subtree_w[name] = max(nw, total)
                    continue
                if name in counted or name not in name_to_scene:
                    continue
                counted.add(name)
                kids_now = [k for k in get_children(name)
                            if k in name_to_scene and k not in counted]
                parent_kids[name] = kids_now
                stack.append((name, True))
                # 逆順 push で左→右の順に処理
                for k in reversed(kids_now):
                    stack.append((k, False))

        compute_w(scene_names[0])
        for name in scene_names:
            if name not in counted:
                compute_w(name)

        placed: set[str] = set()

        def place(root_name, root_cx, root_y):
            yg = _y_gap()
            stack: list = [(root_name, root_cx, root_y)]
            while stack:
                name, cx, y = stack.pop()
                if name not in name_to_scene or name in placed:
                    continue
                placed.add(name)
                nw = _calc_node_w(name)
                nx = max(self.X + 4,
                         min(cx - nw // 2, self.X + self.W - nw - 4))
                self._pos[name] = [nx, y]
                kids = [k for k in get_children(name) if k not in placed]
                if not kids:
                    continue
                kid_ws = [(k, subtree_w.get(k, _calc_node_w(k)))
                          for k in kids]
                valid_ws = [(k, w) for k, w in kid_ws if w > 0]
                if not valid_ws:
                    continue
                total = sum(w for _, w in valid_ws) + X_GAP * (len(valid_ws) - 1)
                x_start = cx - total // 2
                pushes = []
                for k, w in valid_ws:
                    pushes.append((k, x_start + w // 2, y + yg))
                    x_start += w + X_GAP
                # 逆順 push で先頭の子から pop される
                for entry in reversed(pushes):
                    stack.append(entry)

        scene_y0 = self._scene_y0()
        place(scene_names[0], self.X + self.W // 2, scene_y0)
        cx = self.X + self.W // 2
        yg = _y_gap()
        for name in scene_names:
            if name not in placed:
                nw = _calc_node_w(name)
                bot_y = max((p[1] for p in self._pos.values()),
                            default=scene_y0)
                self._pos[name] = [cx - nw // 2, bot_y + yg]

    def _scene_y0(self) -> int:
        """シーンノードの初期 Y 位置。特殊ノード行の下に余白を取る。"""
        return self.Y + title_bar_h() + _node_h() + 20

    # ── 描画 ──────────────────────────────────────────────────

    def _draw_edges(self, sx, sy, nh):
        scene_name_set = {s["name"] for s in self.state.scenes}
        for i, scene in enumerate(self.state.scenes):
            src = scene["name"]
            sp  = self._pos.get(src)
            if sp is None:
                continue
            src_w = _calc_node_w(src)
            spo = (sp[0] + sx, sp[1] + sy)
            choices = scene.get("choices", [])
            if choices:
                for choice in choices:
                    dst = choice.get("goto", "")
                    dp  = self._pos.get(dst)
                    if dp:
                        dst_w = _calc_node_w(dst)
                        dpo = (dp[0] + sx, dp[1] + sy)
                        x1, y1 = _port_out(*spo, src_w, nh)
                        x2, y2 = _port_in(*dpo, dst_w)
                        _draw_arrow(x1, y1, x2, y2, EDIT_ACCENT)
                        # チョイスラベルはアロー右側・縦中央に配置
                        lx = (x1 + x2) // 2 + 6
                        ly = (y1 + y2) // 2 - _ui_font_size // 2
                        label = choice.get("label", "")[:8]
                        draw_unicode(lx, ly, label, EDIT_HIGHLIGHT,
                                     size=_ui_font_size)
            else:
                goto = scene.get("goto", "")
                if goto and goto in scene_name_set:
                    dp = self._pos.get(goto)
                    if dp:
                        dst_w = _calc_node_w(goto)
                        dpo = (dp[0] + sx, dp[1] + sy)
                        x1, y1 = _port_out(*spo, src_w, nh)
                        x2, y2 = _port_in(*dpo, dst_w)
                        _draw_arrow(x1, y1, x2, y2, EDIT_ACCENT)
                        lx = (x1 + x2) // 2 + 6
                        ly = (y1 + y2) // 2 - 3
                        pyxel.text(lx, ly, "go", EDIT_TEXT_DIM)
                elif not goto and i + 1 < len(self.state.scenes):
                    dst = self.state.scenes[i + 1]["name"]
                    dp  = self._pos.get(dst)
                    if dp:
                        dst_w = _calc_node_w(dst)
                        dpo = (dp[0] + sx, dp[1] + sy)
                        x1, y1 = _port_out(*spo, src_w, nh)
                        x2, y2 = _port_in(*dpo, dst_w)
                        _draw_arrow(x1, y1, x2, y2, EDIT_BORDER)

    def _draw_node(self, x, y, name, selected, has_choices, nh):
        nw = _calc_node_w(name)
        if selected:
            bg, fg, border = EDIT_ACCENT, EDIT_BG, EDIT_ACCENT
        elif has_choices:
            bg, fg, border = EDIT_BTN_BG, EDIT_TEXT, EDIT_BTN_BG
        else:
            bg, fg, border = EDIT_PANEL, EDIT_TEXT, EDIT_BORDER

        pyxel.rect(x, y, nw, nh, bg)
        pyxel.rectb(x, y, nw, nh, border)
        disp = _PREFIX_RE.sub("", name)
        # テキスト幅に基づいて切り詰め
        tw = _text_px_w(disp)
        max_tw = nw - 12
        if tw > max_tw:
            # 文字を1つずつ削って収まるまで切り詰め
            while len(disp) > 1 and _text_px_w(disp) > max_tw:
                disp = disp[:-1]
        tx = x + (nw - _text_px_w(disp)) // 2
        rh = _font_render_h(_ui_font_size)
        ty = y + max(0, (nh - rh) // 2)
        draw_unicode(tx, ty, disp, fg, size=_ui_font_size)

        # ポートインジケータ
        px, py_ = _port_out(x, y, nw, nh)
        pyxel.rect(px - 3, py_ - 1, 6, 5, EDIT_HIGHLIGHT)

    # ── ユーティリティ ────────────────────────────────────────

    def _node_at(self, mx, my):
        sx, sy = self._scroll_x, self._scroll_y
        nh = _node_h()
        for scene in reversed(self.state.scenes):
            name = scene["name"]
            pos  = self._pos.get(name)
            if pos:
                nw = _calc_node_w(name)
                if is_hover(mx, my, pos[0] + sx, pos[1] + sy, nw, nh):
                    return name
        return None

    def _port_at(self, mx, my):
        sx, sy = self._scroll_x, self._scroll_y
        nh = _node_h()
        for scene in self.state.scenes:
            name = scene["name"]
            pos  = self._pos.get(name)
            if pos:
                nw = _calc_node_w(name)
                px, py_ = _port_out(pos[0] + sx, pos[1] + sy, nw, nh)
                if is_hover(mx, my, px - 4, py_ - 2, 9, 8):
                    return name
        return None

    def _scene_index(self, name):
        for i, s in enumerate(self.state.scenes):
            if s["name"] == name:
                return i
        return None

    def _in_panel(self, mx, my):
        return self.X <= mx < self.X + self.W and self.Y <= my < self.Y + self.H

    # ── 特殊ノード (タイトル / エンディング) ──────────────────────

    def _special_node_rects(self):
        """タイトル/エンディングノードの画面座標矩形 (スクロール反映済み)。

        Returns: list of (sel_id, label, x, y, w, h)
        """
        sx, sy = self._scroll_x, self._scroll_y
        nh = _node_h()
        base_y = self.Y + title_bar_h() + 4 + sy
        rects = []
        # タイトル
        t_disp = "[TITLE]"
        tw = _calc_node_w(t_disp)
        rects.append(("title", t_disp, self.X + 8 + sx, base_y, tw, nh))
        # エンディング
        gap = 12
        x_cursor = self.X + 8 + sx + tw + gap
        endings = list(self.state.endings or [])
        if not endings:
            lbl = "[ENDING] Ending not set"
            w = _calc_node_w(lbl)
            rects.append((("ending", -1), lbl, x_cursor, base_y, w, nh))
        else:
            for i, e in enumerate(endings):
                name = str(e.get("name", "") or f"Ending {i + 1}")
                lbl = f"[ENDING] {name}"
                w = _calc_node_w(lbl)
                rects.append((("ending", i), lbl, x_cursor, base_y, w, nh))
                x_cursor += w + gap
        return rects

    def _draw_special_nodes(self, nh):
        sel = self.state.selected_special
        for sid, label, x, y, w, h in self._special_node_rects():
            is_sel = (sid == sel)
            if sid == "title":
                bg, fg = (EDIT_HIGHLIGHT, EDIT_BG) if is_sel else (EDIT_TITLE_BG, EDIT_TEXT)
            else:
                # エンディング
                is_unset = (isinstance(sid, tuple) and sid[1] == -1)
                if is_sel:
                    bg, fg = EDIT_HIGHLIGHT, EDIT_BG
                elif is_unset:
                    bg, fg = EDIT_BG, EDIT_TEXT_DIM
                else:
                    bg, fg = EDIT_BTN_BG, EDIT_TEXT
            pyxel.rect(x, y, w, h, bg)
            pyxel.rectb(x, y, w, h, EDIT_ACCENT if is_sel else EDIT_BORDER)
            disp = label
            max_tw = w - 12
            if _text_px_w(disp) > max_tw:
                while len(disp) > 1 and _text_px_w(disp) > max_tw:
                    disp = disp[:-1]
            tx = x + (w - _text_px_w(disp)) // 2
            rh = _font_render_h(_ui_font_size)
            ty = y + max(0, (h - rh) // 2)
            draw_unicode(tx, ty, disp, fg, size=_ui_font_size)

    def _special_node_at(self, mx, my):
        for sid, _lbl, x, y, w, h in self._special_node_rects():
            if x <= mx < x + w and y <= my < y + h:
                return sid
        return None


def _port_out(nx, ny, nw=NODE_W_MIN, nh=18):
    return nx + nw // 2, ny + nh


def _port_in(nx, ny, nw=NODE_W_MIN):
    return nx + nw // 2, ny


def _draw_arrow(x1, y1, x2, y2, col):
    pyxel.line(x1, y1, x2, y2, col)
    dx, dy = x2 - x1, y2 - y1
    length = max(1.0, math.sqrt(dx * dx + dy * dy))
    nx_, ny_ = dx / length, dy / length
    px_, py_ = -ny_, nx_
    size = 5
    ax1 = round(x2 - nx_ * size + px_ * 2)
    ay1 = round(y2 - ny_ * size + py_ * 2)
    ax2 = round(x2 - nx_ * size - px_ * 2)
    ay2 = round(y2 - ny_ * size - py_ * 2)
    pyxel.tri(x2, y2, ax1, ay1, ax2, ay2, col)
