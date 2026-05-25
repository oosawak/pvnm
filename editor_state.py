"""エディタの状態管理 (schema v4: COLOR KEY AUTO 対応)"""
import copy
import json
import re
from engine.title_colors import normalize_button_colors
from engine.gallery_config import normalize_gallery_config
from engine.extra_text_config import normalize_extra_text_config
from engine.image_cache import COLOR_KEY_AUTO, normalize_color_key


def _default_char(x: int = 0, y: int = 0) -> dict:
    """キャラクタースロットのデフォルト設定。

    file が "" は「INHERIT (前シーンから引き継ぎ)」を意味する (旧仕様の "未設定"
    と同一表現を再解釈)。明示的にこのスロットを非表示にしたい場合は
    `hide: True` を立てる (player はそのスロットの persistent をクリアする)。
    """
    return {
        "file":     "",
        "hide":     False,        # True: このスロットを明示的に非表示 (継承を断つ)
        "x": x,    "y": y,
        "scale":    1.0,          # CHARACTER SCALING (倍率, vertical axis position を基準にスケール)
        "flip_h":   False,
        "flip_v":   False,
        "colkey":   COLOR_KEY_AUTO,  # -2=AUTO, -1=なし, 0-255=手動
        "border_w": 0,
        "border_col": 7,
        "anim": {},
        "keep_anim": False,       # True: animation を次シーンにも明示継承
        "hold_motion_end": False, # True: motion 終了位置を次シーンへ引き継ぐ
    }


# LEFT / CENTER / RIGHT のデフォルト座標 (vertical axis position = 216 = 下端から 216 px)
_CHAR_DEFAULT_X = {"l": 45, "c": 295, "r": 545}
_CHAR_DEFAULT_Y = 216


def _normalize_scene_char_colkeys(scenes, *, migrate_default_zero: bool = False):
    """キャラクター透過設定を現在の COLOR KEY 仕様へ寄せる。

    旧プロジェクトではデフォルト値として 0 が保存されていたため、
    それを AUTO に移行する。明示的な NONE(-1) と 1-255 は維持する。
    """
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        for key in ("char_l", "char_c", "char_r"):
            cfg = scene.get(key)
            if not isinstance(cfg, dict):
                continue
            raw = cfg.get("colkey", COLOR_KEY_AUTO)
            if migrate_default_zero and raw == 0:
                cfg["colkey"] = COLOR_KEY_AUTO
            else:
                cfg["colkey"] = normalize_color_key(raw)


def _default_anim() -> dict:
    return {
        "shake_amp": 0, "shake_speed": 4,
        "rot_speed": 0.0,
        "scale_start": 1.0, "scale_end": 1.0, "scale_frames": 0,
        "motion_x": 0, "motion_y": 0, "motion_frames": 0,
        "flipbook_files": [], "flipbook_interval": 6,
    }


def _default_character_position_memory() -> dict:
    return {"l": None, "c": None, "r": None}


def normalize_character_position_memory(data) -> dict:
    """Normalize per-slot remembered character positions."""
    out = _default_character_position_memory()
    if not isinstance(data, dict):
        return out
    for slot in ("l", "c", "r"):
        raw = data.get(slot)
        if not isinstance(raw, dict):
            continue
        try:
            out[slot] = {
                "x": int(raw.get("x", 0)),
                "y": int(raw.get("y", 0)),
                "scale": float(raw.get("scale", 1.0)),
            }
        except Exception:
            out[slot] = None
    return out


# ── プレフィックスユーティリティ ────────────────────────────────

_PREFIX_RE = re.compile(r"^(\d{4})_(\d{4})_(.*)$")


def parse_scene_name(name: str):
    """シーン名をパース → (part_id, chapter_id, display_name) or None"""
    m = _PREFIX_RE.match(name)
    if m:
        return int(m.group(1)), int(m.group(2)), m.group(3)
    return None


def make_scene_name(part_id: int, chapter_id: int, display: str) -> str:
    return f"{part_id:04d}_{chapter_id:04d}_{display}"


def display_name(scene: dict) -> str:
    """シーンの表示名（プレフィックス除去）"""
    parsed = parse_scene_name(scene.get("name", ""))
    return parsed[2] if parsed else scene.get("name", "")


# ── デフォルトシーン ──────────────────────────────────────────

def _new_scene(name: str) -> dict:
    return {
        "name": name,
        # bg = "" は INHERIT (前シーン継続)、bg_hide=True は明示クリア、
        # bg = "/path/..." は SET (この scene 以降の persistent を上書き)。
        # bg_above_dialog=True: BG をダイアログ上の領域 (720x324) に収めて
        # ダイアログで隠れないようにする。継承時にも引き継がれる。
        "bg": "", "bg_hide": False, "bg_above_dialog": False,
        "bg_x": 0, "bg_y": 0, "bg_w": 0, "bg_h": 0,
        "bg_anim": {}, "bg_fullscreen": False,
        "char_l": _default_char(60,  3),
        "char_c": _default_char(260, 3),
        "char_r": _default_char(460, 3),
        "font_file": "", "font_size": 0,
        "speaker": "", "text": "",
        "goto": "", "transition": "",
        "choices": [],
        "bgm_file": "", "bgm_volume": 7, "bgm_stop": False,
        "bgm_loop": True,
        "bgm_fadeout_frames": 0,
        "se_file": "", "se_volume": 7, "se_repeat": 0,
        "goto_ending": "",
        "hide_dialog": False,
        "auto_pause": False,
    }


class EditorState:
    def __init__(self):
        # Part / Chapter
        self.parts = [{"id": 1, "name": "Part 1"}]
        self.chapters = [{"id": 1, "part_id": 1, "name": "Chapter 1"}]
        self.current_part_id = 1
        self.current_chapter_id = 1

        # シーン
        self.scenes = [
            {
                "name": "0001_0001_scene_01",
                "bg": "",
                "bg_x": 0, "bg_y": 0, "bg_w": 0, "bg_h": 0,
                "bg_anim": {},
                "bg_fullscreen": False,
                "char_l": _default_char(_CHAR_DEFAULT_X["l"], _CHAR_DEFAULT_Y),
                "char_c": _default_char(_CHAR_DEFAULT_X["c"], _CHAR_DEFAULT_Y),
                "char_r": _default_char(_CHAR_DEFAULT_X["r"], _CHAR_DEFAULT_Y),
                "font_file": "", "font_size": 0,
                "speaker": "Alice",
                "text": "屋上に行ってみない?",
                "goto": "", "transition": "",
                "bgm_file": "", "bgm_volume": 7, "bgm_stop": False,
                "bgm_loop": True,
                "bgm_fadeout_frames": 0,
                "se_file": "", "se_volume": 7, "se_repeat": 0,
                "choices": [
                    {"label": "行く!",      "goto": "0001_0001_scene_02a"},
                    {"label": "やめとく…", "goto": "0001_0001_scene_02b"},
                ],
                "auto_pause": False,
            },
            {
                "name": "0001_0001_scene_02a",
                "bg": "", "bg_x": 0, "bg_y": 0, "bg_w": 0, "bg_h": 0,
                "bg_anim": {}, "bg_fullscreen": False,
                "char_l": _default_char(_CHAR_DEFAULT_X["l"], _CHAR_DEFAULT_Y),
                "char_c": _default_char(_CHAR_DEFAULT_X["c"], _CHAR_DEFAULT_Y),
                "char_r": _default_char(_CHAR_DEFAULT_X["r"], _CHAR_DEFAULT_Y),
                "font_file": "", "font_size": 0,
                "speaker": "Alice",
                "text": "景色が最高だね!",
                "goto": "0001_0001_scene_03", "transition": "fade",
                "bgm_file": "", "bgm_volume": 7, "bgm_stop": False,
                "bgm_loop": True,
                "bgm_fadeout_frames": 0,
                "se_file": "", "se_volume": 7, "se_repeat": 0,
                "choices": [],
                "auto_pause": False,
            },
            {
                "name": "0001_0001_scene_02b",
                "bg": "", "bg_x": 0, "bg_y": 0, "bg_w": 0, "bg_h": 0,
                "bg_anim": {}, "bg_fullscreen": False,
                "char_l": _default_char(_CHAR_DEFAULT_X["l"], _CHAR_DEFAULT_Y),
                "char_c": _default_char(_CHAR_DEFAULT_X["c"], _CHAR_DEFAULT_Y),
                "char_r": _default_char(_CHAR_DEFAULT_X["r"], _CHAR_DEFAULT_Y),
                "font_file": "", "font_size": 0,
                "speaker": "Bob",
                "text": "また今度ね。",
                "goto": "0001_0001_scene_03", "transition": "fade",
                "bgm_file": "", "bgm_volume": 7, "bgm_stop": False,
                "bgm_loop": True,
                "bgm_fadeout_frames": 0,
                "se_file": "", "se_volume": 7, "se_repeat": 0,
                "choices": [],
                "auto_pause": False,
            },
            {
                "name": "0001_0001_scene_03",
                "bg": "", "bg_x": 0, "bg_y": 0, "bg_w": 0, "bg_h": 0,
                "bg_anim": {}, "bg_fullscreen": False,
                "char_l": _default_char(_CHAR_DEFAULT_X["l"], _CHAR_DEFAULT_Y),
                "char_c": _default_char(_CHAR_DEFAULT_X["c"], _CHAR_DEFAULT_Y),
                "char_r": _default_char(_CHAR_DEFAULT_X["r"], _CHAR_DEFAULT_Y),
                "font_file": "", "font_size": 0,
                "speaker": "",
                "text": "また明日。",
                "goto": "", "transition": "",
                "bgm_file": "", "bgm_volume": 7, "bgm_stop": False,
                "bgm_loop": True,
                "bgm_fadeout_frames": 0,
                "se_file": "", "se_volume": 7, "se_repeat": 0,
                "choices": [],
                "auto_pause": False,
            },
        ]
        self.selected_scene = 0
        # FLOWビュー上で選択中の特殊ノード
        #   None        → 通常シーン選択
        #   "title"     → タイトル画面
        #   ("ending", idx) → エンディング
        self.selected_special = None
        self.active_tab     = 0     # 0=SCENE, 1=FLOW
        self.request_play   = False
        self.request_title  = False
        self.request_quit   = False

        # ファイル管理
        self.file_path  = ""
        self.dirty      = False
        self.scene_gen  = 0
        self.preview_expanded      = False  # MainView snapshot 拡大表示中
        self.request_open          = False
        self.request_colors        = False
        self.request_font_settings = False
        self.request_parts         = False
        self.request_chapters      = False
        self.request_endings       = False
        self.request_settings      = False
        self.request_delete_scene  = False
        self.request_import_md     = False

        # タイトル & エンディング
        self.title_config = {
            "bg_image": "", "bg_fullscreen": False,
            "bgm_file": "", "bgm_volume": 7, "bgm_loop": True,
            "button_colors": normalize_button_colors(),
        }
        self.endings = []  # [{"id":1,"name":"End A","slides":[],"credits":"","font_file":"","font_size":14,"scroll_speed":1.0}]
        self.gallery_config = normalize_gallery_config({})
        self.extra_text_config = normalize_extra_text_config({})
        self.character_position_memory = _default_character_position_memory()

    # ── Part 操作 ──────────────────────────────────────────

    def next_part_id(self) -> int:
        if not self.parts:
            return 1
        return min(9999, max(p["id"] for p in self.parts) + 1)

    def get_part(self, part_id: int):
        for p in self.parts:
            if p["id"] == part_id:
                return p
        return None

    def add_part(self, name: str = ""):
        pid = self.next_part_id()
        if not name:
            name = f"Part {pid}"
        self.parts.append({"id": pid, "name": name})
        # 新しい Part にはデフォルト Chapter を1つ作る
        cid = 1
        self.chapters.append({"id": cid, "part_id": pid, "name": "Chapter 1"})
        self.scene_gen += 1
        self.dirty = True
        return pid

    def copy_part(self, part_id: int):
        src = self.get_part(part_id)
        if not src:
            return
        new_pid = self.next_part_id()
        self.parts.append({"id": new_pid, "name": src["name"]})
        # 該当 Part の Chapter をコピー
        src_chapters = [c for c in self.chapters if c["part_id"] == part_id]
        chapter_id_map = {}  # old_cid -> new_cid
        for ch in src_chapters:
            new_cid = self.next_chapter_id(new_pid)
            self.chapters.append({"id": new_cid, "part_id": new_pid, "name": ch["name"]})
            chapter_id_map[ch["id"]] = new_cid
        # 該当 Part の Scene をコピー（goto 参照も更新）
        old_to_new = {}
        new_scenes = []
        for s in self.scenes:
            parsed = parse_scene_name(s["name"])
            if parsed and parsed[0] == part_id:
                new_s = copy.deepcopy(s)
                old_cid = parsed[1]
                new_cid = chapter_id_map.get(old_cid, old_cid)
                new_name = make_scene_name(new_pid, new_cid, parsed[2])
                old_to_new[s["name"]] = new_name
                new_s["name"] = new_name
                new_scenes.append(new_s)
        # goto 参照を更新
        for ns in new_scenes:
            if ns.get("goto") in old_to_new:
                ns["goto"] = old_to_new[ns["goto"]]
            for c in ns.get("choices", []):
                if c.get("goto") in old_to_new:
                    c["goto"] = old_to_new[c["goto"]]
        self.scenes.extend(new_scenes)
        self.normalize_scene_order()
        self.scene_gen += 1
        self.dirty = True

    def _clear_goto_refs(self, removed_names: set):
        for s in self.scenes:
            if s.get("goto") in removed_names:
                s["goto"] = ""
            for c in s.get("choices", []):
                if c.get("goto") in removed_names:
                    c["goto"] = ""

    def delete_part(self, part_id: int):
        prefix = f"{part_id:04d}_"
        removed_names = {
            s.get("name", "") for s in self.scenes
            if s.get("name", "").startswith(prefix)
        }
        self.parts = [p for p in self.parts if p["id"] != part_id]
        self.chapters = [c for c in self.chapters if c["part_id"] != part_id]
        self.scenes = [s for s in self.scenes if not s["name"].startswith(prefix)]
        self._clear_goto_refs(removed_names)
        self.selected_scene = min(self.selected_scene, max(0, len(self.scenes) - 1))
        self.selected_special = None
        # current_part が削除された場合、最初の Part に切り替え
        if not self.get_part(self.current_part_id) and self.parts:
            self.current_part_id = self.parts[0]["id"]
            chs = self.chapters_for_part(self.current_part_id)
            self.current_chapter_id = chs[0]["id"] if chs else 0
        self.scene_gen += 1
        self.dirty = True

    def rename_part(self, part_id: int, name: str):
        p = self.get_part(part_id)
        if p:
            p["name"] = name
            self.scene_gen += 1
            self.dirty = True

    def reorder_parts(self, from_idx: int, to_idx: int):
        if from_idx == to_idx:
            return
        if 0 <= from_idx < len(self.parts) and 0 <= to_idx < len(self.parts):
            item = self.parts.pop(from_idx)
            self.parts.insert(to_idx, item)
            self.scene_gen += 1
            self.dirty = True

    # ── Chapter 操作 ──────────────────────────────────────

    def chapters_for_part(self, part_id: int) -> list:
        return [c for c in self.chapters if c["part_id"] == part_id]

    def next_chapter_id(self, part_id: int) -> int:
        chs = self.chapters_for_part(part_id)
        if not chs:
            return 1
        return min(9999, max(c["id"] for c in chs) + 1)

    def get_chapter(self, part_id: int, chapter_id: int):
        for c in self.chapters:
            if c["part_id"] == part_id and c["id"] == chapter_id:
                return c
        return None

    def add_chapter(self, part_id: int, name: str = ""):
        cid = self.next_chapter_id(part_id)
        if not name:
            name = f"Chapter {cid}"
        self.chapters.append({"id": cid, "part_id": part_id, "name": name})
        self.scene_gen += 1
        self.dirty = True
        return cid

    def copy_chapter(self, part_id: int, chapter_id: int):
        src = self.get_chapter(part_id, chapter_id)
        if not src:
            return
        new_cid = self.next_chapter_id(part_id)
        self.chapters.append({"id": new_cid, "part_id": part_id, "name": src["name"]})
        # 該当 Chapter の Scene をコピー
        old_to_new = {}
        new_scenes = []
        for s in self.scenes:
            parsed = parse_scene_name(s["name"])
            if parsed and parsed[0] == part_id and parsed[1] == chapter_id:
                new_s = copy.deepcopy(s)
                new_name = make_scene_name(part_id, new_cid, parsed[2])
                old_to_new[s["name"]] = new_name
                new_s["name"] = new_name
                new_scenes.append(new_s)
        for ns in new_scenes:
            if ns.get("goto") in old_to_new:
                ns["goto"] = old_to_new[ns["goto"]]
            for c in ns.get("choices", []):
                if c.get("goto") in old_to_new:
                    c["goto"] = old_to_new[c["goto"]]
        self.scenes.extend(new_scenes)
        self.normalize_scene_order()
        self.scene_gen += 1
        self.dirty = True

    def delete_chapter(self, part_id: int, chapter_id: int):
        prefix = f"{part_id:04d}_{chapter_id:04d}_"
        removed_names = {
            s.get("name", "") for s in self.scenes
            if s.get("name", "").startswith(prefix)
        }
        self.chapters = [c for c in self.chapters
                         if not (c["part_id"] == part_id and c["id"] == chapter_id)]
        self.scenes = [s for s in self.scenes if not s["name"].startswith(prefix)]
        self._clear_goto_refs(removed_names)
        self.selected_scene = min(self.selected_scene, max(0, len(self.scenes) - 1))
        self.selected_special = None
        if not self.get_chapter(self.current_part_id, self.current_chapter_id):
            chs = self.chapters_for_part(self.current_part_id)
            self.current_chapter_id = chs[0]["id"] if chs else 0
        self.scene_gen += 1
        self.dirty = True

    def rename_chapter(self, part_id: int, chapter_id: int, name: str):
        c = self.get_chapter(part_id, chapter_id)
        if c:
            c["name"] = name
            self.scene_gen += 1
            self.dirty = True

    def reorder_chapters(self, part_id: int, from_idx: int, to_idx: int):
        """part内のchapterリストで並べ替え"""
        chs = self.chapters_for_part(part_id)
        if from_idx == to_idx or not (0 <= from_idx < len(chs) and 0 <= to_idx < len(chs)):
            return
        item = chs[from_idx]
        # 全体リストから取り出して正しい位置に挿入
        self.chapters.remove(item)
        # 移動先を再計算（part内のchapterの中でto_idxの位置）
        chs_after = self.chapters_for_part(part_id)
        if to_idx >= len(chs_after):
            # 末尾に追加
            self.chapters.append(item)
        else:
            target = chs_after[to_idx]
            global_idx = self.chapters.index(target)
            self.chapters.insert(global_idx, item)
        self.normalize_scene_order()
        self.scene_gen += 1
        self.dirty = True

    # ── Scene 操作 ──────────────────────────────────────────

    def scene_prefix(self) -> str:
        return f"{self.current_part_id:04d}_{self.current_chapter_id:04d}_"

    def filtered_scenes(self) -> list:
        """現在のPart+Chapterに属するシーンの (元index, scene) リスト"""
        prefix = self.scene_prefix()
        return [(i, s) for i, s in enumerate(self.scenes)
                if s["name"].startswith(prefix)]

    def current_scene(self):
        if 0 <= self.selected_scene < len(self.scenes):
            return self.scenes[self.selected_scene]
        return None

    def select_scene(self, index: int):
        if 0 <= index < len(self.scenes):
            self.selected_scene = index
            self.selected_special = None

    def select_scene_by_name(self, name: str) -> bool:
        """シーン名で選択し、対応するPart/Chapter表示へ切り替える。"""
        for i, scene in enumerate(self.scenes):
            if scene.get("name") != name:
                continue
            self.select_scene(i)
            parsed = parse_scene_name(name)
            if parsed:
                part_id, chapter_id, _display = parsed
                if self.get_part(part_id):
                    self.current_part_id = part_id
                if self.get_chapter(part_id, chapter_id):
                    self.current_chapter_id = chapter_id
            return True
        return False

    def add_scene(self):
        prefix = self.scene_prefix()
        # 現在のチャプター内のシーン数をカウント
        existing_indices = [
            i for i, s in enumerate(self.scenes)
            if s["name"].startswith(prefix)
        ]
        existing = [self.scenes[i] for i in existing_indices]
        n = len(existing) + 1
        name = make_scene_name(self.current_part_id, self.current_chapter_id,
                               f"scene_{n:02d}")
        # 重複回避
        existing_names = {s["name"] for s in self.scenes}
        while name in existing_names:
            n += 1
            name = make_scene_name(self.current_part_id, self.current_chapter_id,
                                   f"scene_{n:02d}")
        scene = _new_scene(name)
        if self.selected_scene in existing_indices:
            insert_at = self.selected_scene + 1
        elif existing_indices:
            insert_at = existing_indices[-1] + 1
        else:
            insert_at = len(self.scenes)
            current_key = (self.current_part_id, self.current_chapter_id)
            for i, s in enumerate(self.scenes):
                parsed = parse_scene_name(s.get("name", ""))
                if parsed and (parsed[0], parsed[1]) > current_key:
                    insert_at = i
                    break
        self.scenes.insert(insert_at, scene)
        self.selected_scene = insert_at
        self.selected_special = None
        self.scene_gen += 1
        self.dirty = True

    def copy_scene(self):
        """現在のシーンを複製する。表示名を維持し新しいインクリメント番号を付与。"""
        scene = self.current_scene()
        if scene is None:
            return
        new_scene = copy.deepcopy(scene)
        # 表示名を取得
        disp = display_name(scene)
        # 現在のPart+Chapterのプレフィックスを使う
        existing_names = {s["name"] for s in self.scenes}
        # 同じ表示名で新しい名前を試行
        candidate = make_scene_name(self.current_part_id, self.current_chapter_id, disp)
        if candidate in existing_names:
            candidate = make_scene_name(self.current_part_id,
                                        self.current_chapter_id,
                                        f"{disp}_copy")
            n = 2
            while candidate in existing_names:
                candidate = make_scene_name(self.current_part_id,
                                            self.current_chapter_id,
                                            f"{disp}_copy{n}")
                n += 1
        new_scene["name"] = candidate
        idx = self.selected_scene + 1
        self.scenes.insert(idx, new_scene)
        self.selected_scene = idx
        self.selected_special = None
        self.scene_gen += 1
        self.dirty = True

    def delete_scene(self, index: int = None):
        """指定シーン（省略時は選択中）を削除する。最後のシーンは削除できない。"""
        if index is None:
            index = self.selected_scene
        if not (0 <= index < len(self.scenes)):
            return False
        if len(self.scenes) <= 1:
            return False
        removed = self.scenes.pop(index)
        # goto 参照のクリア
        removed_name = removed.get("name", "")
        for s in self.scenes:
            if s.get("goto") == removed_name:
                s["goto"] = ""
            for c in s.get("choices", []):
                if c.get("goto") == removed_name:
                    c["goto"] = ""
        if self.selected_scene >= len(self.scenes):
            self.selected_scene = len(self.scenes) - 1
        self.selected_special = None
        self.scene_gen += 1
        self.dirty = True
        return True

    def rename_scene(self, index: int, new_display: str):
        """シーンの表示名を変更する（goto参照も更新）"""
        if not (0 <= index < len(self.scenes)):
            return False
        scene = self.scenes[index]
        parsed = parse_scene_name(scene["name"])
        if parsed:
            old_name = scene["name"]
            new_name = make_scene_name(parsed[0], parsed[1], new_display)
            if old_name == new_name:
                return True
            # 重複チェック
            existing = {s["name"] for s in self.scenes}
            existing.discard(old_name)
            if new_name in existing:
                base_display = new_display
                n = 2
                while new_name in existing:
                    new_name = make_scene_name(
                        parsed[0], parsed[1], f"{base_display}_{n}")
                    n += 1
            # goto 参照を更新
            for s in self.scenes:
                if s.get("goto") == old_name:
                    s["goto"] = new_name
                for c in s.get("choices", []):
                    if c.get("goto") == old_name:
                        c["goto"] = new_name
            scene["name"] = new_name
            self.scene_gen += 1
            self.dirty = True
            return True
        return False

    def reorder_scenes(self, from_global: int, to_global: int):
        """シーンの並べ替え（グローバルインデックスで指定）"""
        if from_global == to_global:
            return
        if 0 <= from_global < len(self.scenes) and 0 <= to_global < len(self.scenes):
            item = self.scenes.pop(from_global)
            self.scenes.insert(to_global, item)
            # selected_scene を追跡
            if self.selected_scene == from_global:
                self.selected_scene = to_global
            elif from_global < self.selected_scene <= to_global:
                self.selected_scene -= 1
            elif to_global <= self.selected_scene < from_global:
                self.selected_scene += 1
            self.scene_gen += 1
            self.dirty = True

    def normalize_scene_order(self) -> bool:
        """Part/Chapter 表示順と内部シーン配列の順序を揃える。

        旧 add_scene は現在章のシーンでも内部配列の末尾へ追加していた。
        その状態だと一覧では正しく見えても、暗黙の次シーン遷移や
        背景/BGM継承が別章をまたいで解決されるため、読み込み時に正規化する。
        """
        part_order = {int(p.get("id", 0)): i
                      for i, p in enumerate(self.parts)}
        chapter_order = {
            (int(c.get("part_id", 0)), int(c.get("id", 0))): i
            for i, c in enumerate(self.chapters)
        }

        def _key(item):
            original_index, scene = item
            parsed = parse_scene_name(scene.get("name", ""))
            if not parsed:
                return (1, original_index, 0, 0)
            part_id, chapter_id, _display = parsed
            return (
                0,
                part_order.get(part_id, 10_000),
                chapter_order.get((part_id, chapter_id), 10_000),
                original_index,
            )

        before = [id(scene) for scene in self.scenes]
        ordered = [scene for _i, scene in sorted(enumerate(self.scenes),
                                                key=_key)]
        after = [id(scene) for scene in ordered]
        if before == after:
            return False
        selected_name = ""
        if 0 <= self.selected_scene < len(self.scenes):
            selected_name = self.scenes[self.selected_scene].get("name", "")
        self.scenes = ordered
        if selected_name:
            for i, scene in enumerate(self.scenes):
                if scene.get("name", "") == selected_name:
                    self.selected_scene = i
                    break
        self.scene_gen += 1
        return True

    # ── ファイル操作 ────────────────────────────────────────

    def save(self, path: str) -> bool:
        try:
            data = {
                "version": 4,
                "parts": self.parts,
                "chapters": self.chapters,
                "scenes": self.scenes,
                "title_config": self.title_config,
                "endings": self.endings,
                "character_position_memory": normalize_character_position_memory(
                    self.character_position_memory),
                "gallery_config": normalize_gallery_config(self.gallery_config),
                "extra_text_config": normalize_extra_text_config(
                    self.extra_text_config),
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.file_path = path
            self.dirty     = False
            return True
        except Exception:
            return False

    def load(self, path: str) -> bool:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            ver = data.get("version", 1)
            if ver == 1:
                data = {"version": 2, "scenes": [_migrate_v1(s) for s in data["scenes"]]}
                ver = 2
            if ver == 2:
                data = _migrate_v2_to_v3(data)
                ver = 3
            self.parts    = data.get("parts", [{"id": 1, "name": "Part 1"}])
            self.chapters = data.get("chapters", [{"id": 1, "part_id": 1, "name": "Chapter 1"}])
            self.scenes   = data["scenes"]
            _normalize_scene_char_colkeys(
                self.scenes, migrate_default_zero=ver <= 3)
            for scene in self.scenes:
                if isinstance(scene, dict):
                    scene.setdefault("bgm_stop", False)
                    scene.setdefault("bgm_loop", True)
                    scene.setdefault("bgm_fadeout_frames", 0)
                    scene.setdefault("auto_pause", False)
                    for key in ("char_l", "char_c", "char_r"):
                        cfg = scene.get(key)
                        if isinstance(cfg, dict):
                            cfg.setdefault("keep_anim", False)
                            cfg.setdefault("hold_motion_end", False)
            self.normalize_scene_order()
            self.title_config = data.get("title_config", {
                "bg_image": "", "bg_fullscreen": False,
                "bgm_file": "", "bgm_volume": 7, "bgm_loop": True,
                "button_colors": normalize_button_colors(),
            })
            # 旧プロジェクト互換: 欠けているキーを補完
            self.title_config.setdefault("bg_fullscreen", False)
            self.title_config.setdefault("bgm_file", "")
            self.title_config.setdefault("bgm_volume", 7)
            self.title_config.setdefault("bgm_loop", True)
            self.title_config["button_colors"] = normalize_button_colors(
                self.title_config.get("button_colors"))
            # title_text は廃止 (BG画像にタイトルを埋め込む運用)
            self.title_config.pop("title_text", None)
            self.endings  = data.get("endings", [])
            self.character_position_memory = normalize_character_position_memory(
                data.get("character_position_memory", {}))
            self.gallery_config = normalize_gallery_config(
                data.get("gallery_config", {}))
            self.extra_text_config = normalize_extra_text_config(
                data.get("extra_text_config", {}))
            self.selected_scene = 0
            self.active_tab     = 0
            self.file_path      = path
            self.dirty          = False
            self.scene_gen     += 1
            # current_part/chapter を最初の Part/Chapter に設定
            if self.parts:
                self.current_part_id = self.parts[0]["id"]
                chs = self.chapters_for_part(self.current_part_id)
                self.current_chapter_id = chs[0]["id"] if chs else 0
            return True
        except Exception:
            return False

    def reset(self):
        old_gen = self.scene_gen + 1
        self.__init__()
        self.scene_gen = old_gen


# ── v1 マイグレーション ──────────────────────────────────────────

def _migrate_v1(s: dict) -> dict:
    """schema v1（文字列 char_l/c/r）→ v2（dict）"""
    def _char_from_name(name: str, x: int) -> dict:
        c = _default_char(x, _CHAR_DEFAULT_Y)
        return c

    return {
        "name":          s.get("name", ""),
        "bg":            s.get("bg", ""),
        "bg_x": 0, "bg_y": 0, "bg_w": 0, "bg_h": 0, "bg_anim": {},
        "bg_fullscreen": False,
        "font_file": "", "font_size": 0,
        "char_l": (_char_from_name(s.get("char_l", ""), _CHAR_DEFAULT_X["l"])
                   if isinstance(s.get("char_l"), str)
                   else s.get("char_l", _default_char(_CHAR_DEFAULT_X["l"], _CHAR_DEFAULT_Y))),
        "char_c": (_char_from_name(s.get("char_c", ""), _CHAR_DEFAULT_X["c"])
                   if isinstance(s.get("char_c"), str)
                   else s.get("char_c", _default_char(_CHAR_DEFAULT_X["c"], _CHAR_DEFAULT_Y))),
        "char_r": (_char_from_name(s.get("char_r", ""), _CHAR_DEFAULT_X["r"])
                   if isinstance(s.get("char_r"), str)
                   else s.get("char_r", _default_char(_CHAR_DEFAULT_X["r"], _CHAR_DEFAULT_Y))),
        "speaker":    s.get("speaker", ""),
        "text":       s.get("text", ""),
        "goto":       s.get("goto", ""),
        "transition": s.get("transition", ""),
        "choices":    s.get("choices", []),
    }


# ── v2 → v3 マイグレーション ────────────────────────────────────

def _migrate_v2_to_v3(data: dict) -> dict:
    """v2 フラットシーン → v3 Part/Chapter/Scene 階層"""
    prefix = "0001_0001_"
    old_to_new = {}
    scenes = data.get("scenes", [])
    for s in scenes:
        old_name = s["name"]
        new_name = prefix + old_name
        old_to_new[old_name] = new_name
        s["name"] = new_name
    # goto 参照を更新
    for s in scenes:
        if s.get("goto") and s["goto"] in old_to_new:
            s["goto"] = old_to_new[s["goto"]]
        for c in s.get("choices", []):
            if c.get("goto") and c["goto"] in old_to_new:
                c["goto"] = old_to_new[c["goto"]]
    return {
        "version": 3,
        "parts": [{"id": 1, "name": "Part 1"}],
        "chapters": [{"id": 1, "part_id": 1, "name": "Chapter 1"}],
        "scenes": scenes,
    }
