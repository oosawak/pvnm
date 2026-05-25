"""
スクリプト変換とユーティリティ

JSONシナリオ形式 (v2):
{
  "scenes": [
    {
      "name": "scene_01",
      "bg":     "bg_classroom.png",
      "bg_x": 0, "bg_y": 0,
      "bg_anim": {},
      "char_l": { "file": "alice.png", "x": 60, "y": 3, ... },
      "char_c": { ... },
      "char_r": { ... },
      "steps": [
        { "op": "say",    "speaker": "Alice", "text": "Hello!" },
        { "op": "choice", "options": [{"label":"Yes","goto":"scene_02"}] },
        { "op": "goto",   "scene": "scene_02", "transition": "fade" },
        { "op": "end" }
      ]
    }
  ]
}
"""
import json


def from_editor_state(state) -> dict:
    """
    EditorState → スクリプト dict に変換する。
    視覚設定（bg/chars）はシーンに直接持たせ、
    stepsには台詞フロー制御のみを格納する。
    """
    scenes = []
    for i, s in enumerate(state.scenes):
        steps = []

        # セリフ: 空でも「クリック待ち」のために必ず say ステップを入れる
        steps.append({
            "op":      "say",
            "speaker": s.get("speaker", ""),
            "text":    s.get("text", ""),
        })

        # 選択肢 or goto / end
        choices = s.get("choices", [])
        if choices:
            steps.append({"op": "choice", "options": [
                {"label": c.get("label", ""), "goto": c.get("goto", "")}
                for c in choices
            ]})
        else:
            explicit_goto = s.get("goto", "")
            goto_ending   = s.get("goto_ending", "")
            trans         = s.get("transition", "")
            if explicit_goto:
                step = {"op": "goto", "scene": explicit_goto}
                if trans:
                    step["transition"] = trans
                steps.append(step)
            elif goto_ending:
                # GOTO ENDING is handled by VNPlayer after the scene steps are
                # exhausted. Do not append the automatic "next scene" goto here,
                # otherwise the player never reaches that ending branch.
                pass
            elif i + 1 < len(state.scenes):
                step = {"op": "goto", "scene": state.scenes[i + 1]["name"]}
                if trans:
                    step["transition"] = trans
                steps.append(step)
            else:
                steps.append({"op": "end"})

        scenes.append({
            "name":          s["name"],
            # 視覚設定をそのまま引き継ぐ
            "bg":            s.get("bg", ""),
            "bg_x":          s.get("bg_x", 0),
            "bg_y":          s.get("bg_y", 0),
            "bg_w":          s.get("bg_w", 0),
            "bg_h":          s.get("bg_h", 0),
            "bg_anim":       s.get("bg_anim", {}),
            "bg_fullscreen":   s.get("bg_fullscreen", False),
            "bg_hide":         s.get("bg_hide", False),
            "bg_above_dialog": s.get("bg_above_dialog", False),
            "char_l":        s.get("char_l", {}),
            "char_c":        s.get("char_c", {}),
            "char_r":        s.get("char_r", {}),
            "font_file":     s.get("font_file", ""),
            "font_size":     s.get("font_size", 0),
            "palette_file":  s.get("palette_file", ""),
            "palette":       s.get("palette", []),
            # オーディオ
            "bgm_file":      s.get("bgm_file", ""),
            "bgm_volume":    s.get("bgm_volume", 7),
            "bgm_stop":      s.get("bgm_stop", False),
            "bgm_loop":      bool(s.get("bgm_loop", True)),
            "bgm_fadeout_frames": s.get("bgm_fadeout_frames", 0),
            "se_file":       s.get("se_file", ""),
            "se_volume":     s.get("se_volume", 7),
            "se_repeat":     s.get("se_repeat", 0),
            # エンディング
            "goto_ending":   s.get("goto_ending", ""),
            "hide_dialog":   s.get("hide_dialog", False),
            "auto_pause":    bool(s.get("auto_pause", False)),
            "steps":         steps,
        })

    return {"scenes": scenes}


def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(script: dict, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)


def build_index(script: dict) -> dict:
    """scene名 → scene dict のインデックスを作る"""
    return {s["name"]: s for s in script["scenes"]}
