"""Cross-platform native text dialogs for PVNM editor tools.

Pyxel itself is not suitable for IME-heavy text entry, so editor text input is
delegated to OS-native helpers where possible. Keeping this in one module
avoids macOS/Windows behavior drifting across editor panels.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading


def _apple_quote(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _run_osascript(script: str) -> str | None:
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except Exception as exc:
        print(f"[native_dialogs] osascript failed: {exc}")
        return None
    if result.returncode != 0:
        return None
    return result.stdout.rstrip("\n")


def _run_tk_script(script: str, *args: str) -> str | None:
    fd, out_path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        result = subprocess.run(
            [sys.executable, "-c", script, *args, out_path],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            msg = (result.stderr or result.stdout or "").strip()
            if msg:
                print(f"[native_dialogs] tkinter dialog failed: {msg[:400]}")
            return None
        if os.path.getsize(out_path) <= 0:
            return None
        with open(out_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and data.get("ok"):
            return str(data.get("value", ""))
        return None
    except Exception:
        return None
    finally:
        try:
            os.unlink(out_path)
        except Exception:
            pass


def ask_text(label: str, initial: str = "") -> str | None:
    """Ask for a single-line string. Returns None on cancel."""
    if sys.platform == "darwin":
        script = (
            f"text returned of (display dialog {_apple_quote(label)} "
            f"default answer {_apple_quote(initial)} with title \"PVNM\")"
        )
        return _run_osascript(script)

    script = (
        "import json,sys,tkinter as tk,tkinter.simpledialog as sd\n"
        "ini,lbl,out=sys.argv[1],sys.argv[2],sys.argv[3]\n"
        "root=tk.Tk(); root.withdraw(); root.attributes('-topmost', True)\n"
        "try: root.lift(); root.focus_force()\n"
        "except Exception: pass\n"
        "val=sd.askstring(lbl, lbl, initialvalue=ini, parent=root)\n"
        "root.destroy()\n"
        "if val is not None:\n"
        "    open(out,'w',encoding='utf-8').write(json.dumps({'ok':True,'value':val},ensure_ascii=False))\n"
    )
    return _run_tk_script(script, str(initial), str(label))


def ask_multiline(label: str, initial: str = "") -> str | None:
    """Ask for multi-line text. Returns None on cancel."""
    fd, ini_path = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    try:
        with open(ini_path, "w", encoding="utf-8") as f:
            f.write(str(initial))
        script = (
            "import json,os,sys,tkinter as tk,tkinter.ttk as ttk\n"
            "ini_file,lbl,out=sys.argv[1],sys.argv[2],sys.argv[3]\n"
            "ini=''\n"
            "if os.path.exists(ini_file):\n"
            "    ini=open(ini_file,'r',encoding='utf-8').read()\n"
            "root=tk.Tk(); root.withdraw(); root.title('PVNM - '+lbl)\n"
            "root.attributes('-topmost', True)\n"
            "w,h=640,420\n"
            "root.minsize(460,300)\n"
            "x=max(0,(root.winfo_screenwidth()-w)//2)\n"
            "y=max(0,(root.winfo_screenheight()-h)//3)\n"
            "root.geometry(f'{w}x{h}+{x}+{y}')\n"
            "tk.Label(root,text=lbl,font=('',12,'bold')).pack(padx=8,pady=(8,0),anchor='w')\n"
            "result=[None]\n"
            "def on_ok(e=None):\n"
            "    result[0]=txt.get('1.0','end-1c'); root.destroy(); return 'break'\n"
            "def on_cancel(e=None):\n"
            "    root.destroy(); return 'break'\n"
            "bf=tk.Frame(root); bf.pack(side='bottom',fill='x',padx=8,pady=(4,8))\n"
            "tk.Label(bf,text='Ctrl+Enter = OK / Esc = Cancel',fg='gray').pack(side='left')\n"
            "ttk.Button(bf,text='OK',command=on_ok,width=12).pack(side='right',padx=(4,0))\n"
            "ttk.Button(bf,text='Cancel',command=on_cancel,width=12).pack(side='right',padx=4)\n"
            "txt=tk.Text(root,font=('',13),wrap='word',undo=True)\n"
            "txt.pack(fill='both',expand=True,padx=8,pady=4); txt.insert('1.0',ini)\n"
            "ime_keys={'eisu_toggle','kana_shift','kana_lock','kanji','muhenkan','henkan','hiragana_katakana','mode_switch'}\n"
            "ime_keycodes={0,102,104,131,132}\n"
            "suppress_space=[False]\n"
            "last_text=[txt.get('1.0','end-1c')]\n"
            "def on_keypress(e):\n"
            "    keysym=(getattr(e,'keysym','') or '').lower()\n"
            "    keycode=getattr(e,'keycode',None)\n"
            "    if keysym in ime_keys or (sys.platform=='darwin' and keycode in ime_keycodes):\n"
            "        suppress_space[0]=True\n"
            "        root.after(80,lambda:suppress_space.__setitem__(0,False))\n"
            "        return 'break'\n"
            "    if sys.platform=='darwin' and keysym=='space' and suppress_space[0]:\n"
            "        suppress_space[0]=False\n"
            "        return 'break'\n"
            "    if sys.platform=='darwin' and keysym=='space' and keycode!=49:\n"
            "        return 'break'\n"
            "def remove_ime_space():\n"
            "    try:\n"
            "        if txt.get('insert-1c','insert')==' ':\n"
            "            txt.delete('insert-1c','insert')\n"
            "    except Exception:\n"
            "        pass\n"
            "    suppress_space[0]=False\n"
            "def on_keyrelease(e):\n"
            "    keysym=(getattr(e,'keysym','') or '').lower()\n"
            "    keycode=getattr(e,'keycode',None)\n"
            "    if keysym in ime_keys or (sys.platform=='darwin' and keycode in ime_keycodes):\n"
            "        suppress_space[0]=True\n"
            "        root.after(1,remove_ime_space)\n"
            "def watch_text():\n"
            "    cur=txt.get('1.0','end-1c')\n"
            "    prev=last_text[0]\n"
            "    if sys.platform=='darwin' and suppress_space[0] and len(cur)==len(prev)+1 and cur.startswith(prev):\n"
            "        added=cur[len(prev):]\n"
            "        if added==' ':\n"
            "            try:\n"
            "                txt.delete('insert-1c','insert')\n"
            "                cur=txt.get('1.0','end-1c')\n"
            "            except Exception:\n"
            "                pass\n"
            "            suppress_space[0]=False\n"
            "    last_text[0]=cur\n"
            "    root.after(25,watch_text)\n"
            "txt.bind('<Control-Return>',on_ok); txt.bind('<Control-KP_Enter>',on_ok)\n"
            "txt.bind('<Command-Return>',on_ok); txt.bind('<KeyPress>',on_keypress)\n"
            "txt.bind('<KeyRelease>',on_keyrelease)\n"
            "root.bind('<Control-Return>',on_ok)\n"
            "root.bind('<Command-Return>',on_ok); root.bind('<Escape>',on_cancel)\n"
            "root.protocol('WM_DELETE_WINDOW',on_cancel)\n"
            "root.deiconify(); root.lift()\n"
            "root.after(20,lambda:(root.lift(),txt.focus_force()))\n"
            "root.after(25,watch_text)\n"
            "root.mainloop()\n"
            "if result[0] is not None:\n"
            "    open(out,'w',encoding='utf-8').write(json.dumps({'ok':True,'value':result[0]},ensure_ascii=False))\n"
        )
        return _run_tk_script(script, ini_path, str(label))
    finally:
        try:
            os.unlink(ini_path)
        except Exception:
            pass


def ask_save_file(title: str, initial_path: str = "",
                  defaultextension: str = "",
                  filetypes: list[tuple[str, str]] | None = None) -> str | None:
    """Ask for a save path using the OS file dialog. Returns None on cancel."""
    initial_path = str(initial_path or "")
    initial_dir = os.path.dirname(os.path.abspath(initial_path)) or os.getcwd()
    initial_file = os.path.basename(initial_path)
    dialog_initial_file = initial_file
    ext = str(defaultextension or "")
    if ext and not ext.startswith("."):
        ext = "." + ext
    # macOS Tk/NSSavePanel appends the selected file type extension to the
    # display name. Passing "name.pyxapp" here can show "name.pyxapp.pyxapp";
    # the caller still normalizes the returned path, so the dialog seed can be
    # extensionless.
    while ext and dialog_initial_file.lower().endswith(ext.lower()):
        dialog_initial_file = dialog_initial_file[:-len(ext)]
    ft = filetypes or [("All files", "*.*")]
    script = (
        "import json,os,sys,tkinter as tk,tkinter.filedialog as fd\n"
        "title,initialdir,initialfile,ext,ft_json,out=sys.argv[1:7]\n"
        "filetypes=json.loads(ft_json)\n"
        "root=tk.Tk(); root.title('PVNM')\n"
        "root.attributes('-topmost', True)\n"
        "root.geometry('1x1+120+120')\n"
        "try: root.update_idletasks(); root.deiconify(); root.lift(); root.focus_force()\n"
        "except Exception: pass\n"
        "try: root.after(80, lambda: (root.lift(), root.focus_force()))\n"
        "except Exception: pass\n"
        "val=fd.asksaveasfilename(title=title,initialdir=initialdir,"
        "initialfile=initialfile,defaultextension='',filetypes=filetypes,"
        "parent=root)\n"
        "root.destroy()\n"
        "if val:\n"
        "    open(out,'w',encoding='utf-8').write(json.dumps({'ok':True,'value':val},ensure_ascii=False))\n"
    )
    return _run_tk_script(
        script,
        title,
        initial_dir,
        dialog_initial_file,
        defaultextension,
        json.dumps(ft, ensure_ascii=False),
    )


class AsyncTextDialog:
    """Run a text dialog in a background thread and poll it from Pyxel."""

    def __init__(self):
        self._thread = None
        self._result = None
        self._ready = False
        self._cb = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def open(self, label: str, initial: str, callback,
             multiline: bool = False):
        if self.running:
            return
        self._cb = callback
        self._ready = False

        def _run():
            self._result = (ask_multiline(label, initial)
                            if multiline else ask_text(label, initial))
            self._ready = True

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def poll(self) -> bool:
        if not self._ready:
            return False
        self._ready = False
        val = self._result
        self._result = None
        cb = self._cb
        self._cb = None
        if not self._thread or not self._thread.is_alive():
            self._thread = None
        if cb and val is not None:
            cb(val)
        return True


class AsyncSaveFileDialog:
    """Run an OS save-file dialog without blocking the Pyxel event loop."""

    def __init__(self):
        self._thread = None
        self._result = None
        self._ready = False
        self._cb = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def open(self, title: str, initial_path: str, defaultextension: str,
             filetypes: list[tuple[str, str]], callback):
        if self.running:
            return
        self._cb = callback
        self._ready = False

        def _run():
            self._result = ask_save_file(
                title, initial_path, defaultextension, filetypes)
            self._ready = True

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def poll(self) -> bool:
        if not self._ready:
            return False
        self._ready = False
        val = self._result
        self._result = None
        cb = self._cb
        self._cb = None
        if not self._thread or not self._thread.is_alive():
            self._thread = None
        if cb and val:
            cb(val)
        return True
