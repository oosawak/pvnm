"""
AnimSprite: 1枚の画像（またはパラパラ漫画フレーム列）を
アニメーション付きで描画するクラス。

対応アニメーション:
  - 位置 (x, y)
  - 左右/上下反転
  - 枠線 (太さ・色)
  - 拡大縮小 (開始→終了スケール、フレーム数)
  - 回転 (速度 度/frame、正=時計回り)
  - 移動 (dx, dy オフセットへ、フレーム数)
  - 震え (振幅、更新間隔フレーム)
  - パラパラ漫画 (複数 pyxel.Image、切替フレーム間隔)
"""
import math
import random
import pyxel
from engine.image_cache import (
    COLOR_KEY_AUTO,
    ImageCache,
    normalize_color_key,
)


def _fit_within(w: int, h: int, max_w: int, max_h: int) -> tuple[int, int, float]:
    """Return cache size within max bounds and visual correction scale."""
    if w <= 0 or h <= 0:
        return max(1, w), max(1, h), 1.0
    fit = min(1.0, max_w / w, max_h / h)
    cw = max(1, round(w * fit))
    ch = max(1, round(h * fit))
    correction = w / cw if cw > 0 else 1.0
    return cw, ch, correction


def sprite_load_size_for_screen(cache: ImageCache, file_path: str,
                                img_w: int = 0, img_h: int = 0,
                                screen_w: int | None = None,
                                screen_h: int | None = None
                                ) -> tuple[int, int, float]:
    """Return the image size/source scale used by AnimSprite.

    Character sprites with no explicit w/h are loaded within the Pyxel screen
    and drawn back with a correction scale. Snapshot previews must use the
    same load size or bottom-axis placement drifts from runtime playback.
    """
    load_w, load_h = int(img_w), int(img_h)
    source_scale = 1.0
    if load_w <= 0 and load_h <= 0:
        src_w, src_h = cache.source_size(file_path)
        if src_w > 0 and src_h > 0:
            max_w = pyxel.width if screen_w is None else int(screen_w)
            max_h = pyxel.height if screen_h is None else int(screen_h)
            load_w, load_h, source_scale = _fit_within(
                src_w, src_h, max_w, max_h)
    return load_w, load_h, source_scale


def sprite_top_left(x: float, y: float, img_h: int, draw_scale: float,
                    screen_h: int | None = None,
                    shake_x: int = 0, shake_y: int = 0) -> tuple[int, int]:
    """Convert PVNM bottom-axis coordinates to Pyxel top-left coordinates."""
    h = pyxel.height if screen_h is None else int(screen_h)
    tl_x = round(int(x) + int(shake_x))
    tl_y = round(h - int(y) - draw_scale * img_h) + int(shake_y)
    return tl_x, tl_y


def _to_int(value, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def prepare_char_config_for_next_scene(cfg: dict) -> None:
    """Apply PVNM's scene-bound animation rule to a persistent char config.

    Static character state is inherited across scenes, but animation is treated
    as a one-scene effect unless the author explicitly enables keep_anim. When
    hold_motion_end is enabled, motion_x/y are baked into the inherited axis
    position before the animation is cleared.
    """
    if not isinstance(cfg, dict):
        return
    if bool(cfg.get("keep_anim", False)):
        return

    anim = cfg.get("anim")
    if not isinstance(anim, dict) or not anim:
        cfg["keep_anim"] = False
        cfg["hold_motion_end"] = False
        return

    if bool(cfg.get("hold_motion_end", False)):
        frames = _to_int(anim.get("motion_frames", 0))
        if frames > 0:
            cfg["x"] = _to_int(cfg.get("x", 0)) + _to_int(anim.get("motion_x", 0))
            cfg["y"] = _to_int(cfg.get("y", 0)) + _to_int(anim.get("motion_y", 0))

    cfg["anim"] = {}
    cfg["keep_anim"] = False
    cfg["hold_motion_end"] = False


def _default_anim() -> dict:
    return {
        "shake_amp":      0,    # 震え振幅 (px)
        "shake_speed":    4,    # 震え更新間隔 (frames)
        "rot_speed":      0.0,  # 回転速度 (度/frame, 正=時計回り)
        "scale_start":    1.0,  # スケール開始値
        "scale_end":      1.0,  # スケール終了値
        "scale_frames":   0,    # スケールアニメ フレーム数 (0=即時)
        "motion_x":       0,    # 移動先 X オフセット
        "motion_y":       0,    # 移動先 Y オフセット
        "motion_frames":  0,    # 移動フレーム数 (0=即時)
        "flipbook_files": [],   # 追加フレームのファイルパスリスト
        "flipbook_interval": 6, # パラパラ切替間隔 (frames)
    }


class AnimSprite:
    """
    Parameters
    ----------
    config   : シーンの bg/char 設定 dict
    cache    : ImageCache インスタンス
    img_w, img_h : ロード時のサイズ（0=元サイズ）
    """

    def __init__(self, config: dict, cache: ImageCache,
                 img_w: int = 0, img_h: int = 0):
        # ── 表示設定 ─────────────────────────────────────────
        self._file   = config.get("file", "")
        self._x0     = float(config.get("x", 0))
        self._y0     = float(config.get("y", 0))
        self.x       = self._x0
        self.y       = self._y0
        self.flip_h  = bool(config.get("flip_h", False))
        self.flip_v  = bool(config.get("flip_v", False))
        self.colkey  = normalize_color_key(config.get("colkey", COLOR_KEY_AUTO))
        self._auto_colkey = self.colkey == COLOR_KEY_AUTO
        self.border_w   = int(config.get("border_w", 0))
        self.border_col = int(config.get("border_col", 7))
        # 静的スケール (キャラ/BG の「CHARACTER SCALING」等で指定)。
        # アニメのスケールとは乗算で合成される。
        self._static_scale = float(config.get("scale", 1.0))

        # ── アニメーション設定 ──────────────────────────────
        anim = {**_default_anim(), **config.get("anim", {})}
        self._shake_amp    = int(anim["shake_amp"])
        self._shake_speed  = max(1, int(anim["shake_speed"]))
        self._rot_speed    = float(anim["rot_speed"])
        self._scale_start  = float(anim["scale_start"])
        self._scale_end    = float(anim["scale_end"])
        self._scale_frames = int(anim["scale_frames"])
        self._motion_x     = int(anim["motion_x"])
        self._motion_y     = int(anim["motion_y"])
        self._motion_frames = int(anim["motion_frames"])
        self._fb_interval  = max(1, int(anim["flipbook_interval"]))
        fb_extra = anim.get("flipbook_files", [])

        # ── pyxel.Image ロード ──────────────────────────────
        load_w, load_h, self._source_scale = sprite_load_size_for_screen(
            cache, self._file, img_w, img_h)
        main_img = cache.get(self._file, load_w, load_h,
                             alpha_colkey=self._auto_colkey)
        self._images: list[pyxel.Image] = []
        self._colkeys: list[int | None] = []
        if main_img:
            self._images.append(main_img)
            self._colkeys.append(self._resolved_colkey(cache, self._file,
                                                       load_w, load_h))
            iw, ih = main_img.width, main_img.height
            for f in fb_extra:
                img = cache.get(f, iw, ih, alpha_colkey=self._auto_colkey)
                if img:
                    self._images.append(img)
                    self._colkeys.append(self._resolved_colkey(cache, f,
                                                               iw, ih))

        # ── ランタイム状態 ──────────────────────────────────
        self._frame    = 0
        self._fb_idx   = 0
        self._rot      = 0.0
        self._scale    = self._scale_start
        self._shake_x  = 0
        self._shake_y  = 0

    # ── 公開 API ────────────────────────────────────────────

    @property
    def loaded(self) -> bool:
        return bool(self._images)

    def reset(self):
        """アニメーション状態をリセット"""
        self._frame   = 0
        self._fb_idx  = 0
        self._rot     = 0.0
        self._scale   = self._scale_start
        self._shake_x = 0
        self._shake_y = 0
        self.x = self._x0
        self.y = self._y0

    def update(self):
        self._frame += 1
        f = self._frame

        # パラパラ漫画
        if len(self._images) > 1:
            self._fb_idx = (f // self._fb_interval) % len(self._images)

        # スケールアニメ
        if self._scale_frames > 0:
            t = min(1.0, f / self._scale_frames)
            self._scale = (self._scale_start
                           + (self._scale_end - self._scale_start) * t)
        else:
            self._scale = self._scale_end if self._scale_frames == 0 else self._scale_start

        # 回転
        self._rot += self._rot_speed

        # 移動
        if self._motion_frames > 0:
            t = min(1.0, f / self._motion_frames)
            self.x = self._x0 + self._motion_x * t
            self.y = self._y0 + self._motion_y * t

        # 震え
        if self._shake_amp > 0 and f % self._shake_speed == 0:
            self._shake_x = random.randint(-self._shake_amp, self._shake_amp)
            self._shake_y = random.randint(-self._shake_amp, self._shake_amp)
        elif self._shake_amp == 0:
            self._shake_x = self._shake_y = 0

    def draw(self):
        if not self._images:
            return

        img = self._images[self._fb_idx]
        iw, ih = img.width, img.height

        # flip: blt の w/h に負値を渡すだけでよい
        bw = -iw if self.flip_h else iw
        bh = -ih if self.flip_v else ih

        scale = max(0.01, self._scale * self._static_scale)
        draw_scale = scale * self._source_scale
        ck = (self._colkeys[self._fb_idx]
              if self._fb_idx < len(self._colkeys) else None)
        rot   = self._rot % 360

        # ── 座標変換: 左下原点 → 画面(左上原点) ────────────────
        # ユーザー座標: x=右方向, y=上方向(0=画面下端)
        # pyxel.blt の (x, y) は rotate/scale 指定時も描画先の左上
        # 画像の左上の画面Y = HEIGHT - user_y - ih_scaled
        # ─────────────────────────────────────────────────────────
        tl_x, tl_y = sprite_top_left(
            self.x, self.y, ih, draw_scale,
            shake_x=self._shake_x, shake_y=self._shake_y)

        if rot == 0.0 and abs(draw_scale - 1.0) < 0.001:
            pyxel.blt(tl_x, tl_y, img, 0, 0, bw, bh, ck)
        else:
            pyxel.blt(tl_x, tl_y, img, 0, 0, bw, bh, ck,
                      rotate=rot, scale=draw_scale)

        # 枠線（画面左上基準で描く）
        if self.border_w > 0:
            rw = round(iw * draw_scale)
            rh = round(ih * draw_scale)
            for bwi in range(self.border_w):
                pyxel.rectb(tl_x - bwi, tl_y - bwi,
                            rw + bwi * 2, rh + bwi * 2,
                            self.border_col)

    def _resolved_colkey(self, cache: ImageCache, path: str,
                         width: int, height: int) -> "int | None":
        if self._auto_colkey:
            return cache.get_auto_colkey(path, width, height)
        return self.colkey if self.colkey >= 0 else None
