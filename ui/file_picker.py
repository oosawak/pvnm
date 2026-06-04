"""ファイル選択ピッカー（モーダルオーバーレイ, 720×480 対応）

EDIT_BG/キャラクター/パレット/フォントの各ファイルを
ディレクトリ一覧から選択し、プレビュー表示する。
"""
import os
import pyxel
from ui.colors import *
import ui.widgets as _w
from ui.widgets import (
    draw_panel, draw_titlebar, draw_button, draw_unicode,
    is_hover, is_clicked, _font_render_h, _ui_font_size,
)

# ── レイアウト ─────────────────────────────────────────────────
_MARGIN   = 20
_TITLE_H  = 22
_SCROLL_W = 6


def _item_h():
    """リストアイテム高さ（エディタフォントサイズに応じて動的に算出）"""
    return _font_render_h(_w._editor_font_size) + 4

# 画像拡張子
_IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp"}
# パレットファイル拡張子
_PAL_EXTS = {".pal", ".txt", ".hex", ".png", ".jpg", ".jpeg", ".gif", ".bmp"}
# フォント拡張子
_FONT_EXTS = {".ttf", ".otf"}
# プロジェクトファイル拡張子
_PVNM_EXTS = {".pvnm"}
# オーディオファイル拡張子
_AUDIO_EXTS = {".mp3", ".ogg", ".wav"}
# Markdown拡張子
_MARKDOWN_EXTS = {".md", ".markdown", ".txt"}

# プレビュー最大サイズ
_PREVIEW_MAX = 256


def _picker_text_size() -> int:
    return max(14, _w._editor_font_size)


def _picker_line_h(size: int | None = None) -> int:
    size = _picker_text_size() if size is None else size
    return _font_render_h(size) + 6


def _fit_text(text: str, max_w: int, size: int) -> str:
    text = str(text or "")
    if _w.text_px_w(text, size) <= max_w:
        return text
    ell = "..."
    if _w.text_px_w(ell, size) > max_w:
        return ""
    out = text
    while out and _w.text_px_w(ell + out, size) > max_w:
        out = out[1:]
    return ell + out


def _text_width(text: str, size: int) -> int:
    """テキストの描画幅を概算する（全角=size, 半角=size//2+1）"""
    half = size // 2 + 1
    return sum(size if ord(c) > 0x7F else half for c in text)


def _fit_size(orig_w: int, orig_h: int, max_w: int, max_h: int):
    """アスペクト比を維持して max_w x max_h に収める"""
    if orig_w <= 0 or orig_h <= 0:
        return max_w, max_h
    ratio = min(max_w / orig_w, max_h / orig_h)
    return max(1, int(orig_w * ratio)), max(1, int(orig_h * ratio))


class FilePicker:
    """ファイル選択オーバーレイ。

    使い方:
        picker.open("EDIT_BG FILE", "./assets/images/bg/", mode="image", callback=fn)
        毎フレーム picker.update() / picker.draw() を呼ぶ。
        選択確定時に callback(relative_path) が呼ばれる。
    """

    # エントリ種別
    _ENTRY_UP   = "up"     # ".." 親フォルダへ
    _ENTRY_DIR  = "dir"    # サブフォルダ
    _ENTRY_FILE = "file"   # 通常ファイル

    def __init__(self, image_cache=None):
        self.active   = False
        self._title   = ""
        self._base_dir = ""       # 起点ディレクトリ (callback の relpath 基準)
        self._current_dir = ""    # 現在表示中のディレクトリ (navigation で変化)
        self._mode    = "image"   # "image" | "palette" | "font"
        self._callback = None
        # エントリ: (kind, name) のリスト。kind は _ENTRY_UP/DIR/FILE。
        # 表示順: ".." → folders → files
        self._entries: list = []
        self._sel     = -1        # 選択インデックス
        self._scroll  = 0         # スクロールオフセット（ピクセル）
        self._cache   = image_cache
        self._project_base = ""   # プロジェクトルートディレクトリ
        # 設定 (per-image palette 構築用)。
        self._settings: dict = {}
        # プレビュー用
        self._preview_img = None  # pyxel.Image
        self._preview_w   = 0
        self._preview_h   = 0
        self._preview_path = ""
        self._preview_palette = None
        # フォントプレビュー
        self._font_writer  = None
        self._font_size    = 16
        self._font_preview_path = ""
        # オーディオプレビュー
        self._audio_playing_path = ""
        self._audio_preview_ch   = 3  # 最終 SE チャンネルを借用

    def set_settings(self, settings: dict) -> None:
        """per-image palette 構築用 settings (reserved_indices) を注入。"""
        self._settings = settings or {}

    @property
    def running(self) -> bool:
        return self.active

    def open(self, title: str, base_dir: str, mode: str, callback,
             project_base: str = "", initial_path: str = ""):
        """ピッカーを開く。

        Parameters
        ----------
        title        : ダイアログタイトル
        base_dir     : 起点ディレクトリ（callback の relpath 基準）
        mode         : "image" | "palette" | "font" | "audio" | "pvnm" | "markdown"
        callback     : 選択確定時のコールバック fn(relative_path)
        project_base : プロジェクトルート（相対パス解決用）
        initial_path : 既存の選択値 (base_dir からの相対パスまたは絶対)。
                       指定があれば該当ファイルにカーソルを合わせ、サブフォルダ
                       にあれば自動的にそのフォルダへ navigate する。
        """
        self.active     = True
        self._title     = title
        self._mode      = mode
        self._callback  = callback
        self._sel       = -1
        self._scroll    = 0
        self._preview_img  = None
        self._preview_path = ""
        self._font_writer  = None
        self._font_preview_path = ""
        self._font_size    = 16

        # base_dir を絶対パスに解決
        pbase = project_base or self._project_base
        if pbase and not os.path.isabs(base_dir):
            abs_dir = os.path.join(pbase, base_dir)
        else:
            abs_dir = base_dir
        self._base_dir    = os.path.normpath(abs_dir)
        self._current_dir = self._base_dir

        # initial_path がサブフォルダ内なら、そのフォルダへ自動 navigate
        target_filename = ""
        if initial_path:
            ip = initial_path
            if not os.path.isabs(ip):
                # base_dir に対する相対と想定。"./assets/images/bg/..." のような
                # project_base 起点の相対も許容する: base_dir 起点で resolve できない場合
                # project_base 起点で再試行する。
                cand1 = os.path.normpath(os.path.join(self._base_dir, ip))
                cand2 = os.path.normpath(os.path.join(pbase, ip)) if pbase else cand1
                ip_abs = cand1 if os.path.exists(cand1) else cand2
            else:
                ip_abs = os.path.normpath(ip)
            if os.path.exists(ip_abs) and os.path.isfile(ip_abs):
                parent = os.path.dirname(ip_abs)
                # base_dir の子孫ならそこへ navigate、それ以外は base_dir 維持
                if (parent == self._base_dir
                        or parent.startswith(self._base_dir + os.sep)):
                    self._current_dir = parent
                target_filename = os.path.basename(ip_abs)

        # 現ディレクトリをスキャンしてエントリを構築
        self._rescan()

        # initial_path が指すファイルにカーソルを合わせる
        if target_filename:
            for i, (kind, name) in enumerate(self._entries):
                if kind == self._ENTRY_FILE and name == target_filename:
                    self._sel = i
                    self._load_preview()
                    # 該当行が画面内に来るようスクロール位置を調整。
                    # update()/draw() 前なので list_h は使えないが、現在のレイアウト
                    # 計算式と一致させる (pyxel.height はこの時点で確定済み)。
                    H = pyxel.height
                    list_h = (H - _MARGIN * 2) - _TITLE_H - 40
                    self._ensure_visible(list_h)
                    break

    def close(self):
        self.active = False
        self._callback = None
        self._preview_img = None
        self._font_writer = None
        self._stop_audio_preview()
        # プレビューで書き換えていた pyxel.colors[] / ImageCache 既定値を戻す。
        # 戻さないと閉じた後のエディタが画像最適化パレットのままになる。
        if self._mode == "image":
            self._restore_master_palette()

    # ── スキャン / ナビゲーション ─────────────────────────────────

    def _mode_extensions(self) -> set:
        if self._mode == "image":
            return _IMG_EXTS
        if self._mode == "palette":
            return _PAL_EXTS
        if self._mode == "font":
            return _FONT_EXTS
        if self._mode == "pvnm":
            return _PVNM_EXTS
        if self._mode == "audio":
            return _AUDIO_EXTS
        if self._mode == "markdown":
            return _MARKDOWN_EXTS
        return _IMG_EXTS

    def _rescan(self) -> None:
        """現在のディレクトリ (`_current_dir`) を 1 階層だけスキャンして
        `_entries` を更新する。

        順序:
          1. ".."  (current_dir が base_dir でないとき)
          2. サブフォルダ (アルファベット順)
          3. ファイル (アルファベット順、モード対応拡張子のみ)
        """
        self._entries = []
        cur = self._current_dir
        if not os.path.isdir(cur):
            return
        # 上向き: base_dir までは許可 (それ以上は遡らない)
        if os.path.normpath(cur) != os.path.normpath(self._base_dir):
            self._entries.append((self._ENTRY_UP, ".."))
        exts = self._mode_extensions()
        subdirs: list = []
        files: list = []
        try:
            for entry in sorted(os.listdir(cur)):
                if entry.startswith("."):
                    continue
                full = os.path.join(cur, entry)
                if os.path.isdir(full):
                    subdirs.append(entry)
                elif os.path.isfile(full):
                    ext = os.path.splitext(entry)[1].lower()
                    if ext in exts:
                        files.append(entry)
        except OSError:
            pass
        for d in subdirs:
            self._entries.append((self._ENTRY_DIR, d))
        for f in files:
            self._entries.append((self._ENTRY_FILE, f))

    def _navigate(self, new_dir: str) -> None:
        """指定ディレクトリへ移動して再スキャン。選択・スクロールをリセット。"""
        target = os.path.normpath(new_dir)
        if os.path.isdir(target):
            self._current_dir = target
            self._sel = -1
            self._scroll = 0
            self._preview_img = None
            self._preview_path = ""
            self._rescan()

    # ── 更新 ────────────────────────────────────────────────────

    def update(self):
        if not self.active:
            return

        mx, my = pyxel.mouse_x, pyxel.mouse_y
        W, H = pyxel.width, pyxel.height

        # ダイアログ全体の領域
        dx, dy = _MARGIN, _MARGIN
        dw, dh = W - _MARGIN * 2, H - _MARGIN * 2

        # リスト領域（左半分）
        list_x = dx + 4
        list_y = dy + _TITLE_H + 4
        list_w = dw // 2 - 8
        list_h = dh - _TITLE_H - 40  # 下部にボタン領域

        # スクロール
        if is_hover(mx, my, list_x, list_y, list_w, list_h):
            wheel = pyxel.mouse_wheel
            if wheel:
                self._scroll -= wheel * 24
                max_scroll = max(0, len(self._entries) * _item_h() - list_h)
                self._scroll = max(0, min(max_scroll, self._scroll))

        # リストクリック (フォルダはナビゲート、ファイルは選択)
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            if is_hover(mx, my, list_x, list_y, list_w, list_h):
                rel_y = my - list_y + self._scroll
                idx = int(rel_y // _item_h())
                if 0 <= idx < len(self._entries):
                    kind, name = self._entries[idx]
                    if kind == self._ENTRY_UP:
                        self._navigate(os.path.dirname(self._current_dir))
                        return
                    if kind == self._ENTRY_DIR:
                        self._navigate(os.path.join(self._current_dir, name))
                        return
                    # FILE: 選択
                    self._sel = idx
                    self._load_preview()

        # ダブルクリック（簡易: 高速2回クリック）で確定
        # → 代わりにOKボタンで確定

        # プレビュー領域でのフォントサイズ変更（フォントモード）
        if self._mode == "font":
            preview_x = dx + dw // 2 + 4
            preview_y = dy + _TITLE_H + 4
            preview_w = dw // 2 - 8
            preview_h = list_h
            if is_hover(mx, my, preview_x, preview_y, preview_w, preview_h):
                wheel = pyxel.mouse_wheel
                if wheel:
                    new_size = max(8, min(48, self._font_size + wheel))
                    if new_size != self._font_size:
                        self._font_size = new_size
                        # pyxel.Font はサイズ固定なので再生成
                        if self._font_preview_path:
                            try:
                                self._font_writer = pyxel.Font(
                                    self._font_preview_path, self._font_size)
                            except Exception:
                                pass

        # ボタン領域
        btn_y  = dy + dh - 30
        btn_w  = 80
        ok_x   = dx + dw - btn_w * 2 - 16
        cancel_x = dx + dw - btn_w - 8

        # オーディオプレビュー用の PLAY / STOP ボタン
        if self._mode == "audio" and self._selected_file_abs():
            preview_x = dx + dw // 2 + 4
            preview_y = dy + _TITLE_H + 4
            preview_w = dw // 2 - 8
            ax = preview_x + 8
            ay = preview_y + 40
            if is_clicked(mx, my, ax, ay, 70, 22):
                self._play_audio_preview()
                return
            if is_clicked(mx, my, ax + 78, ay, 70, 22):
                self._stop_audio_preview()
                return

        if is_clicked(mx, my, ok_x, btn_y, btn_w, 24):
            self._confirm()
            return
        if is_clicked(mx, my, cancel_x, btn_y, btn_w, 24):
            self.close()
            return

        # ESC でキャンセル
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self.close()
            return

        # ENTER: ファイルなら確定、フォルダなら入る、上ボタンなら遡る
        if pyxel.btnp(pyxel.KEY_RETURN) and 0 <= self._sel < len(self._entries):
            kind, name = self._entries[self._sel]
            if kind == self._ENTRY_UP:
                self._navigate(os.path.dirname(self._current_dir))
                return
            if kind == self._ENTRY_DIR:
                self._navigate(os.path.join(self._current_dir, name))
                return
            self._confirm()
            return

        # 上下キーで選択移動 (フォルダ行も選択可。ファイル行ならプレビュー更新)
        if pyxel.btnp(pyxel.KEY_UP) and self._sel > 0:
            self._sel -= 1
            self._ensure_visible(list_h)
            self._load_preview()
        if (pyxel.btnp(pyxel.KEY_DOWN)
                and self._sel < len(self._entries) - 1):
            self._sel += 1
            self._ensure_visible(list_h)
            self._load_preview()

    def _ensure_visible(self, list_h: int):
        """選択アイテムがスクロール範囲内に見えるようにする"""
        if self._sel < 0:
            return
        item_top = self._sel * _item_h()
        item_bot = item_top + _item_h()
        if item_top < self._scroll:
            self._scroll = item_top
        elif item_bot > self._scroll + list_h:
            self._scroll = item_bot - list_h

    def _selected_file_abs(self) -> str:
        """選択中エントリがファイルならその絶対パス、それ以外は ""。"""
        if not (0 <= self._sel < len(self._entries)):
            return ""
        kind, name = self._entries[self._sel]
        if kind != self._ENTRY_FILE:
            return ""
        return os.path.join(self._current_dir, name)

    def _confirm(self):
        abs_path = self._selected_file_abs()
        if abs_path and self._callback:
            if self._mode == "pvnm":
                # pvnm モードでは絶対パスを返す
                self._callback(abs_path)
            else:
                # base_dir からの相対 (旧仕様互換: callback 側で base prefix と結合)
                rel = os.path.relpath(abs_path, self._base_dir)
                self._callback(rel)
        self.close()

    def _load_preview(self):
        """選択されたファイルのプレビューをロードする (フォルダ行ではクリア)。"""
        abs_path = self._selected_file_abs()
        if not abs_path:
            self._preview_img = None
            return
        if self._mode in ("image",):
            self._load_image_preview(abs_path)
        elif self._mode == "font":
            self._load_font_preview(abs_path)
        elif self._mode == "audio":
            # 選択を切り替えたら直前のプレビュー音を停止
            self._stop_audio_preview()
        # palette mode: no preview needed

    def _load_image_preview(self, abs_path: str):
        if abs_path == self._preview_path and self._preview_img is not None:
            return
        self._preview_path = abs_path
        self._preview_img  = None
        self._preview_palette = None
        if not self._cache:
            return
        try:
            from PIL import Image
            with Image.open(abs_path) as img:
                ow, oh = img.size
            pw, ph = _fit_size(ow, oh, _PREVIEW_MAX, _PREVIEW_MAX)
            # 画像ごとに最適化された 256色パレットを構築・適用してから読込む
            # ことで、シーン/エンディングで実際にプレイ時に見える色味と
            # 一致させる。K-D tree 量子化が高速なので毎ファイル切替でも軽い。
            self._preview_palette = self._apply_per_image_palette(abs_path)
            self._preview_img = self._cache.get(abs_path, pw, ph)
            self._preview_w = pw
            self._preview_h = ph
        except Exception:
            self._preview_img = None

    def _activate_preview_palette(self) -> None:
        if self._preview_palette is None:
            return
        try:
            from engine import palette as _palette_mod
            from engine.image_cache import set_default_palette as _set_image_cache_palette
            _palette_mod.apply_to_pyxel_colors(self._preview_palette)
            _set_image_cache_palette(self._preview_palette)
        except Exception:
            pass

    def _apply_per_image_palette(self, abs_path: str):
        """選択中の画像専用の 256色パレットを構築して pyxel.colors[] と
        ImageCache 既定パレットに適用する。

        UI 役割色 (settings.json で予約された index) はマスター値で固定するので
        ピッカー UI の見た目は保たれる。残りスロットは画像の Median Cut 代表色。
        """
        if not self._cache:
            return None
        try:
            from engine import palette as _palette_mod
            from engine.image_cache import set_default_palette as _set_image_cache_palette
        except Exception:
            return None
        try:
            reserved = _palette_mod.reserved_from_settings(self._settings)
            if not reserved:
                return None
            pal = _palette_mod.build_scene_palette(
                [abs_path], reserved,
                base_dir=getattr(self._cache, "base_dir", ""))
            _palette_mod.apply_to_pyxel_colors(pal)
            _set_image_cache_palette(pal)
            return pal
        except Exception as e:
            print(f"[picker] per-image palette failed: {e}")
            return None

    def _restore_master_palette(self) -> None:
        """ピッカー終了時に MasterColor.pyxpal へ戻す。"""
        try:
            from engine import palette as _palette_mod
            from engine.image_cache import set_default_palette as _set_image_cache_palette
            _palette_mod.load()
            _set_image_cache_palette(_palette_mod.snapshot_pyxel_colors())
        except Exception:
            pass

    def _load_font_preview(self, abs_path: str):
        if abs_path == self._font_preview_path and self._font_writer is not None:
            return
        self._font_preview_path = abs_path
        self._font_writer = None
        try:
            self._font_writer = pyxel.Font(abs_path, self._font_size)
        except Exception:
            self._font_writer = None

    # ── 描画 ────────────────────────────────────────────────────

    def draw(self):
        if not self.active:
            return

        W, H = pyxel.width, pyxel.height
        mx, my = pyxel.mouse_x, pyxel.mouse_y

        # 暗いオーバーレイ
        for y in range(0, H, 2):
            pyxel.line(0, y, W - 1, y, 0)

        dx, dy = _MARGIN, _MARGIN
        dw, dh = W - _MARGIN * 2, H - _MARGIN * 2

        # 外枠
        pyxel.rect(dx - 2, dy - 2, dw + 4, dh + 4, EDIT_BORDER)
        draw_panel(dx, dy, dw, dh)
        draw_titlebar(dx, dy, dw, self._title)

        # 現在パスを表示（フルパス）
        cur_disp = self._current_dir
        path_y = dy + _TITLE_H + 2
        path_size = _w._editor_font_size - 2
        status_w = max(1, dw - 16)
        draw_unicode(dx + 4, path_y, 
                     _fit_text(cur_disp, status_w, path_size),
                     EDIT_TEXT, size=path_size, bg_col=EDIT_PANEL)

        # リスト領域（左半分）
        list_x = dx + 4
        list_y = dy + _TITLE_H + 20
        list_w = dw // 2 - 8
        list_h = dh - _TITLE_H - 56

        # リスト背景
        pyxel.rect(list_x, list_y, list_w, list_h, EDIT_BG)
        pyxel.rectb(list_x, list_y, list_w, list_h, EDIT_BORDER)

        # リストアイテム（クリップ）
        pyxel.clip(list_x, list_y, list_w, list_h)
        if not self._entries:
            draw_unicode(list_x + 4, list_y + 4, "(empty)",
                         EDIT_TEXT_DIM, size=_w._editor_font_size)
        else:
            fsz = _w._editor_font_size
            char_w = max(4, int(fsz * 0.65))
            max_chars = max(1, (list_w - 8) // char_w)
            rh = _font_render_h(fsz)
            for i, (kind, name) in enumerate(self._entries):
                iy = list_y + i * _item_h() - self._scroll
                if iy + _item_h() < list_y or iy > list_y + list_h:
                    continue
                sel = (i == self._sel)
                hov = is_hover(mx, my, list_x, max(list_y, iy),
                               list_w, min(_item_h(), list_y + list_h - iy))
                if sel:
                    pyxel.rect(list_x + 1, iy, list_w - 2, _item_h(), EDIT_ACCENT)
                elif hov:
                    pyxel.rect(list_x + 1, iy, list_w - 2, _item_h(), EDIT_BTN_HOVER)

                # 表示文字列とフォルダ/ファイル区別
                if kind == self._ENTRY_UP:
                    label = "<- ..  parent folder"
                elif kind == self._ENTRY_DIR:
                    label = f"[D] {name}/"
                else:
                    label = name
                if len(label) > max_chars:
                    label = "..." + label[-(max_chars - 3):]
                ty = iy + max(0, (_item_h() - rh) // 2)
                # フォルダ・上行はアクセント (青/緑) で目立たせる
                if sel:
                    fg = EDIT_BG
                elif kind in (self._ENTRY_UP, self._ENTRY_DIR):
                    fg = EDIT_ACCENT
                else:
                    fg = EDIT_TEXT
                # 実 row 背景色を bg_col に渡してアンチエイリアスの halo を防ぐ
                if sel:
                    row_bg = EDIT_ACCENT
                elif hov:
                    row_bg = EDIT_BTN_HOVER
                else:
                    row_bg = EDIT_BG
                draw_unicode(list_x + 4, ty, label, fg, size=fsz, bg_col=row_bg)
        pyxel.clip()

        # スクロールバー
        if self._entries:
            total_h = len(self._entries) * _item_h()
            if total_h > list_h:
                bar_area = list_h - 4
                bar_h = max(12, bar_area * list_h // total_h)
                bar_y = list_y + 2 + (bar_area - bar_h) * self._scroll // max(1, total_h - list_h)
                sb_x = list_x + list_w - _SCROLL_W - 1
                pyxel.rect(sb_x, list_y + 2, _SCROLL_W, bar_area, EDIT_BORDER)
                pyxel.rect(sb_x, bar_y, _SCROLL_W, bar_h, EDIT_ACCENT)

        # プレビュー領域（右半分）
        preview_x = dx + dw // 2 + 4
        preview_y = dy + _TITLE_H + 20
        preview_w = dw // 2 - 8
        preview_h = list_h

        pyxel.rect(preview_x, preview_y, preview_w, preview_h, EDIT_BG)
        pyxel.rectb(preview_x, preview_y, preview_w, preview_h, EDIT_BORDER)

        sel_is_file = bool(self._selected_file_abs())
        if self._mode == "image" and self._preview_img is not None:
            self._draw_image_preview(preview_x, preview_y, preview_w, preview_h)
        elif self._mode == "font" and self._font_writer is not None:
            self._draw_font_preview(preview_x, preview_y, preview_w, preview_h)
        elif self._mode == "palette" and sel_is_file:
            self._draw_palette_preview(preview_x, preview_y, preview_w, preview_h)
        elif self._mode == "pvnm" and sel_is_file:
            self._draw_pvnm_preview(preview_x, preview_y, preview_w, preview_h)
        elif self._mode == "audio" and sel_is_file:
            self._draw_audio_preview(preview_x, preview_y, preview_w, preview_h, mx, my)
        else:
            cx = preview_x + preview_w // 2 - 30
            cy = preview_y + preview_h // 2 - 4
            pyxel.text(cx, cy, "No preview", EDIT_TEXT_DIM)

        # ボタン
        btn_y  = dy + dh - 30
        btn_w  = 80
        ok_x   = dx + dw - btn_w * 2 - 16
        cancel_x = dx + dw - btn_w - 8

        ok_en = bool(self._selected_file_abs())
        draw_button(ok_x, btn_y, btn_w, "OK", h=24,
                    active=ok_en,
                    hover=ok_en and is_hover(mx, my, ok_x, btn_y, btn_w, 24))
        draw_button(cancel_x, btn_y, btn_w, "CANCEL", h=24,
                    hover=is_hover(mx, my, cancel_x, btn_y, btn_w, 24))

        # 現在パス + 件数
        n_files = sum(1 for k, _ in self._entries if k == self._ENTRY_FILE)
        n_dirs = sum(1 for k, _ in self._entries if k == self._ENTRY_DIR)
        try:
            rel_cur = os.path.relpath(self._current_dir, self._base_dir)
        except ValueError:
            rel_cur = self._current_dir
        cur_disp = "." if rel_cur == "." else rel_cur
        info = f"{cur_disp}  ({n_dirs} dirs, {n_files} files)"
        status_size = _picker_text_size()
        status_y = dy + dh - 18
        status_w = max(1, ok_x - (dx + 8) - 12)
        draw_unicode(dx + 8, status_y,
                     _fit_text(info, status_w, status_size),
                     EDIT_TEXT_DIM, size=status_size, bg_col=EDIT_PANEL)

    def _draw_image_preview(self, px, py, pw, ph):
        """画像プレビュー（256x256に収まるようにアスペクト比維持）"""
        img = self._preview_img
        if img is None:
            return
        self._activate_preview_palette()
        iw, ih = self._preview_w, self._preview_h
        # プレビュー領域内に中央配置
        ix = px + (pw - iw) // 2
        iy = py + (ph - ih) // 2
        pyxel.blt(ix, iy, img, 0, 0, iw, ih)

        # サイズ情報
        try:
            from PIL import Image
            abs_path = self._preview_path
            with Image.open(abs_path) as orig:
                ow, oh = orig.size
            info = f"{ow}x{oh}"
            pyxel.text(px + 4, py + 4, info, EDIT_TEXT_DIM)
        except Exception:
            pass

    def _draw_font_preview(self, px, py, pw, ph):
        """フォントプレビュー"""
        w = self._font_writer
        if w is None:
            return

        # フォントサイズ表示 + 操作ヒント
        pyxel.text(px + 4, py + 4, f"Size: {self._font_size}", EDIT_ACCENT)
        pyxel.text(px + 4, py + 14, "(scroll to change size)", EDIT_TEXT_DIM)

        # サンプルテキスト
        samples = [
            "ABCDEFGabcdefg",
            "0123456789!?@#",
            "あいうえおかきくけこ",
            "The quick brown fox",
            "吾輩は猫である。",
        ]
        ty = py + 30
        pyxel.clip(px + 2, py + 2, pw - 4, ph - 4)
        for line in samples:
            if ty + self._font_size > py + ph:
                break
            try:
                pyxel.text(px + 8, ty, line, EDIT_TEXT, w)
            except Exception:
                pyxel.text(px + 8, ty, line, EDIT_TEXT)
            ty += int(self._font_size * 1.6)
        pyxel.clip()

    def _draw_pvnm_preview(self, px, py, pw, ph):
        """PVNMファイルの基本情報プレビュー"""
        abs_path = self._selected_file_abs()
        if not abs_path:
            return
        try:
            rel = os.path.relpath(abs_path, self._base_dir)
        except ValueError:
            rel = os.path.basename(abs_path)

        fsz = _picker_text_size()
        lh = _picker_line_h(fsz)
        tx = px + 8
        ty = py + 8
        max_w = max(1, pw - 16)

        draw_unicode(tx, ty, "Project File:", EDIT_ACCENT,
                     size=fsz, bg_col=EDIT_BG)
        ty += lh + 2
        draw_unicode(tx, ty, _fit_text(rel, max_w, fsz), EDIT_TEXT,
                     size=fsz, bg_col=EDIT_BG)
        ty += lh + 8

        # ファイル情報
        try:
            import json
            stat = os.stat(abs_path)
            size_kb = stat.st_size / 1024

            with open(abs_path, encoding="utf-8") as f:
                data = json.load(f)
            ver = data.get("version", "?")
            n_scenes = len(data.get("scenes", []))
            n_parts = len(data.get("parts", []))
            n_chapters = len(data.get("chapters", []))
            lines = [
                f"Size: {size_kb:.1f} KB",
                f"Version: {ver}",
                f"Scenes: {n_scenes}",
            ]
            if ver >= 3:
                lines.append(f"Parts: {n_parts}  Chapters: {n_chapters}")
            for line in lines:
                if ty + _font_render_h(fsz) > py + ph - 4:
                    break
                draw_unicode(tx, ty, _fit_text(line, max_w, fsz),
                             EDIT_TEXT_DIM, size=fsz, bg_col=EDIT_BG)
                ty += lh
        except Exception:
            draw_unicode(tx, ty, "Cannot read file info", EDIT_TEXT_DIM,
                         size=fsz, bg_col=EDIT_BG)

    def _draw_palette_preview(self, px, py, pw, ph):
        """パレットファイルプレビュー（ファイル名とパスを表示）"""
        abs_path = self._selected_file_abs()
        if not abs_path:
            return
        try:
            rel = os.path.relpath(abs_path, self._base_dir)
        except ValueError:
            rel = os.path.basename(abs_path)

        pyxel.text(px + 4, py + 4, "Palette:", EDIT_ACCENT)
        # ファイル名
        fsz = _w._editor_font_size
        char_w = max(4, int(fsz * 0.65))
        max_c = max(1, (pw - 8) // char_w)
        draw_unicode(px + 4, py + 16, rel[:max_c], EDIT_TEXT, size=fsz)

        # パレットの色を読み込んでプレビュー
        colors = self._read_palette_colors(abs_path)
        if colors:
            swatch_size = min(32, (pw - 16) // 8)
            sx = px + 8
            sy = py + 32
            for i, (r, g, b) in enumerate(colors[:16]):
                col_x = sx + (i % 8) * (swatch_size + 2)
                col_y = sy + (i // 8) * (swatch_size + 2)
                # pyxel パレットに一時的に色を描画するのは難しいので
                # 最も近い pyxel カラーで表示
                nearest = self._nearest_pyxel_color(r, g, b)
                pyxel.rect(col_x, col_y, swatch_size, swatch_size, nearest)
                pyxel.rectb(col_x, col_y, swatch_size, swatch_size, EDIT_BORDER)
                # hex テキスト
                hex_str = f"#{r:02X}{g:02X}{b:02X}"
                if swatch_size >= 28:
                    pyxel.text(col_x + 2, col_y + swatch_size + 2, hex_str, EDIT_TEXT_DIM)

    def _read_palette_colors(self, abs_path: str) -> list:
        """パレットファイルからRGBタプルのリストを読み取る"""
        ext = os.path.splitext(abs_path)[1].lower()
        try:
            if ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
                from PIL import Image
                with Image.open(abs_path) as img:
                    rgb = img.convert("RGB")
                    pixels = list(rgb.getdata())
                return [(r, g, b) for r, g, b in pixels[:16]]
            else:
                colors = []
                with open(abs_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith(("//", ";")):
                            continue
                        try:
                            v = int(line.lstrip("#"), 16)
                            r = (v >> 16) & 0xFF
                            g = (v >> 8) & 0xFF
                            b = v & 0xFF
                            colors.append((r, g, b))
                        except ValueError:
                            continue
                        if len(colors) >= 16:
                            break
                return colors
        except Exception:
            return []

    def _draw_audio_preview(self, px, py, pw, ph, mx, my):
        """オーディオファイルのプレビュー（再生/停止）"""
        abs_path = self._selected_file_abs()
        if not abs_path:
            return
        try:
            rel = os.path.relpath(abs_path, self._base_dir)
        except ValueError:
            rel = os.path.basename(abs_path)

        pyxel.text(px + 4, py + 4, "Audio:", EDIT_ACCENT)
        fsz = _w._editor_font_size
        char_w = max(4, int(fsz * 0.65))
        max_c = max(1, (pw - 8) // char_w)
        draw_unicode(px + 4, py + 18, rel[:max_c], EDIT_TEXT, size=fsz)

        # 再生 / 停止ボタン
        ax = px + 8
        ay = py + 40
        playing = bool(self._audio_playing_path)
        draw_button(ax, ay, 70, "PLAY", h=22,
                    hover=is_hover(mx, my, ax, ay, 70, 22))
        draw_button(ax + 78, ay, 70, "STOP", h=22,
                    active=playing,
                    hover=is_hover(mx, my, ax + 78, ay, 70, 22))

        # ステータス
        status_y = ay + 30
        if playing:
            status = f"Playing: {os.path.basename(self._audio_playing_path)}"
            pyxel.text(px + 4, status_y, status[:40], EDIT_ACCENT)
        else:
            pyxel.text(px + 4, status_y, "(not playing)", EDIT_TEXT_DIM)

        # ファイルサイズ
        try:
            stat = os.stat(abs_path)
            size_kb = stat.st_size / 1024
            pyxel.text(px + 4, status_y + 14, f"Size: {size_kb:.1f} KB", EDIT_TEXT_DIM)
        except Exception:
            pass

    def _play_audio_preview(self):
        abs_path = self._selected_file_abs()
        if not abs_path or not os.path.exists(abs_path):
            return
        abs_path = os.path.abspath(abs_path)
        # 他の再生を止めてから再生
        self._stop_audio_preview()
        ch = self._audio_preview_ch
        snd = ch  # 同じインデックスのスロットを使う
        try:
            pyxel.sounds[snd].pcm(abs_path)
            pyxel.play(ch, snd, loop=True)
            self._audio_playing_path = abs_path
        except Exception:
            self._audio_playing_path = ""

    def _stop_audio_preview(self):
        if self._audio_playing_path:
            try:
                pyxel.stop(self._audio_preview_ch)
            except Exception:
                pass
            self._audio_playing_path = ""

    def _nearest_pyxel_color(self, r: int, g: int, b: int) -> int:
        """最も近い pyxel パレットカラーのインデックスを返す"""
        best_i = 0
        best_d = float("inf")
        for i in range(16):
            c = pyxel.colors[i]
            pr = (c >> 16) & 0xFF
            pg = (c >> 8) & 0xFF
            pb = c & 0xFF
            d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
            if d < best_d:
                best_d = d
                best_i = i
        return best_i
