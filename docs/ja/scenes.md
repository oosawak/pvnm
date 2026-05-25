# シーン制作

このページでは、PVNMでシーンを作るときの主な編集項目を説明します。右側の編集パネルは `SCENE`、`CHARACTERS`、`CHOICES` の3タブに分かれています。

## シーン一覧

左側の `SCENES` では、現在のPart / Chapterに属するシーンを管理します。

| 操作 | 内容 |
| --- | --- |
| `[P:...]` | Partを選ぶ |
| `[C:...]` | Chapterを選ぶ |
| `<` / `>` | 前後のPart / Chapterへ移動する |
| `+ADD` | 現在のPart / Chapterにシーンを追加する |
| `COPY` | 選択中シーンを複製する |
| `DEL` | 選択中シーンを削除する |

シーン名は内部的にはPart / Chapterの番号を含みますが、画面上では表示名を中心に扱います。

## SCENEタブ

`SCENE` タブでは、会話本文、背景、音声、通常遷移を設定します。

### TEXT

| 項目 | 内容 |
| --- | --- |
| `[SPEAKER]` | 名前欄に表示する話者名 |
| `[EDIT_TEXT]` | メッセージウィンドウに表示する本文 |
| `TEXT SIZE` | このシーンの本文サイズ。リセットすると既定値に戻る |

`TEXT SIZE` はBDFフォントサイズから選びます。通常は既定値のままで問題ありません。

### BACKGROUND

| 項目 | 内容 |
| --- | --- |
| `[BACKGROUND IMAGE]` | 背景画像を選ぶ |
| `BACKGROUND FULLSCREEN` | 背景を画面全体に合わせて表示する |
| `BG SAFE AREA` | 背景をダイアログ上の領域に収める |
| `HIDE BACKGROUND` | 背景の継承を切り、背景を非表示にする |
| `HIDE DIALOG` | メッセージウィンドウを非表示にする |
| `TRANSITION` | 次シーンへの遷移をfadeにする |

背景画像が空の場合は、前のシーンの背景を引き継ぎます。`HIDE BACKGROUND` をONにすると、このシーンで背景を明示的に消します。

### AUDIO

| 項目 | 内容 |
| --- | --- |
| `[BACKGROUND MUSIC FILE]` | BGMを選ぶ |
| `STOP BGM` | 継承中のBGMを停止する |
| `PLAY BGM ONCE` | BGMをループせず、このシーンで一度だけ再生する |
| `BACKGROUND MUSIC VOLUME` | BGM音量 |
| `BGM FADE OUT` | 遷移時のBGMフェードアウトフレーム数 |
| `[SOUND EFFECT FILE]` | シーン開始時に鳴らすSEを選ぶ |
| `SOUND EFFECT VOLUME` | SE音量 |
| `SOUND EFFECT REPEAT (0=once)` | SEの繰り返し回数。0は1回再生 |

BGMが空の場合は、前のシーンのBGMを引き継ぎます。SEはそのシーンで鳴る効果音で、BGMのようには継承されません。

### FLOW

| 項目 | 内容 |
| --- | --- |
| `[GOTO]` | 通常進行で移動する次のシーン |
| `[GOTO ENDING]` | 到達するエンディング |
| `PAUSE AUTO` | AUTO再生中でも、このシーンだけAUTOを一時停止する |

一本道の進行では `[GOTO]` を使います。エンディングへ進ませるシーンでは `[GOTO ENDING]` を設定します。

## CHARACTERSタブ

`CHARACTERS` タブでは、左、中央、右の3スロットに立ち絵を設定します。

| サブタブ | 位置 |
| --- | --- |
| `LEFT` | 左スロット |
| `CENTER` | 中央スロット |
| `RIGHT` | 右スロット |

各スロットで設定できる項目は同じです。

| 項目 | 内容 |
| --- | --- |
| `[FILE]` | 立ち絵画像を選ぶ |
| `HIDE CHARACTER` | このスロットの継承を切り、非表示にする |
| `[STORE POS]` | 現在のx/y/scaleをスロットごとに記憶する |
| `[APPLY POS]` | 記憶したx/y/scaleを適用する |
| `CHARACTER SCALING` | 立ち絵の倍率 |
| `horizontal axis position` | 横位置 |
| `vertical axis position` | 縦位置 |
| `COLOR KEY` | 透過色。`AUTO`、`NONE`、0-255のパレット番号 |
| `FLIP HORIZONTAL` | 左右反転 |
| `FLIP VERTICAL` | 上下反転 |

立ち絵のファイルが空の場合は、前のシーンの同じスロットを引き継ぎます。`HIDE CHARACTER` をONにすると、そのスロットを明示的に消します。

## アニメーション

`CHARACTERS` タブの下部には、立ち絵スロットごとのアニメーション項目があります。

| 項目 | 内容 |
| --- | --- |
| `KEEP ANIM NEXT` | アニメーション設定を次シーンにも引き継ぐ |
| `HOLD MOTION END` | 移動終了位置を次シーンへ引き継ぐ |
| `CLEAR ANIM` | アニメーション設定を消す |
| `SHAKE AMPLITUDE` | 揺れ幅 |
| `SHAKE SPEED` | 揺れ速度 |
| `ROTATION SPEED` | 回転速度 |
| `SCALE START` | 拡大縮小の開始倍率 |
| `SCALE END` | 拡大縮小の終了倍率 |
| `SCALE FRAMES` | 拡大縮小にかけるフレーム数 |
| `MOTION X` | 横方向の移動量 |
| `MOTION Y` | 縦方向の移動量 |
| `MOTION FRAMES` | 移動にかけるフレーム数 |
| `FLIPBOOK INTERVAL` | フリップブック画像の切り替え間隔 |

通常、アニメーションはそのシーン限りです。次のシーンへ演出を残したい場合だけ `KEEP ANIM NEXT` や `HOLD MOTION END` を使います。

## CHOICESタブ

`CHOICES` タブでは、選択肢による分岐を設定します。

| 操作 | 内容 |
| --- | --- |
| `+ ADD CHOICE` | 選択肢を追加する |
| `x` | 選択肢を削除する |
| `[LABEL]` | 選択肢として表示する文言 |
| `[GOTO]` | その選択肢を選んだときの移動先シーン |

選択肢は最大8個まで編集できます。通常進行は `SCENE` タブの `[GOTO]`、プレイヤーに選ばせたい分岐は `CHOICES` タブを使います。

## プレビュー

`PLAY` または `1` キーで現在のプロジェクトをプレイヤーとして確認できます。テキスト送り、分岐、音声、画像表示、エンディング到達、EXTRASの開放条件は、配布前に通しで確認してください。
