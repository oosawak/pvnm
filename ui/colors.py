# Pyxel パレットの「役割 → インデックス」マッピング
#
# マスターパレット (256色) のうち、UIで意味付けされた色のインデックスを定義する。
# デフォルトでは 0-15 のエディタ予約 UI パレットを使うが、settings.json の
# `dialog_role_indices` キーで任意のマスターパレットインデックス (0-255) に
# 変更できる。`apply_role_indices()` で各モジュールへ伝播し、ライブ反映する。
#
# 命名規則:
#   EDIT_* — エディタ画面 (シーンリスト/プロパティパネル/ツールバー、設定モーダル、
#            共有ダイアログ chrome 等) のみで使う色。プレイ画面には影響しない。
#   PLAY_* — プレイ画面 (背景、ダイアログボックス、選択肢、話者バッジ等) のみで
#            使う色。エディタ画面には影響しない。
#
# settings.json 例:
#   {
#     "dialog_role_indices": {
#       "EDIT_TEXT": 7, "PLAY_DIALOG_BG": 4, ...
#     }
#   }

import os
import json

# 旧 (接頭辞なし) → 新キー名のマイグレーションマップ。
# 既存 settings.json をそのまま読めるように、ロード時に旧名を新名に振り分ける。
# 共有役割 (EDIT/PLAY 両方に存在するもの) は両側へコピーする。
_LEGACY_RENAME = {
    # editor-only
    "PANEL":        ["EDIT_PANEL"],
    "BTN_BG":       ["EDIT_BTN_BG"],
    "BTN_HOVER":    ["EDIT_BTN_HOVER"],
    "TITLE_BG":     ["EDIT_TITLE_BG"],
    "PREVIEW_BG":   ["EDIT_PREVIEW_BG", "PLAY_BG"],  # 旧 PREVIEW_BG はプレイ背景兼用だった
    # play-only
    "DIALOG_BG":    ["PLAY_DIALOG_BG"],
    "SPEAKER_FG":   ["PLAY_SPEAKER_FG"],
    "SPEAKER_BG":   ["PLAY_SPEAKER_BG"],
    "CHOICE_BG":    ["PLAY_CHOICE_BG"],
    "CHOICE_HOVER": ["PLAY_CHOICE_HOVER"],
    # shared → 両方へ複製
    "BG":           ["EDIT_BG", "PLAY_BG"],
    "BORDER":       ["EDIT_BORDER", "PLAY_BORDER"],
    "TEXT":         ["EDIT_TEXT", "PLAY_TEXT"],
    "TEXT_DIM":     ["EDIT_TEXT_DIM", "PLAY_TEXT_DIM"],
    "ACCENT":       ["EDIT_ACCENT", "PLAY_ACCENT"],
    "HIGHLIGHT":    ["EDIT_HIGHLIGHT", "PLAY_HIGHLIGHT"],
}

# 役割名 → デフォルトインデックス
_DEFAULTS = {
    # ── EDIT (エディタ画面) ─────────────────────────────────
    "EDIT_BG":           0,
    "EDIT_PANEL":        1,
    "EDIT_BTN_BG":       2,
    "EDIT_PREVIEW_BG":   3,
    "EDIT_BORDER":       5,
    "EDIT_TEXT_DIM":     6,
    "EDIT_TEXT":         7,
    "EDIT_BTN_HOVER":    8,
    "EDIT_ACCENT":       9,
    "EDIT_HIGHLIGHT":    10,
    "EDIT_TITLE_BG":     13,
    # ── PLAY (プレイ画面) ───────────────────────────────────
    "PLAY_BG":           0,
    "PLAY_DIALOG_BG":    4,
    "PLAY_BORDER":       5,
    "PLAY_TEXT_DIM":     6,
    "PLAY_TEXT":         7,
    "PLAY_ACCENT":       9,
    "PLAY_HIGHLIGHT":    10,
    "PLAY_SPEAKER_FG":   11,
    "PLAY_SPEAKER_BG":   12,
    "PLAY_CHOICE_BG":    14,
    "PLAY_CHOICE_HOVER": 15,
}


def _load_role_indices() -> dict:
    """settings.json から role → index マッピングを読み込む。

    旧名 (BG / TEXT 等) は `_LEGACY_RENAME` に従って自動的に新名へ振り分ける。
    プロジェクトルートは ui/ の親ディレクトリと仮定する。失敗してもデフォルトを
    返すだけなので副作用はない。
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(project_root, "settings.json")
    result = dict(_DEFAULTS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        overrides = data.get("dialog_role_indices") or {}
        if isinstance(overrides, dict):
            for k, v in overrides.items():
                if not (isinstance(v, int) and 0 <= v <= 255):
                    continue
                if k in result:
                    result[k] = v
                elif k in _LEGACY_RENAME:
                    for new_key in _LEGACY_RENAME[k]:
                        if new_key in result:
                            result[new_key] = v
    except Exception:
        pass
    return result


_indices = _load_role_indices()

EDIT_BG           = _indices["EDIT_BG"]
EDIT_PANEL        = _indices["EDIT_PANEL"]
EDIT_BTN_BG       = _indices["EDIT_BTN_BG"]
EDIT_PREVIEW_BG   = _indices["EDIT_PREVIEW_BG"]
EDIT_BORDER       = _indices["EDIT_BORDER"]
EDIT_TEXT_DIM     = _indices["EDIT_TEXT_DIM"]
EDIT_TEXT         = _indices["EDIT_TEXT"]
EDIT_BTN_HOVER    = _indices["EDIT_BTN_HOVER"]
EDIT_ACCENT       = _indices["EDIT_ACCENT"]
EDIT_HIGHLIGHT    = _indices["EDIT_HIGHLIGHT"]
EDIT_TITLE_BG     = _indices["EDIT_TITLE_BG"]

PLAY_BG           = _indices["PLAY_BG"]
PLAY_DIALOG_BG    = _indices["PLAY_DIALOG_BG"]
PLAY_BORDER       = _indices["PLAY_BORDER"]
PLAY_TEXT_DIM     = _indices["PLAY_TEXT_DIM"]
PLAY_TEXT         = _indices["PLAY_TEXT"]
PLAY_ACCENT       = _indices["PLAY_ACCENT"]
PLAY_HIGHLIGHT    = _indices["PLAY_HIGHLIGHT"]
PLAY_SPEAKER_FG   = _indices["PLAY_SPEAKER_FG"]
PLAY_SPEAKER_BG   = _indices["PLAY_SPEAKER_BG"]
PLAY_CHOICE_BG    = _indices["PLAY_CHOICE_BG"]
PLAY_CHOICE_HOVER = _indices["PLAY_CHOICE_HOVER"]


def role_names() -> list:
    """役割名の一覧 (定義順)。設定 UI の表示順として使う。"""
    return list(_DEFAULTS.keys())


def edit_role_names() -> list:
    """EDIT_* 役割のみ。"""
    return [k for k in _DEFAULTS if k.startswith("EDIT_")]


def play_role_names() -> list:
    """PLAY_* 役割のみ。"""
    return [k for k in _DEFAULTS if k.startswith("PLAY_")]


def default_index(role: str) -> int:
    """指定役割のデフォルトインデックス (見つからなければ 0)。"""
    return _DEFAULTS.get(role, 0)


def current_index(role: str) -> int:
    """settings 読込後の現在のインデックス。"""
    return _indices.get(role, _DEFAULTS.get(role, 0))


def apply_role_indices(new_indices: dict) -> None:
    """役割→indexマッピングを全コンシューマモジュールへ即時反映する。

    `from ui.colors import *` 経由で取り込まれた定数 (例: EDIT_TEXT) は
    各モジュールの名前空間にコピーされるため、_indices だけ更新しても
    既に import 済みのモジュールには反映されない。本関数は sys.modules
    を走査し、該当属性 (整数 0–255) を持つモジュールに対して setattr で
    新しい値を書き込むことで、再起動なしの「ライブ反映」を実現する。

    旧キー (TEXT 等) も `_LEGACY_RENAME` に従って新キーへ振り分けるので、
    古い形式の入力でも動作する。
    """
    import sys

    if not isinstance(new_indices, dict):
        return

    # 1) 旧キーを新キーへ正規化
    normalized: dict = {}
    for role, idx in new_indices.items():
        if not (isinstance(idx, int) and 0 <= idx <= 255):
            continue
        if role in _DEFAULTS:
            normalized[role] = idx
        elif role in _LEGACY_RENAME:
            for new_key in _LEGACY_RENAME[role]:
                if new_key in _DEFAULTS:
                    normalized[new_key] = idx

    # 2) ui.colors 自身の状態を更新
    for role, idx in normalized.items():
        _indices[role] = idx
        globals()[role] = idx

    # 3) 既に import 済みの全モジュールに伝播
    role_keys = tuple(_DEFAULTS.keys())
    for mod in list(sys.modules.values()):
        if mod is None:
            continue
        for role in role_keys:
            try:
                cur = getattr(mod, role, None)
            except Exception:
                continue
            if isinstance(cur, int) and 0 <= cur <= 255:
                new = _indices.get(role)
                if isinstance(new, int) and cur != new:
                    try:
                        setattr(mod, role, new)
                    except Exception:
                        pass
