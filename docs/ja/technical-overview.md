# PVNM技術設計概要

このページは、PVNMを改造する開発者、エクスポート不具合を追う人、画像処理やランタイムの設計意図を知りたい人向けの入口です。

操作手順ではなく、PVNM内部で何が起きているかを説明します。特に詳しい内容は次のページに分けています。

| テーマ | ページ |
| --- | --- |
| 256色制約、シーンパレット、減色、画像キャッシュ | [減色・パレット・画像キャッシュ設計](technical-palette.md) |
| VN Palette Toolの各設定、補正、ディザリング、0-10系パラメータ | [VN Palette Tool詳細設計](technical-vn-palette-tool.md) |
| `.pyxapp`、Web、Android、Windows、macOSの書き出し構造 | [エクスポート設計](technical-export.md) |

## 全体像

PVNMは大きく分けると、編集用アプリ、プレイヤーランタイム、エクスポートパイプラインの3層でできています。

| 層 | 主な責務 | 代表ファイル |
| --- | --- | --- |
| 編集用アプリ | `.pvnm`プロジェクトの編集、画面UI、素材選択、設定保存 | `main.py`、`editor_state.py`、`ui/` |
| プレイヤーランタイム | シーン再生、入力、画像表示、音声、セーブ、タイトル、EXTRAS | `engine/player.py`、`engine/standalone_app.py`、`engine/audio.py` |
| エクスポート | ランタイムツリー生成、画像キャッシュ事前ビルド、各形式への包装 | `engine/export.py`、`engine/export_worker.py`、`engine/export_prebuild_worker.py` |

編集時のデータは `EditorState` として扱われ、書き出し時に `engine.script.from_editor_state()` でランタイム向けの `story.json` 相当へ変換されます。エクスポート成果物には、プレイヤーに必要なPythonコード、設定JSON、フォント、マスターパレット、画像キャッシュ、音声、Web/Android用のJavaScriptブリッジなどが入ります。

## Pyxelの制約が設計を決めている

PVNMの中心的な制約は、Pyxelが基本的に「グローバルな256色パレット」と「パレットindex画像」で描画することです。

通常のフルカラー画像では、各ピクセルがRGB値を持ちます。しかしPyxelの画像データは、各ピクセルが `0..255` の色番号を持ち、実際のRGBは `pyxel.colors[index]` を参照して決まります。このため、次の設計課題が出ます。

| 課題 | PVNMでの対応 |
| --- | --- |
| 1枚の画像に合う色だけでパレットを作ると、UI文字色が変わる | UI/本文/話者色に使うindexを予約し、シーンパレットでも固定する |
| 背景と立ち絵を同時に出すと、それぞれに必要な色が違う | そのシーンで実際に表示される画像群から、シーン単位パレットを作る |
| 画像を毎フレーム減色すると遅すぎる | 画像、表示サイズ、パレットhashごとに `.npy` のindex配列をキャッシュする |
| エクスポート後に元PNGを入れない形式がある | 書き出し時に必要な `.npy` を事前生成し、`image_manifest.json` に登録する |
| Web/Androidでは同期ファイル読込が重い | 画像キャッシュを外部assetsへ出し、同一オリジンのバイナリ取得に寄せる |

つまりPVNMの減色処理は、単に「画像を256色にする」処理ではありません。画面全体で一つのパレットしか使えない前提で、UI色、本文色、話者色、背景、立ち絵、ギャラリー、タイトル画面の関係を壊さないためのランタイム設計です。

## 実行時の画像表示パイプライン

プレイヤーがあるシーンを表示するとき、概念的には次の順に処理します。

```text
シーン状態を解決
  ↓
継承中の背景・立ち絵・flipbook画像を列挙
  ↓
予約色を固定したシーンパレットを取得
  ↓
pyxel.colors[0..255] にシーンパレットを反映
  ↓
画像ファイル + 表示サイズ + パレットhash で画像キャッシュを取得
  ↓
pyxel.Image にindex配列を直接コピー
  ↓
pyxel.blt で描画
```

実装上は `engine/player.py` の `_apply_scene_palette()` がシーンパレットを選び、`engine/image_cache.py` の `ImageCache.get()` が画像を `pyxel.Image` 化します。

重要なのは、画像キャッシュのkeyにパレットhashが含まれることです。同じ `bg.png` でも、シーンAのパレットとシーンBのパレットでは違うindex配列になる可能性があります。そのためPVNMは、同じファイルでもパレット違いを別キャッシュとして扱います。

## データ形式

PVNMが内部とエクスポートで使う主なデータは次の通りです。

| ファイル | 役割 |
| --- | --- |
| `.pvnm` | 編集用プロジェクトファイル。シーン、手順、素材参照などを保存 |
| `settings.json` | UI色、話者色、フォントサイズなどアプリ/ランタイム設定 |
| `story.json` | エクスポートランタイム用のコンパクトなシナリオJSON |
| `title_config.json` | タイトル画面設定 |
| `gallery_config.json` | CGギャラリー設定 |
| `extra_text_config.json` | EXTRASのテキストページ設定 |
| `endings.json` | エンディング一覧とスライド設定 |
| `MasterColor.pyxpal` | PVNMの基準256色パレット |
| `image_manifest.json` | エクスポート済み画像キャッシュの索引 |
| `pvnm_cache/*.npy` | 画像をPyxel palette index配列にしたNumPy保存データ |

`story.json` はエクスポート時にインデントなしのコンパクトJSONで書かれます。大規模プロジェクトでは、見た目用の空白を書くだけで時間が伸びるためです。一方、編集用 `.pvnm` は人間が確認しやすい保存形式を優先します。

## 設計上の分離

PVNMでは、画像の「色を決める処理」と「画像をキャッシュする処理」と「成果物を包装する処理」が分かれています。

| 処理 | 代表関数 | ポイント |
| --- | --- | --- |
| マスターパレット読込 | `engine.palette.load()` | `pyxel.colors` に256色を適用 |
| シーンパレット構築 | `engine.palette.build_scene_palette()` | 表示画像群から代表色を抽出し、予約色を固定 |
| 固定パレットへの量子化 | `engine.image_cache._quantize()` | Pillowの固定パレットquantizeを使う |
| 画像キャッシュ取得 | `ImageCache.get()` | メモリ、ディスク、manifest、外部cacheの順で取得 |
| エクスポート事前生成 | `engine.export._prebuild_image_manifest()` | ランタイムが必要とするサイズ/パレットを先に生成 |
| フルエクスポートworker | `engine.export_worker` | Pyxel GUIプロセスから重い処理を分離 |
| 画像prebuild worker | `engine.export_prebuild_worker` | Pillow/NumPy処理をさらに独立プロセス化 |

この分離により、エディタ実行中、通常の `.pyxapp`、Web、Android、Windows、macOSで同じランタイムロジックを使い回せます。エクスポート形式ごとの差分は、主に「どこへファイルを置くか」「どの包装ツールを呼ぶか」「Web/Android向けに何を注入するか」に寄せられています。

## 関連する詳細ページ

まず読むなら [減色・パレット・画像キャッシュ設計](technical-palette.md) からがおすすめです。PVNMの表示品質と速度の大部分は、このページで説明するパレット生成と固定パレット量子化で決まっています。

エクスポートの処理順、`image_manifest.json`、Web/Androidの外部assets化、worker分離の理由を追う場合は [エクスポート設計](technical-export.md) を参照してください。
