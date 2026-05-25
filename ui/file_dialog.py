"""ファイルパス入力ダイアログ（モーダルオーバーレイ, 720×480 対応）"""
import os
import pyxel
from ui.colors import *
from ui.widgets import draw_panel, draw_titlebar

_DW, _DH = 440, 80


class FileDialog:
    """
    Ctrl+S / Ctrl+O / Ctrl+E で開くモーダルダイアログ。
    update() / draw() を毎フレーム呼ぶ。
    確定すると result にパスが入り active=False。
    キャンセルすると cancelled=True。
    """

    def __init__(self):
        self.active    = False
        self.mode      = "save"
        self._path     = ""
        self.result    = None
        self.cancelled = False

    def open_save(self, default_path: str = ""):
        self._init("save", default_path or "./untitled.pvnm")

    def open_load(self, default_path: str = ""):
        self._init("open", default_path or "./")

    def update(self):
        if not self.active:
            return

        if pyxel.btnp(pyxel.KEY_BACKSPACE):
            self._path = self._path[:-1]

        if pyxel.btnp(pyxel.KEY_RETURN):
            path = self._path.strip()
            if path:
                if not os.path.splitext(path)[1]:
                    path += ".pvnm"
                self.result = path
                self.active = False
            return

        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self.cancelled = True
            self.active    = False
            return

        # Ctrl+V / Cmd+V: クリップボードから貼り付け
        _cmd = pyxel.btn(pyxel.KEY_CTRL) or pyxel.btn(pyxel.KEY_GUI)
        if _cmd and pyxel.btnp(pyxel.KEY_V):
            text = _get_clipboard()
            if text:
                self._path += text.strip()
            return
        if _cmd:
            return

        for code in range(32, 127):
            if pyxel.btnp(code):
                ch = _path_char(code, pyxel.btn(pyxel.KEY_SHIFT))
                if ch:
                    self._path += ch

    def draw(self):
        if not self.active:
            return

        W, H = pyxel.width, pyxel.height
        dx = (W - _DW) // 2
        dy = (H - _DH) // 2

        # 薄暗いオーバーレイ
        for y in range(0, H, 2):
            pyxel.line(0, y, W - 1, y, 0)

        pyxel.rect(dx - 4, dy - 4, _DW + 8, _DH + 8, EDIT_BORDER)
        draw_panel(dx, dy, _DW, _DH)
        title_map = {"save": "SAVE AS", "open": "OPEN FILE",
                     "export": "EXPORT AS .pyxapp"}
        draw_titlebar(dx, dy, _DW, title_map.get(self.mode, "FILE"))

        pyxel.text(dx + 6, dy + 18, "Path:", EDIT_TEXT_DIM)

        fx, fy = dx + 6, dy + 28
        fw, fh = _DW - 12, 20
        pyxel.rect(fx, fy, fw, fh, EDIT_BG)
        pyxel.rectb(fx, fy, fw, fh, EDIT_ACCENT)
        max_chars = (fw - 8) // 4
        display   = self._path[-max_chars:]
        cursor    = "|" if pyxel.frame_count % 30 < 15 else ""
        pyxel.text(fx + 4, fy + 7, display + cursor, EDIT_TEXT)

        pyxel.text(dx + 6, dy + _DH - 14,
                   "Enter = confirm    Esc = cancel", EDIT_TEXT_DIM)

    def _init(self, mode, default):
        self.active    = True
        self.mode      = mode
        self._path     = default
        self.result    = None
        self.cancelled = False


def _get_clipboard() -> str:
    import sys, subprocess
    try:
        if sys.platform == "darwin":
            r = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=2)
            return r.stdout
        elif sys.platform == "win32":
            r = subprocess.run(
                ["powershell", "-NoProfile", "-command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=2,
            )
            return r.stdout.rstrip("\r\n")
        else:
            r = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True, text=True, timeout=2,
            )
            return r.stdout
    except Exception:
        return ""


def _path_char(code: int, shift: bool) -> str:
    if 97 <= code <= 122:  # pyxel.KEY_A=97 .. KEY_Z=122
        return chr(code - 32) if shift else chr(code)
    if 48 <= code <= 57:
        return "" if shift else chr(code)
    return {
        pyxel.KEY_SLASH:  "/",
        pyxel.KEY_PERIOD: ".",
        pyxel.KEY_MINUS:  "_" if shift else "-",
        pyxel.KEY_SPACE:  " ",
    }.get(code, "")
