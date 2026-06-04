from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from editor_state import EditorState, _new_scene, make_scene_name


ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_PATH = os.path.join(ROOT, "coastal_station.pvnm")
BACKGROUND = "assets/coastal_station_dusk.png"
YUMA_STAND = "assets/chars/yuma.png"
ENDING_NAME = "潮待ちの夜明け"


def scene_name(display: str) -> str:
    return make_scene_name(1, 1, display)


def make_scene(display: str, speaker: str, text: str, **overrides) -> dict:
    scene = _new_scene(scene_name(display))
    scene["speaker"] = speaker
    scene["text"] = text
    scene["bg"] = BACKGROUND
    scene["bg_fullscreen"] = True
    scene["transition"] = "fade"
    scene.update(overrides)
    return scene


def yuma_stand(**overrides) -> dict:
    cfg = {
        "file": YUMA_STAND,
        "hide": False,
        "x": 272,
        "y": 38,
        "scale": 0.2,
        "flip_h": False,
        "flip_v": False,
        "colkey": -2,
        "border_w": 0,
        "border_col": 7,
        "anim": {},
        "keep_anim": False,
        "hold_motion_end": False,
    }
    cfg.update(overrides)
    return cfg


def main() -> None:
    state = EditorState()
    state.parts = [{"id": 1, "name": "潮待ちステーション"}]
    state.chapters = [{"id": 1, "part_id": 1, "name": "第一章 消えた最終電車"}]
    state.current_part_id = 1
    state.current_chapter_id = 1
    state.title_config = {
        "bg_image": BACKGROUND,
        "bg_fullscreen": True,
        "bgm_file": "",
        "bgm_volume": 7,
        "bgm_loop": True,
    }

    scenes = [
        make_scene(
            "00_prologue",
            "",
            "潮風の匂いがする無人駅に、最終電車の発車ベルだけが残っていた。",
            goto=scene_name("01_arrival"),
        ),
        make_scene(
            "01_arrival",
            "澪",
            "また記録が消えてる。昨日の二十三時四十二分、ここに電車が来たはずなのに。",
            goto=scene_name("02_terminal"),
        ),
        make_scene(
            "02_terminal",
            "悠真",
            "改札の端末は生きてる。けど、行き先表示が全部「灯台前」になってる。",
            char_c=yuma_stand(),
            goto=scene_name("03_choice"),
        ),
        make_scene(
            "03_choice",
            "澪",
            "線路沿いに灯台へ向かうか、駅員室のログを先に見るか。どちらか決めよう。",
            choices=[
                {"label": "灯台へ向かう", "goto": scene_name("04_lighthouse")},
                {"label": "駅員室を調べる", "goto": scene_name("06_office")},
            ],
        ),
        make_scene(
            "04_lighthouse",
            "悠真",
            "灯台の足元に切符が落ちてる。日付は明日だ。",
            goto=scene_name("05_signal"),
        ),
        make_scene(
            "05_signal",
            "澪",
            "つまり、電車は未来から来た？ それとも、私たちの時間だけが遅れている？",
            goto=scene_name("05b_nagi"),
        ),
        make_scene(
            "05b_nagi",
            "凪",
            "待って。灯台の鍵なら私が預かってる。最終電車が消えた夜、駅長はここに来た。",
            goto=scene_name("08_merge"),
        ),
        make_scene(
            "06_office",
            "悠真",
            "駅員室の録音が残ってる。「海霧が出たら、乗客をホームに残すな」って。",
            goto=scene_name("07_map"),
        ),
        make_scene(
            "07_map",
            "澪",
            "古い路線図に、廃止された分岐がある。灯台の下を通って海へ抜けてる。",
            goto=scene_name("07b_ren"),
        ),
        make_scene(
            "07b_ren",
            "蓮",
            "その分岐、記録上は存在しない。でも、乗客名簿には同じ時刻の空白が三年分ある。",
            goto=scene_name("08_merge"),
        ),
        make_scene(
            "08_merge",
            "悠真",
            "凪の鍵と蓮の名簿がそろった。どちらにしても答えは灯台の下だ。",
            goto=scene_name("09_truth"),
        ),
        make_scene(
            "09_truth",
            "澪",
            "地下ホームだ。凪、蓮、見て。ここに、消えた乗客たちの名前が全部刻まれている。",
            goto=scene_name("10_final_choice"),
        ),
        make_scene(
            "10_final_choice",
            "悠真",
            "ベルが鳴った。扉が開く。乗れば真相に届く。残れば、四人でこの駅を止められるかもしれない。",
            choices=[
                {"label": "電車に乗る", "goto": scene_name("11_board_train")},
                {"label": "駅に残る", "goto": scene_name("12_stay_station")},
            ],
        ),
        make_scene(
            "11_board_train",
            "澪",
            "行こう。消えた人たちが向かった先を、この目で見る。凪、蓮、記録をお願い。",
            goto=scene_name("13_end"),
        ),
        make_scene(
            "12_stay_station",
            "澪",
            "私は残る。悠真は端末を、凪は鍵を、蓮は名簿を。次の誰かを止めよう。",
            goto=scene_name("13_end"),
        ),
        make_scene(
            "13_end",
            "",
            "潮が満ち、駅名標の文字が月明かりに沈んでいく。",
            goto_ending=ENDING_NAME,
        ),
    ]
    state.scenes = scenes
    state.endings = [
        {
            "name": ENDING_NAME,
            "slides": [
                {
                    "image": BACKGROUND,
                    "time": 0.0,
                    "effect": "fade",
                    "effect_duration": 1.0,
                    "duration": 8.0,
                }
            ],
            "credits": "潮待ちステーション\n\n企画・シナリオ: PVNM Sample\n背景: generated with built-in image_gen\n\nEND",
            "font_file": "",
            "font_size": 14,
            "scroll_speed": 1.0,
            "bgm_file": "",
            "bgm_volume": 7,
            "bgm_loop": False,
            "goto_ending": "",
        }
    ]
    state.extra_text_config = {
        "pages": [
            {
                "title": "設定メモ",
                "text": "海霧の夜だけ現れる無人駅。最終電車に乗った人は、記録からも記憶からも少しずつ消えていく。凪は駅員見習い、蓮は町の記録係として、澪と悠真の調査に加わる。",
                "font_file": "",
                "font_size": 14,
            }
        ]
    }
    if not state.save(PROJECT_PATH):
        raise SystemExit(f"failed to save {PROJECT_PATH}")
    print(PROJECT_PATH)


if __name__ == "__main__":
    main()
