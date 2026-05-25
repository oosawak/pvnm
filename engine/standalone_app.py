"""Standalone PVNM player app used by exported builds."""
from __future__ import annotations

import json
import os
import sys

import pyxel

from engine.script import load_json
from engine.player import VNPlayer, _draw_scanline_fade
from engine.image_cache import ImageCache
from engine import audio as _audio
from engine import image_cache as _image_cache_mod
from engine import palette as _palette_mod
from engine import platform_input as _platform_input
from engine import player_prefs as _player_prefs
from engine import runtime_assets as _runtime_assets
from engine import startup_timing as _startup_timing
from engine import storage as _storage
from engine.controller import GamepadControls
from engine.extra_text_config import has_extra_text_pages
from engine.gallery_config import has_gallery_pages
from engine.title_colors import normalize_button_colors, title_button_color_indices
from ui.extra_text_viewer import ExtraTextViewer
from ui.extras_menu import ExtrasMenu
from ui.gallery_preview import GalleryPreview
from ui.player_options import PlayerOptions
from ui.save_load_screen import SaveLoadScreen
from ui.title_screen import TitleScreen
from ui.widgets import set_bdf_dir


WIDTH, HEIGHT = 720, 480
MODE_TITLE = "title"
MODE_PLAY = "play"
TITLE_START_TRANSITION_FRAMES = 120
TITLE_START_TRANSITION_HALF = TITLE_START_TRANSITION_FRAMES // 2

def _runtime_base_dir() -> str:
    """Return the exported runtime data directory.

    In normal pyxapp/source runs, data lives beside the engine package root.
    In PyInstaller macOS .app builds, Python modules are loaded from
    ``Contents/Frameworks`` while data files are placed in
    ``Contents/Resources``. Prefer the directory that actually contains
    ``story.json`` so both layouts resolve assets consistently.
    """
    candidates: list[str] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            meipass = os.path.abspath(meipass)
            candidates.append(meipass)
            candidates.append(os.path.join(os.path.dirname(meipass),
                                           "Resources"))
            candidates.append(os.path.join(os.path.dirname(
                os.path.dirname(meipass)), "Resources"))
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates.append(os.path.abspath(os.path.join(exe_dir, "..",
                                                       "Resources")))
    candidates.append(os.path.dirname(os.path.dirname(os.path.abspath(
        __file__))))

    seen: set[str] = set()
    ordered: list[str] = []
    for path in candidates:
        path = os.path.abspath(path)
        if path not in seen:
            seen.add(path)
            ordered.append(path)
            if os.path.exists(os.path.join(path, "story.json")):
                return path
    return ordered[0]


_HERE = _runtime_base_dir()
_LAUNCH_CWD = os.getcwd()


def _load_optional_json(name: str, default):
    path = os.path.join(_HERE, name)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


class StandaloneApp:
    """Full exported-game runtime with title screen and player loop."""

    def __init__(self, title: str = "My Visual Novel",
                 storage_app_id: str = "pvnm-game"):
        self.title = title or "My Visual Novel"
        self.storage_app_id = storage_app_id or "pvnm-game"
        self.mode = MODE_TITLE
        self.player: VNPlayer | None = None
        self._quitting = False
        self._first_draw_recorded = False
        self._title_start_transition = False
        self._title_start_transition_frame = 0
        self._title_pending_load_state = None

        _startup_timing.mark("python.app_init.start")
        os.chdir(_HERE)

        # Initialize audio before pyxel.init(). On some Linux handheld
        # environments, loading SDL through Pyxel first can make pygame's
        # SDL_mixer reject MP3 files that pygame can load correctly on its own.
        _startup_timing.mark("audio.init.before_pyxel.start")
        _audio.init_audio()
        _startup_timing.mark("audio.init.before_pyxel.done", {
            "available": bool(getattr(_audio, "_available", False)),
        })

        _startup_timing.mark("pyxel.init.start")
        # Exported players handle ESC inside their own title/OPT/save screens.
        # Disable Pyxel's built-in ESC quit so modal back handling cannot leak
        # into an immediate app exit on desktop pyxapp builds.
        pyxel.init(WIDTH, HEIGHT, title=self.title, fps=30,
                   quit_key=pyxel.KEY_NONE)
        print(f"[PVNM] pyxel_size={pyxel.width}x{pyxel.height}")
        web_runtime = self._apply_web_canvas_fit()
        _startup_timing.mark("pyxel.init.done")
        pyxel.mouse(not web_runtime)

        _startup_timing.mark("fonts.init.start")
        set_bdf_dir(os.path.join(_HERE, "assets", "fonts",
                                 "efont-unicode-bdf"))
        _startup_timing.mark("fonts.init.done")

        _startup_timing.mark("palette.load.start")
        _palette_mod.load()
        _image_cache_mod.set_default_palette(
            _palette_mod.snapshot_pyxel_colors())
        _startup_timing.mark("palette.load.done")

        if not _audio._available:
            _startup_timing.mark("audio.init.after_pyxel.start")
            _audio.init_audio()
            _startup_timing.mark("audio.init.after_pyxel.done", {
                "available": bool(getattr(_audio, "_available", False)),
            })
        if not _audio._available:
            print("[INFO] Audio disabled")

        _startup_timing.mark("json.load.start")
        self.settings = _load_optional_json("settings.json", {})
        _storage.set_app_id(self.settings.get("storage_app_id",
                                              self.storage_app_id))
        self.endings = _load_optional_json("endings.json", [])
        self.story = load_json(os.path.join(_HERE, "story.json"))
        self.title_config = _load_optional_json("title_config.json", {})
        self.gallery_config = _load_optional_json("gallery_config.json", {})
        self.extra_text_config = _load_optional_json(
            "extra_text_config.json", {})
        _startup_timing.mark("json.load.done", {
            "scenes": len(self.story),
            "endings": len(self.endings),
        })

        _startup_timing.mark("asset_root.resolve.start")
        self.asset_root = _runtime_assets.find_asset_root(
            _HERE, launch_dir=_LAUNCH_CWD, argv=sys.argv)
        print(f"[PVNM] runtime_dir={_HERE}")
        print(f"[PVNM] launch_cwd={_LAUNCH_CWD}")
        print(f"[PVNM] asset_root={self.asset_root}")
        _startup_timing.mark("asset_root.resolve.done", {
            "external": self.asset_root != _HERE,
            "asset_root": self.asset_root,
        })

        _startup_timing.mark("image_cache.init.start")
        self.cache = ImageCache(self.asset_root, cache_dir="pvnm_cache")
        _startup_timing.mark("image_cache.init.done")

        self.controller = GamepadControls(self.settings)
        self.title_screen = TitleScreen()
        self.save_screen = SaveLoadScreen()
        self.options = PlayerOptions()
        self.extras_menu = ExtrasMenu()
        self.gallery_preview = GalleryPreview()
        self.extra_text_viewer = ExtraTextViewer()

        self._open_title_screen(restart_audio=True)
        _startup_timing.mark("pyxel.run.start")
        pyxel.run(self.update, self.draw)

    def _apply_web_canvas_fit(self):
        try:
            from js import window  # type: ignore
            apply_fit = getattr(window, "PVNM_APPLY_CANVAS_FIT", None)
            if apply_fit:
                apply_fit()
                print("[PVNM] web_canvas_fit=applied")
                return True
            print("[PVNM] web_canvas_fit=missing")
            return True
        except Exception:
            print("[PVNM] web_canvas_fit=unavailable")
            return False

    def _save_path(self) -> str:
        return _storage.runtime_data_path("pvnm_saves.json")

    def _ending_collection_key(self) -> str:
        return _player_prefs.project_key(_storage.app_id())

    def _ending_names(self) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()
        for ending in self.endings or []:
            name = str(ending.get("name", "") or "").strip()
            if name and name not in seen:
                names.append(name)
                seen.add(name)
        return names

    def _extras_available(self) -> bool:
        return (
            has_gallery_pages(self.gallery_config)
            or has_extra_text_pages(self.extra_text_config)
        )

    def _extras_unlocked(self) -> bool:
        if not self._extras_available():
            return False
        project = self._ending_collection_key()
        names = self._ending_names()
        if _player_prefs.all_endings_collected(project, names):
            return True
        _player_prefs.migrate_collected_endings_by_label(
            _storage.app_id(), project)
        return _player_prefs.all_endings_collected(project, names)

    def _mark_ending_collected(self, ending_name: str):
        _player_prefs.mark_ending_collected(
            self._ending_collection_key(), ending_name)

    def _restore_master_palette(self) -> None:
        try:
            _palette_mod.load()
            _image_cache_mod.set_default_palette(
                _palette_mod.snapshot_pyxel_colors())
        except Exception:
            pass

    def _apply_image_palette(self, image_paths: list[str],
                             extra_reserved_indices: set[int] | None = None
                             ) -> None:
        reserved = _palette_mod.reserved_from_settings(self.settings)
        if extra_reserved_indices:
            master = _palette_mod.as_array()
            if master is not None:
                for idx in extra_reserved_indices:
                    if isinstance(idx, int) and 0 <= idx < len(master):
                        reserved[idx] = (
                            int(master[idx, 0]),
                            int(master[idx, 1]),
                            int(master[idx, 2]),
                        )
        if not reserved:
            return
        pal = None
        if self.cache and hasattr(self.cache, "get_prebuilt_palette"):
            pal = self.cache.get_prebuilt_palette(image_paths, reserved)
        if pal is None:
            pal = _palette_mod.build_scene_palette(
                image_paths, reserved, base_dir=self.cache.base_dir)
        _palette_mod.apply_to_pyxel_colors(pal)
        _image_cache_mod.set_default_palette(pal)

    def _open_title_screen(self, restart_audio: bool = True):
        self.mode = MODE_TITLE
        self.player = None
        self._title_start_transition = False
        self._title_start_transition_frame = 0
        self._title_pending_load_state = None
        self._restore_master_palette()

        cfg = dict(self.title_config or {})
        button_colors = normalize_button_colors(cfg.get("button_colors"))
        bg_img = None
        bg_file = str(cfg.get("bg_image", "") or "")
        if bg_file:
            self._apply_image_palette(
                [bg_file],
                extra_reserved_indices=title_button_color_indices(button_colors))
            bg_img = self.cache.get(bg_file)

        self.title_screen.open(
            bg_image=bg_img,
            bg_fullscreen=bool(cfg.get("bg_fullscreen", False)),
            button_colors=button_colors,
            extras_available=self._extras_available(),
            extras_unlocked=self._extras_unlocked(),
            controller=self.controller,
        )

        if restart_audio:
            _audio.stop_bgm()
            _audio.stop_all_se()
            bgm_file = str(cfg.get("bgm_file", "") or "")
            if bgm_file:
                abs_bgm = _runtime_assets.resolve_asset_path(
                    bgm_file, self.cache.base_dir)
                _audio.play_bgm(abs_bgm,
                                volume=int(cfg.get("bgm_volume", 7) or 7),
                                loop=bool(cfg.get("bgm_loop", True)),
                                start=0.0)

    def _start_player(self, load_state: dict | None = None):
        self._restore_master_palette()
        start_scene = ""
        if isinstance(load_state, dict):
            start_scene = str(load_state.get("scene_name") or "")
        self.player = VNPlayer(
            self.story,
            start_scene=start_scene or None,
            cache=self.cache,
            endings=self.endings,
            settings=self.settings,
            ending_complete_callback=self._mark_ending_collected,
            defer_start=bool(load_state),
        )
        self.player.set_save_path(self._save_path())
        if load_state:
            self.player.load_save_state(load_state)
        self.mode = MODE_PLAY

    def _begin_title_start_transition(self, load_state: dict | None = None):
        self._title_pending_load_state = load_state
        self._title_start_transition = True
        self._title_start_transition_frame = 0
        self.title_screen.active = True
        self.save_screen.active = False
        self.options.active = False
        try:
            _audio.fadeout_bgm(TITLE_START_TRANSITION_FRAMES)
        except Exception:
            pass

    def _update_title_start_transition(self):
        _audio.update()
        self._title_start_transition_frame += 1
        if (self.mode == MODE_TITLE
                and self._title_start_transition_frame >= TITLE_START_TRANSITION_HALF):
            pending = self._title_pending_load_state
            self._title_pending_load_state = None
            self._start_player(pending)
        if self._title_start_transition_frame >= TITLE_START_TRANSITION_FRAMES:
            self._title_start_transition = False

    def _draw_title_start_transition_overlay(self):
        if not self._title_start_transition:
            return
        half = max(1, TITLE_START_TRANSITION_HALF)
        frame = max(0, min(TITLE_START_TRANSITION_FRAMES,
                           self._title_start_transition_frame))
        if frame < half:
            alpha = frame / half
        else:
            alpha = 1.0 - ((frame - half)
                           / max(1, TITLE_START_TRANSITION_FRAMES - half))
        _draw_scanline_fade(alpha)

    def _update_title(self):
        if self._title_start_transition:
            self._update_title_start_transition()
            return

        if self.gallery_preview.active:
            self.gallery_preview.update()
            if self.gallery_preview.closed:
                self.gallery_preview.closed = False
                self._open_title_screen(restart_audio=False)
            return

        if self.extra_text_viewer.active:
            self.extra_text_viewer.update()
            if self.extra_text_viewer.closed:
                self.extra_text_viewer.closed = False
                self._open_title_screen(restart_audio=False)
            return

        if self.extras_menu.active:
            self.extras_menu.update()
            result = self.extras_menu.result
            if result is None:
                return
            self.extras_menu.result = None
            if result == "gallery":
                self.gallery_preview.open(
                    self.gallery_config,
                    cache=self.cache,
                    base_dir=self.cache.base_dir,
                    settings=self.settings,
                    controller=self.controller,
                )
            elif result == "extra_text":
                self.extra_text_viewer.open(
                    self.extra_text_config,
                    controller=self.controller,
                )
            else:
                self._open_title_screen(restart_audio=False)
            return

        if self.save_screen.active:
            if _platform_input.consume_back_pressed() or self.controller.pressed("back"):
                self.save_screen.active = False
                self.save_screen.closed = False
                self._open_title_screen(restart_audio=False)
                return
            self.save_screen.update()
            if self.save_screen.closed:
                self.save_screen.closed = False
                result = self.save_screen.load_result
                if result:
                    self._begin_title_start_transition(load_state=result)
                else:
                    self._open_title_screen(restart_audio=False)
            return

        if self.options.active:
            if (pyxel.btnp(pyxel.KEY_ESCAPE)
                    or pyxel.btnp(pyxel.KEY_BACKSPACE)
                    or self.controller.pressed("back")
                    or _platform_input.consume_back_pressed()):
                self.options.handle_back()
                if self.options.closed:
                    self.options.closed = False
                    self._open_title_screen(restart_audio=False)
                return
            self.options.update()
            if self.options.closed:
                self.options.closed = False
                self._open_title_screen(restart_audio=False)
            return

        self.title_screen.update()
        result = self.title_screen.result
        if result is None:
            return
        self.title_screen.result = None
        if result == "start":
            self._begin_title_start_transition()
        elif result == "continue":
            self.title_screen.active = False
            self.save_screen.open("load", save_path=self._save_path(),
                                  controller=self.controller)
        elif result == "options":
            self.title_screen.active = False
            self.options.open(
                self.controller,
                text_size_getter=_player_prefs.load_text_size_override,
                text_size_effective_getter=self._effective_player_text_size,
                text_size_setter=self._save_player_text_size,
            )
        elif result == "extras":
            self.title_screen.active = False
            self.extras_menu.open(
                button_colors=self.title_screen._button_colors,
                show_gallery=has_gallery_pages(self.gallery_config),
                show_extra_text=has_extra_text_pages(self.extra_text_config),
                controller=self.controller,
            )
        elif result == "quit":
            self._quit_app()

    def _effective_player_text_size(self) -> int:
        override = _player_prefs.normalize_text_size(
            _player_prefs.load_text_size_override())
        if override is not None:
            return override
        try:
            return int(self.settings.get("dialog_font_size", 16))
        except Exception:
            return 16

    def _save_player_text_size(self, size: int | None):
        _player_prefs.save_text_size_override(
            _player_prefs.normalize_text_size(size))

    def _update_play(self):
        if self.player is None:
            self._open_title_screen(restart_audio=True)
            return
        self.player.update()
        if self._title_start_transition:
            self._update_title_start_transition()
        if self.player.finished:
            self.player = None
            self._open_title_screen(restart_audio=True)

    def _quit_app(self):
        if self._quitting:
            return
        self._quitting = True
        try:
            _audio.stop_bgm()
            _audio.stop_all_se()
            _audio.cleanup()
        except Exception:
            pass
        _platform_input.request_exit_app()
        pyxel.quit()

    def update(self):
        if pyxel.btnp(pyxel.KEY_Q) and pyxel.btn(pyxel.KEY_CTRL):
            self._quit_app()
            return
        if self.mode == MODE_TITLE:
            self._update_title()
        else:
            self._update_play()

    def draw(self):
        pyxel.cls(0)
        if self.mode == MODE_TITLE:
            self.title_screen.draw()
            if self.gallery_preview.active:
                self.gallery_preview.draw()
            if self.extra_text_viewer.active:
                self.extra_text_viewer.draw()
            if self.extras_menu.active:
                self.extras_menu.draw()
            if self.save_screen.active:
                self.save_screen.draw()
            if self.options.active:
                self.options.draw()
        elif self.player is not None:
            self.player.draw()

        if self._title_start_transition:
            self._draw_title_start_transition_overlay()

        if not self._first_draw_recorded:
            self._first_draw_recorded = True
            _startup_timing.mark("python.first_draw.done")


def App(title: str = "My Visual Novel", storage_app_id: str = "pvnm-game"):
    return StandaloneApp(title=title, storage_app_id=storage_app_id)
