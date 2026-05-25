"""ビジュアルノベルメーカー PVNM (720×480)"""
import os
import json
import threading
import random
import shlex
import subprocess
import sys
import pyxel
from editor_state import EditorState
from ui.panels import (SceneListPanel, MainViewPanel, PropertiesPanel, Toolbar,
                       set_file_picker_cache, set_file_picker_base,
                       set_file_picker_settings,
                       get_file_picker_base,
                       is_file_picker_active, draw_file_picker,
                       open_file_picker, update_file_picker)
from ui.native_dialogs import AsyncSaveFileDialog
from ui.quit_dialog import QuitDialog
from ui.confirm_dialog import ConfirmDialog
from ui.color_editor import ColorEditor
from ui.speaker_color_editor import SpeakerColorEditor
from ui.colors import apply_role_indices as _apply_role_indices
from ui.toast import Toast
from ui.widgets import (set_editor_font, set_ui_font_size, set_font_base_dir,
                        set_ui_scale, set_bdf_dir,
                        draw_unicode, text_px_w, _font_render_h)
from engine.script import from_editor_state
from engine.player import VNPlayer, _draw_scanline_fade
from engine.ending_player import EndingPlayer
from engine.export import (
    export_android_apk,
    export_capacitor_project,
    export_macos_app,
    export_pyxapp,
    export_pyxapp_external_assets,
    export_web_html,
    export_windows_exe,
)
from engine.github_actions import trigger_github_workflow
from engine.md_import import import_into_state as _md_import_into_state
from engine.image_cache import ImageCache
from engine import image_cache as _image_cache_mod
from engine import palette as _master_palette
from engine import player_prefs as _player_prefs
from engine.controller import GamepadControls
from engine.title_colors import (
    normalize_button_colors,
    title_button_color_indices,
)
from engine.gallery_config import normalize_gallery_config, has_gallery_pages
from engine.extra_text_config import (
    normalize_extra_text_config,
    has_extra_text_pages,
)
from ui.font_settings_editor import FontSettingsEditor
from ui.part_chapter_editor import PartChapterEditor
from engine.player import set_dialog_font_size
from ui.title_screen import TitleScreen
from ui.save_load_screen import SaveLoadScreen
from ui.player_options import PlayerOptions
from ui.ending_editor import EndingEditor
from ui.settings_menu import SettingsMenu
from ui.title_config_editor import TitleConfigEditor
from ui.gallery_config_editor import GalleryConfigEditor
from ui.gallery_preview import GalleryPreview
from ui.extra_text_config_editor import ExtraTextConfigEditor
from ui.extra_text_viewer import ExtraTextViewer
from ui.extras_menu import ExtrasMenu


WIDTH  = 720
HEIGHT = 480

MODE_EDITOR = "editor"
MODE_PLAY   = "play"
MODE_QUIT   = "quit"
MODE_COLORS        = "colors"
MODE_SPEAKER_COLORS = "speaker_colors"
MODE_FONT_SETTINGS = "font_settings"
MODE_PARTS         = "parts"
MODE_CHAPTERS      = "chapters"
MODE_TITLE         = "title"
MODE_ENDINGS       = "endings"
MODE_SETTINGS      = "settings"
MODE_TITLE_CONFIG  = "title_config"
MODE_GALLERY_CONFIG = "gallery_config"
MODE_GALLERY_PREVIEW = "gallery_preview"
MODE_EXTRA_TEXT_CONFIG = "extra_text_config"
MODE_EXTRA_TEXT_PREVIEW = "extra_text_preview"
MODE_ENDING_PLAY   = "ending_play"
MODE_FONT_TEST     = "font_test"

TITLE_START_TRANSITION_FRAMES = 120
TITLE_START_TRANSITION_HALF = TITLE_START_TRANSITION_FRAMES // 2
EXPORT_DIR_NAME = "export"


def _normalize_save_output_path(path: str, ext: str) -> tuple[str, bool]:
    """Return a safe output path whose extension matches the requested action.

    OS save dialogs may replace the typed filename when an existing file is
    clicked. For export/save actions with a fixed extension, PVNM must not let
    that unrelated extension become the final overwrite target.
    """
    out = os.path.abspath(os.path.expanduser(str(path or ""))).rstrip(os.sep)
    wanted = str(ext or "").strip()
    if not out or not wanted:
        return out, False
    if not wanted.startswith("."):
        wanted = "." + wanted
    root, current = os.path.splitext(out)
    lower_out = out.lower()
    lower_wanted = wanted.lower()
    repeated = lower_wanted + lower_wanted
    if lower_out.endswith(repeated):
        while out.lower().endswith(repeated):
            out = out[:-len(wanted)]
        return out, True
    if current != wanted:
        return (root + wanted if current else out + wanted), True
    return out, False


class App:
    def __init__(self):
        # quit_key=pyxel.KEY_NONE で ESC による自動終了を無効化。
        # 終了は QuitDialog 経由で明示的に行う。
        pyxel.init(WIDTH, HEIGHT, title="Palette Visual Novel Maker (PVNM)", fps=30,
                   quit_key=pyxel.KEY_NONE)
        pyxel.mouse(True)

        # 音声バックエンド (pygame.mixer 44.1kHz) を初期化する。
        # pyxel 組込 PCM は 22050Hz で音質に難があるため別系統に置き換え。
        # pygame import 失敗時は audio.py 側で no-op に落ちる。
        from engine import audio as _audio
        _audio.init_audio()

        self.mode  = MODE_EDITOR
        self.state = EditorState()

        self._base_dir = os.path.dirname(os.path.abspath(__file__))
        self.cache = ImageCache(self._base_dir)
        set_font_base_dir(self._base_dir)
        # UI 全体の文字描画を BDF (efont-unicode-bdf) で統一する。
        # pyxel.Font(BDF) はラスタライズなしでビットマップを直接描画するので
        # サイズ・字種を問わず破綻しない。
        set_bdf_dir(os.path.join(self._base_dir,
                                 "assets/fonts/efont-unicode-bdf"))

        # マスターパレット (256色) を pyxel.colors[] に読み込む。
        # 役割→indexの割当は ui/colors.py が settings.json から読み込み済み。
        _master_palette.load()

        # settings.json を読み込んでフォントを初期化
        self._settings = _load_settings(self._base_dir)
        _ensure_palettes(self._settings)
        _init_fonts(self._base_dir, self._settings)

        # ImageCache の量子化基準パレットとして pyxel.colors[] を登録
        _image_cache_mod.set_default_palette(_master_palette.snapshot_pyxel_colors())

        _main_view = MainViewPanel(self.state)
        _props     = PropertiesPanel(self.state)
        _main_view.set_props_panel(_props)
        _main_view.set_settings(self._settings)
        _main_view.set_cache(self.cache)
        self.panels = [
            SceneListPanel(self.state),
            _main_view,
            _props,
            Toolbar(self.state),
        ]
        set_file_picker_cache(self.cache)
        set_file_picker_base(self._base_dir)
        set_file_picker_settings(self._settings)
        self.player        = None
        self.ending_runtime: EndingPlayer | None = None
        self._ending_runtime_name = ""
        self.quit_dialog   = QuitDialog()
        self.confirm_dialog = ConfirmDialog()
        self.color_editor      = ColorEditor()
        self.speaker_color_editor = SpeakerColorEditor()
        self.font_settings_editor = FontSettingsEditor()
        self.part_editor    = PartChapterEditor()
        self.chapter_editor = PartChapterEditor()
        self.toast         = Toast()
        self.title_screen  = TitleScreen()
        self.ending_editor = EndingEditor()
        self.ending_editor.set_cache(self.cache)
        self.settings_menu = SettingsMenu()
        self.title_config_editor = TitleConfigEditor()
        self.gallery_config_editor = GalleryConfigEditor()
        self.gallery_preview = GalleryPreview()
        self.extra_text_config_editor = ExtraTextConfigEditor()
        self.extra_text_viewer = ExtraTextViewer()
        self.extras_menu = ExtrasMenu()
        self._gallery_image_picker_root = ""
        self._gallery_image_picker_project_base = ""
        self._last_import_md_path = str(
            self._settings.get("last_import_markdown_path", "") or "")
        self._title_save_screen = SaveLoadScreen()
        self._title_options = PlayerOptions()
        self._title_controller = GamepadControls(self._settings)
        self._title_start_transition = False
        self._title_start_transition_frame = 0
        self._title_pending_load_state = None
        self._title_active_config = None
        self._ending_to_title_transition = False
        self._ending_to_title_transition_frame = 0
        self._return_mode  = MODE_EDITOR  # sub-editor の戻り先
        self._title_return_mode = MODE_EDITOR  # タイトル画面終了時の戻り先
        self._save_dialog = AsyncSaveFileDialog()
        self._save_dialog_cooldown = 0
        self._export_thread: threading.Thread | None = None
        self._export_result = None
        self._export_status = ""
        self._export_next_steps: dict | None = None
        self._pending_export_action = ""
        self._pending_confirm_action = ""
        self._pending_save_path = ""
        self._pending_save_callback = None
        self._restore_last_project()

        pyxel.run(self.update, self.draw)

    # ── update ──────────────────────────────────────────────────

    def update(self):
        self.toast.update()
        self._check_export_thread()
        if self._save_dialog.poll():
            self._save_dialog_cooldown = 8
        if self._save_dialog.running:
            return
        if self._save_dialog_cooldown > 0:
            self._save_dialog_cooldown -= 1
        if self._export_next_steps:
            if self._update_export_next_steps():
                return
            return
        if self._export_thread and self._export_thread.is_alive():
            return
        if self.confirm_dialog.active and self.mode == MODE_QUIT:
            self._update_confirm_dialog()
            return

        # フォント検証ページ: SPACE / ENTER でエディタへ
        if self.mode == MODE_FONT_TEST:
            if (pyxel.btnp(pyxel.KEY_SPACE) or pyxel.btnp(pyxel.KEY_RETURN)
                    or pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT)):
                self.mode = MODE_EDITOR
            return

        # ── ESC は常にエディターへ戻る ───────────────────────
        if (pyxel.btnp(pyxel.KEY_ESCAPE) and not is_file_picker_active()
                and not self.confirm_dialog.active):
            if self.mode == MODE_QUIT:
                self.mode = MODE_EDITOR
            elif self.mode == MODE_EDITOR and self.state.preview_expanded:
                self.state.preview_expanded = False
            elif self.mode == MODE_PLAY:
                if self.player is not None and self.player.modal_active():
                    self._update_play()
                else:
                    self._return_to_editor()
            elif self.mode == MODE_ENDING_PLAY:
                # ESC で再生終了 → return_to (中断時の戻り先) へ
                if self.ending_runtime is not None:
                    self._capture_ending_preview_time()
                    self.ending_runtime.finished = True
                    self.ending_runtime.aborted = True
                self._finish_ending_play(
                    getattr(self, "_ending_return_mode", MODE_EDITOR))
            elif self.mode == MODE_TITLE:
                if self.gallery_preview.active:
                    self.gallery_preview.close()
                    self.gallery_preview.closed = False
                    self._restore_title_after_modal()
                    return
                if self.extra_text_viewer.active:
                    self.extra_text_viewer.close()
                    self.extra_text_viewer.closed = False
                    self._restore_title_after_modal()
                    return
                if self.extras_menu.active:
                    self.extras_menu.active = False
                    self.extras_menu.result = None
                    self._restore_title_after_modal()
                    return
                if self._title_options.active:
                    self._title_options.handle_back()
                    if self._title_options.closed:
                        self._title_options.closed = False
                    self._restore_title_after_modal()
                    return
                if self._title_save_screen.active:
                    self._title_save_screen.active = False
                    self._title_save_screen.closed = False
                    self._restore_title_after_modal()
                    return
                self.title_screen.active = False
                self._title_save_screen.active = False
                self._stop_title_audio()
                # タイトル BG 用に書き換えていた pyxel.colors[] / ImageCache を戻す
                self._restore_master_palette()
                self._title_start_transition = False
                self._title_pending_load_state = None
                ret = self._title_return_mode
                self._title_return_mode = MODE_EDITOR
                if ret == MODE_TITLE_CONFIG:
                    self.title_config_editor.refresh_palette_grid()
                self.mode = ret
            elif self.mode == MODE_COLORS:
                self._update_colors()
                return
            elif self.mode == MODE_SPEAKER_COLORS:
                self._update_speaker_colors()
                return
            elif self.mode == MODE_FONT_SETTINGS:
                self._update_font_settings()
                return
            elif self.mode == MODE_SETTINGS:
                self.settings_menu.active = False
                self.mode = MODE_EDITOR
            elif self.mode == MODE_TITLE_CONFIG:
                # 子エディタ自身が ESC を処理する: 通常 update に流す
                self._update_title_config()
                return
            elif self.mode == MODE_GALLERY_CONFIG:
                # 子エディタ自身が ESC を処理する: 通常 update に流す
                self._update_gallery_config()
                return
            elif self.mode == MODE_GALLERY_PREVIEW:
                self._update_gallery_preview()
                return
            elif self.mode == MODE_EXTRA_TEXT_CONFIG:
                self._update_extra_text_config()
                return
            elif self.mode == MODE_EXTRA_TEXT_PREVIEW:
                self._update_extra_text_preview()
                return
            elif self.mode == MODE_PARTS:
                # 子エディタ自身が ESC を処理する: ここでは消費せず通常の update に流す
                self._update_parts()
                return
            elif self.mode == MODE_CHAPTERS:
                self._update_chapters()
                return
            elif self.mode == MODE_ENDINGS:
                # EndingEditor 自身が ESC を処理する
                self._update_endings()
                return
            # MODE_EDITOR では何もしない
            return

        # ── Ctrl/Cmd+Q → 終了ダイアログ ─────────────────────
        if not is_file_picker_active():
            if (pyxel.btn(pyxel.KEY_CTRL) or pyxel.btn(pyxel.KEY_GUI)):
                if pyxel.btnp(pyxel.KEY_Q):
                    self._open_quit_dialog()
                    return

        if self.mode == MODE_EDITOR:
            self._update_editor()
        elif self.mode == MODE_PLAY:
            self._update_play()
        elif self.mode == MODE_QUIT:
            self._update_quit_dialog()
        elif self.mode == MODE_COLORS:
            self._update_colors()
        elif self.mode == MODE_SPEAKER_COLORS:
            self._update_speaker_colors()
        elif self.mode == MODE_FONT_SETTINGS:
            self._update_font_settings()
        elif self.mode == MODE_TITLE:
            self._update_title()
        elif self.mode == MODE_ENDINGS:
            self._update_endings()
        elif self.mode == MODE_SETTINGS:
            self._update_settings()
        elif self.mode == MODE_TITLE_CONFIG:
            self._update_title_config()
        elif self.mode == MODE_GALLERY_CONFIG:
            self._update_gallery_config()
        elif self.mode == MODE_GALLERY_PREVIEW:
            self._update_gallery_preview()
        elif self.mode == MODE_EXTRA_TEXT_CONFIG:
            self._update_extra_text_config()
        elif self.mode == MODE_EXTRA_TEXT_PREVIEW:
            self._update_extra_text_preview()
        elif self.mode == MODE_PARTS:
            self._update_parts()
        elif self.mode == MODE_CHAPTERS:
            self._update_chapters()
        elif self.mode == MODE_ENDING_PLAY:
            self._update_ending_play()

    def _update_editor(self):
        # 確認ダイアログが開いている間はパネル操作をブロック
        if self.confirm_dialog.active:
            self._update_confirm_dialog()
            return
        # ファイルピッカーがアクティブな場合は PropertiesPanel のみ更新
        if is_file_picker_active():
            for panel in self.panels:
                if isinstance(panel, PropertiesPanel):
                    panel.update()
            return

        ctrl = pyxel.btn(pyxel.KEY_CTRL) or pyxel.btn(pyxel.KEY_GUI)
        alt = False
        for key_name in ("KEY_ALT", "KEY_OPTION"):
            key = getattr(pyxel, key_name, None)
            if key is not None and pyxel.btn(key):
                alt = True
                break

        if self._save_dialog_cooldown > 0:
            return

        if ctrl and pyxel.btnp(pyxel.KEY_S):
            if pyxel.btn(pyxel.KEY_SHIFT) or not self.state.file_path:
                self._open_project_save_as_dialog()
            else:
                self._do_save(self.state.file_path)
            return

        if ctrl and pyxel.btnp(pyxel.KEY_O):
            self._request_open_project()
            return

        if ctrl and pyxel.btnp(pyxel.KEY_N):
            self._request_new_project()
            return

        if ctrl and pyxel.btnp(pyxel.KEY_E):
            if alt and pyxel.btn(pyxel.KEY_SHIFT):
                self._launch_export_action("capacitor")
            elif alt:
                self._launch_export_action("web")
            elif pyxel.btn(pyxel.KEY_SHIFT):
                self._launch_export_action("macos")
            else:
                self._launch_export_action("pyxapp")
            return

        if not ctrl and pyxel.btnp(pyxel.KEY_1):
            self._start_play()
            return

        # プレビュー拡大モード中は MainViewPanel のみ update
        # (他パネルへの誤クリックを防ぐ)
        if self.state.preview_expanded:
            for panel in self.panels:
                if isinstance(panel, MainViewPanel):
                    panel.update()
        else:
            for panel in self.panels:
                panel.update()

        if self.state.request_play:
            self.state.request_play = False
            self._start_play()

        if self.state.request_open:
            self.state.request_open = False
            self._request_open_project()

        if self.state.request_colors:
            self.state.request_colors = False
            self._return_mode = MODE_EDITOR
            self._restore_master_palette()
            self.color_editor.open(
                role_indices=self._settings.get("dialog_role_indices"))
            self.mode = MODE_COLORS

        if self.state.request_font_settings:
            self.state.request_font_settings = False
            self._return_mode = MODE_EDITOR
            self.font_settings_editor.open(self._settings, self._base_dir)
            self.mode = MODE_FONT_SETTINGS

        if self.state.request_parts:
            self.state.request_parts = False
            self.part_editor.open_parts(self.state)
            self.mode = MODE_PARTS

        if self.state.request_chapters:
            self.state.request_chapters = False
            self.chapter_editor.open_chapters(self.state, self.state.current_part_id)
            self.mode = MODE_CHAPTERS

        if self.state.request_title:
            self.state.request_title = False
            self._open_title_screen()

        if self.state.request_endings:
            self.state.request_endings = False
            self._return_mode = MODE_EDITOR
            self.ending_editor.open(self.state.endings)
            self.mode = MODE_ENDINGS

        if self.state.request_settings:
            self.state.request_settings = False
            self.settings_menu.open(self.state.title_config)
            self.mode = MODE_SETTINGS

        if self.state.request_quit:
            self.state.request_quit = False
            self._open_quit_dialog()

        if self.state.request_delete_scene:
            self.state.request_delete_scene = False
            self._open_delete_scene_confirm()

        if self.state.request_import_md:
            self.state.request_import_md = False
            self._open_import_md_picker()

    def _update_parts(self):
        self.part_editor.update()
        if self.part_editor.result:
            if self.part_editor.result == "saved":
                self.toast.show("Parts updated")
            self.part_editor.active = False
            self.mode = MODE_EDITOR

    def _update_chapters(self):
        self.chapter_editor.update()
        if self.chapter_editor.result:
            if self.chapter_editor.result == "saved":
                self.toast.show("Chapters updated")
            self.chapter_editor.active = False
            self.mode = MODE_EDITOR

    def _update_endings(self):
        # ファイルピッカーがアクティブな場合はそちらを優先
        if is_file_picker_active():
            update_file_picker()
            return
        self.ending_editor.update()
        # PREVIEW ボタンが押されたか? (エディタは active のまま維持)
        if self.ending_editor.preview_request is not None:
            preview = self.ending_editor.preview_request
            start_sec = float(self.ending_editor.preview_start_for_request or 0.0)
            self.ending_editor.preview_request = None
            # プレビューは ESC でも自然終了でも編集画面に戻す (タイトルを開かない)。
            # goto_ending チェーンはプレビューでも有効 (state.endings から検索)。
            self._start_ending_play(preview, return_to=MODE_ENDINGS,
                                    natural_to=MODE_ENDINGS,
                                    preview_start_sec=start_sec)
            return
        if self.ending_editor.result:
            if self.ending_editor.result == "saved":
                self.state.endings = self.ending_editor.get_endings()
                self.state.dirty = True
                self.toast.show("Endings updated")
            self.ending_editor.active = False
            ret = self._return_mode
            self._return_mode = MODE_EDITOR
            if ret == MODE_SETTINGS:
                self.settings_menu.open(self.state.title_config)
            self.mode = ret

    def _update_settings(self):
        """統合設定メニューの更新"""
        if self.confirm_dialog.active:
            self._update_confirm_dialog()
            return

        # ファイルピッカーがアクティブな場合はそちらを優先
        if is_file_picker_active():
            update_file_picker()
            return

        self.settings_menu.update()
        result = self.settings_menu.result
        if result is None:
            return

        self.settings_menu.result = None

        if result == "closed":
            self.settings_menu.active = False
            self.mode = MODE_EDITOR
        elif isinstance(result, str) and result.startswith("project:"):
            self._launch_project_action(result.split(":", 1)[1])
        elif isinstance(result, str) and result.startswith("export:"):
            self._launch_export_action(result.split(":", 1)[1])
        elif isinstance(result, str) and result.startswith("tool:"):
            self._launch_tool_action(result.split(":", 1)[1])
        elif result == "ending":
            self._return_mode = MODE_SETTINGS
            self.ending_editor.open(self.state.endings)
            self.mode = MODE_ENDINGS
        elif result == "font":
            self._return_mode = MODE_SETTINGS
            self.font_settings_editor.open(self._settings, self._base_dir)
            self.mode = MODE_FONT_SETTINGS
        elif result == "color":
            self._return_mode = MODE_SETTINGS
            self._restore_master_palette()
            self.color_editor.open(
                role_indices=self._settings.get("dialog_role_indices"))
            self.mode = MODE_COLORS
        elif result == "speakers":
            self._return_mode = MODE_SETTINGS
            self._restore_master_palette()
            self.speaker_color_editor.open(
                self._settings.get("speaker_colors"))
            self.mode = MODE_SPEAKER_COLORS
        elif result == "title":
            # TITLE Config を専用画面で開く
            self._return_mode = MODE_SETTINGS
            self._restore_master_palette()
            self.title_config_editor.open(self.state.title_config)
            self.mode = MODE_TITLE_CONFIG
        elif result == "gallery":
            self._return_mode = MODE_SETTINGS
            self._restore_master_palette()
            self.gallery_config_editor.open(
                self.state.gallery_config,
                cache=self.cache,
                base_dir=self.cache.base_dir if self.cache else self._base_dir,
                settings=self._settings,
            )
            self.mode = MODE_GALLERY_CONFIG
        elif result == "extra_text":
            self._return_mode = MODE_SETTINGS
            self._restore_master_palette()
            self.extra_text_config_editor.open(self.state.extra_text_config)
            self.mode = MODE_EXTRA_TEXT_CONFIG

    def _update_title_config(self):
        """TITLE Config 専用画面の更新"""
        if is_file_picker_active():
            update_file_picker()
            return
        # TITLE preview rewrites pyxel.colors[] for the background image. The
        # config editor's palette grid must always represent MasterColor.
        self._restore_master_palette()
        self.title_config_editor.refresh_palette_grid()

        self.title_config_editor.update()
        result = self.title_config_editor.result
        if result is None:
            return

        self.title_config_editor.result = None

        if result == "saved":
            self.state.title_config = self.title_config_editor.get_config()
            self.state.dirty = True
            self.toast.show("Title config updated")
            ret = self._return_mode
            self._return_mode = MODE_EDITOR
            if ret == MODE_SETTINGS:
                self.settings_menu.open(self.state.title_config)
            self.mode = ret
        elif result == "cancelled":
            ret = self._return_mode
            self._return_mode = MODE_EDITOR
            if ret == MODE_SETTINGS:
                self.settings_menu.open(self.state.title_config)
            self.mode = ret
        elif result == "bg_pick":
            scan_dir = os.path.join(self._base_dir, "assets", "images", "bg")
            if not os.path.isdir(scan_dir):
                scan_dir = self._base_dir
            initial_path = self.title_config_editor.get_config().get(
                "bg_image", "")
            open_file_picker("TITLE BG IMAGE", scan_dir, "image",
                             self._on_title_bg_selected,
                             project_base=self._base_dir,
                             initial_path=initial_path)
        elif result == "bgm_pick":
            scan_dir = os.path.join(self._base_dir, "assets", "sounds", "bgm")
            if not os.path.isdir(scan_dir):
                scan_dir = self._base_dir
            initial_path = self.title_config_editor.get_config().get(
                "bgm_file", "")
            open_file_picker("TITLE BGM", scan_dir, "audio",
                             self._on_title_bgm_selected,
                             project_base=self._base_dir,
                             initial_path=initial_path)
        elif result == "preview":
            # 編集中の (未保存) 設定でタイトル画面をプレビュー再生。
            # ESC でタイトル画面を閉じると元の TITLE CONFIG へ戻る。
            self._open_title_screen(
                config=self.title_config_editor.get_config(),
                return_mode=MODE_TITLE_CONFIG)

    def _on_title_bg_selected(self, path: str):
        """タイトルBG画像がファイルピッカーで選択された"""
        # ファイルピッカーは scan_dir からの相対パスを返す。
        # プロジェクトルート基準で解決されるよう "./assets/images/bg/" を前置する。
        stored = path
        if path and not os.path.isabs(path) and not path.startswith("."):
            stored = "./assets/images/bg/" + path
        self.title_config_editor.set_bg_image(stored)
        self.toast.show("Title BG updated")

    def _on_title_bgm_selected(self, path: str):
        """タイトルBGMがファイルピッカーで選択された"""
        stored = path
        if path and not os.path.isabs(path) and not path.startswith("."):
            stored = "./assets/sounds/bgm/" + path
        self.title_config_editor.set_bgm_file(stored)
        self.toast.show("Title BGM updated")

    def _update_title(self):
        if self._title_start_transition:
            self._update_title_start_transition()
            return

        if self.gallery_preview.active:
            self.gallery_preview.update()
            if self.gallery_preview.closed:
                self.gallery_preview.closed = False
                self._restore_title_after_modal()
            return

        if self.extra_text_viewer.active:
            self.extra_text_viewer.update()
            if self.extra_text_viewer.closed:
                self.extra_text_viewer.closed = False
                self._restore_title_after_modal()
            return

        if self.extras_menu.active:
            self.extras_menu.update()
            result = self.extras_menu.result
            if result is None:
                return
            self.extras_menu.result = None
            if result == "gallery":
                self.gallery_preview.open(
                    self.state.gallery_config,
                    cache=self.cache,
                    base_dir=self.cache.base_dir if self.cache else self._base_dir,
                    settings=self._settings,
                )
            elif result == "extra_text":
                self.extra_text_viewer.open(self.state.extra_text_config)
            else:
                self._restore_title_after_modal()
            return

        # セーブ/ロード画面がアクティブならそちらを処理
        if self._title_save_screen.active:
            self._title_save_screen.update()
            if self._title_save_screen.closed:
                self._title_save_screen.closed = False
                result = self._title_save_screen.load_result
                if result:
                    # ロード実行も START と同じ遷移を通し、フェード途中で復元する。
                    self._begin_title_start_transition(load_state=result)
                else:
                    self._restore_title_after_modal()
            return

        if self._title_options.active:
            self._title_options.update()
            if self._title_options.closed:
                self._title_options.closed = False
                self._restore_title_after_modal()
            return

        self.title_screen.update()
        result = self.title_screen.result
        if result is None:
            return

        self.title_screen.result = None
        if result == "start":
            self._begin_title_start_transition()
        elif result == "continue":
            save_path = self._get_save_path()
            self._restore_title_after_modal()
            self._title_save_screen.open(
                "load", save_path=save_path)
        elif result == "options":
            self._open_title_options()
        elif result == "extras":
            self._restore_title_after_modal()
            self.extras_menu.open(
                button_colors=self.title_screen._button_colors,
                show_gallery=has_gallery_pages(self.state.gallery_config),
                show_extra_text=has_extra_text_pages(
                    self.state.extra_text_config),
            )
        elif result == "extras_locked":
            return
        elif result == "quit":
            self._open_quit_dialog()

    def _restore_title_after_modal(self):
        """タイトル上のモーダルを閉じた後、背面のタイトルを表示状態へ戻す。"""
        self._refresh_title_palette_and_bg()
        self.title_screen.open(
            bg_image=self.title_screen._bg_image,
            bg_fullscreen=bool(self.title_screen._bg_fullscreen),
            button_colors=self.title_screen._button_colors,
            extras_available=self._extras_available(),
            extras_unlocked=self._extras_unlocked())

    def _open_title_options(self):
        """タイトル画面から、プレイ中OPTと同じオプションを開く。"""
        self._restore_title_after_modal()
        self._title_controller.load_user_mapping()
        self._title_options.open(
            self._title_controller,
            text_size_getter=self._get_player_text_size_override,
            text_size_effective_getter=self._get_player_effective_text_size,
            text_size_setter=self._set_player_text_size_override,
        )

    def _get_player_text_size_override(self) -> int | None:
        return _player_prefs.load_text_size_override()

    def _get_player_effective_text_size(self) -> int:
        override = _player_prefs.normalize_text_size(
            _player_prefs.load_text_size_override())
        if override is not None:
            return override
        try:
            return int(self._settings.get("dialog_font_size", 16))
        except Exception:
            return 16

    def _set_player_text_size_override(self, size: int | None):
        _player_prefs.save_text_size_override(
            _player_prefs.normalize_text_size(size))

    def _begin_title_start_transition(self, load_state: dict | None = None):
        """Start/Load選択後、タイトルからプレイ画面へ120Fで遷移する。"""
        self.state.current_idx = 0
        self._restore_title_after_modal()
        self._title_save_screen.active = False
        self._title_options.active = False
        self._title_pending_load_state = load_state
        self._title_start_transition = True
        self._title_start_transition_frame = 0
        try:
            from engine import audio as _audio
            _audio.fadeout_bgm(TITLE_START_TRANSITION_FRAMES)
        except Exception:
            pass

    def _update_title_start_transition(self):
        if not self._title_start_transition:
            return
        if self.mode == MODE_TITLE:
            try:
                from engine import audio as _audio
                _audio.update()
            except Exception:
                pass
        self._title_start_transition_frame += 1
        if (self.mode == MODE_TITLE
                and self._title_start_transition_frame >= TITLE_START_TRANSITION_HALF):
            self._finish_title_start_fade_out()
            return
        if self._title_start_transition_frame >= TITLE_START_TRANSITION_FRAMES:
            self._title_start_transition = False

    def _finish_title_start_fade_out(self):
        """フェードアウト完了時にプレイ画面へ入り、ロードなら状態復元する。"""
        self._restore_master_palette()
        pending_load = self._title_pending_load_state
        self._title_pending_load_state = None
        self._start_play()
        if pending_load and self.mode == MODE_PLAY and self.player:
            self.player.load_save_state(pending_load)
        if self.mode != MODE_PLAY:
            self._title_start_transition = False
            self._stop_title_audio()

    def _draw_title_start_transition_overlay(self):
        if not self._title_start_transition:
            return
        half = max(1, TITLE_START_TRANSITION_HALF)
        frame = max(0, min(TITLE_START_TRANSITION_FRAMES,
                           self._title_start_transition_frame))
        if frame < half:
            alpha = frame / half
        else:
            alpha = 1.0 - ((frame - half) / max(1, TITLE_START_TRANSITION_FRAMES - half))
        _draw_scanline_fade(alpha)

    def _apply_image_palette(self, image_paths: list,
                             extra_reserved_indices: set[int] | None = None) -> None:
        """シーン用パレット生成ロジックを任意の画像群に対して適用する。

        タイトル BG / エンディングスライドなど、シーン以外でも同じ最適化を
        効かせるための共通ヘルパー。
        - reserved_indices は settings.json (dialog_role_indices / speaker_colors)
          + 0-15 (UI予約) で構築。
        - 残りスロットを画像から抽出した最頻色 (Median Cut) で埋める。
        - pyxel.colors[] と ImageCache の既定パレットを更新する。
        """
        if not self.cache:
            return
        reserved = _master_palette.reserved_from_settings(self._settings)
        if extra_reserved_indices:
            master = _master_palette.as_array()
            if master is not None:
                for idx in extra_reserved_indices:
                    if isinstance(idx, int) and 0 <= idx < len(master):
                        reserved[idx] = (
                            int(master[idx, 0]),
                            int(master[idx, 1]),
                            int(master[idx, 2]),
                        )
        if not reserved:
            return  # マスターパレット未ロード
        pal = _master_palette.build_scene_palette(
            image_paths, reserved, base_dir=self.cache.base_dir)
        _master_palette.apply_to_pyxel_colors(pal)
        _image_cache_mod.set_default_palette(pal)

    def _restore_master_palette(self) -> None:
        """pyxel.colors[] と ImageCache 既定値を MasterColor.pyxpal に戻す。"""
        try:
            _master_palette.load()
            _image_cache_mod.set_default_palette(
                _master_palette.snapshot_pyxel_colors())
        except Exception:
            pass

    def _extras_available(self) -> bool:
        return (
            has_gallery_pages(self.state.gallery_config)
            or has_extra_text_pages(self.state.extra_text_config)
        )

    def _ending_collection_key(self) -> str:
        source = (
            self.state.file_path
            or self._settings.get("last_project_path", "")
            or self._base_dir
        )
        return _player_prefs.project_key(source)

    def _ending_names(self) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()
        for ending in self.state.endings or []:
            name = str(ending.get("name", "") or "").strip()
            if name and name not in seen:
                names.append(name)
                seen.add(name)
        return names

    def _extras_unlocked(self) -> bool:
        if not self._extras_available():
            return False
        return _player_prefs.all_endings_collected(
            self._ending_collection_key(), self._ending_names())

    def _mark_ending_collected(self, ending_name: str):
        _player_prefs.mark_ending_collected(
            self._ending_collection_key(), ending_name)

    def _refresh_title_palette_and_bg(self):
        """Restore the active title palette after full-screen extras views."""
        cfg = dict(self._title_active_config or self.state.title_config)
        bg_file = cfg.get("bg_image", "")
        button_colors = normalize_button_colors(cfg.get("button_colors"))
        bg_img = self.title_screen._bg_image
        if bg_file and self.cache:
            self._apply_image_palette(
                [bg_file],
                extra_reserved_indices=title_button_color_indices(button_colors))
            bg_img = self.cache.get(bg_file)
        self.title_screen._bg_image = bg_img
        self.title_screen._button_colors = button_colors

    def _open_title_screen(self, config: dict = None,
                           return_mode: str = MODE_EDITOR):
        """タイトル画面を開く。

        config が指定されていればそれをプレビュー再生する (未保存値の確認用)。
        ESC で抜けた時は return_mode へ戻る。
        """
        cfg = dict(config) if config is not None else dict(self.state.title_config)
        self._title_active_config = dict(cfg)
        self._title_return_mode = return_mode
        self._title_start_transition = False
        self._title_start_transition_frame = 0
        self._title_pending_load_state = None
        self._ending_to_title_transition = False
        self._ending_to_title_transition_frame = 0

        bg_img = None
        bg_file = cfg.get("bg_image", "")
        button_colors = normalize_button_colors(cfg.get("button_colors"))
        if bg_file and self.cache:
            # シーンと同じくタイトル BG 用に最適化された 256色パレットを構築・適用してから
            # 画像をキャッシュ取得する。これでマスターパレットによる色破綻を回避する。
            self._apply_image_palette(
                [bg_file],
                extra_reserved_indices=title_button_color_indices(button_colors))
            bg_img = self.cache.get(bg_file)
        self.title_screen.open(bg_image=bg_img,
                               bg_fullscreen=bool(cfg.get("bg_fullscreen", False)),
                               button_colors=button_colors,
                               extras_available=self._extras_available(),
                               extras_unlocked=self._extras_unlocked())
        # タイトル画面に入ったら FLOW の特殊選択は解除
        self.state.selected_special = None
        self.mode = MODE_TITLE
        # BGM再生。プロジェクトベース基準で絶対パスに解決してから渡す。
        bgm_file = cfg.get("bgm_file", "")
        if bgm_file:
            from engine import audio as _audio
            if os.path.isabs(bgm_file):
                abs_bgm = bgm_file
            else:
                abs_bgm = os.path.join(self.cache.base_dir, bgm_file)
            _audio.play_bgm(abs_bgm,
                            volume=int(cfg.get("bgm_volume", 7)),
                            loop=bool(cfg.get("bgm_loop", True)))

    def _update_gallery_config(self):
        """CG Gallery Config 専用画面の更新"""
        if is_file_picker_active():
            update_file_picker()
            return

        self.gallery_config_editor.update()
        result = self.gallery_config_editor.result
        if result is None:
            return

        self.gallery_config_editor.result = None

        if result == "saved":
            self.state.gallery_config = normalize_gallery_config(
                self.gallery_config_editor.get_config())
            self.state.dirty = True
            self.toast.show("CG gallery updated")
            ret = self._return_mode
            self._return_mode = MODE_EDITOR
            self._restore_master_palette()
            if ret == MODE_SETTINGS:
                self.settings_menu.open(self.state.title_config)
            self.mode = ret
        elif result == "cancelled":
            ret = self._return_mode
            self._return_mode = MODE_EDITOR
            self._restore_master_palette()
            if ret == MODE_SETTINGS:
                self.settings_menu.open(self.state.title_config)
            self.mode = ret
        elif result == "image_pick":
            project_base = self.cache.base_dir if self.cache else self._base_dir
            scan_dir = os.path.join(project_base, "assets", "images")
            if not os.path.isdir(scan_dir):
                scan_dir = project_base
            self._gallery_image_picker_root = scan_dir
            self._gallery_image_picker_project_base = project_base
            open_file_picker(
                "CG GALLERY IMAGE",
                scan_dir,
                "image",
                self._on_gallery_image_selected,
                project_base=project_base,
                initial_path=self.gallery_config_editor.selected_image(),
            )
        elif result == "preview":
            self.gallery_preview.open(
                self.gallery_config_editor.get_config(),
                cache=self.cache,
                base_dir=self.cache.base_dir if self.cache else self._base_dir,
                settings=self._settings,
            )
            self.mode = MODE_GALLERY_PREVIEW
        elif isinstance(result, str) and result.startswith("import_used:"):
            parts = result.split(":")
            scope = parts[1] if len(parts) > 1 else "bg_ending"
            mode = parts[2] if len(parts) > 2 else "append"
            paths = self._collect_used_gallery_images(scope)
            if not paths:
                self.toast.show("No used images found", 45)
                return
            added, skipped = self.gallery_config_editor.import_images(
                paths, replace=(mode == "replace"))
            self.toast.show(
                f"Imported {added} image(s)"
                + (f" / skipped {skipped}" if skipped else ""),
                45)

    def _on_gallery_image_selected(self, path: str):
        """CGギャラリー画像がファイルピッカーで選択された"""
        stored = path
        image_root = os.path.join(
            self._gallery_image_picker_project_base or self._base_dir,
            "assets", "images")
        if (path and not os.path.isabs(path) and not path.startswith(".")
                and os.path.abspath(self._gallery_image_picker_root)
                == os.path.abspath(image_root)):
            stored = "./assets/images/" + path
        self.gallery_config_editor.set_selected_image(stored)
        self.toast.show("CG image set")

    def _collect_used_gallery_images(self, scope: str = "bg_ending") -> list[str]:
        """Collect images used by the current project for CG gallery import."""
        include_chars = scope == "all"
        paths: list[str] = []
        seen: set[str] = set()

        def add(path: str):
            text = str(path or "").strip()
            if not text or not self._looks_like_image_path(text):
                return
            if not self._gallery_image_exists(text):
                return
            stored = self._project_relative_asset_path(text)
            if stored in seen:
                return
            seen.add(stored)
            paths.append(stored)

        def add_anim(anim):
            if not isinstance(anim, dict):
                return
            for item in anim.get("flipbook_files", []) or []:
                add(item)

        title_bg = (self.state.title_config or {}).get("bg_image", "")
        add(title_bg)

        for scene in self.state.scenes or []:
            add(scene.get("bg", ""))
            add_anim(scene.get("bg_anim", {}))
            if include_chars:
                for key in ("char_l", "char_c", "char_r"):
                    cfg = scene.get(key, {}) or {}
                    if not isinstance(cfg, dict):
                        continue
                    add(cfg.get("file", ""))
                    add_anim(cfg.get("anim", {}))

        for ending in self.state.endings or []:
            for slide in ending.get("slides", []) or []:
                if isinstance(slide, dict):
                    add(slide.get("image", ""))

        return paths

    def _looks_like_image_path(self, path: str) -> bool:
        ext = os.path.splitext(str(path or ""))[1].lower()
        return ext in {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}

    def _project_relative_asset_path(self, path: str) -> str:
        text = str(path or "").replace("\\", "/")
        project_base = self.cache.base_dir if self.cache else self._base_dir
        if os.path.isabs(text):
            try:
                rel = os.path.relpath(text, project_base)
                if not rel.startswith(".."):
                    return "./" + rel.replace(os.sep, "/")
            except Exception:
                pass
        return text

    def _gallery_image_exists(self, path: str) -> bool:
        text = str(path or "").strip()
        if not text:
            return False
        project_base = self.cache.base_dir if self.cache else self._base_dir
        abs_path = text if os.path.isabs(text) else os.path.join(project_base, text)
        return os.path.isfile(os.path.abspath(abs_path))

    def _update_gallery_preview(self):
        """CG Gallery Config から開くプレビュー画面の更新"""
        self.gallery_preview.update()
        if self.gallery_preview.closed:
            self.gallery_preview.closed = False
            self._restore_master_palette()
            self.mode = MODE_GALLERY_CONFIG

    def _update_extra_text_config(self):
        """EXTRA TEXT Config 専用画面の更新"""
        self.extra_text_config_editor.update()
        result = self.extra_text_config_editor.result
        if result is None:
            return

        self.extra_text_config_editor.result = None

        if result == "saved":
            self.state.extra_text_config = normalize_extra_text_config(
                self.extra_text_config_editor.get_config())
            self.state.dirty = True
            self.toast.show("Extra text updated")
            ret = self._return_mode
            self._return_mode = MODE_EDITOR
            self._restore_master_palette()
            if ret == MODE_SETTINGS:
                self.settings_menu.open(self.state.title_config)
            self.mode = ret
        elif result == "cancelled":
            ret = self._return_mode
            self._return_mode = MODE_EDITOR
            self._restore_master_palette()
            if ret == MODE_SETTINGS:
                self.settings_menu.open(self.state.title_config)
            self.mode = ret
        elif result == "preview":
            self.extra_text_viewer.open(
                self.extra_text_config_editor.get_config(),
                initial_page=self.extra_text_config_editor.current_page_index())
            self.mode = MODE_EXTRA_TEXT_PREVIEW

    def _update_extra_text_preview(self):
        """EXTRA TEXT Config から開くプレビュー画面の更新"""
        self.extra_text_viewer.update()
        if self.extra_text_viewer.closed:
            self.extra_text_viewer.closed = False
            self._restore_master_palette()
            self.mode = MODE_EXTRA_TEXT_CONFIG

    def _stop_title_audio(self):
        """タイトル画面終了時に BGM を停止する。"""
        try:
            from engine import audio as _audio
            _audio.stop_bgm()
        except Exception:
            try:
                pyxel.stop()
            except Exception:
                pass

    def _get_save_path(self) -> str:
        if self.state.file_path:
            return os.path.splitext(self.state.file_path)[0] + "_saves.json"
        return os.path.join(self._base_dir, "pvnm_saves.json")

    def _update_play(self):
        self.player.update()
        if self._title_start_transition:
            self._update_title_start_transition()
        if self.player.finished:
            self._return_to_editor()

    # ── draw ────────────────────────────────────────────────────

    def draw(self):
        pyxel.cls(0)

        if self.mode == MODE_FONT_TEST:
            self._draw_font_test()
            return

        if self.mode == MODE_COLORS:
            self.color_editor.draw()
        elif self.mode == MODE_SPEAKER_COLORS:
            self.speaker_color_editor.draw()
        elif self.mode == MODE_FONT_SETTINGS:
            self.font_settings_editor.draw()
        elif self.mode == MODE_ENDINGS:
            self.ending_editor.draw()
            draw_file_picker()
        elif self.mode == MODE_SETTINGS:
            self.settings_menu.draw()
            draw_file_picker()
        elif self.mode == MODE_TITLE_CONFIG:
            self.title_config_editor.draw()
            draw_file_picker()
        elif self.mode == MODE_GALLERY_CONFIG:
            self.gallery_config_editor.draw()
            draw_file_picker()
        elif self.mode == MODE_GALLERY_PREVIEW:
            self.gallery_preview.draw()
        elif self.mode == MODE_EXTRA_TEXT_CONFIG:
            self.extra_text_config_editor.draw()
        elif self.mode == MODE_EXTRA_TEXT_PREVIEW:
            self.extra_text_viewer.draw()
        elif self.mode == MODE_PARTS:
            self.part_editor.draw()
        elif self.mode == MODE_CHAPTERS:
            self.chapter_editor.draw()
        elif self.mode == MODE_TITLE:
            self._draw_title()
        elif self.mode == MODE_ENDING_PLAY:
            self._draw_ending_play()
        elif self.mode in (MODE_EDITOR, MODE_QUIT):
            self._draw_editor()
        else:
            self._draw_play()

        if self.mode == MODE_QUIT:
            self.quit_dialog.draw()

        if self.confirm_dialog.active and self.mode in (
                MODE_EDITOR, MODE_SETTINGS, MODE_QUIT):
            self.confirm_dialog.draw()

        if self.mode not in (MODE_COLORS, MODE_SPEAKER_COLORS,
                             MODE_FONT_SETTINGS, MODE_TITLE_CONFIG,
                             MODE_GALLERY_CONFIG, MODE_GALLERY_PREVIEW,
                             MODE_EXTRA_TEXT_CONFIG, MODE_EXTRA_TEXT_PREVIEW):
            self.toast.draw()
        self._draw_export_status()
        self._draw_export_next_steps()

    def _draw_font_test(self):
        """フォント比較ページ: BDF (efont-unicode) を中心に各サイズで日本語を表示。

        BDF はピクセル単位で事前描画されたビットマップフォントなので、pyxel が
        ラスタライズせずそのまま描画する → 滑らかさはないが崩れもない。
        """
        from ui.widgets import draw_ui_text, ui_text_h
        x0 = 20

        jp_short = "吾輩は猫である。名前はまだ無い。"
        jp_quote = "コーダ「うん、いまの状況を確認しよう。」"
        jp_mix   = "0123456789 !? あいうえお ABCabc"

        # efont BDF 各サイズで pyxel.Font をロードして直接 pyxel.text で描画
        bdf_dir = os.path.join(self._base_dir, "assets/fonts/efont-unicode-bdf")
        # f = Fixed (等幅), b = Biwidth (1/2 幅対応)。ここは f を採用。
        bdf_sizes = [10, 12, 14, 16, 24]

        y = 14
        # ヘッダ: pyxel デフォルトフォント
        draw_ui_text(x0, y, "[pyxel default font scale=2]", 7, scale=2)
        y += ui_text_h(2) + 8

        # 各 BDF サイズで日本語を表示
        if not hasattr(self, "_bdf_test_fonts"):
            self._bdf_test_fonts = {}
            for sz in bdf_sizes:
                # "b" = Biwidth (ASCII + 日本語両対応)。"f" は日本語のみで ASCII 不可。
                path = os.path.join(bdf_dir, f"b{sz}.bdf")
                if os.path.exists(path):
                    try:
                        self._bdf_test_fonts[sz] = pyxel.Font(path)
                    except Exception as e:
                        print(f"[font_test] BDF b{sz}.bdf load failed: {e}")

        for sz in bdf_sizes:
            font = self._bdf_test_fonts.get(sz)
            if font is None:
                continue
            if y > HEIGHT - 30:
                break
            # ラベルは scale=1 の pyxel デフォルトフォントで
            draw_ui_text(x0, y, f"[efont b{sz}.bdf  pyxel.text]", 9, scale=1)
            y += ui_text_h(1) + 2
            # サンプル文 (pyxel.text + BDF Font)
            pyxel.text(x0, y, jp_short, 7, font)
            y += sz + 4
            pyxel.text(x0, y, jp_quote, 7, font)
            y += sz + 4
            pyxel.text(x0, y, jp_mix,   7, font)
            y += sz + 8

        # 終了ガイド (画面下端)
        draw_ui_text(x0, HEIGHT - 14,
                     "Press SPACE / ENTER / CLICK to enter editor",
                     6, scale=1)

    def _draw_editor(self):
        if self.state.preview_expanded:
            # 実物大プレビュー時は MainViewPanel のみ描画して
            # 他パネル (Properties / Toolbar / SceneList) が上に乗らないようにする
            for panel in self.panels:
                if isinstance(panel, MainViewPanel):
                    panel.draw()
        else:
            for panel in self.panels:
                panel.draw()
        # ファイルピッカーは全パネルの上にオーバーレイ描画
        draw_file_picker()
        # カーソル（十字）
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        pyxel.line(mx - 4, my, mx + 4, my, 7)
        pyxel.line(mx, my - 4, mx, my + 4, 7)

    def _draw_title(self):
        self.title_screen.draw()
        if self._title_start_transition:
            self._draw_title_start_transition_overlay()
            return
        if self.gallery_preview.active:
            self.gallery_preview.draw()
            return
        if self.extra_text_viewer.active:
            self.extra_text_viewer.draw()
            return
        if self.extras_menu.active:
            self.extras_menu.draw()
            return
        if self._title_save_screen.active:
            self._title_save_screen.draw()
            return
        if self._title_options.active:
            self._title_options.draw()
            return
        pyxel.text(WIDTH - 96, HEIGHT - 10, "[ESC] back to editor", 5)

    def _draw_play(self):
        self.player.draw()
        if self._title_start_transition:
            self._draw_title_start_transition_overlay()
            return
        pyxel.text(WIDTH - 96, HEIGHT - 10, "[ESC] back to editor", 5)

    # ── モード切り替え ──────────────────────────────────────────

    def _start_play(self):
        # マスターパレット運用: プレイ時に色を切り替えない。
        # 役割→indexは settings.json["dialog_role_indices"] で一元管理。

        # キャッシュのベースをプロジェクトファイルのあるフォルダに合わせる
        # (FLOW → title / ending の特殊遷移でも BG 画像が正しく解決されるよう
        #  早めに揃える)
        if self.state.file_path:
            base = os.path.dirname(os.path.abspath(self.state.file_path))
            if base != self.cache.base_dir:
                self._set_project_base(self.state.file_path)

        # FLOW で特殊ノード（タイトル / エンディング）が選択されている場合は
        # それぞれの再生フローに切り替える
        special = getattr(self.state, "selected_special", None)
        if special == "title":
            self._open_title_screen()
            return
        if isinstance(special, tuple) and special[0] == "ending":
            idx = special[1]
            endings = self.state.endings or []
            if 0 <= idx < len(endings):
                # FLOW から起動した本番再生:
                # - ESC で中断 → 編集画面に戻る (テスト便宜)
                # - 自然終了 → タイトル画面 (実プレイのループ復帰を再現)
                self._start_ending_play(endings[idx],
                                        return_to=MODE_EDITOR,
                                        natural_to=MODE_TITLE)
                return
            # 未設定の場合は通常再生にフォールスルー
            self.toast.show("Ending not set", 8)
            return

        script = from_editor_state(self.state)

        selected_name = None
        scene = self.state.current_scene()
        if scene:
            selected_name = scene["name"]
        self.player = VNPlayer(script, start_scene=selected_name,
                               cache=self.cache,
                               endings=self.state.endings,
                               settings=self._settings,
                               ending_complete_callback=self._mark_ending_collected)
        # スピーカー色設定を注入 (None 値は player 側で PLAY_* デフォルトに falls back)
        self.player.set_speaker_config(self._settings.get("speaker_colors") or {})
        # セーブパス設定
        if self.state.file_path:
            save_path = os.path.splitext(self.state.file_path)[0] + "_saves.json"
        else:
            save_path = os.path.join(self._base_dir, "pvnm_saves.json")
        self.player.set_save_path(save_path)
        self.mode = MODE_PLAY

    def _start_ending_play(self, ending: dict, return_to: str = MODE_EDITOR,
                           natural_to: "str | None" = None,
                           preview_start_sec: float = 0.0):
        """エンディングを単独再生する。

        Parameters
        ----------
        return_to    : ESC で中断した時の戻り先モード。
        natural_to   : 自然終了 (BGM 終了 / スライド完了) 時の戻り先モード。
                       None なら return_to と同じ。
                       通常プレイ (FLOW) では MODE_TITLE 推奨。
                       プレビュー時は MODE_ENDINGS。
        preview_start_sec : BGM のシーク開始秒数 (PREVIEW FROM)。
        """
        self.ending_runtime = EndingPlayer(
            ending, cache=self.cache, settings=self._settings,
            preview_start_sec=preview_start_sec)
        self._ending_runtime_name = str(ending.get("name", "") or "")
        self._ending_return_mode = return_to
        self._ending_natural_to = natural_to if natural_to is not None else return_to
        self.mode = MODE_ENDING_PLAY

    def _find_ending_by_name(self, name: str) -> "dict | None":
        if not name:
            return None
        if (
            self.ending_editor.active
            and (
                self._ending_return_mode == MODE_ENDINGS
                or self._ending_natural_to == MODE_ENDINGS
            )
        ):
            draft = self.ending_editor.find_ending_by_name(name)
            if draft is not None:
                return draft
        for e in (self.state.endings or []):
            if e.get("name", "") == name:
                return e
        return None

    def _finish_ending_play(self, target_mode: str):
        """エンディング再生終了処理。target_mode に応じて戻る。

        target_mode == MODE_TITLE  → タイトル画面を開いて戻る
        target_mode == MODE_ENDINGS → ENDING エディタへ戻る
        その他 → そのモードへ遷移
        """
        self._ending_to_title_transition = False
        self._ending_to_title_transition_frame = 0
        self.ending_runtime = None
        self._ending_runtime_name = ""
        self._ending_return_mode = MODE_EDITOR
        self._ending_natural_to = MODE_EDITOR
        try:
            from engine import audio as _audio
            _audio.stop_bgm()
            _audio.stop_all_se()
        except Exception:
            pass
        # MasterColor へ戻す (シーン/エンディングで書き換えたパレットを戻す)
        self._restore_master_palette()
        if target_mode == MODE_TITLE:
            # 自然終了時の本流: タイトル画面を起動して戻る
            self._open_title_screen()
        elif target_mode == MODE_ENDINGS:
            self.mode = MODE_ENDINGS
        else:
            self.mode = target_mode

    def _begin_ending_to_title_transition(self):
        """エンディング自然終了後、タイトル復帰前に120Fフェードを挟む。"""
        self._ending_to_title_transition = True
        self._ending_to_title_transition_frame = 0
        if self.ending_runtime is not None:
            # 終了済みフラグのままだと draw() が何も描かないため、最終状態を
            # そのまま保持してフェードアウトできるようにする。
            self.ending_runtime.finished = False
        try:
            from engine import audio as _audio
            _audio.fadeout_bgm(TITLE_START_TRANSITION_FRAMES)
            _audio.stop_all_se()
        except Exception:
            pass

    def _update_ending_to_title_transition(self):
        if not self._ending_to_title_transition:
            return
        try:
            from engine import audio as _audio
            _audio.update()
        except Exception:
            pass
        self._ending_to_title_transition_frame += 1
        if self._ending_to_title_transition_frame >= TITLE_START_TRANSITION_FRAMES:
            self._ending_to_title_transition = False
            self._ending_to_title_transition_frame = 0
            self._finish_ending_play(MODE_TITLE)

    def _capture_ending_preview_time(self):
        """ENDING PREVIEWをESCで抜けた時刻を、エディタへ一時確保する。"""
        if getattr(self, "_ending_return_mode", MODE_EDITOR) != MODE_ENDINGS:
            return
        if self.ending_runtime is None:
            return
        try:
            sec = self.ending_runtime.current_time_sec()
        except Exception:
            sec = 0.0
        try:
            applied = self.ending_editor.capture_preview_time(sec)
        except Exception:
            applied = False
        if applied:
            try:
                label = self.ending_editor._format_time(sec)
            except Exception:
                label = f"{sec:.2f}"
            self.toast.show(f"Captured preview time: {label}", 45)

    def _update_ending_play(self):
        if self._ending_to_title_transition:
            self._update_ending_to_title_transition()
            return
        if self.ending_runtime is None:
            self._finish_ending_play(MODE_EDITOR)
            return
        self.ending_runtime.update()
        if not self.ending_runtime.finished:
            return
        # 終了。ESC か自然終了か、および goto_ending の有無で分岐:
        # - ESC (aborted=True) → チェーンは無視して return_to へ
        # - 自然終了 + goto_ending あり → そのエンディングへチェーン
        # - 自然終了 + goto_ending 無し → natural_to へ
        aborted = bool(getattr(self.ending_runtime, "aborted", False))
        if aborted:
            self._capture_ending_preview_time()
        if not aborted:
            if self._ending_natural_to == MODE_TITLE:
                self._mark_ending_collected(self._ending_runtime_name)
            next_name = getattr(self.ending_runtime, "next_ending_name", "")
            next_ending = self._find_ending_by_name(next_name)
            if next_ending is not None:
                # チェーン: 戻り先設定を保持したまま次のエンディングを起動
                self._start_ending_play(
                    next_ending,
                    return_to=self._ending_return_mode,
                    natural_to=self._ending_natural_to)
                return
        target = (self._ending_return_mode if aborted
                  else self._ending_natural_to)
        if target == MODE_TITLE and not aborted:
            self._begin_ending_to_title_transition()
            return
        self._finish_ending_play(target)

    def _draw_ending_play(self):
        if self.ending_runtime is not None:
            self.ending_runtime.draw()
        if self._ending_to_title_transition:
            alpha = min(1.0, self._ending_to_title_transition_frame
                        / max(1, TITLE_START_TRANSITION_FRAMES))
            _draw_scanline_fade(alpha)
            return
        pyxel.text(WIDTH - 96, HEIGHT - 10, "[ESC] back to editor", 5)

    def _return_to_editor(self):
        self._sync_editor_selection_from_player()
        self.player = None
        self.ending_runtime = None
        self._ending_runtime_name = ""
        self._title_start_transition = False
        self._title_pending_load_state = None
        self._ending_to_title_transition = False
        self._ending_to_title_transition_frame = 0
        # プレイ中に再生していたBGM/SEを停止
        try:
            from engine import audio as _audio
            _audio.stop_bgm()
            _audio.stop_all_se()
        except Exception:
            try:
                pyxel.stop()
            except Exception:
                pass
        # シーン用に書き換えていた pyxel.colors[] と ImageCache 既定パレットを
        # MasterColor に戻す。これをしないとエディタ UI 色が前シーンの色のままになる。
        self._restore_master_palette()
        self.mode = MODE_EDITOR

    def _sync_editor_selection_from_player(self):
        """プレイから戻る時、エディタの選択を現在再生中のシーンへ合わせる。"""
        if self.player is None:
            return
        scene_name = getattr(self.player, "scene_name", "") or ""
        if not scene_name:
            return
        if not self.state.select_scene_by_name(scene_name):
            return
        for panel in self.panels:
            if isinstance(panel, SceneListPanel):
                panel.scroll_selected_into_view()
                break

    def _update_font_settings(self):
        self.font_settings_editor.update()
        result = self.font_settings_editor.result
        if result is None:
            return
        if result == "saved":
            new_settings = self.font_settings_editor.get_settings()
            self._settings.update(new_settings)
            path = os.path.join(self._base_dir, "settings.json")
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self._settings, f, ensure_ascii=False, indent=2)
                self.toast.show("Font settings saved")
            except Exception:
                self.toast.show("Save failed!", 8)
        self.font_settings_editor.result = None
        ret = self._return_mode
        self._return_mode = MODE_EDITOR
        if ret == MODE_SETTINGS:
            self.settings_menu.open(self.state.title_config)
        self.mode = ret

    def _update_colors(self):
        self.color_editor.update()
        if self.color_editor.result == "saved":
            new_indices = self.color_editor.get_role_indices()
            self._settings["dialog_role_indices"] = new_indices
            self._save_settings()
            # 全コンシューマモジュールに即時反映 (再起動不要)
            _apply_role_indices(new_indices)
            self.toast.show("Color settings saved")
            self.color_editor.result = None
            ret = self._return_mode
            self._return_mode = MODE_EDITOR
            if ret == MODE_SETTINGS:
                self.settings_menu.open(self.state.title_config)
            self.mode = ret
        elif self.color_editor.result == "cancelled":
            self.color_editor.result = None
            ret = self._return_mode
            self._return_mode = MODE_EDITOR
            if ret == MODE_SETTINGS:
                self.settings_menu.open(self.state.title_config)
            self.mode = ret

    def _update_speaker_colors(self):
        self.speaker_color_editor.update()
        result = self.speaker_color_editor.result
        if result == "saved":
            cfg = self.speaker_color_editor.get_config()
            self._settings["speaker_colors"] = cfg
            self._save_settings()
            if self.player is not None:
                self.player.set_speaker_config(cfg)
            self.toast.show("Speaker colors saved")
            self.speaker_color_editor.result = None
            ret = self._return_mode
            self._return_mode = MODE_EDITOR
            if ret == MODE_SETTINGS:
                self.settings_menu.open(self.state.title_config)
            self.mode = ret
        elif result == "cancelled":
            self.speaker_color_editor.result = None
            ret = self._return_mode
            self._return_mode = MODE_EDITOR
            if ret == MODE_SETTINGS:
                self.settings_menu.open(self.state.title_config)
            self.mode = ret

    def _save_settings(self):
        path = os.path.join(self._base_dir, "settings.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, ensure_ascii=False, indent=2)
        except Exception:
            self.toast.show("Save failed!", 8)

    def _open_quit_dialog(self):
        self.quit_dialog.open(self.state.dirty)
        self.mode = MODE_QUIT

    def _open_delete_scene_confirm(self):
        scene = self.state.current_scene()
        if scene is None:
            return
        if len(self.state.scenes) <= 1:
            self.toast.show("Cannot delete the last scene", 8)
            return
        from editor_state import display_name
        name = display_name(scene)
        self.confirm_dialog.open(
            "削除の確認",
            f"シーン「{name}」を削除しますか？",
            ok_label="DELETE",
            cancel_label="CANCEL",
        )

    def _update_confirm_dialog(self):
        if not self.confirm_dialog.active:
            return
        self.confirm_dialog.update()
        result = self.confirm_dialog.result
        if result is None:
            return
        pending_import = getattr(self, "_pending_import_md", False)
        pending_export = self._pending_export_action
        pending_action = self._pending_confirm_action
        pending_save_path = self._pending_save_path
        pending_save_callback = self._pending_save_callback
        if result == "ok":
            if pending_save_path and pending_save_callback:
                pending_save_callback(pending_save_path)
            elif pending_export:
                self._save_project_then_export(pending_export)
            elif pending_action == "new_project":
                self._do_new_project()
            elif pending_action == "open_project":
                self._open_pvnm_picker()
            elif pending_action == "import_md":
                self._launch_md_picker()
            elif pending_import:
                self._launch_md_picker()
            else:
                if self.state.delete_scene():
                    self.toast.show("Scene deleted")
        self._pending_import_md = False
        self._pending_export_action = ""
        self._pending_confirm_action = ""
        self._pending_save_path = ""
        self._pending_save_callback = None
        self.confirm_dialog.result = None

    def _update_quit_dialog(self):
        self.quit_dialog.update()
        result = self.quit_dialog.result
        if result is None:
            return
        if result == "cancel":
            self.mode = MODE_EDITOR
        elif result == "quit":
            pyxel.quit()
        elif result == "save_quit":
            if self.state.file_path:
                self._do_save(self.state.file_path)
                pyxel.quit()
            else:
                # ファイルパス未設定 → 保存ダイアログを開いてから終了
                def _save_then_quit(path):
                    if self.state.save(path):
                        self._set_project_base(path)
                        self._remember_project_path(path)
                        pyxel.quit()
                    else:
                        self.toast.show("Save failed!", 8)
                        self.mode = MODE_EDITOR
                self._open_save_path_dialog(
                    "SAVE PROJECT",
                    os.path.join(self._base_dir, "untitled.pvnm"),
                    ".pvnm",
                    [("PVNM Project", "*.pvnm"), ("All files", "*.*")],
                    _save_then_quit,
                )

    # ── ファイル操作 ────────────────────────────────────────────

    def _open_save_path_dialog(self, title: str, default_path: str,
                               ext: str, filetypes: list[tuple[str, str]],
                               callback) -> None:
        """OS保存ダイアログを非同期で開く。Pyxelのメインループは止めない。"""
        if self._save_dialog.running:
            self.toast.show("Save dialog is already open", 9)
            return

        def _cb(path: str):
            safe_path, changed = _normalize_save_output_path(path, ext)
            if not safe_path:
                return
            if changed:
                self.toast.show(
                    f"Using {os.path.basename(safe_path)}", 9)
            if os.path.exists(safe_path):
                self._pending_save_path = safe_path
                self._pending_save_callback = callback
                self.confirm_dialog.open(
                    "OVERWRITE FILE",
                    "The selected export/save path already exists.\n"
                    "PVNM will write to this exact file:\n"
                    f"{safe_path}\n"
                    "Overwrite it?",
                    ok_label="OVERWRITE",
                    cancel_label="CANCEL",
                )
                return
            callback(safe_path)

        self._save_dialog.open(title, default_path, ext, filetypes, _cb)

    def _default_save_as_path(self) -> str:
        """現在のプロジェクトから別名保存用の初期パスを作る。"""
        if self.state.file_path:
            src = os.path.abspath(self.state.file_path)
            base, ext = os.path.splitext(src)
            ext = ext or ".pvnm"
            candidate = base + "_copy" + ext
            index = 2
            while os.path.exists(candidate):
                candidate = f"{base}_copy{index}{ext}"
                index += 1
            return candidate
        return os.path.join(self._base_dir, "untitled.pvnm")

    def _open_project_save_as_dialog(self) -> None:
        self._open_save_path_dialog(
            "SAVE PROJECT AS",
            self._default_save_as_path(),
            ".pvnm",
            [("PVNM Project", "*.pvnm"), ("All files", "*.*")],
            self._do_save,
        )

    def _launch_project_action(self, action: str):
        if action == "save":
            if self.state.file_path:
                self._do_save(self.state.file_path)
            else:
                self._open_project_save_as_dialog()
        elif action == "save_as":
            self._open_project_save_as_dialog()

    def _request_new_project(self):
        if self.state.dirty:
            self._pending_confirm_action = "new_project"
            self.confirm_dialog.open(
                "NEW PROJECT",
                "Current project has unsaved changes.\n"
                "Starting a new project will discard those unsaved edits.\n"
                "Save or Save As first if you want to keep them.",
                ok_label="NEW",
                cancel_label="CANCEL",
            )
            return
        self._do_new_project()

    def _do_new_project(self):
        self.state.reset()
        self._reset_project_scoped_settings()
        # キャッシュのベースディレクトリはリセット後も変わらないが
        # プロジェクトが変わった場合に備えて再生成
        self._set_project_base(os.path.join(self._base_dir, "untitled.pvnm"))
        self.toast.show("New project")

    def _request_open_project(self):
        if self.state.dirty:
            self._pending_confirm_action = "open_project"
            self.confirm_dialog.open(
                "OPEN PROJECT",
                "Current project has unsaved changes.\n"
                "Opening another .pvnm will replace the editor contents\n"
                "and discard those unsaved edits.\n"
                "Save or Save As first if you want to keep them.",
                ok_label="OPEN",
                cancel_label="CANCEL",
            )
            return
        self._open_pvnm_picker()

    def _open_pvnm_picker(self):
        """OPENボタン: .pvnm ファイル一覧からプロジェクトを選択"""
        scan_dir = os.path.dirname(os.path.abspath(
            self.state.file_path)) if self.state.file_path else self._base_dir
        open_file_picker("OPEN PROJECT", scan_dir, "pvnm",
                         self._on_pvnm_selected, project_base=self._base_dir,
                         initial_path=self.state.file_path)

    def _export_default_dir(self) -> str:
        """Default folder for generated export artifacts."""
        return os.path.join(self._base_dir, EXPORT_DIR_NAME)

    def _export_base_path(self) -> str:
        name = "untitled"
        if self.state.file_path:
            name = os.path.splitext(os.path.basename(self.state.file_path))[0]
        return os.path.join(self._export_default_dir(), name or "untitled")

    def _android_project_dir_for_output(self, output_path: str) -> str:
        """Keep Android project output beside the selected APK path."""
        out_dir = os.path.dirname(os.path.abspath(output_path))
        stem = os.path.splitext(os.path.basename(output_path))[0] or "untitled"
        for suffix in ("-debug", "-release", "_debug", "_release"):
            if stem.lower().endswith(suffix):
                stem = stem[:-len(suffix)] or "untitled"
                break
        return os.path.join(out_dir, f"{stem}_android")

    def _launch_tool_action(self, action: str):
        if action == "palette":
            self._launch_vn_palette_tool()

    def _launch_vn_palette_tool(self):
        """Launch the standalone image palette tool as a separate app."""
        candidates = [
            os.path.join(self._base_dir, "vn_palette_tool.py"),
            os.path.join(self._base_dir, "tools", "vn_palette_tool.py"),
        ]
        tool_path = next((path for path in candidates if os.path.exists(path)),
                         "")
        if not tool_path:
            self.toast.show("VN Palette Tool not found", 9)
            return
        env = os.environ.copy()
        pythonpath = env.get("PYTHONPATH", "")
        paths = [self._base_dir]
        if pythonpath:
            paths.append(pythonpath)
        env["PYTHONPATH"] = os.pathsep.join(paths)
        try:
            kwargs = {"cwd": self._base_dir, "env": env}
            if os.name != "nt":
                kwargs["start_new_session"] = True
            subprocess.Popen([sys.executable, tool_path], **kwargs)
            self.toast.show("VN Palette Tool launched", 8)
        except Exception as exc:
            print(f"[PVNM] VN Palette Tool launch failed: {exc}")
            self.toast.show("VN Palette Tool launch failed", 9)

    def _launch_export_action(self, action: str, skip_unsaved_check: bool = False):
        if self._export_thread and self._export_thread.is_alive():
            self.toast.show("Export already running", 9)
            return
        self._export_next_steps = None

        if (not skip_unsaved_check
                and (self.state.dirty or not self.state.file_path)):
            self._pending_export_action = action
            self.confirm_dialog.open(
                "UNSAVED PROJECT",
                "Save the .pvnm project before export?",
                ok_label="SAVE & EXPORT",
                cancel_label="CANCEL",
            )
            return

        base = self._export_base_path()
        os.makedirs(os.path.dirname(base), exist_ok=True)

        if action == "pyxapp":
            self._open_save_path_dialog(
                "EXPORT AS .pyxapp",
                base + ".pyxapp",
                ".pyxapp",
                [("Pyxel App", "*.pyxapp"), ("All files", "*.*")],
                self._do_export,
            )
        elif action == "pyxapp_external":
            self._open_save_path_dialog(
                "EXPORT LINUX PYXAPP + ASSETS",
                base + ".pyxapp",
                ".pyxapp",
                [("Pyxel App", "*.pyxapp"), ("All files", "*.*")],
                self._do_export_pyxapp_external,
            )
        elif action == "macos":
            self._open_save_path_dialog(
                "EXPORT macOS APP",
                base + ".app",
                ".app",
                [("macOS App", "*.app"), ("All files", "*.*")],
                self._do_export_macos,
            )
        elif action == "windows_exe":
            if sys.platform != "win32":
                self._do_run_windows_github_actions()
                return
            self._open_save_path_dialog(
                "EXPORT WINDOWS ZIP",
                base + "-windows.zip",
                ".zip",
                [("ZIP", "*.zip"), ("All files", "*.*")],
                self._do_export_windows_exe,
            )
        elif action == "web":
            self._open_save_path_dialog(
                "EXPORT WEB HTML",
                base + ".html",
                ".html",
                [("HTML", "*.html"), ("All files", "*.*")],
                self._do_export_web,
            )
        elif action == "capacitor":
            self._open_save_path_dialog(
                "EXPORT CAPACITOR PROJECT",
                base + "_android",
                "",
                [("All files", "*.*")],
                self._do_export_capacitor_project,
            )
        elif action == "android_debug_apk":
            self._open_save_path_dialog(
                "EXPORT ANDROID DEBUG APK",
                base + "-debug.apk",
                ".apk",
                [("Android APK", "*.apk"), ("All files", "*.*")],
                lambda path: self._do_export_android_apk(path, "debug"),
            )
        elif action == "android_release_apk":
            self._open_save_path_dialog(
                "EXPORT ANDROID RELEASE APK",
                base + "-release.apk",
                ".apk",
                [("Android APK", "*.apk"), ("All files", "*.*")],
                lambda path: self._do_export_android_apk(path, "release"),
            )

    def _save_project_then_export(self, action: str):
        if self.state.file_path:
            if not self.state.save(self.state.file_path):
                self.toast.show("Save failed!", 8)
                return
            self._remember_project_path(self.state.file_path)
            self.toast.show(f"Saved: {os.path.basename(self.state.file_path)}")
            self._launch_export_action(action, skip_unsaved_check=True)
            return

        def _cb(path: str):
            if self.state.save(path):
                self.toast.show(f"Saved: {os.path.basename(path)}")
                self._set_project_base(path)
                self._remember_project_path(path)
                self._launch_export_action(action, skip_unsaved_check=True)
            else:
                self.toast.show("Save failed!", 8)

        self._open_save_path_dialog(
            "SAVE PROJECT BEFORE EXPORT",
            os.path.join(self._base_dir, "untitled.pvnm"),
            ".pvnm",
            [("PVNM Project", "*.pvnm"), ("All files", "*.*")],
            _cb,
        )

    def _on_pvnm_selected(self, path: str):
        """ファイルピッカーから .pvnm ファイルが選択された時のコールバック"""
        self._do_load(path)

    def _restore_last_project(self):
        """起動時に前回開いていた .pvnm を復元する。無ければ従来通り起動。"""
        path = self._settings.get("last_project_path", "")
        if not isinstance(path, str) or not path.strip():
            return
        path = os.path.abspath(os.path.expanduser(path.strip()))
        if not (os.path.isfile(path) and path.lower().endswith(".pvnm")):
            self._reset_project_scoped_settings()
            return
        self._load_project(path, show_toast=False)

    def _reset_project_scoped_settings(self):
        """前回プロジェクトに属する設定を初期化する。"""
        if _reset_project_scoped_settings_values(self._settings):
            self._save_settings()
            if self.player is not None:
                self.player.set_speaker_config(
                    self._settings.get("speaker_colors") or {})

    def _remember_project_path(self, path: str):
        """最後に開いた/保存した .pvnm を settings.json に記録する。"""
        if not path:
            return
        abs_path = os.path.abspath(os.path.expanduser(path))
        if not abs_path.lower().endswith(".pvnm"):
            return
        if self._settings.get("last_project_path") == abs_path:
            return
        self._settings["last_project_path"] = abs_path
        self._save_settings()

    def _set_project_base(self, path: str):
        """プロジェクト基準ディレクトリに合わせてキャッシュ/ピッカーを更新する。"""
        base = os.path.dirname(os.path.abspath(path))
        self.cache = ImageCache(base)
        set_file_picker_cache(self.cache)
        set_file_picker_base(base)
        for panel in getattr(self, "panels", []):
            setter = getattr(panel, "set_cache", None)
            if callable(setter):
                setter(self.cache)
        if hasattr(self, "ending_editor"):
            self.ending_editor.set_cache(self.cache)

    def _load_project(self, path: str, show_toast: bool = True) -> bool:
        if self.state.load(path):
            if show_toast:
                self.toast.show(f"Loaded: {os.path.basename(path)}")
            self._set_project_base(path)
            self._remember_project_path(path)
            return True
        if show_toast:
            self.toast.show("Load failed!", 8)
        return False

    def _open_import_md_picker(self):
        """IMPORT MD ボタン: .md ファイル一覧から原稿を選択。

        Markdown import は現状、既存の Part/Chapter/Scene を丸ごと
        置き換える強い操作なので、保存状態に関わらず確認する。
        """
        self._pending_confirm_action = "import_md"
        unsaved = (
            "Current project also has unsaved changes.\n"
            if self.state.dirty else ""
        )
        self.confirm_dialog.open(
            "IMPORT MARKDOWN",
            "This will replace all Parts, Chapters, and Scenes\n"
            "with the contents of the selected Markdown file.\n"
            "Scene images, BGM, SE, choices, and goto settings\n"
            "currently in the project will not be merged.\n"
            f"{unsaved}"
            "Save As a backup before importing if needed.",
            ok_label="IMPORT",
            cancel_label="CANCEL",
        )

    def _launch_md_picker(self):
        ref_path = self._last_import_md_path or self.state.file_path
        scan_dir = (os.path.dirname(os.path.abspath(ref_path))
                    if ref_path else self._base_dir)
        open_file_picker("IMPORT MARKDOWN", scan_dir, "markdown",
                         self._on_md_selected, project_base=self._base_dir,
                         initial_path=self._last_import_md_path)

    def _on_md_selected(self, path: str):
        abs_path = (path if os.path.isabs(path)
                    else os.path.join(self._base_dir, path))
        try:
            with open(abs_path, encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            self.toast.show(f"Read failed: {str(e)[:40]}", 8)
            return
        try:
            np_, nc_, ns_ = _md_import_into_state(self.state, text)
        except Exception as e:
            self.toast.show(f"Import failed: {str(e)[:40]}", 8)
            return
        self._last_import_md_path = abs_path
        self._settings["last_import_markdown_path"] = abs_path
        self._save_settings()
        self.toast.show(
            f"Imported {ns_} scenes / {nc_} chapters / {np_} parts", 11)

    def _do_save(self, path: str):
        if self.state.save(path):
            self.toast.show(f"Saved: {os.path.basename(path)}")
            # 保存先フォルダをキャッシュのベースに設定
            self._set_project_base(path)
            self._remember_project_path(path)
        else:
            self.toast.show("Save failed!", 8)

    def _do_load(self, path: str):
        self._load_project(path, show_toast=True)

    def _do_export(self, path: str):
        title = os.path.splitext(os.path.basename(path))[0] or "My Visual Novel"
        state = self.state
        self.toast.show("Exporting...", 9)
        self._export_next_steps = None

        def _run():
            self._export_status = "Starting .pyxapp export"
            ok, msg = export_pyxapp(state, path, settings=self._settings,
                                    title=title,
                                    progress=self._set_export_status)
            self._export_result = (ok, msg, "pyxapp")

        self._export_result = None
        self._export_status = "Starting .pyxapp export"
        self._export_thread = threading.Thread(target=_run, daemon=True)
        self._export_thread.start()

    def _do_export_pyxapp_external(self, path: str):
        title = os.path.splitext(os.path.basename(path))[0] or "My Visual Novel"
        state = self.state
        self.toast.show("Exporting portable .pyxapp...", 9)
        self._export_next_steps = None

        def _run():
            self._export_status = "Starting portable .pyxapp export"
            ok, msg = export_pyxapp_external_assets(
                state, path, settings=self._settings, title=title,
                progress=self._set_export_status)
            self._export_result = (ok, msg, "pyxapp_external")

        self._export_result = None
        self._export_status = "Starting portable .pyxapp export"
        self._export_thread = threading.Thread(target=_run, daemon=True)
        self._export_thread.start()

    def _do_export_macos(self, path: str):
        title = os.path.splitext(os.path.basename(path))[0] or "My Visual Novel"
        state = self.state
        self.toast.show("Exporting macOS app...", 9)
        self._export_next_steps = None

        def _run():
            self._export_status = "Starting macOS app export"
            ok, msg = export_macos_app(state, path, settings=self._settings,
                                       title=title,
                                       progress=self._set_export_status)
            self._export_result = (ok, msg, "macos")

        self._export_result = None
        self._export_status = "Starting macOS app export"
        self._export_thread = threading.Thread(target=_run, daemon=True)
        self._export_thread.start()

    def _do_export_windows_exe(self, path: str):
        source_name = (os.path.basename(self.state.file_path)
                       if self.state.file_path else os.path.basename(path))
        title = os.path.splitext(source_name)[0] or "My Visual Novel"
        state = self.state
        self.toast.show("Exporting Windows EXE...", 9)
        self._export_next_steps = None

        def _run():
            self._export_status = "Starting Windows EXE export"
            ok, msg = export_windows_exe(
                state, path, settings=self._settings, title=title,
                progress=self._set_export_status,
                bundle_original_images=False,
                make_zip=True)
            self._export_result = (ok, msg, "windows_exe")

        self._export_result = None
        self._export_status = "Starting Windows EXE export"
        self._export_thread = threading.Thread(target=_run, daemon=True)
        self._export_thread.start()

    def _do_run_windows_github_actions(self):
        self.toast.show("Starting GitHub Actions...", 9)
        self._export_next_steps = None
        repo_dir = self._base_dir

        def _run():
            self._export_status = "Starting GitHub Actions"
            result = trigger_github_workflow(
                repo_dir,
                "windows-exe.yml",
                tag_fallback_prefix="pvnm-windows-build",
                progress=self._set_export_status,
            )
            self._export_result = (result.ok, result, "github_actions")

        self._export_result = None
        self._export_status = "Starting GitHub Actions"
        self._export_thread = threading.Thread(target=_run, daemon=True)
        self._export_thread.start()

    def _do_export_web(self, path: str):
        title = os.path.splitext(os.path.basename(path))[0] or "My Visual Novel"
        state = self.state
        self.toast.show("Exporting Web HTML...", 9)
        self._export_next_steps = None

        def _run():
            self._export_status = "Starting Web HTML export"
            ok, msg = export_web_html(state, path, settings=self._settings,
                                      title=title,
                                      progress=self._set_export_status)
            self._export_result = (ok, msg, "web")

        self._export_result = None
        self._export_status = "Starting Web HTML export"
        self._export_thread = threading.Thread(target=_run, daemon=True)
        self._export_thread.start()

    def _do_export_capacitor_project(self, path: str):
        title = os.path.basename(os.path.normpath(path)) or "My Visual Novel"
        state = self.state
        self.toast.show("Exporting Capacitor project...", 9)
        self._export_next_steps = None

        def _run():
            self._export_status = "Starting Capacitor export"
            ok, msg = export_capacitor_project(
                state, path, settings=self._settings, title=title,
                progress=self._set_export_status)
            self._export_result = (ok, msg, "capacitor")

        self._export_result = None
        self._export_status = "Starting Capacitor export"
        self._export_thread = threading.Thread(target=_run, daemon=True)
        self._export_thread.start()

    def _do_export_android_apk(self, path: str, variant: str):
        variant = "release" if variant == "release" else "debug"
        source_name = (os.path.basename(self.state.file_path)
                       if self.state.file_path else os.path.basename(path))
        title = os.path.splitext(source_name)[0] or "My Visual Novel"
        state = self.state
        project_dir = self._android_project_dir_for_output(path)
        self.toast.show(f"Exporting Android {variant} APK...", 9)
        self._export_next_steps = None

        def _run():
            self._export_status = f"Starting Android {variant} APK export"
            ok, msg = export_android_apk(
                state,
                path,
                variant=variant,
                project_dir=project_dir,
                settings=self._settings,
                title=title,
                progress=self._set_export_status,
            )
            self._export_result = (ok, msg, f"android_{variant}_apk")

        self._export_result = None
        self._export_status = f"Starting Android {variant} APK export"
        self._export_thread = threading.Thread(target=_run, daemon=True)
        self._export_thread.start()

    def _set_export_status(self, message: str):
        self._export_status = str(message or "")

    def _check_export_thread(self):
        if self._export_thread is None:
            return
        if not self._export_thread.is_alive():
            self._export_thread = None
            if self._export_result is None:
                return
            result = self._export_result
            self._export_result = None
            if len(result) == 3:
                ok, msg, kind = result
            else:
                ok, msg = result
                kind = ""
            if ok:
                if kind == "capacitor":
                    self._export_next_steps = self._capacitor_next_steps(msg)
                    self.toast.show("Capacitor export ready", 11)
                elif kind == "pyxapp_external":
                    self._export_next_steps = self._pyxapp_external_next_steps(msg)
                    self.toast.show("Portable .pyxapp export ready", 11)
                elif kind == "windows_exe":
                    self._export_next_steps = self._windows_exe_ready_steps(msg)
                    self.toast.show("Windows EXE export ready", 11)
                elif kind == "github_actions":
                    self._export_next_steps = self._github_actions_ready_steps(msg)
                    self.toast.show("GitHub Actions started", 11)
                else:
                    self._export_next_steps = None
                    self.toast.show(f"Exported: {os.path.basename(msg)}", 11)
            else:
                if kind == "github_actions":
                    self._export_next_steps = self._github_actions_error_steps(msg)
                    self.toast.show("GitHub Actions not started", 8)
                else:
                    self._export_next_steps = None
                    self.toast.show(f"Export failed: {str(msg)[:40]}", 8)
            self._export_status = ""

    def _update_export_next_steps(self) -> bool:
        if (pyxel.btnp(pyxel.KEY_ESCAPE)
                or pyxel.btnp(pyxel.KEY_RETURN)
                or pyxel.btnp(pyxel.KEY_SPACE)
                or pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT)):
            self._export_next_steps = None
            return True
        return False

    def _capacitor_next_steps(self, path: str) -> dict:
        folder = os.path.abspath(path)
        quoted = shlex.quote(folder)
        return {
            "folder": folder,
            "lines": [
                "CAPACITOR EXPORT READY",
                f"Folder: {folder}",
                "Next commands:",
                f"cd {quoted}",
                "./serve_web.sh diagnostics",
                "./serve_web.sh debug",
                "./build_android.sh open",
                "./build_android.sh build-release",
                "If Android fails: ./android_log.sh pvnm",
                "Docs: README_PVNM_CAPACITOR.md",
                "ESC / ENTER / CLICK: close",
            ],
        }

    def _pyxapp_external_next_steps(self, path: str) -> dict:
        pyxapp = os.path.abspath(path)
        folder = os.path.dirname(pyxapp)
        name = os.path.splitext(os.path.basename(pyxapp))[0]
        assets = os.path.join(folder, f"{name}_assets")
        return {
            "folder": folder,
            "lines": [
                "LINUX PORTABLE PYXAPP READY",
                f"Pyxapp: {pyxapp}",
                f"Assets: {assets}",
                "Keep both side by side on the SD card.",
                "EmulationStation can launch the .pyxapp as usual.",
                "If paths differ, set PVNM_ASSET_ROOT to the assets folder.",
                "ESC / ENTER / CLICK: close",
            ],
        }

    def _windows_export_next_steps(self) -> dict:
        folder = os.path.abspath(self._base_dir)
        return {
            "folder": folder,
            "lines": [
                "WINDOWS EXE BUILD",
                "This host cannot build a Windows .exe.",
                "Use the GitHub Actions workflow after pushing.",
                "Actions: Build Windows EXE > Run workflow",
                "Or run on Windows:",
                "python -m pip install -r requirements-build.txt",
                "python tools/build_windows_exe.py --zip",
                "ESC / ENTER / CLICK: close",
            ],
        }

    def _github_actions_ready_steps(self, result) -> dict:
        folder = os.path.abspath(self._base_dir)
        workflow = getattr(result, "workflow", "") or "windows-exe.yml"
        repo = getattr(result, "repo", "") or "GitHub repository"
        ref = getattr(result, "ref", "") or "current branch"
        url = getattr(result, "url", "") or ""
        provider = getattr(result, "provider", "") or "GitHub"
        tag = getattr(result, "tag", "") or ""
        lines = [
            "GITHUB ACTIONS STARTED",
            "Workflow: Build Windows EXE",
            f"Repo: {repo}",
            f"Ref: {ref}",
            f"Auth: {provider}",
            f"Tag: {tag}" if tag else "Trigger: workflow_dispatch",
            f"URL: {url}" if url else f"Workflow: {workflow}",
            "Artifact: Actions run > LastEmulator-windows",
            "ESC / ENTER / CLICK: close",
        ]
        return {"folder": folder, "lines": lines}

    def _github_actions_error_steps(self, result) -> dict:
        folder = os.path.abspath(self._base_dir)
        message = getattr(result, "message", str(result))
        url = getattr(result, "url", "") or ""
        lines = [
            "GITHUB ACTIONS NOT STARTED",
            str(message),
            "Commit and push project changes first.",
            "Auth: gh auth login, token, or SSH git push",
            f"URL: {url}" if url else "Workflow: .github/workflows/windows-exe.yml",
            "ESC / ENTER / CLICK: close",
        ]
        return {"folder": folder, "lines": lines}

    def _windows_exe_ready_steps(self, path: str) -> dict:
        result = os.path.abspath(path)
        folder = os.path.dirname(result)
        stem = os.path.splitext(os.path.basename(result))[0]
        app_name = stem[:-8] if stem.lower().endswith("-windows") else stem
        app_dir = os.path.join(folder, app_name)
        return {
            "folder": folder,
            "lines": [
                "WINDOWS EXE READY",
                f"Zip: {result}",
                f"Folder: {app_dir}",
                "Distribute the zip or the whole folder.",
                "Keep the .exe with its runtime files.",
                "ESC / ENTER / CLICK: close",
            ],
        }

    def _draw_export_status(self):
        if not (self._export_thread and self._export_thread.is_alive()):
            return
        msg = self._export_status or "Exporting..."
        text = f"EXPORT: {msg}"
        size = 24
        max_w = pyxel.width - 48
        while text_px_w(text, size) > max_w and len(text) > 16:
            text = text[:-2] + "…"
        tw = text_px_w(text, size)
        th = _font_render_h(size)
        box_w = min(pyxel.width - 32, tw + 32)
        box_h = th + 24
        x = (pyxel.width - box_w) // 2
        y = (pyxel.height - box_h) // 2
        pyxel.rect(x, y, box_w, box_h, 0)
        pyxel.rectb(x, y, box_w, box_h, 10)
        draw_unicode(x + (box_w - tw) // 2,
                     y + (box_h - th) // 2,
                     text, 10, size=size)

    def _draw_export_next_steps(self):
        info = self._export_next_steps
        if not info:
            return
        lines = list(info.get("lines", []))
        if not lines:
            return

        box_w = pyxel.width - 52
        x = (pyxel.width - box_w) // 2
        max_text_w = box_w - 28
        y = 86
        row_gap = 5
        sizes = [16, 12, 12, 12, 12, 12, 12, 12, 12, 10]
        colors = [10, 7, 6, 11, 11, 11, 11, 9, 6, 5]
        heights = [_font_render_h(sizes[min(i, len(sizes) - 1)])
                   for i in range(len(lines))]
        box_h = sum(heights) + row_gap * (len(lines) - 1) + 30
        y = max(36, min(y, pyxel.height - box_h - 18))

        pyxel.rect(x, y, box_w, box_h, 0)
        pyxel.rectb(x, y, box_w, box_h, 10)
        pyxel.rectb(x + 2, y + 2, box_w - 4, box_h - 4, 5)

        cy = y + 14
        for i, raw in enumerate(lines):
            size = sizes[min(i, len(sizes) - 1)]
            col = colors[min(i, len(colors) - 1)]
            text = self._fit_export_text(str(raw), size, max_text_w)
            draw_unicode(x + 14, cy, text, col, size=size)
            cy += heights[i] + row_gap

    def _fit_export_text(self, text: str, size: int, max_w: int) -> str:
        if text_px_w(text, size) <= max_w:
            return text
        marker = "..."
        if max_w <= text_px_w(marker, size):
            return marker
        left = max(4, len(text) // 2)
        right = len(text) - left
        while left > 2 and right > 2:
            candidate = text[:left] + marker + text[-right:]
            if text_px_w(candidate, size) <= max_w:
                return candidate
            if left >= right:
                left -= 1
            else:
                right -= 1
        clipped = text
        while clipped and text_px_w(clipped + marker, size) > max_w:
            clipped = clipped[:-1]
        return (clipped + marker) if clipped else marker



def _default_speaker_colors() -> dict:
    return {
        "narration_text_color": None,  # None = PLAY_TEXT 既定
        "speakers": {},
    }


def _default_settings() -> dict:
    return {
        "editor_font":      "IPA_Gothic.ttf",
        "dialog_font":      "IPA_Gothic.ttf",
        "editor_font_size": 16,
        "dialog_font_size": 16,
        "ui_font_size":     16,
        "ui_scale":         1,
        "last_project_path": "",
        # スピーカーごとのテキスト/バッジ色 + 地の文色
        # 形式: {"narration_text_color": int,
        #        "speakers": {name: {"name_color": int,
        #                            "name_bg_color": int,
        #                            "text_color": int}}}
        "speaker_colors": _default_speaker_colors(),
    }


def _reset_project_scoped_settings_values(settings: dict) -> bool:
    """別プロジェクトや新規プロジェクトへ引き継がない設定を初期化する。"""
    defaults = _default_settings()
    changed = False
    for key in ("last_project_path", "speaker_colors"):
        if settings.get(key) != defaults[key]:
            settings[key] = defaults[key]
            changed = True
    return changed


def _load_settings(base_dir: str) -> dict:
    """settings.json を読み込む。不足キーはデフォルト値で補い、ファイルに書き戻す。"""
    path = os.path.join(base_dir, "settings.json")
    defaults = _default_settings()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = {**defaults, **data}
        # 不足キーがあれば書き戻して常に全キーをファイルに保持
        if set(defaults) - set(data):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(merged, f, ensure_ascii=False, indent=2)
        return merged
    except FileNotFoundError:
        # 新規作成
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(defaults, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return defaults
    except Exception:
        return defaults


def _ensure_palettes(settings: dict):
    """廃止された旧キーを掃除する。

    マスターパレット運用に統一されたため、editor_palette / palette /
    play_palette などの旧フォーマットは settings.json から除去する。
    色の割当は dialog_role_indices (role名→0-255) のみで管理する。
    """
    for k in ("palette", "play_palette", "editor_palette"):
        if k in settings:
            del settings[k]


def _init_fonts(base_dir: str, settings: dict):
    """エディタフォント + BDFダイアログサイズを初期化する。"""
    from ui.widgets import load_pyxel_font, set_font_base_dir
    set_font_base_dir(base_dir)

    # エディタフォント
    font_file = settings.get("editor_font", "IPA_Gothic.ttf")
    font_size = int(settings.get("editor_font_size", 16))
    ui_font_size = int(settings.get("ui_font_size", 16))
    set_ui_font_size(ui_font_size)
    set_ui_scale(int(settings.get("ui_scale", 1)))

    editor_font = load_pyxel_font(font_file, font_size)
    if editor_font:
        set_editor_font(editor_font, font_size, path=font_file)
        print(f"[PVNM] Editor font: {font_file} (size={font_size})")
    else:
        print(f"[PVNM] Editor font not found: {font_file} — using ASCII fallback")

    # ダイアログフォント: BDF統一後はTTF指定を無視し、サイズだけ使う。
    dialog_file = settings.get("dialog_font", "IPA_Gothic.ttf")
    dialog_size = int(settings.get("dialog_font_size", 16))
    if dialog_file:
        print(f"[PVNM] dialog_font ignored (BDF runtime): {dialog_file}")
    set_dialog_font_size(dialog_size)
    print(f"[PVNM] Dialog BDF size: {dialog_size}")


if __name__ == "__main__":
    App()
