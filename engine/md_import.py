"""Markdown 形式のシナリオを EditorState に取り込む。

書式:
    # PartName              … Part を開始
    ## ChapterName          … Chapter を開始
    ### SceneName           … 次のシーンの表示名 (省略時は scene_NN)
    話者：テキスト           … speaker + text のシーン
    話者「テキスト」          … speaker + text のシーン (鍵括弧版)
    話者：「複数行           … speaker + text のシーン (鍵括弧内は改行可)
    のテキスト」
    （話者なしの段落）        … 地の文 (speaker は空)
    - ラベル                … 直前のシーンの選択肢 (連続行=複数選択肢)

空行で段落を区切る。選択肢の goto 先は空にしてインポートし、
PVNM 上で個別に紐付ける運用とする。
"""
import re
from editor_state import EditorState, make_scene_name, _new_scene


# 「話者：「複数行テキスト」」(全角/半角コロン + 鍵括弧、改行可)
_DLG_COLON_BRACKET = re.compile(
    r"^([^\s「」:：]{1,32})[：:]「([\s\S]+)」$")
# 「話者：テキスト」「話者:テキスト」(全角/半角コロン、単一行)
_DLG_COLON   = re.compile(r"^([^\s「」:：]{1,32})[：:]\s*(.*)$")
# 「話者「テキスト」」(単一行)
_DLG_BRACKET = re.compile(r"^([^\s「」:：]{1,32})「(.+)」$")
# 「- 選択肢」「* 選択肢」
_CHOICE      = re.compile(r"^[-*]\s+(.+)$")


def parse_markdown(text: str) -> dict:
    """Markdown を解析し parts/chapters/scenes の辞書を返す。"""
    parts: list[dict] = []
    chapters: list[dict] = []
    scenes: list[dict] = []

    state = {
        "pid": 0,
        "cid": 0,
        "scene_n": 0,
        "pending_name": None,  # ### で指定された次シーンの表示名
        "last_scene": None,    # choices 付与対象
    }
    para_lines: list[str] = []
    pending_choices: list[str] = []

    def ensure_part(name: str = ""):
        state["pid"] = (max((p["id"] for p in parts), default=0) + 1)
        parts.append({"id": state["pid"], "name": name or f"Part {state['pid']}"})
        state["cid"] = 0
        state["scene_n"] = 0

    def ensure_chapter(name: str = ""):
        if state["pid"] == 0:
            ensure_part()
        existing = [c["id"] for c in chapters if c["part_id"] == state["pid"]]
        state["cid"] = (max(existing, default=0) + 1)
        chapters.append({
            "id": state["cid"],
            "part_id": state["pid"],
            "name": name or f"Chapter {state['cid']}",
        })
        state["scene_n"] = 0

    def add_scene(speaker: str, text: str):
        if state["cid"] == 0:
            ensure_chapter()
        state["scene_n"] += 1
        disp = state["pending_name"] or f"scene_{state['scene_n']:02d}"
        state["pending_name"] = None
        full = make_scene_name(state["pid"], state["cid"], disp)
        # 重複回避
        existing_names = {s["name"] for s in scenes}
        n = state["scene_n"]
        while full in existing_names:
            n += 1
            full = make_scene_name(state["pid"], state["cid"],
                                   f"scene_{n:02d}")
        scn = _new_scene(full)
        scn["speaker"] = speaker
        scn["text"] = text
        scenes.append(scn)
        state["last_scene"] = scn

    def flush_paragraph():
        if not para_lines:
            return
        line = "\n".join(para_lines).strip()
        para_lines.clear()
        if not line:
            return
        # コロン+鍵括弧 (改行可) を最優先で判定
        m = _DLG_COLON_BRACKET.match(line)
        if m:
            add_scene(m.group(1).strip(), m.group(2).strip())
            return
        # 鍵括弧形式を優先 (コロンを含む台詞でも誤判定しない)
        m = _DLG_BRACKET.match(line)
        if m:
            add_scene(m.group(1).strip(), m.group(2).strip())
            return
        m = _DLG_COLON.match(line)
        if m:
            add_scene(m.group(1).strip(), m.group(2).strip())
            return
        add_scene("", line)

    def flush_choices():
        if pending_choices and state["last_scene"] is not None:
            state["last_scene"]["choices"] = [
                {"label": lbl, "goto": ""} for lbl in pending_choices
            ]
        pending_choices.clear()

    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.rstrip()

        if line.startswith("# ") or line == "#":
            flush_paragraph()
            flush_choices()
            ensure_part(line[2:].strip() if len(line) > 1 else "")
            continue
        if line.startswith("## "):
            flush_paragraph()
            flush_choices()
            ensure_chapter(line[3:].strip())
            continue
        if line.startswith("### "):
            flush_paragraph()
            flush_choices()
            state["pending_name"] = line[4:].strip() or None
            continue

        m = _CHOICE.match(line)
        if m:
            flush_paragraph()
            pending_choices.append(m.group(1).strip())
            continue

        if not line:
            flush_paragraph()
            flush_choices()
            continue

        # 通常行: 直前が選択肢ブロックなら先に確定
        if pending_choices:
            flush_choices()
        para_lines.append(line)

    flush_paragraph()
    flush_choices()

    # 最低限の構造を保証
    if not parts:
        parts.append({"id": 1, "name": "Part 1"})
    if not chapters:
        chapters.append({"id": 1, "part_id": parts[0]["id"], "name": "Chapter 1"})
    if not scenes:
        scenes.append(_new_scene(make_scene_name(
            parts[0]["id"], chapters[0]["id"], "scene_01")))

    return {"parts": parts, "chapters": chapters, "scenes": scenes}


def import_into_state(state: EditorState, text: str) -> tuple[int, int, int]:
    """Markdown をパースして state にロードする。

    Returns: (parts, chapters, scenes) の件数
    """
    result = parse_markdown(text)
    state.parts    = result["parts"]
    state.chapters = result["chapters"]
    state.scenes   = result["scenes"]
    state.current_part_id    = state.parts[0]["id"]
    chs = state.chapters_for_part(state.current_part_id)
    state.current_chapter_id = chs[0]["id"] if chs else 0
    state.selected_scene     = 0
    state.selected_special   = None
    state.scene_gen         += 1
    state.dirty              = True
    return len(result["parts"]), len(result["chapters"]), len(result["scenes"])
