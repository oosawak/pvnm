"""VNプレイヤー: スクリプトを順に実行してビジュアルノベルを再生する (720×480)"""
import copy
import os
import pyxel
from ui.colors import *
from ui.widgets import is_clicked, draw_unicode, text_px_w, _font_render_h
from engine.script import build_index
from engine.animator import (
    AnimSprite,
    prepare_char_config_for_next_scene,
    sprite_load_size_for_screen,
)
from engine.image_cache import (
    COLOR_KEY_AUTO,
    ImageCache,
    normalize_color_key,
    set_default_palette as _set_image_cache_palette,
)
from engine import palette as _palette_mod
from engine import audio as _audio
from engine import platform_input as _platform_input
from engine import runtime_assets as _runtime_assets
from engine import runtime_debug as _runtime_debug
from engine import player_prefs as _player_prefs
from engine.text_wrap import dialog_letter_spacing, wrap_text
from ui.player_ui import PlayerUI
from ui.conversation_log import ConversationLog
from ui.save_load_screen import SaveLoadScreen
from ui.player_options import PlayerOptions
from engine.controller import GamepadControls
from engine.ending_player import EndingPlayer

# ── 定数 ────────────────────────────────────────────────────────

TYPING_SPEED  = 2      # フレーム数/文字
FADE_FRAMES   = 18     # フェードトランジション（0.6秒@30fps）

# オート再生速度 (フレーム数)
AUTO_SPEEDS   = [30, 60, 90]  # fast=1s, normal=2s, slow=3s @30fps
AUTO_LABELS   = ["FAST", "NORMAL", "SLOW"]

# スキップ速度
SKIP_INTERVAL = 9  # 0.3秒@30fps
LOG_MAX_ENTRIES = 240
PREWARM_DELAY_FRAMES = 5
PREWARM_MAX_TARGET_SCENES = 4
PREWARM_INPUT_GRACE_FRAMES = 6

# ダイアログレイアウト (720×480)
DIALOG_X  = 16
DIALOG_Y  = 324
DIALOG_W  = 688
DIALOG_H  = 140
DIALOG_PAD_X = 16    # テキスト左右内側余白
DIALOG_PAD_Y = 26    # テキスト上側内側余白 (右上のボタンバー回避のため少し下げる)
FONT_SIZE    = 14    # デフォルトダイアログフォントサイズ（後方互換用）

# 選択肢ボタン
CHOICE_W  = 280
CHOICE_GAP = 6
CHOICE_PAD_X = 24
CHOICE_MAX_MARGIN_X = 48

# ── フォント ─────────────────────────────────────────────────────

_font_size = 16
_warned_scene_fonts: set[str] = set()


def set_dialog_font(font: "pyxel.Font | None", size: int = 16):
    """Set dialog size. The font object is ignored; runtime text is BDF-only."""
    global _font_size
    _font_size = max(8, min(25, int(size)))


def set_dialog_font_size(size: int = 16):
    set_dialog_font(None, size)


def _font_rh(size: int | None = None):
    rh = _font_render_h(_font_size if size is None else size)
    return max(rh, int(rh * 1.5))
def _speaker_h(size: int | None = None):  return _font_rh(size) + 8
def _choice_h(size: int | None = None):   return _font_rh(size) + 12
def _line_h(size: int | None = None):     return _font_rh(size) + 4


def _choice_w(choices: list, size: int, screen_w: int) -> int:
    labels = [str(opt.get("label", "")) for opt in choices if isinstance(opt, dict)]
    text_w = max((text_px_w(label, size) for label in labels), default=0)
    max_w = max(CHOICE_W, screen_w - CHOICE_MAX_MARGIN_X * 2)
    return max(CHOICE_W, min(max_w, text_w + CHOICE_PAD_X * 2))


def _draw_text(x: int, y: int, text: str, size: int, col: int):
    draw_unicode(x, y, text, col, size=size)


# ── スキャンラインフェード ────────────────────────────────────────

def _draw_scanline_fade(alpha: float):
    if alpha <= 0:
        return
    W, H = pyxel.width, pyxel.height
    if alpha >= 1.0:
        pyxel.rect(0, 0, W, H, 0)
        return
    if alpha > 0.75:
        step = 1
    elif alpha > 0.5:
        step = 2
    elif alpha > 0.25:
        step = 3
    else:
        step = 4
    for y in range(0, H, step):
        pyxel.line(0, y, W - 1, y, 0)


# ── VNPlayer ────────────────────────────────────────────────────

class VNPlayer:
    """
    スクリプト dict を受け取り VN を再生する。
    update() / draw() を毎フレーム呼ぶ。
    終了時は self.finished が True。
    """

    def __init__(self, script: dict, start_scene: str = None,
                 cache: ImageCache = None, endings: list = None,
                 settings: dict = None,
                 ending_complete_callback=None,
                 defer_start: bool = False):
        self.index = build_index(script)
        # エディタの平坦シーン順序を保持する。「シーン2 から再生開始」のような
        # 途中再生で、開始シーンより前のシーンを仮想走査して永続状態 (BG /
        # キャラ) を復元するために必要。
        self._scene_order: list = list(script.get("scenes", []))
        first = (start_scene if (start_scene and start_scene in self.index)
                 else (self._scene_order[0]["name"] if self._scene_order else None))
        self._cache = cache  # None の場合は画像なし
        self._endings = {e.get("name", ""): e for e in (endings or [])}
        # シーン単位パレット生成用に settings.json (dialog_role_indices, speaker_colors)
        # を保持する。reserved_from_settings() で参照される。
        self._settings: dict = settings or {}
        self._speaker_config = (
            self._settings.get("speaker_colors")
            if isinstance(self._settings.get("speaker_colors"), dict)
            else {}
        )

        # 実行状態
        self.scene_name = first
        self.step_i     = 0
        self.finished   = False

        # ビジュアルスプライト
        self._bg_sprite:   AnimSprite | None = None
        self._char_sprites: dict[str, AnimSprite] = {}  # slot -> AnimSprite
        self._prewarm_queue: list[dict] = []
        self._prewarm_seen: set[tuple] = set()
        self._prewarm_delay = 0
        self._prewarm_input_grace = 0

        # 画像の永続状態 (前シーンから引き継ぐ BG / キャラ設定)。
        # シーン入場時の解決ルール:
        #   - scene.bg_hide=True              → _persistent_bg = None (明示クリア)
        #   - scene.bg = "/path/..."           → _persistent_bg = {…} を更新 (SET)
        #   - 上記以外 (bg="" / 欠落)         → _persistent_bg を維持 (INHERIT)
        # キャラも各スロット (char_l/c/r) ごとに同じ規則。
        self._persistent_bg: dict | None = None
        self._persistent_chars: dict[str, dict | None] = {}
        # BGM も背景と同じくシーンをまたいで継承する。SE は単発効果音なので
        # 永続化しない。
        self._persistent_bgm: dict | None = None

        # ダイアログ
        self.speaker     = ""
        self.full_text   = ""
        self.shown_chars = 0
        self.typing_timer = 0
        self._dialog_suppressed = False

        # 選択肢
        self.choices     = []
        self.choice_hover = -1

        # 待ち状態
        self._waiting = False

        # フェードトランジション
        self._trans_state  = None
        self._trans_frame  = 0
        self._trans_target = ""
        self._trans_out_frames = FADE_FRAMES
        self._trans_in_frames  = FADE_FRAMES

        # シーン別フォントサイズ (フォントファイル指定はBDF統一のため無視)。
        # プレイヤーがOPTで指定した文字サイズはアクセシビリティ設定として
        # 作者側のシーンサイズより優先する。
        self._scene_base_font_size = _font_size
        self._text_size_override = _player_prefs.load_text_size_override()
        self._scene_font_size = self._effective_text_size(self._scene_base_font_size)

        # オーディオ初期化
        _audio.init_audio()

        # 会話ログ
        self.log: list[tuple[str, str]] = []
        self._log_chapter_key: str | None = None

        # シーン遷移履歴 (←キーで前シーンに戻る)。シーン遷移ごとに「直前の
        # シーン名」をプッシュする。choices/goto/transition 経由の遷移は
        # 全て積まれるが、ロードや戻る操作自身では積まない。
        self._scene_history: list[str] = []

        # オート再生
        self._auto_on    = False
        self._auto_speed = 1       # 0=fast, 1=normal, 2=slow
        self._auto_timer = 0
        self._auto_resume_after_scene = False

        # スキップ
        self._skip_on    = False
        self._skip_hold_on = False
        self._skip_timer = 0
        self._input_suppress_frames = 0
        self._input_suppress_until_release = False

        # エンディング
        self._ending_player: EndingPlayer | None = None
        self._ending_player_name = ""
        self._ending_complete_callback = ending_complete_callback

        # プレイヤーUI
        self._controller = GamepadControls(self._settings)
        self._ui = PlayerUI(DIALOG_X, DIALOG_Y, DIALOG_W)
        self._log_view = ConversationLog()
        self._save_screen = SaveLoadScreen()
        self._options = PlayerOptions()
        self._save_path = ""  # set_save_path() で設定

        if first and not defer_start:
            # エディタの「途中シーンから再生」に対応するため、開始シーンより
            # 前のシーンを順番に仮想走査して永続状態を構築する。
            # _resolve_persistent_state はBGMの継承状態だけ更新し、実際の再生は
            # _enter_scene 内で行うので、この走査中に音は鳴らない。
            self._initialize_persistent_for_start(first)
            self._enter_scene(first)

    # ── 公開 ────────────────────────────────────────────────────

    def modal_active(self) -> bool:
        """SAVE/LOG など、プレイ上のモーダルが前面に出ているか。"""
        return bool(self._save_screen.active or self._log_view.active
                    or self._options.active)

    def set_ending_complete_callback(self, callback):
        """エンディングを自然終了した時に呼ぶ callback(name) を設定する。"""
        self._ending_complete_callback = callback

    def _open_options(self):
        self._options.open(
            self._controller,
            text_size_getter=self._get_text_size_override,
            text_size_effective_getter=self._get_effective_text_size,
            text_size_setter=self._set_text_size_override,
            allow_title_return=True,
        )

    def _effective_text_size(self, base_size: int | None = None) -> int:
        override = _player_prefs.normalize_text_size(self._text_size_override)
        if override is not None:
            return override
        try:
            n = int(self._scene_base_font_size if base_size is None else base_size)
        except Exception:
            n = _font_size
        return n if n > 0 else _font_size

    def _get_text_size_override(self) -> int | None:
        return _player_prefs.normalize_text_size(self._text_size_override)

    def _get_effective_text_size(self) -> int:
        return self._effective_text_size()

    def _set_text_size_override(self, size: int | None):
        self._text_size_override = _player_prefs.normalize_text_size(size)
        _player_prefs.save_text_size_override(self._text_size_override)
        self._scene_font_size = self._effective_text_size()

    def _open_log_view(self):
        self._log_view.open(
            self.log,
            controller=self._controller,
            font_size=self._effective_text_size(),
        )

    def _scene_log_scope(self, scene_name: str) -> str:
        parts = str(scene_name or "").split("_", 2)
        if len(parts) >= 2:
            return f"{parts[0]}_{parts[1]}"
        return str(scene_name or "")

    def _update_log_scope(self, scene_name: str) -> None:
        scope = self._scene_log_scope(scene_name)
        if not scope:
            return
        if self._log_chapter_key is None:
            self._log_chapter_key = scope
            return
        if scope != self._log_chapter_key:
            self.log.clear()
            self._log_chapter_key = scope

    def _append_log(self, speaker: str, text: str) -> None:
        self.log.append((speaker, text))
        overflow = len(self.log) - LOG_MAX_ENTRIES
        if overflow > 0:
            del self.log[:overflow]

    def update(self):
        if self.finished:
            return
        _audio.update()
        platform_back = _platform_input.consume_back_pressed()
        if self._controller.quit_combo_pressed():
            self.finished = True
            return

        # エンディング再生中
        if self._ending_player:
            if platform_back:
                return
            self._ending_player.update()
            if self._ending_player.finished:
                ending_name = self._ending_player_name
                aborted = bool(getattr(self._ending_player, "aborted", False))
                next_name = getattr(self._ending_player, "next_ending_name", "")
                self._ending_player = None
                self._ending_player_name = ""
                if (not aborted and ending_name
                        and callable(self._ending_complete_callback)):
                    try:
                        self._ending_complete_callback(ending_name)
                    except Exception:
                        pass
                if not aborted and next_name and next_name in self._endings:
                    self._restore_master_palette()
                    self._ending_player_name = next_name
                    self._ending_player = EndingPlayer(
                        self._endings[next_name], cache=self._cache,
                        settings=self._settings)
                    return
                self.finished = True
            return

        # セーブ/ロード画面モーダル
        if self._save_screen.active:
            if platform_back or self._controller.pressed("back"):
                self._save_screen.active = False
                self._save_screen.closed = True
                return
            self._save_screen.update()
            if self._save_screen.closed:
                self._save_screen.closed = False
            return

        # 会話ログモーダル
        if self._log_view.active:
            if platform_back or self._controller.pressed("back"):
                self._log_view.active = False
                self._log_view.closed = True
                return
            self._log_view.update()
            if self._log_view.closed:
                self._log_view.closed = False
            return

        # OPT モーダル
        if self._options.active:
            if (pyxel.btnp(pyxel.KEY_ESCAPE)
                    or pyxel.btnp(pyxel.KEY_BACKSPACE)
                    or self._controller.pressed("back")
                    or platform_back):
                self._options.handle_back()
                if self._options.closed:
                    self._options.closed = False
                return
            self._options.update()
            if self._options.title_requested:
                self._reset_playback_assist_state(clear_prewarm=True)
                try:
                    _audio.stop_all_se()
                except Exception:
                    pass
                self._options.title_requested = False
                self.finished = True
                return
            if self._options.closed:
                self._options.closed = False
            return

        # Exported desktop builds use ESC as a quick return to the title
        # screen. Editor preview still intercepts ESC in main.py and returns to
        # the editor, so this only affects the standalone player path.
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self._reset_playback_assist_state(clear_prewarm=True)
            try:
                _audio.stop_all_se()
            except Exception:
                pass
            self.finished = True
            return

        # フェードトランジション
        if self._trans_state == "fade_out":
            self._run_prewarm_step()
            self._trans_frame += 1
            if self._trans_frame >= self._trans_out_frames:
                self._enter_scene(self._trans_target)
                self._trans_state = "fade_in"
                self._trans_frame = 0
                self._advance()
            return
        if self._trans_state == "fade_in":
            self._trans_frame += 1
            if self._trans_frame >= self._trans_in_frames:
                self._trans_state = None
            return

        # ← キーで履歴スタックを 1 段戻る (前シーンへ)
        if ((pyxel.btnp(pyxel.KEY_LEFT) or self._controller.pressed("back"))
                or platform_back) and self._scene_history:
            self._go_back_scene()
            return

        # スプライト更新
        if self._bg_sprite:
            self._bg_sprite.update()
        for sp in self._char_sprites.values():
            sp.update()

        # ロード直後などは、セーブ/ロード画面で使ったA/START/R1等の
        # 押しっぱなし入力を次の再生状態へ持ち越さない。
        if self._suppressing_action_input():
            return

        # プレイヤーUIボタン
        self._ui.auto_on = self._auto_on
        self._ui.skip_on = self._skip_active()
        ui_available = (
            (self.full_text or self.speaker)
            and not getattr(self, "_hide_dialog", False)
            and not getattr(self, "_dialog_suppressed", False)
        )
        if ui_available:
            self._ui.update()
        else:
            self._ui.active_btn = None
            self._ui._hover = -1

        btn = self._ui.active_btn
        if btn == "AUTO":
            self._cycle_auto()
        elif btn == "SKIP":
            self._auto_resume_after_scene = False
            self._skip_on = not self._skip_on
            self._skip_timer = 0
            if self._skip_on:
                self._auto_on = False
        elif btn == "LOG":
            self._open_log_view()
            return
        elif btn == "SAVE":
            self._save_screen.open(
                "save",
                on_save=self.get_save_state,
                on_load=self.load_save_state,
                save_path=self._save_path,
                controller=self._controller,
            )
            return
        elif btn == "OPT":
            self._open_options()
            return

        if self._controller.pressed("save"):
            self._save_screen.open(
                "save",
                on_save=self.get_save_state,
                on_load=self.load_save_state,
                save_path=self._save_path,
                controller=self._controller,
            )
            return
        if self._controller.pressed("log"):
            self._open_log_view()
            return
        if self._controller.pressed("opt"):
            self._open_options()
            return
        if self._controller.pressed("auto"):
            self._cycle_auto()

        if self._controller.pressed("hide_dialog"):
            if ((self.full_text or self.speaker)
                    and not self.choices
                    and not getattr(self, "_hide_dialog", False)):
                self._dialog_suppressed = not self._dialog_suppressed
                self._auto_on = False
                self._skip_on = False
                self._skip_hold_on = False
                return

        # 右クリックでオート速度切替
        if self._auto_on and pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT):
            self._cycle_auto()

        # Ctrl/R1押し続けでスキップ。SKIPボタンのトグル状態とは分離する。
        self._skip_hold_on = (
            pyxel.btn(pyxel.KEY_CTRL)
            or self._controller.held("skip_hold")
        )
        if self._skip_hold_on:
            self._auto_on = False

        mx, my  = pyxel.mouse_x, pyxel.mouse_y
        mouse_clicked = pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT)
        advance_key = (pyxel.btnp(pyxel.KEY_SPACE)
                       or pyxel.btnp(pyxel.KEY_RETURN)
                       or self._controller.pressed("confirm"))
        clicked = mouse_clicked or advance_key
        hide_dialog = getattr(self, "_hide_dialog", False)
        dialog_visible = (
            (self.full_text or self.speaker)
            and not hide_dialog
            and not self._dialog_suppressed
        )
        dialog_area_clicked = (
            mouse_clicked
            and DIALOG_X <= mx < DIALOG_X + DIALOG_W
            and DIALOG_Y <= my < DIALOG_Y + DIALOG_H
        )

        # 左クリックでオート/スキップ解除（UIボタン上でない場合）
        if clicked and self._ui._hover < 0:
            if self._auto_on:
                self._auto_on = False
            if self._skip_on and not self._skip_hold_on:
                self._skip_on = False

        if self.choices:
            self._update_choices(mx, my, mouse_clicked, advance_key)
            if self.choices:
                self._run_prewarm_step()
            return

        if (mouse_clicked and self._ui._hover < 0
                and (self.full_text or self.speaker)
                and not getattr(self, "_hide_dialog", False)):
            if self._dialog_suppressed:
                self._dialog_suppressed = False
                return
            if not dialog_area_clicked:
                self._dialog_suppressed = True
                return

        # スキップ処理
        if self._skip_active() and self._waiting:
            self._skip_timer += 1
            self.shown_chars = len(self.full_text)  # 即全表示
            if self._skip_timer >= self._skip_interval_frames():
                self._skip_timer = 0
                self._waiting = False
                self._advance()
            else:
                self._run_prewarm_step()
            return

        if self._waiting:
            was_text_complete = self.shown_chars >= len(self.full_text)
            self._update_typing()
            if (not was_text_complete
                    and self.shown_chars >= len(self.full_text)):
                self._prewarm_input_grace = max(
                    self._prewarm_input_grace, PREWARM_INPUT_GRACE_FRAMES)

            # オート再生
            if self._auto_on and self.shown_chars >= len(self.full_text):
                self._auto_timer += 1
                if self._auto_timer >= AUTO_SPEEDS[self._auto_speed]:
                    self._auto_timer = 0
                    self._waiting = False
                    self._advance()
                else:
                    self._run_prewarm_step()
                return

            # 左クリックでの進行は「表示中のダイアログ内」に限定する。
            # ダイアログ外クリックは上の分岐で一時非表示/再表示に使うため、
            # ここで進行扱いにしない。
            # ただし HIDE DIALOG シーンはクリック対象のダイアログが無いので、
            # 画面クリックを従来どおり進行扱いにする。
            # 画像/SEだけの空テキストシーンもダイアログが表示されないため、
            # 画面クリックで進行できるようにする。
            empty_say_waiting = (not self.full_text and not self.speaker)
            can_advance = (
                advance_key
                or (hide_dialog and mouse_clicked)
                or (empty_say_waiting and mouse_clicked)
                or (dialog_visible and dialog_area_clicked)
            )
            if can_advance and self._ui._hover < 0:
                if self.shown_chars < len(self.full_text):
                    self.shown_chars = len(self.full_text)
                    self._prewarm_input_grace = max(
                        self._prewarm_input_grace, PREWARM_INPUT_GRACE_FRAMES)
                else:
                    self._waiting = False
                    self._advance()
            else:
                self._run_prewarm_step()
        else:
            self._advance()

    def draw(self):
        if self.finished:
            return

        # エンディング再生中
        if self._ending_player:
            self._ending_player.draw()
            return

        W, H = pyxel.width, pyxel.height
        pyxel.cls(PLAY_BG)

        # ── 背景 ──
        if self._bg_sprite and self._bg_sprite.loaded:
            self._bg_sprite.draw()
        else:
            pyxel.rect(0, 0, W, H, PLAY_BG)

        # ── キャラクター (left → right → center の順で前面へ) ──
        for slot in ("left", "right", "center"):
            sp = self._char_sprites.get(slot)
            if sp and sp.loaded:
                sp.draw()

        # ── ダイアログ ──
        hide_dlg = getattr(self, "_hide_dialog", False)
        dialog_suppressed = getattr(self, "_dialog_suppressed", False)
        if (self.full_text or self.speaker) and not hide_dlg and not dialog_suppressed:
            self._draw_dialog(W, H)

        # ── 選択肢 ──
        if self.choices:
            self._draw_choices(W, H)

        # ── プレイヤーUIボタン ──
        if (self.full_text or self.speaker) and not hide_dlg and not dialog_suppressed:
            self._ui.draw()

        # ── オート速度表示 ──
        if self._auto_on and not dialog_suppressed:
            label = AUTO_LABELS[self._auto_speed]
            draw_unicode(DIALOG_X + 8, DIALOG_Y + 6, f"AUTO:{label}", 8,
                         size=10)

        # ── 操作ヒント (▼点滅) ──
        if (self._waiting and not self.choices and not self._auto_on
                and not self._skip_active() and not hide_dlg
                and not dialog_suppressed):
            if self.shown_chars >= len(self.full_text):
                if pyxel.frame_count % 30 < 20:
                    marker = "▼"
                    marker_size = 14
                    mx = DIALOG_X + DIALOG_W - text_px_w(marker, marker_size) - 18
                    my = DIALOG_Y + DIALOG_H - _font_render_h(marker_size) - 12
                    draw_unicode(mx, my, marker, PLAY_ACCENT, size=marker_size)

        # ── フェードオーバーレイ ──
        if self._trans_state:
            frames = (self._trans_in_frames if self._trans_state == "fade_in"
                      else self._trans_out_frames)
            alpha = self._trans_frame / max(1, frames)
            if self._trans_state == "fade_in":
                alpha = 1.0 - alpha
            _draw_scanline_fade(alpha)

        # ── 会話ログオーバーレイ ──
        if self._log_view.active:
            self._log_view.draw()

        # ── セーブ/ロード画面 ──
        if self._save_screen.active:
            self._save_screen.draw()

        # ── OPT画面 ──
        if self._options.active:
            self._options.draw()

        _runtime_debug.draw_hud()

    # ── 内部 ────────────────────────────────────────────────────

    def _skip_active(self) -> bool:
        return bool(self._skip_on or self._skip_hold_on)

    def _skip_interval_frames(self) -> int:
        return SKIP_INTERVAL

    def _reset_playback_assist_state(self, suppress_input: bool = False,
                                     clear_prewarm: bool = False) -> None:
        """Stop AUTO/SKIP and clear transient input/UI state safely."""
        self._auto_on = False
        self._auto_timer = 0
        self._auto_resume_after_scene = False
        self._skip_on = False
        self._skip_hold_on = False
        self._skip_timer = 0
        self._prewarm_input_grace = 0
        if clear_prewarm:
            self._prewarm_queue.clear()
            self._prewarm_seen.clear()
            self._prewarm_delay = 0
        try:
            self._ui.auto_on = False
            self._ui.skip_on = False
            self._ui.active_btn = None
            self._ui._hover = -1
        except Exception:
            pass
        if suppress_input:
            self._input_suppress_frames = max(self._input_suppress_frames, 8)
            self._input_suppress_until_release = True

    def _action_input_held(self) -> bool:
        try:
            if (pyxel.btn(pyxel.KEY_SPACE)
                    or pyxel.btn(pyxel.KEY_RETURN)
                    or pyxel.btn(pyxel.KEY_CTRL)
                    or pyxel.btn(pyxel.KEY_ESCAPE)
                    or pyxel.btn(pyxel.MOUSE_BUTTON_LEFT)):
                return True
        except Exception:
            pass
        for action in (
            "confirm", "back", "auto", "opt", "save", "log",
            "skip_hold", "hide_dialog", "back_button", "start_button",
        ):
            try:
                if self._controller.held(action):
                    return True
            except Exception:
                pass
        return False

    def _suppressing_action_input(self) -> bool:
        if (self._input_suppress_frames <= 0
                and not self._input_suppress_until_release):
            return False
        if self._input_suppress_frames > 0:
            self._input_suppress_frames -= 1
        held = self._action_input_held()
        if self._input_suppress_until_release:
            if held or self._input_suppress_frames > 0:
                return True
            self._input_suppress_until_release = False
            return False
        return self._input_suppress_frames > 0

    def _cycle_auto(self):
        """Cycle FAST -> NORMAL -> SLOW -> OFF."""
        self._auto_resume_after_scene = False
        if not self._auto_on:
            self._auto_on = True
            self._auto_speed = 0
            self._skip_on = False
            self._skip_hold_on = False
        else:
            self._auto_speed += 1
            if self._auto_speed >= len(AUTO_SPEEDS):
                self._auto_on = False
                self._auto_speed = 0
        self._auto_timer = 0

    def _apply_scene_auto_pause(self, scene: dict) -> None:
        """Pause AUTO for this scene, then restore it on the next scene."""
        if self._auto_resume_after_scene:
            self._auto_on = True
            self._auto_resume_after_scene = False
            self._auto_timer = 0
        if bool(scene.get("auto_pause", False)) and self._auto_on:
            self._auto_on = False
            self._auto_resume_after_scene = True
            self._auto_timer = 0

    def _collect_scene_image_paths(self) -> list:
        """現在の persistent 状態 (継承解決後) から画像パスを集める。

        シーンパレット構築のため、画面に実際に出る BG + 各キャラスロットの
        画像 + flipbook 補助画像をすべて列挙する。INHERIT で前シーンから
        引き継いでいる画像も対象。
        """
        return self._collect_image_paths_from_state(
            self._persistent_bg, self._persistent_chars)

    def _collect_image_paths_from_state(self, bg: dict | None,
                                        chars: dict | None) -> list:
        paths: list = []
        if bg:
            bp = bg.get("path", "")
            if bp:
                paths.append(bp)
            for fb in (bg.get("anim", {}) or {}).get("flipbook_files", []) or []:
                if fb:
                    paths.append(fb)
        for cfg in (chars or {}).values():
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

    def _palette_for_paths(self, paths: list):
        if not self._cache:
            return None
        reserved = _palette_mod.reserved_from_settings(self._settings)
        if not reserved:
            return None
        pal = None
        if hasattr(self._cache, "get_prebuilt_palette"):
            pal = self._cache.get_prebuilt_palette(paths, reserved)
        if pal is None:
            pal = _palette_mod.build_scene_palette(
                paths, reserved, base_dir=self._cache.base_dir)
        return pal

    def _simulate_persistent_after_scene(self, scene: dict) -> dict:
        snap = self._snapshot_persistent()
        work = copy.deepcopy(snap)
        restore = copy.deepcopy(snap)
        try:
            self._restore_persistent(work)
            self._resolve_persistent_state(scene)
            return self._snapshot_persistent()
        finally:
            self._restore_persistent(restore)

    def _scene_successors(self, scene: dict) -> list[str]:
        names: list[str] = []
        steps = scene.get("steps", []) or []
        for step in steps:
            if not isinstance(step, dict):
                continue
            op = step.get("op", "")
            if op == "choice":
                for opt in step.get("options", []) or []:
                    if isinstance(opt, dict):
                        target = opt.get("goto", "")
                        if target and target in self.index and target not in names:
                            names.append(target)
            elif op == "goto":
                target = step.get("scene", "")
                if target and target in self.index and target not in names:
                    names.append(target)
                break
            elif op in ("end",):
                break
        if names or scene.get("goto_ending"):
            return names[:PREWARM_MAX_TARGET_SCENES]

        cur_name = scene.get("name", "")
        for i, item in enumerate(self._scene_order):
            if not isinstance(item, dict) or item.get("name") != cur_name:
                continue
            if i + 1 < len(self._scene_order):
                nxt = self._scene_order[i + 1].get("name", "")
                if nxt and nxt in self.index:
                    names.append(nxt)
            break
        return names[:PREWARM_MAX_TARGET_SCENES]

    def _queue_prewarm_item(self, path: str, width: int, height: int,
                            palette, alpha_colkey: bool) -> None:
        if not path or not self._cache or palette is None:
            return
        w = max(0, int(width or 0))
        h = max(0, int(height or 0))
        try:
            pal_key = bytes(palette.tobytes())
        except Exception:
            pal_key = repr(palette).encode("utf-8", "ignore")
        key = (path, w, h, pal_key, bool(alpha_colkey))
        if key in self._prewarm_seen:
            return
        self._prewarm_seen.add(key)
        self._prewarm_queue.append({
            "path": path,
            "w": w,
            "h": h,
            "palette": palette,
            "alpha_colkey": bool(alpha_colkey),
        })

    def _queue_bg_prewarm(self, bg: dict | None, hide_dialog: bool,
                          palette) -> None:
        if not self._cache or not bg:
            return
        bg_path = bg.get("path", "")
        if not bg_path:
            return
        iw, ih = self._cache.source_size(bg_path)
        if iw <= 0 or ih <= 0:
            return
        W, H = pyxel.width, pyxel.height
        above_dialog = bool(bg.get("above_dialog")) and not hide_dialog
        H_eff = DIALOG_Y if above_dialog else H
        fit_scale = min(W / iw, H_eff / ih)
        if bg.get("fullscreen") or above_dialog:
            scale = fit_scale
        else:
            scale = min(1.0, fit_scale)
        sw = max(1, round(iw * scale))
        sh = max(1, round(ih * scale))
        self._queue_prewarm_item(bg_path, sw, sh, palette, False)
        for fb in (bg.get("anim", {}) or {}).get("flipbook_files", []) or []:
            self._queue_prewarm_item(fb, sw, sh, palette, False)

    def _queue_char_prewarm(self, chars: dict | None, palette) -> None:
        if not self._cache:
            return
        for cfg in (chars or {}).values():
            if not cfg or not cfg.get("file"):
                continue
            path = cfg.get("file", "")
            load_w, load_h, _scale = sprite_load_size_for_screen(
                self._cache, path, int(cfg.get("w") or 0),
                int(cfg.get("h") or 0))
            alpha = (
                normalize_color_key(cfg.get("colkey", COLOR_KEY_AUTO))
                == COLOR_KEY_AUTO
            )
            self._queue_prewarm_item(path, load_w, load_h, palette, alpha)
            for fb in (cfg.get("anim", {}) or {}).get("flipbook_files", []) or []:
                self._queue_prewarm_item(fb, load_w, load_h, palette, alpha)

    def _schedule_prewarm_for_scene_names(self, names: list[str],
                                          delay_frames: int = PREWARM_DELAY_FRAMES,
                                          clear: bool = False) -> None:
        if not self._cache:
            return
        if clear:
            self._prewarm_queue.clear()
            self._prewarm_seen.clear()
            self._prewarm_input_grace = 0
        queued_before = len(self._prewarm_queue)
        for name in names[:PREWARM_MAX_TARGET_SCENES]:
            scene = self.index.get(name)
            if not isinstance(scene, dict):
                continue
            sim = self._simulate_persistent_after_scene(scene)
            bg = sim.get("bg")
            chars = sim.get("chars") or {}
            paths = self._collect_image_paths_from_state(bg, chars)
            if not paths:
                continue
            pal = self._palette_for_paths(paths)
            if pal is None:
                continue
            self._queue_bg_prewarm(bg, bool(scene.get("hide_dialog", False)), pal)
            self._queue_char_prewarm(chars, pal)
        if len(self._prewarm_queue) > queued_before:
            self._prewarm_delay = max(0, int(delay_frames))

    def _confirm_input_held(self) -> bool:
        return (
            pyxel.btn(pyxel.KEY_SPACE)
            or pyxel.btn(pyxel.KEY_RETURN)
            or pyxel.btn(pyxel.MOUSE_BUTTON_LEFT)
            or self._controller.held("confirm")
        )

    def _schedule_successor_prewarm(self, scene: dict,
                                    delay_frames: int = PREWARM_DELAY_FRAMES
                                    ) -> None:
        self._schedule_prewarm_for_scene_names(
            self._scene_successors(scene), delay_frames=delay_frames)

    def _run_prewarm_step(self) -> None:
        if not self._cache or not self._prewarm_queue:
            return
        # 先読みは同期的に実画像キャッシュをメモリへ載せる。Web/Androidでも
        # JS側の非同期プリフェッチは使わず、以前と同じ deterministic な経路に
        # 戻している。タイピング中だけは文字送りの滑らかさを優先して避ける。
        if self._waiting and self.shown_chars < len(self.full_text):
            return
        if self._confirm_input_held():
            self._prewarm_input_grace = max(
                self._prewarm_input_grace, PREWARM_INPUT_GRACE_FRAMES)
            return
        if self._prewarm_input_grace > 0:
            self._prewarm_input_grace -= 1
            return
        if self._prewarm_delay > 0:
            self._prewarm_delay -= 1
            return
        item = self._prewarm_queue.pop(0)
        try:
            self._cache.get(
                item["path"], item["w"], item["h"],
                palette=item["palette"],
                alpha_colkey=bool(item.get("alpha_colkey", False)),
            )
        except Exception as e:
            print(f"[PVNM] image prewarm failed: {item.get('path')}: {e}")

    def _go_back_scene(self) -> None:
        """履歴スタックを 1 段戻して前のシーンへ遷移する。

        履歴が空なら何もしない。シーン遷移時の状態 (待機中テキスト・選択肢・
        フェード中フラグ) はリセットし、新しいシーンの先頭ステップから再生する。
        永続画像状態 (BG / キャラ) はスナップショットから復元する。
        """
        if not self._scene_history:
            return
        prev_name, prev_snap = self._scene_history.pop()
        if prev_name not in self.index:
            return
        # 進行中のテキスト/選択肢/フェードを破棄
        self.choices = []
        self.choice_hover = -1
        self._waiting = False
        self.full_text = ""
        self.shown_chars = 0
        self._dialog_suppressed = False
        self._trans_state = None
        self._trans_frame = 0
        self._trans_out_frames = FADE_FRAMES
        self._trans_in_frames = FADE_FRAMES
        # スキップ/オートも前シーンでは中断
        self._skip_on = False
        self._skip_hold_on = False
        self._auto_on = False
        self._auto_resume_after_scene = False
        # 永続状態を戻り先のものに復元してから再入場する。
        # resolve_state=False で再解決をスキップ — スナップショットが既に
        # 「prev_name 解決後の状態」を表しているため。
        self._restore_persistent(prev_snap)
        self._enter_scene(prev_name, push_history=False, resolve_state=False)
        # 新シーンの最初のステップを実行 (通常は say で _waiting=True に入る)
        self._advance()

    def _restore_master_palette(self) -> None:
        """pyxel.colors[] と ImageCache 既定パレットを MasterColor に戻す。"""
        try:
            _palette_mod.load()
            _set_image_cache_palette(_palette_mod.snapshot_pyxel_colors())
        except Exception:
            pass

    def _scene_bgm_fadeout_frames(self) -> int:
        scene = self.index.get(self.scene_name, {})
        try:
            return max(0, int(scene.get("bgm_fadeout_frames", 0) or 0))
        except Exception:
            return 0

    def _begin_scene_bgm_fadeout(self, frames: int) -> None:
        if frames <= 0:
            return
        _audio.fadeout_bgm(frames)
        # Prevent an inherited BGM from being restarted when the target scene
        # does not explicitly set a new BGM.
        self._persistent_bgm = None

    def _apply_scene_palette(self) -> None:
        """継承解決後の persistent 画像群から 256色パレットを構築して適用。

        UI 役割色 (0-15) と settings.json の dialog_role_indices / speaker_colors
        で参照されている全 index は MasterColor の値で固定し、残りスロットを
        画像から抽出した最頻色で埋める。これにより画像ごとの色破綻を抑えつつ
        UI/スピーカー色の見た目を保つ。

        この関数は `_resolve_persistent_state` の後に呼ぶこと。
        """
        if not self._cache:
            return
        paths = self._collect_scene_image_paths()
        reserved = _palette_mod.reserved_from_settings(self._settings)
        if not reserved:
            return  # マスターパレット未ロード — 何もしない
        pal = None
        if hasattr(self._cache, "get_prebuilt_palette"):
            pal = self._cache.get_prebuilt_palette(paths, reserved)
        if pal is None:
            pal = _palette_mod.build_scene_palette(
                paths, reserved, base_dir=self._cache.base_dir)
        _palette_mod.apply_to_pyxel_colors(pal)
        _set_image_cache_palette(pal)

    # ── 永続画像状態の解決 / スナップショット ─────────────────────

    def _resolve_persistent_state(self, scene: dict) -> None:
        """シーンの BG / 各キャラスロット設定から、`_persistent_*` を更新する。

        各フィールドの 3 状態:
          - hide=True              → 明示クリア (persistent = None)
          - file/path に値あり     → SET (persistent を上書き)
          - 上記以外 (空 / 欠落)   → INHERIT (persistent を変更しない)
        """
        # キャラの画像/座標などは状態として継承するが、shake/motion などの
        # animation は演出なので通常は 1 シーン限り。必要な場合だけ keep_anim
        # で明示継承し、hold_motion_end は次シーンへ入る前に移動後座標を焼く。
        for cfg in self._persistent_chars.values():
            prepare_char_config_for_next_scene(cfg)

        # BG
        if scene.get("bg_hide"):
            self._persistent_bg = None
        else:
            bg_path = scene.get("bg", "") or ""
            if bg_path:
                self._persistent_bg = {
                    "path":         bg_path,
                    "fullscreen":   bool(scene.get("bg_fullscreen", False)),
                    "above_dialog": bool(scene.get("bg_above_dialog", False)),
                    "anim":         scene.get("bg_anim", {}) or {},
                }
            # else: INHERIT (既存値を保持)

        # キャラ各スロット
        for slot_key in ("char_l", "char_c", "char_r"):
            cfg = scene.get(slot_key, {})
            if not isinstance(cfg, dict):
                cfg = {}
            if cfg.get("hide"):
                self._persistent_chars[slot_key] = None
                continue
            f = cfg.get("file", "") or ""
            if f:
                # SET: 設定全体 (座標・スケール・anim 等含む) を引き継ぎ。
                # AnimSprite はフレーム状態を持つため毎回新規生成する想定で
                # ここでは設定 dict のディープコピーを保持するだけ。
                self._persistent_chars[slot_key] = copy.deepcopy(cfg)
            # else: INHERIT (既存値を保持)

        if scene.get("bgm_stop"):
            self._persistent_bgm = None
        else:
            bgm_path = scene.get("bgm_file", "") or ""
            if bgm_path:
                if bool(scene.get("bgm_loop", True)):
                    self._persistent_bgm = {
                        "path": bgm_path,
                        "volume": scene.get("bgm_volume", 7),
                        "loop": True,
                    }
                else:
                    # One-shot BGM replaces inherited BGM but is not itself
                    # inherited, so it will not restart in later scenes.
                    self._persistent_bgm = None

    def _initialize_persistent_for_start(self, start_name: str) -> None:
        """開始シーンより前のシーンを仮想走査して永続状態を構築する。

        エディタからシーン途中 (例: シーン2) を選んで再生した場合、
        単純に `_persistent_bg = None` のまま `_enter_scene("シーン2")` を呼ぶと、
        シーン2 が INHERIT (bg="") なら BG が空のままになる。
        本メソッドは scene_order の先頭から start_name の直前までを順次
        `_resolve_persistent_state` し、BG/キャラの引き継ぎ状態を再現する。

        制限: エディタ平坦リスト順を「過去の再生履歴」とみなして適用するので、
        実際の play 経路 (goto / choice 分岐) と一致しない場合がある。
        ただし VN のように線形なシナリオが大半なら実用上問題ない。
        """
        self._persistent_bg = None
        self._persistent_chars = {}
        self._persistent_bgm = None
        if not start_name:
            return
        for sc in self._scene_order:
            if not isinstance(sc, dict):
                continue
            if sc.get("name") == start_name:
                break
            self._resolve_persistent_state(sc)

    def _snapshot_persistent(self) -> dict:
        """履歴スタック用に現在の永続状態を独立コピーで返す。"""
        return {
            "bg": (None if self._persistent_bg is None
                   else copy.deepcopy(self._persistent_bg)),
            "chars": {k: (None if v is None else copy.deepcopy(v))
                      for k, v in self._persistent_chars.items()},
            "bgm": (None if self._persistent_bgm is None
                    else copy.deepcopy(self._persistent_bgm)),
        }

    def _restore_persistent(self, snap: dict) -> None:
        """履歴スタックから取り出したスナップショットで永続状態を上書きする。"""
        self._persistent_bg = snap.get("bg") if snap else None
        self._persistent_chars = dict((snap or {}).get("chars") or {})
        self._persistent_bgm = (
            None if not snap else copy.deepcopy(snap.get("bgm")))

    def _sync_persistent_bgm(self, scene: dict) -> None:
        """現在の永続BGM状態を実際のオーディオ再生へ反映する。"""
        if scene.get("bgm_stop"):
            _audio.stop_bgm()
            return
        scene_bgm_path = scene.get("bgm_file", "") or ""
        if scene_bgm_path and not bool(scene.get("bgm_loop", True)):
            abs_bgm = self._resolve_path(scene_bgm_path)
            _audio.play_bgm(abs_bgm, scene.get("bgm_volume", 7), loop=False)
            return
        if not self._persistent_bgm:
            return
        bgm_path = self._persistent_bgm.get("path", "")
        if not bgm_path:
            return
        abs_bgm = self._resolve_path(bgm_path)
        _audio.play_bgm(abs_bgm, self._persistent_bgm.get("volume", 7),
                        loop=bool(self._persistent_bgm.get("loop", True)))

    # ── スプライト構築 (継承解決後の状態から) ─────────────────────

    def _build_bg_sprite(self) -> None:
        """`_persistent_bg` から背景 AnimSprite を構築する (None ならクリア)。

        スケーリングモード:
          - 通常 (fullscreen=False, above_dialog=False):
              画像そのままの解像度でセンタリング、画面より大きければ縮小
          - フルスクリーン (fullscreen=True):
              アスペクト比を維持して画面 (720x480) いっぱいまで拡縮
          - ダイアログ上配置 (above_dialog=True):
              ダイアログで覆われない領域 (720 x DIALOG_Y) に収まるよう拡縮し、
              上端揃えで配置。横に黒帯が出ても画像内のキャラは隠れない。
              hide_dialog=True のシーンではダイアログが描画されないので
              この設定は無視されフルスクリーン相当に振る舞う。
        """
        self._bg_sprite = None
        if not self._cache or not self._persistent_bg:
            return
        bg_path = self._persistent_bg.get("path", "")
        if not bg_path:
            return
        iw, ih = self._cache.source_size(bg_path)
        if iw <= 0 or ih <= 0:
            return
        W, H = pyxel.width, pyxel.height
        # ダイアログ表示中なら BG が使える縦領域は y=0..DIALOG_Y。
        # hide_dialog=True のときは BG 配置に上限なし (= H 全部使える)。
        above_dialog = (bool(self._persistent_bg.get("above_dialog"))
                        and not self._hide_dialog)
        H_eff = DIALOG_Y if above_dialog else H

        fit_scale = min(W / iw, H_eff / ih)
        if self._persistent_bg.get("fullscreen") or above_dialog:
            scale = fit_scale
        else:
            scale = min(1.0, fit_scale)
        sw = max(1, round(iw * scale))
        sh = max(1, round(ih * scale))
        tl_x = (W - sw) // 2
        # above_dialog: 安全領域 (0..H_eff) 内で上下中央揃え。
        # それ以外: 画面 (0..H) 全体で上下中央揃え (従来挙動)。
        tl_y = (H_eff - sh) // 2 if above_dialog else (H - sh) // 2
        ay = H - tl_y - sh  # AnimSprite の y は画面下端基準
        bg_cfg = {
            "file":   bg_path,
            "x":      tl_x,
            "y":      ay,
            "w":      sw,
            "h":      sh,
            "colkey": -1,
            "anim":   self._persistent_bg.get("anim", {}) or {},
        }
        self._bg_sprite = self._make_sprite(bg_cfg, sw, sh)

    def _build_char_sprites(self) -> None:
        """`_persistent_chars` から各スロットの AnimSprite を構築する。"""
        self._char_sprites = {}
        for slot_short, slot_key in (
                ("left", "char_l"), ("center", "char_c"), ("right", "char_r")):
            cfg = self._persistent_chars.get(slot_key)
            if not cfg:
                continue
            if not cfg.get("file"):
                continue
            sp = self._make_sprite(cfg)
            if sp:
                self._char_sprites[slot_short] = sp

    def _enter_scene(self, name: str, push_history: bool = True,
                     resolve_state: bool = True,
                     play_scene_se: bool = True):
        """シーン入場処理。

        Parameters
        ----------
        push_history : True なら直前のシーン (+ 永続状態スナップショット) を
                       履歴スタックに積む。←キー戻る・セーブロードでは False。
        resolve_state : False なら BG / キャラの永続状態を再解決しない (履歴
                        から復元したスナップショットをそのまま使うケース用)。
        """
        # シーンを切り替える前に、現在のシーン名 + 永続状態を履歴へ積む。
        # 同じシーンへの再入場や、明示的に push_history=False が指定された
        # ケース (戻る操作自身、セーブロード) では積まない。
        if (push_history and self.scene_name
                and self.scene_name != name
                and name in self.index):
            self._scene_history.append(
                (self.scene_name, self._snapshot_persistent()))
        self.scene_name = name
        self.step_i     = 0
        self._update_log_scope(name)
        scene = self.index.get(name, {})
        self._prewarm_queue.clear()
        self._prewarm_seen.clear()
        self._prewarm_delay = 0
        self._hide_dialog = bool(scene.get("hide_dialog", False))
        self._dialog_suppressed = False

        # 画像の永続状態を解決 (継承 / 明示クリア / 上書きの 3 状態)。
        # ←キー戻る経路ではスナップショットを既に復元済みなので skip。
        if resolve_state:
            self._resolve_persistent_state(scene)

        # シーンに登場する画像群から最適パレットを構築して適用する。
        # ここから下の self._cache.get(...) は全てこのパレットで量子化される。
        self._apply_scene_palette()

        # 背景・キャラのスプライトを永続状態から再構築
        self._build_bg_sprite()
        self._build_char_sprites()
        self._schedule_successor_prewarm(scene)

        # シーン別フォント。BDF統一後は font_file を無視し、size だけ使う。
        scene_font_file = scene.get("font_file", "")
        scene_font_size = int(scene.get("font_size", 0))
        if scene_font_file and scene_font_file not in _warned_scene_fonts:
            print(f"[PVNM] Scene font_file ignored (BDF runtime): {scene_font_file}")
            _warned_scene_fonts.add(scene_font_file)
        self._scene_base_font_size = scene_font_size if scene_font_size > 0 else _font_size
        self._scene_font_size = self._effective_text_size(self._scene_base_font_size)

        self._apply_scene_auto_pause(scene)

        # オーディオ: BGM は背景と同様に継承、SE はこのシーンだけで再生する。
        self._sync_persistent_bgm(scene)
        se = scene.get("se_file", "")
        if play_scene_se and se:
            abs_se = self._resolve_path(se)
            _audio.play_se(abs_se, scene.get("se_volume", 7),
                           scene.get("se_repeat", 0))

    def _load_scene_font(self, font_file: str) -> "pyxel.Font | None":
        """シーン別フォントを取得する。"""
        return None

    def _draw_text_s(self, x: int, y: int, text: str, size: int, col: int):
        """BDFでテキスト描画。size は最も近い b{N}.bdf にスナップされる。"""
        draw_unicode(x, y, text, col, size=size)

    def _draw_body_text_s(self, x: int, y: int, text: str, size: int, col: int):
        """ダイアログ本文用: サイズ別の文字間隔を加えて描画する。"""
        draw_unicode(
            x, y, text, col, size=size,
            letter_spacing=dialog_letter_spacing(size),
        )

    def _resolve_path(self, path: str) -> str:
        """相対パスをキャッシュのベースディレクトリから解決"""
        if self._cache and hasattr(self._cache, 'base_dir'):
            return _runtime_assets.resolve_asset_path(path, self._cache.base_dir)
        if os.path.isabs(path):
            return path
        return path

    def set_save_path(self, path: str):
        """セーブファイルのパスを設定する"""
        self._save_path = path

    def get_save_state(self) -> dict:
        """現在の再生状態を辞書で返す"""
        # シーン名からPart/Chapter/表示名を分解
        name = self.scene_name or ""
        parts = name.split("_", 2)
        if len(parts) >= 3:
            part_name = f"Part {int(parts[0]):d}" if parts[0].isdigit() else parts[0]
            chap_name = f"Chapter {int(parts[1]):d}" if parts[1].isdigit() else parts[1]
            scene_disp = parts[2]
        else:
            part_name = ""
            chap_name = ""
            scene_disp = name

        text_preview = self.full_text[:40] if self.full_text else ""

        return {
            "version":       2,
            "scene_name":    self.scene_name,
            "step_i":        self.step_i,
            "part_name":     part_name,
            "chapter_name":  chap_name,
            "scene_display": scene_disp,
            "speaker":       self.speaker,
            "full_text":     self.full_text,
            "text_preview":  text_preview,
            "shown_chars":   self.shown_chars,
            "waiting":       bool(self._waiting),
            "choices":       copy.deepcopy(self.choices),
            "choice_hover":  self.choice_hover,
        }

    def load_save_state(self, data: dict):
        """セーブデータから状態を復元する"""
        scene_name = data.get("scene_name", "")
        step_i     = data.get("step_i", 0)
        if scene_name not in self.index:
            return False
        self._reset_playback_assist_state(
            suppress_input=True, clear_prewarm=True)
        self._trans_state = None
        self._trans_frame = 0
        self.choices = []
        self.choice_hover = -1
        self.speaker = ""
        self.full_text = ""
        self.shown_chars = 0
        self._waiting = False
        self._dialog_suppressed = False
        self.log.clear()
        self._log_chapter_key = None
        # ロード時はシーン履歴をリセットし、永続画像状態は開始シーン以前を
        # 仮想走査して再構築する。これでセーブ地点が INHERIT のシーンでも
        # 直前の SET 設定が引き継がれた状態で復元される。
        self._scene_history.clear()
        self._initialize_persistent_for_start(scene_name)
        # セーブ地点復元でも、保存対象シーン自身に設定されたSEは1回再生する。
        # start_scene は defer_start=True で抑止されているため、ここで鳴るのは
        # load対象シーンのSEだけで、以前のシーンのSEは再生されない。
        self._enter_scene(scene_name, push_history=False, play_scene_se=True)
        # step_i まで実行（say は最後のみ表示）
        scene = self.index.get(scene_name, {})
        steps = scene.get("steps", [])
        try:
            step_i = max(0, min(int(step_i), len(steps)))
        except Exception:
            step_i = 0
        last_say = None
        for i in range(min(step_i, len(steps))):
            st = steps[i]
            if st["op"] == "say":
                last_say = st
            self.step_i = i + 1

        saved_text = data.get("full_text")
        if isinstance(saved_text, str):
            self.speaker = str(data.get("speaker", "") or "")
            self.full_text = saved_text.replace("\\n", "\n")
            try:
                shown = int(data.get("shown_chars", len(self.full_text)))
            except Exception:
                shown = len(self.full_text)
            self.shown_chars = max(0, min(shown, len(self.full_text)))

        saved_choices = data.get("choices")
        if isinstance(saved_choices, list) and saved_choices:
            self.choices = copy.deepcopy(saved_choices)
            try:
                hover = int(data.get("choice_hover", 0))
            except Exception:
                hover = 0
            self.choice_hover = max(0, min(hover, len(self.choices) - 1))
            self.shown_chars = len(self.full_text)
            self._waiting = False
            return True

        # 最後の say を表示状態にする。v2セーブなら保存時の本文を優先し、
        # 古いセーブでは step_i 以前の最後の say を復元する。
        if self.full_text or self.speaker:
            self.shown_chars = len(self.full_text)
            self._waiting = True
            return True
        if last_say:
            self.speaker     = last_say.get("speaker", "")
            self.full_text   = last_say.get("text", "").replace("\\n", "\n")
            self.shown_chars = len(self.full_text)
            self._waiting    = True
            return True
        return True

    def _make_sprite(self, cfg: dict,
                     default_w: int = 0,
                     default_h: int = 0) -> AnimSprite | None:
        if not self._cache:
            return None
        file_path = cfg.get("file", "")
        if not file_path:
            return None
        # 0 は「デフォルト値を使う」の意味（BG なら画面サイズ、キャラなら元サイズ）
        w = int(cfg.get("w") or default_w)
        h = int(cfg.get("h") or default_h)
        sp = AnimSprite(cfg, self._cache, w, h)
        return sp if sp.loaded else None

    def _advance(self):
        scene = self.index.get(self.scene_name)
        if scene is None:
            self.finished = True
            return

        steps = scene.get("steps", [])
        while self.step_i < len(steps):
            step = steps[self.step_i]
            self.step_i += 1
            if self._exec(step):
                return

        # ステップ終了後: goto_ending があればエンディングへ
        goto_ending = scene.get("goto_ending", "")
        if goto_ending and goto_ending in self._endings:
            # シーン用パレットから一旦 MasterColor へ戻し、EndingPlayer 内部で
            # スライドごとに最適パレットを再生成する。
            self._restore_master_palette()
            self._ending_player_name = goto_ending
            self._ending_player = EndingPlayer(
                self._endings[goto_ending], cache=self._cache,
                settings=self._settings)
            return

        self.finished = True

    def _exec(self, step: dict) -> bool:
        op = step["op"]

        if op == "say":
            self.speaker     = step.get("speaker", "")
            self.full_text   = step.get("text", "").replace("\\n", "\n")
            self.shown_chars = 0
            self.typing_timer = 0
            self._waiting    = True
            self._dialog_suppressed = False
            if self.speaker or self.full_text:
                self._append_log(self.speaker, self.full_text)
            return True

        if op == "choice":
            self.choices      = step.get("options", [])
            self.choice_hover = 0 if self.choices else -1
            self._dialog_suppressed = False
            targets = [
                opt.get("goto", "")
                for opt in self.choices
                if isinstance(opt, dict) and opt.get("goto", "") in self.index
            ]
            self._schedule_prewarm_for_scene_names(targets, delay_frames=0)
            return True

        if op == "goto":
            target = step.get("scene", "")
            trans  = step.get("transition", "")
            fadeout_frames = self._scene_bgm_fadeout_frames()
            if trans == "fade" and target in self.index:
                self._schedule_prewarm_for_scene_names(
                    [target], delay_frames=0, clear=True)
                if fadeout_frames > 0:
                    self._begin_scene_bgm_fadeout(fadeout_frames)
                self._trans_state  = "fade_out"
                self._trans_frame  = 0
                self._trans_target = target
                self._trans_out_frames = (
                    fadeout_frames if fadeout_frames > 0 else FADE_FRAMES)
                self._trans_in_frames = FADE_FRAMES
            elif target in self.index:
                if fadeout_frames > 0:
                    self._begin_scene_bgm_fadeout(fadeout_frames)
                self._enter_scene(target)
                self._advance()
            else:
                self.finished = True
            return True

        if op == "end":
            self.finished = True
            return True

        return False

    def _update_typing(self):
        if self.shown_chars < len(self.full_text):
            self.typing_timer += 1
            if self.typing_timer >= TYPING_SPEED:
                self.typing_timer = 0
                self.shown_chars += 1

    def _choice_hit_index(self, mx: int, my: int) -> int:
        W = pyxel.width
        cx, cy_start, choice_w, ch = self._choice_layout(W)

        for i, _opt in enumerate(self.choices):
            cy = cy_start + i * (ch + CHOICE_GAP)
            if (cx <= mx < cx + choice_w and cy <= my < cy + ch):
                return i
        return -1

    def _update_choices(self, mx, my, mouse_clicked, advance_key):
        if pyxel.btnp(pyxel.KEY_UP, hold=15, repeat=5) or self._controller.nav_up():
            if self.choice_hover < 0:
                self.choice_hover = 0
            else:
                self.choice_hover = (self.choice_hover - 1) % len(self.choices)
        if pyxel.btnp(pyxel.KEY_DOWN, hold=15, repeat=5) or self._controller.nav_down():
            if self.choice_hover < 0:
                self.choice_hover = 0
            else:
                self.choice_hover = (self.choice_hover + 1) % len(self.choices)

        mouse_hover = self._choice_hit_index(mx, my)
        if mouse_hover >= 0:
            self.choice_hover = mouse_hover

        confirm = advance_key or (mouse_clicked and mouse_hover >= 0)
        if confirm and 0 <= self.choice_hover < len(self.choices):
            opt = self.choices[self.choice_hover]
            goto = opt.get("goto", "")
            self.choices   = []
            self.full_text = ""
            self.speaker   = ""
            if goto in self.index:
                self._enter_scene(goto)
            else:
                self.finished = True

    def _choice_layout(self, screen_w: int) -> tuple[int, int, int, int]:
        fsz = self._scene_font_size
        ch = _choice_h(fsz)
        choice_w = _choice_w(self.choices, fsz, screen_w)
        total_h = len(self.choices) * (ch + CHOICE_GAP) - CHOICE_GAP
        cx = (screen_w - choice_w) // 2
        cy_center = DIALOG_Y + (DIALOG_H - total_h) // 2
        if self.full_text or self.speaker:
            cy_bottom = DIALOG_Y + DIALOG_H - total_h - 10
            cy_start = max(cy_center, cy_bottom)
        else:
            cy_start = cy_center
        return cx, cy_start, choice_w, ch

    # ── 描画 ────────────────────────────────────────────────────

    @staticmethod
    def _coerce_color(v, default: int) -> int:
        """None や不正値はデフォルトに置き換える。"""
        if isinstance(v, int) and 0 <= v <= 255:
            return v
        return default

    def _resolve_text_color(self) -> int:
        """セリフ本文の色を解決する。

        スピーカー名が空 → 地の文 (`narration_text_color` 設定)
        登録済みスピーカー → そのスピーカーのテキスト色
        未登録 → デフォルトの `PLAY_TEXT`
        """
        cfg = getattr(self, "_speaker_config", None) or {}
        if not self.speaker:
            return self._coerce_color(
                cfg.get("narration_text_color"), PLAY_TEXT)
        speakers = cfg.get("speakers", {}) or {}
        entry = speakers.get(self.speaker) or {}
        return self._coerce_color(entry.get("text_color"), PLAY_TEXT)

    def _resolve_speaker_colors(self) -> tuple:
        """話者バッジの (背景, 文字) 色を返す。"""
        cfg = getattr(self, "_speaker_config", None) or {}
        speakers = cfg.get("speakers", {}) or {}
        entry = speakers.get(self.speaker) or {}
        bg = self._coerce_color(entry.get("name_bg_color"), PLAY_SPEAKER_BG)
        fg = self._coerce_color(entry.get("name_color"), PLAY_SPEAKER_FG)
        return bg, fg

    def set_speaker_config(self, cfg: dict) -> None:
        """スピーカー色設定を注入する。形式は
        {"narration_text_color": int,
         "speakers": {name: {"name_color": int, "name_bg_color": int,
                              "text_color": int}}}
        """
        self._speaker_config = cfg or {}
        # シーンパレットの予約 index 集合は speaker_colors を含むので、
        # 編集後の設定を _settings 側にも反映しておく (次のシーン遷移で参照される)。
        if isinstance(self._settings, dict):
            self._settings["speaker_colors"] = self._speaker_config

    def _draw_dialog(self, W, H):
        bx, by = DIALOG_X, DIALOG_Y
        bw, bh = DIALOG_W, DIALOG_H
        fsz = self._scene_font_size
        rh  = _font_render_h(fsz)
        lh  = rh + 4

        # ダイアログボックス
        pyxel.rect(bx, by, bw, bh, PLAY_DIALOG_BG)
        pyxel.rectb(bx, by, bw, bh, PLAY_ACCENT)
        pyxel.rectb(bx + 2, by + 2, bw - 4, bh - 4, PLAY_BORDER)

        # 話者バッジ
        if self.speaker:
            badge_x = bx + 12
            badge_y = by - _speaker_h(fsz) + 2
            _tw = text_px_w(self.speaker, fsz)
            badge_w = _tw + 20
            badge_h = _speaker_h(fsz)
            spk_bg, spk_fg = self._resolve_speaker_colors()
            pyxel.rect(badge_x, badge_y, badge_w, badge_h, spk_bg)
            pyxel.rectb(badge_x, badge_y, badge_w, badge_h, PLAY_BORDER)
            self._draw_text_s(badge_x + 10, badge_y + (badge_h - rh) // 2,
                              self.speaker, fsz, spk_fg)

        # テキスト（タイピング、\n 改行対応）
        visible = self.full_text[:self.shown_chars]
        max_w   = max(1, bw - DIALOG_PAD_X * 2)
        tx      = bx + DIALOG_PAD_X
        ty      = by + DIALOG_PAD_Y
        max_y   = by + bh - rh - 4
        text_col = self._resolve_text_color()
        text_spacing = dialog_letter_spacing(fsz)
        for line in wrap_text(visible, max_w, fsz, text_spacing):
            if ty > max_y:
                break
            if line:
                self._draw_body_text_s(tx, ty, line, fsz, text_col)
            ty += lh
            if ty > max_y:
                break

    def _draw_choices(self, W, H):
        fsz      = self._scene_font_size
        rh       = _font_render_h(fsz)
        cx, cy_start, choice_w, ch = self._choice_layout(W)

        for i, opt in enumerate(self.choices):
            cy    = cy_start + i * (ch + CHOICE_GAP)
            hover = (self.choice_hover == i)
            bg    = PLAY_CHOICE_HOVER if hover else PLAY_CHOICE_BG
            fg    = PLAY_BG if hover else PLAY_TEXT
            pyxel.rect(cx, cy, choice_w, ch, bg)
            pyxel.rectb(cx, cy, choice_w, ch, PLAY_ACCENT)
            label = opt.get("label", "")
            lw    = text_px_w(label, fsz)
            self._draw_text_s(cx + (choice_w - lw) // 2,
                              cy + (ch - rh) // 2,
                              label, fsz, fg)
