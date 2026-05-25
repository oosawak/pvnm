# 画面と基本操作

このページでは、PVNMを起動したあとに見る場所と、基本的な操作の流れを説明します。

## 起動後に見る場所

起動すると、左にシーン一覧、中央にプレビュー、右にフィールド編集パネル、下部にツールバーが表示されます。

| 場所 | 役割 |
| --- | --- |
| 下部ツールバー | `SCENE` / `FLOW` 切り替え、ファイル名表示、`IMPORT MD`、`SETTINGS`、`OPEN`、`QUIT`、`PLAY` |
| シーン一覧 | Part / Chapterの切り替え、シーン選択、`+ADD`、`COPY`、`DEL` |
| 編集パネル | 選択中シーンの背景、立ち絵、テキスト、BGM、SE、分岐などを編集する |
| SETTINGS | タイトル、エンディング、色、EXTRAS、エクスポートなどを設定する |

## 基本ワークフロー

1. `Cmd/Ctrl+N` で新規プロジェクトを作るか、`OPEN` で既存プロジェクトを開く。
2. シーン一覧の `+ADD` でシーンを追加する。
3. シーンごとにテキスト、背景、立ち絵、BGM、SE、分岐を設定する。
4. `PLAY` でプレビューする。
5. `Cmd/Ctrl+S`、または `SETTINGS > PROJECT > SAVE PROJECT` で保存する。
6. `SETTINGS` の `EXPORT` から目的の形式へ書き出す。

## SETTINGS

`SETTINGS` には次の項目があります。

| 項目 | できること |
| --- | --- |
| `PROJECT` | プロジェクトの基本情報を確認、編集する |
| `TITLE CONFIG` | タイトル画面を設定する |
| `ENDING CONFIG` | エンディングを登録、編集する |
| `CG GALLERY` | EXTRAS内のCGギャラリー画像を設定する |
| `EXTRA TEXT` | EXTRAS内のテキストを設定する |
| `COLOR CONFIG` | UI全体の色を設定する |
| `SPEAKER COLORS` | 話者ごとの名前色、本文色を設定する |
| `TOOLS` | 補助ツールを開く |
| `EXPORT` | 各形式へ書き出す |

## キーボードショートカット

| 操作 | macOS | Windows |
| --- | --- | --- |
| NEW | `Cmd+N` | `Ctrl+N` |
| OPEN | `Cmd+O` | `Ctrl+O` |
| SAVE | `Cmd+S` | `Ctrl+S` |
| SAVE AS | `Cmd+Shift+S` | `Ctrl+Shift+S` |
| PLAY | `1` | `1` |
| QUIT | `Cmd+Q` | `Ctrl+Q` |
| Export PYXAPP | `Cmd+E` | `Ctrl+E` |
| Export macOS APP | `Cmd+Shift+E` | `Ctrl+Shift+E` |
| Export Web HTML | `Cmd+Option+E` | `Ctrl+Alt+E` |
| Export Android Project | `Cmd+Option+Shift+E` | `Ctrl+Alt+Shift+E` |

`SETTINGS`、`IMPORT MD`、`+ADD`、`COPY`、`DEL`、`WINDOWS EXE`、`ANDROID APK DEBUG`、`ANDROID APK RELEASE` は、現状では画面上のボタンまたは `SETTINGS > EXPORT` から実行します。

## プレイヤー操作

書き出したゲーム内では、クリック、Enter、Spaceでテキスト送りを行います。選択肢が表示されている場面では、選択肢をクリックして分岐します。
