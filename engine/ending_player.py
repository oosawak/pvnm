"""エンディングプレイヤー: タイムライン同期スライドショー + クレジットスクロール

スライドの表示開始タイミングは BGM の再生位置 (秒) に同期する。BGM が
無いエンディングではエンディング開始からの経過秒を使う。

スライドのデータモデル:
  {
    "image":           "/path/to.png",  # 画像
    "time":            10.0,            # 表示開始秒 (BGM 同期)
    "effect":          "fade",          # "cut" | "fade" | "zoom"
    "effect_duration": 1.0,             # 入場エフェクトの長さ (秒)
    "duration":        3.0,             # (旧) time が無い場合の sequential 用
  }

`time` フィールドが 1 つでもあればタイムラインモードで動作する。
無い場合は旧式の sequential (fade-in/show/fade-out チェーン) で動作する。
"""
import os
import pyxel
from ui.widgets import draw_unicode, text_px_w
from engine.image_cache import ImageCache, set_default_palette as _set_image_cache_palette
from engine import palette as _palette_mod
from engine import audio as _audio
from engine import runtime_assets as _runtime_assets

# 旧式 sequential 用の入場/退場フェード長 (フレーム / 30fps)
LEGACY_FADE_FRAMES = 20

# タイムラインモードのエフェクト ID
EFFECT_CUT  = "cut"
EFFECT_FADE = "fade"
EFFECT_ZOOM = "zoom"
_VALID_EFFECTS = (EFFECT_CUT, EFFECT_FADE, EFFECT_ZOOM)


class EndingPlayer:
    """エンディング再生。"""

    def __init__(self, ending: dict, cache: ImageCache = None,
                 settings: dict = None, preview_start_sec: float = 0.0):
        """
        preview_start_sec: BGM をこの秒数から開始する。エンディングエディタの
            PREVIEW で「曲の途中から確認したい」用途。0 なら先頭から。
        """
        self._cache = cache
        self._ending = ending
        self.finished = False
        # ESC で中断されたかどうか。True なら main 側は チェーン (goto_ending) を
        # スキップしてエディタ等へ戻る。
        self.aborted: bool = False
        # 自然終了時に次にチェーン再生したいエンディング名 (空なら無し)。
        # ESC で抜けた場合は main 側で None 扱いされる (aborted=True で識別)。
        self.next_ending_name: str = (ending.get("goto_ending", "") or "")
        self._settings: dict = settings or {}
        self._applied_slide_i: int = -1
        # プレビュー開始秒 (BGM シーク量)。タイムライン時計の初期オフセットにも使う。
        self._preview_start_sec: float = max(0.0, float(preview_start_sec or 0.0))
        # BGM 終了検出用ラッチ:
        #   _bgm_ever_started=False で play_bgm 直後を待つ (起動に数フレーム要する)
        #   一度 True になった後 is_bgm_playing() が False に戻れば曲終了 → エンディング終了
        self._bgm_ever_started: bool = False

        # スライドモード判定: `time` を持つスライドが 1 つでもあれば timeline
        raw_slides = ending.get("slides", []) or []
        has_time = any(isinstance(s, dict) and ("time" in s) for s in raw_slides)
        self._timeline_mode = has_time and len(raw_slides) > 0
        if self._timeline_mode:
            self._timeline = self._build_timeline(raw_slides)
        else:
            # 旧式 sequential 用に元データを保持
            self._timeline = []
            self._slides = raw_slides

        # 現在表示中のスライド (timeline モード)
        self._cur_idx = -1
        # 旧式: スライドステートマシン
        self._slide_i = 0
        self._slide_timer = 0
        self._slide_state = "fade_in"
        self._slide_fade = 0
        if not raw_slides:
            self._slide_state = "done"

        # クレジット
        self._credits = ending.get("credits", "")
        self._credit_lines = self._credits.split("\n") if self._credits else []
        self._credit_y = float(pyxel.height)
        self._scroll_speed = float(ending.get("scroll_speed", 1.0))
        self._credit_font_size = int(ending.get("font_size", 14)) or 14

        # フォント
        font_file = ending.get("font_file", "")
        if font_file:
            print(f"[PVNM] Ending credit font ignored (BDF runtime): {font_file}")

        # 全スライド画像を再生前にキャッシュへ事前ロードする。
        # タイムラインで曲の後半に置いたスライドも、再生時刻に到達した瞬間に
        # 量子化が走ってカクつくのを防ぐ。BGM 開始より先に呼ぶことで、再生開始
        # 直後の数百ms の処理オーバーヘッドを吸収する。
        self._precache_slides()

        # 内部フレームカウンタ (BGM 無し時の時計、および monotonic 維持用)
        self._frame = 0
        # タイムラインの monotonic 時計 (BGM が止まっても単調増加させる)
        self._clock_floor = 0.0
        self._last_clock_frame = 0

        # BGM 再生 (タイムラインの時計源にもなる)
        self._bgm_active = False
        bgm_file = ending.get("bgm_file", "")
        if bgm_file:
            if self._cache:
                abs_bgm = _runtime_assets.resolve_asset_path(
                    bgm_file, self._cache.base_dir)
            else:
                abs_bgm = bgm_file
            _audio.play_bgm(abs_bgm,
                            volume=int(ending.get("bgm_volume", 7)),
                            loop=bool(ending.get("bgm_loop", True)),
                            start=self._preview_start_sec)
            self._bgm_active = True
        # BGM 無し時、preview_start_sec が指定されていれば内部時計を進めておく
        if not self._bgm_active and self._preview_start_sec > 0:
            self._clock_floor = self._preview_start_sec
            self._frame = int(self._preview_start_sec * 30)

        # 初回スライドのパレットを先に適用
        if self._timeline_mode and self._timeline:
            # time=0 のスライドがあれば即座に適用される動きを再現するため
            # 一旦 -1 のまま放置し、最初の update() でパレット適用される
            pass
        elif raw_slides:
            self._apply_slide_palette_legacy(self._slide_i)

    # ── 事前キャッシュ ───────────────────────────────────────────

    def _precache_slides(self) -> None:
        """全スライド画像を再生前にキャッシュへ流し込む。

        各スライドに最適化されたパレットを構築し、`cache.get(palette=pal)` で
        量子化済み pyxel.Image を作っておく。ImageCache は `(path, w, h,
        palette_hash)` キーで保存するので、再生中に同じパレットで取得した時
        メモリヒットして即返る。

        初回はディスクへの .npy 保存も走るので 1-2 秒程度かかることがある。
        2回目以降はディスクキャッシュからロードするだけなので一瞬で済む。
        """
        if not self._cache:
            return
        reserved = _palette_mod.reserved_from_settings(self._settings)
        if not reserved:
            return
        if self._timeline_mode:
            entries = self._timeline
        else:
            entries = self._slides
        # 同じ画像が複数スライドに使われている場合、パレット構築は1回で済む
        import time
        seen: set = set()
        unique_paths = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            img_file = entry.get("image", "") or ""
            if img_file and img_file not in seen:
                seen.add(img_file)
                unique_paths.append(img_file)
        if not unique_paths:
            return
        t0 = time.time()
        for img_file in unique_paths:
            try:
                pal = None
                if hasattr(self._cache, "get_prebuilt_palette"):
                    pal = self._cache.get_prebuilt_palette([img_file], reserved)
                if pal is None:
                    pal = _palette_mod.build_scene_palette(
                        [img_file], reserved, base_dir=self._cache.base_dir)
                iw, ih = self._cache.source_size(img_file)
                if iw > 0 and ih > 0:
                    fit = min(pyxel.width / iw, pyxel.height / ih, 1.0)
                    self._cache.get(
                        img_file,
                        max(1, round(iw * fit)),
                        max(1, round(ih * fit)),
                        palette=pal,
                    )
                else:
                    self._cache.get(img_file, palette=pal)
            except Exception as e:
                print(f"[ending] pre-cache failed for {img_file}: {e}")
        elapsed = time.time() - t0
        # 1秒以上かかった時だけログ出力 (初回ロードを示す)
        if elapsed >= 1.0:
            print(f"[ending] pre-cached {len(unique_paths)} slides "
                  f"in {elapsed:.1f}s (subsequent runs will be near-instant)")

    # ── タイムライン構築 ─────────────────────────────────────────

    def _build_timeline(self, slides: list) -> list:
        """slides 配列を (time, image, effect, effect_dur) に正規化。

        time が欠落しているスライドは、直前のスライドの time + duration から
        自動推定する (混在対応のため)。
        """
        out: list = []
        next_t = 0.0
        for s in slides:
            if not isinstance(s, dict):
                continue
            if "time" in s:
                start = float(s.get("time", 0.0) or 0.0)
            else:
                start = next_t
            img = s.get("image", "") or ""
            effect = s.get("effect", "fade")
            if effect not in _VALID_EFFECTS:
                effect = "fade"
            eff_dur = float(s.get("effect_duration", 1.0) or 1.0)
            show_dur = float(s.get("duration", 3.0) or 3.0)
            out.append({
                "time":            start,
                "image":           img,
                "effect":          effect,
                "effect_duration": max(0.0, eff_dur),
            })
            next_t = start + eff_dur + show_dur
        out.sort(key=lambda x: x["time"])
        return out

    # ── 時計 ─────────────────────────────────────────────────────

    def _clock(self) -> float:
        """エンディングのタイムライン時計 (秒)。

        BGM がある時は `audio.get_bgm_pos_sec()` を採用、無い時はフレーム数。
        BGM 終了時に get_pos が 0 を返すケースを吸収するため、過去最大値で
        monotonic にする。
        """
        if not self._bgm_active:
            return self._frame / 30.0
        pos = _audio.get_bgm_pos_sec()
        if pos > self._clock_floor:
            self._clock_floor = pos
        elif self._frame > self._last_clock_frame:
            # BGM 停止後も時計は進める
            self._clock_floor += (self._frame - self._last_clock_frame) / 30.0
        self._last_clock_frame = self._frame
        return self._clock_floor

    def current_time_sec(self) -> float:
        """現在のBGM同期秒を返す。プレビュー中断時のTIME採取に使う。"""
        try:
            return max(0.0, float(self._clock()))
        except Exception:
            return 0.0

    def _current_slide_idx(self) -> int:
        """現時刻に対応するスライド index。time<=clock の最後 (まだ無ければ -1)。"""
        t = self._clock()
        i = -1
        for k, e in enumerate(self._timeline):
            if e["time"] <= t:
                i = k
            else:
                break
        return i

    # ── パレット ─────────────────────────────────────────────────

    def _apply_slide_palette_for_path(self, img_file: str) -> None:
        if not self._cache or not img_file:
            return
        reserved = _palette_mod.reserved_from_settings(self._settings)
        if not reserved:
            return
        pal = None
        if hasattr(self._cache, "get_prebuilt_palette"):
            pal = self._cache.get_prebuilt_palette([img_file], reserved)
        if pal is None:
            pal = _palette_mod.build_scene_palette(
                [img_file], reserved, base_dir=self._cache.base_dir)
        _palette_mod.apply_to_pyxel_colors(pal)
        _set_image_cache_palette(pal)

    def _get_slide_image(self, img_file: str):
        if not img_file or not self._cache:
            return None
        iw, ih = self._cache.source_size(img_file)
        if iw > 0 and ih > 0:
            fit = min(pyxel.width / iw, pyxel.height / ih, 1.0)
            w = max(1, round(iw * fit))
            h = max(1, round(ih * fit))
            return self._cache.get(img_file, w, h)
        return self._cache.get(img_file)

    def _apply_slide_palette_legacy(self, slide_i: int) -> None:
        """旧式 sequential 用: index 指定でパレット適用。"""
        if self._applied_slide_i == slide_i:
            return
        self._applied_slide_i = slide_i
        if not (0 <= slide_i < len(self._slides)):
            return
        img_file = self._slides[slide_i].get("image", "")
        self._apply_slide_palette_for_path(img_file)

    def _apply_slide_palette_timeline(self, slide_i: int) -> None:
        if self._applied_slide_i == slide_i:
            return
        self._applied_slide_i = slide_i
        if not (0 <= slide_i < len(self._timeline)):
            return
        img_file = self._timeline[slide_i].get("image", "")
        self._apply_slide_palette_for_path(img_file)

    # ── update / draw ────────────────────────────────────────────

    def update(self):
        if self.finished:
            return

        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self.finished = True
            self.aborted = True
            return

        self._frame += 1

        if self._timeline_mode:
            self._update_timeline()
        else:
            if self._slide_state != "done":
                self._update_slide_legacy()

        # クレジットスクロール
        if self._credit_lines:
            self._credit_y -= self._scroll_speed

        # ── 終了条件 ───────────────────────────────────────────────
        # 1) BGM がある場合: 曲が終わった (or 停止された) 時点で終了。
        #    BGM が loop なら明示的な ESC でしか終わらない。
        #    スライドが先に全部表示されても BGM 中は背景表示を継続する。
        # 2) BGM が無い場合: スライド全部表示完了 + クレジット完了で終了。
        #    スライドもクレジットも無いエンディングは即終了。
        if self._bgm_active:
            if self._bgm_ever_started:
                if not _audio.is_bgm_playing():
                    self.finished = True
                    return
            elif _audio.is_bgm_playing():
                self._bgm_ever_started = True
        else:
            credits_done = True
            if self._credit_lines:
                fsz = self._credit_font_size
                total_h = len(self._credit_lines) * (fsz + 6)
                credits_done = self._credit_y < -total_h
            if self._is_slide_phase_done() and credits_done:
                self.finished = True
                return

        if not self._has_slides() and not self._credit_lines and not self._bgm_active:
            self.finished = True

    def _has_slides(self) -> bool:
        return bool(self._timeline if self._timeline_mode else self._slides)

    def _is_slide_phase_done(self) -> bool:
        if self._timeline_mode:
            if not self._timeline:
                return True
            last = self._timeline[-1]
            t = self._clock()
            return t >= last["time"] + last["effect_duration"]
        return self._slide_state == "done"

    def _update_timeline(self):
        new_idx = self._current_slide_idx()
        if new_idx != self._cur_idx:
            self._cur_idx = new_idx
            if 0 <= new_idx < len(self._timeline):
                self._apply_slide_palette_timeline(new_idx)

    def _update_slide_legacy(self):
        slide = (self._slides[self._slide_i]
                 if self._slide_i < len(self._slides) else None)
        if slide is None:
            self._slide_state = "done"
            return
        dur_frames = int(float(slide.get("duration", 3.0)) * 30)
        if self._slide_state == "fade_in":
            self._slide_fade += 1
            if self._slide_fade >= LEGACY_FADE_FRAMES:
                self._slide_state = "show"
                self._slide_timer = 0
        elif self._slide_state == "show":
            self._slide_timer += 1
            if self._slide_timer >= dur_frames:
                self._slide_state = "fade_out"
                self._slide_fade = 0
        elif self._slide_state == "fade_out":
            self._slide_fade += 1
            if self._slide_fade >= LEGACY_FADE_FRAMES:
                self._slide_i += 1
                if self._slide_i >= len(self._slides):
                    self._slide_state = "done"
                else:
                    self._slide_state = "fade_in"
                    self._slide_fade = 0
                    self._apply_slide_palette_legacy(self._slide_i)

    def draw(self):
        if self.finished:
            return
        W, H = pyxel.width, pyxel.height
        pyxel.cls(0)

        # スライド画像
        if self._timeline_mode:
            self._draw_timeline_slide()
        elif self._slide_state != "done" and self._slide_i < len(self._slides):
            self._draw_legacy_slide()

        # クレジット
        if self._credit_lines:
            fsz = self._credit_font_size
            lh = fsz + 6
            cy = int(self._credit_y)
            for i, line in enumerate(self._credit_lines):
                y = cy + i * lh
                if -lh <= y <= H:
                    self._draw_credit_line(line, y, fsz)

    def _draw_timeline_slide(self):
        if not (0 <= self._cur_idx < len(self._timeline)):
            return
        entry = self._timeline[self._cur_idx]
        img_file = entry.get("image", "")
        if not img_file or not self._cache:
            return
        img = self._get_slide_image(img_file)
        if img is None:
            return
        # エフェクト進行度 (0..1)
        t = self._clock()
        eff_dur = max(0.001, entry.get("effect_duration", 1.0))
        progress = max(0.0, min(1.0, (t - entry["time"]) / eff_dur))
        effect = entry.get("effect", "fade")
        if effect == EFFECT_CUT:
            self._blit_fit(img, scale_mul=1.0)
        elif effect == EFFECT_ZOOM:
            # 0.5x → 1.0x で拡大
            scale_mul = 0.5 + 0.5 * progress
            self._blit_fit(img, scale_mul=scale_mul)
        else:  # EFFECT_FADE
            self._blit_fit(img, scale_mul=1.0)
            if progress < 1.0:
                # 黒オーバーレイで覆って徐々に薄くする
                self._draw_fade(1.0 - progress)

    def _draw_legacy_slide(self):
        slide = self._slides[self._slide_i]
        img_file = slide.get("image", "")
        if img_file and self._cache:
            img = self._get_slide_image(img_file)
            if img:
                self._blit_fit(img, scale_mul=1.0)
        if self._slide_state == "fade_in":
            alpha = 1.0 - self._slide_fade / LEGACY_FADE_FRAMES
            self._draw_fade(alpha)
        elif self._slide_state == "fade_out":
            alpha = self._slide_fade / LEGACY_FADE_FRAMES
            self._draw_fade(alpha)

    def _blit_fit(self, img, scale_mul: float = 1.0):
        """画像をアスペクト比保持で画面にフィットさせて描画。

        scale_mul: zoom 効果用の追加倍率 (1.0 = 通常フルフィット)。
        """
        W, H = pyxel.width, pyxel.height
        iw, ih = img.width, img.height
        if iw <= 0 or ih <= 0:
            return
        fit = min(W / iw, H / ih)
        s = fit * scale_mul
        sw = max(1, int(iw * s))
        sh = max(1, int(ih * s))
        x = (W - sw) // 2
        y = (H - sh) // 2
        if abs(s - 1.0) < 0.001:
            pyxel.blt(x, y, img, 0, 0, iw, ih)
        else:
            # pyxel.blt の scale 引数は中央基準なので左上を補正
            bx = x + int(iw * (s - 1) / 2)
            by = y + int(ih * (s - 1) / 2)
            pyxel.blt(bx, by, img, 0, 0, iw, ih, scale=s)

    def _draw_credit_line(self, text: str, y: int, size: int):
        W = pyxel.width
        tw = text_px_w(text, size)
        x = (W - tw) // 2
        draw_unicode(x + 1, y + 1, text, 0, size=size)
        draw_unicode(x, y, text, 7, size=size)

    def _draw_fade(self, alpha: float):
        if alpha <= 0:
            return
        W, H = pyxel.width, pyxel.height
        if alpha >= 1.0:
            pyxel.rect(0, 0, W, H, 0)
            return
        step = max(1, int(4 * (1.0 - alpha)))
        for y in range(0, H, step):
            pyxel.line(0, y, W - 1, y, 0)
