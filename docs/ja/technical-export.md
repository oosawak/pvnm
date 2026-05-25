# エクスポート設計

このページでは、PVNMのエクスポート処理を技術者向けに説明します。操作方法は [エクスポート概要](export.md) と各形式のページを参照してください。

関連実装は主に次のファイルです。

| ファイル | 役割 |
| --- | --- |
| `engine/export.py` | すべてのエクスポート形式の中心実装 |
| `engine/export_worker.py` | フルエクスポートを別Pythonプロセスで実行 |
| `engine/export_prebuild_worker.py` | 画像cache事前ビルドを別Pythonプロセスで実行 |
| `engine/image_cache.py` | エクスポート済み `.npy` と `image_manifest.json` の読込 |
| `engine/standalone_app.py` | 書き出しランタイムの起動入口 |
| `resources/pvnm/web/` | Web/Android向けJavaScriptブリッジとPyxel Webランタイム |
| `tools/build_windows_exe.py` | Windows CI/ローカルビルド補助 |

## エクスポート形式の分類

PVNMは複数形式へ書き出せますが、内部的には「ランタイムツリーを作る」処理を共有し、その後の包装だけを変えています。

| メニュー | 主要な内部処理 |
| --- | --- |
| `[PYXAPP]` | ランタイムツリー生成 → `pyxel package` |
| `[PYXAPP + ASSETS]` | ランタイムツリー生成 → 画像cache/音声を外部assetsへ移動 → `pyxel package` |
| `[macOS APP]` | ランタイムツリー生成 → PyInstaller onedir `.app` |
| `[WINDOWS EXE]` | ランタイムツリー生成 → PyInstaller onedir → zip |
| `[WEB HTML]` | ランタイムツリー生成 → `pyxel package` → `pyxel app2html` → JS/外部assets注入 |
| `[ANDROID PROJECT]` | Web bundle生成 → Capacitorプロジェクト生成 |
| `[ANDROID APK DEBUG/RELEASE]` | Capacitorプロジェクト生成 → Gradle build → APKコピー |

共通部分の中心は `_write_runtime_tree()` です。

## ランタイムツリー生成

`_write_runtime_tree()` は、一時ディレクトリ内にスタンドアロン実行できる構造を作ります。

大まかな順序は次の通りです。

```text
EditorState から script を作る
  ↓
story.json をコンパクトJSONで書く
  ↓
settings/endings/title/gallery/extra_text を正規化して書く
  ↓
参照素材を収集する
  ↓
必要に応じて素材をコピーする
  ↓
画像cacheを事前ビルドする
  ↓
フォントとマスターパレットなど runtime assets をコピーする
  ↓
engine/ と ui/ のランタイム必要ファイルをコピーする
  ↓
生成 main.py と README.md を書く
  ↓
PVNMランタイムのライセンス通知を入れる
```

生成される `main.py` は最小です。

```python
from engine.standalone_app import App

App(title="...", storage_app_id="...")
```

実際の再生処理は `engine.standalone_app.App` とプレイヤー側のコードに残し、エクスポートごとに巨大なlauncherを作らない設計です。

## 素材収集

素材収集は、シナリオ、エンディング、タイトル、ギャラリーから参照パスを集めます。

| 収集元 | 対象 |
| --- | --- |
| シーン | 背景、立ち絵、flipbook、パレットファイル、フォント、BGM、SE |
| エンディング | BGM、スライド画像 |
| タイトル | 背景画像、BGM |
| ギャラリー | CG画像 |

画像は必ずしも元ファイルとして同梱されません。`bundle_original_images=False` の形式では、画像は `.npy` cacheとmanifestで再生する方向に寄せます。音声はWeb/Android/外部assets形式では別ディレクトリにコピーされることがあります。

## なぜworkerを使うのか

PVNMはPyxel GUIアプリです。GUIプロセス内で長時間のPillow/NumPy処理、PyInstaller、Gradle、`pyxel package` を走らせると、UIループやPyxel側の状態と干渉しやすくなります。

そのため、保存済みプロジェクトがある通常ケースでは、フルエクスポートを `engine.export_worker` へ投げます。

```text
GUIプロセス
  ↓ input json
engine.export_worker
  ↓ EditorStateを読み直す
inline exporterを実行
  ↓ result json / PVNM_PROGRESS
GUIプロセスへ結果を返す
```

さらに、画像cacheの事前ビルドは `engine.export_prebuild_worker` に分離されます。

```text
export_worker または GUIプロセス
  ↓ image_prebuild_input.json
engine.export_prebuild_worker
  ↓ _prebuild_image_manifest()
image_manifest.json / pvnm_cache/*.npy / diagnostic logs
```

この二段階分離には次の利点があります。

| 利点 | 内容 |
| --- | --- |
| GUIの安定 | Pyxel表示中のプロセスで重い画像処理を抱えない |
| 状態の再現性 | 保存済み `.pvnm` を読み直して、ファイル上の状態から書き出せる |
| 進捗通知 | workerの標準出力 `PVNM_PROGRESS\t...` をGUIへ流せる |
| 失敗診断 | worker末尾ログとresult JSONをまとめて扱える |
| 環境分離 | `PYTHONPATH` と `PVNM_EXPORT_INLINE_FULL` を制御できる |

`PVNM_EXPORT_INLINE_FULL=1` や `PVNM_EXPORT_INLINE_PREBUILD=1` は、workerを使わず現在プロセスで処理したい場合の開発用スイッチです。

## 画像cache事前ビルド

PVNMのエクスポートで最も設計密度が高い部分は、画像cacheの事前ビルドです。

目的は次の2つです。

1. **プレイ中に重い画像処理をしない**
   画像を開く、リサイズする、減色する、Pyxel index配列にする処理をエクスポート時に済ませます。

2. **元画像なしでも再生できる**
   Webや外部assets形式では、元PNG/JPGをパッケージ内に持たず、`image_manifest.json` と `.npy` で再生します。

事前ビルドは、プレイヤーの継承ルールを再現します。つまり「このシーンで新しい背景が指定されていなければ前の背景を使う」「立ち絵がhideされていなければ前の設定を継承する」といった状態解決を、エクスポート側でも行います。

そのうえで、各シーンの表示画像群からシーンパレットを作り、実際に必要な表示サイズで `.npy` を生成します。

| 対象 | サイズ決定 |
| --- | --- |
| 通常背景 | 画面内に収める。fullscreen時は画面にfit |
| ダイアログ上背景 | ダイアログ領域を避けた高さにfit |
| 立ち絵 | 設定 `w/h` があればそれを使い、なければ画面内fit |
| エンディング画像 | 720x480内にfit |
| ギャラリー詳細 | 720x480内にfit |
| ギャラリーサムネイル | スロット内にfit |
| タイトル背景 | 720x480内にfit |

## image_manifest.json

`image_manifest.json` は、ランタイムが「元画像なしで何を読めばよいか」を知るための索引です。

概念的な構造は次の通りです。

```json
{
  "version": 1,
  "cache_dir": "pvnm_cache",
  "images": {
    "assets/images/bg.png": {
      "<palette-and-options-hash>": {
        "original_size": [1280, 720],
        "sizes": {
          "720x405": {
            "cache": "v2_....npy",
            "width": 720,
            "height": 405,
            "palette_hash": "...",
            "auto_colkey": 123
          }
        }
      }
    }
  },
  "palettes": {
    "<manifest-palette-key>": {
      "hash": "...",
      "paths": ["..."],
      "colors": ["1e1e1e", "..."]
    }
  },
  "prebuild": {
    "report": "image_prebuild_report.json",
    "trace": "image_prebuild_trace.jsonl",
    "mode": "direct_export_cache"
  }
}
```

`images` は画像パス、パレットhash、表示サイズごとにcacheを引きます。`palettes` は、エクスポート後に元画像がない場合でもシーンパレットを復元するための情報です。

ランタイム側の `ImageCache.get_prebuilt_palette()` は、表示画像パスと予約色からmanifest keyを作り、該当する256色を返します。見つからない場合は、元画像が存在すれば通常の `build_scene_palette()` へフォールバックします。

## prebuild診断ログ

画像事前ビルドは時間がかかることがあるため、診断情報を多めに出します。

| ファイル | 内容 |
| --- | --- |
| `image_prebuild_report.json` | 最終統計、処理時間、slow scenes/images |
| `image_prebuild_report.partial.json` | 実行中の途中経過 |
| `image_prebuild_trace.jsonl` | checkpoint形式のイベントログ |
| `.pvnm_export_logs/image_prebuild_report.latest.json` | プロジェクト側へ残す最新report |
| `.pvnm_export_logs/export_pipeline.latest.jsonl` | 形式別エクスポート全体のstageログ |

`stats` には、`requests`、`unique`、`generated`、`duplicate`、`failed` などが入ります。`duplicate` が多いのは異常とは限りません。同じ画像、同じサイズ、同じパレットを複数シーンから要求している場合、2回目以降は処理済みとして数えられます。

## `.pyxapp` エクスポート

標準 `.pyxapp` は、ランタイムツリーを作って `pyxel package` を呼びます。

```text
_write_runtime_tree()
  ↓
python -m pyxel package <app_dir> <app_dir>/main.py
  ↓
<name>.pyxapp
```

`bundle_original_images` の指定により、元画像も含めるか、事前ビルドcache中心にするかが変わります。cache中心にすると成果物は軽くなりますが、manifestとcacheが正しく生成されていることが重要になります。

## `.pyxapp + assets`

`[PYXAPP + ASSETS]` は、軽い `.pyxapp` と外部assetsフォルダを並べて使う形式です。

特徴は次の通りです。

| 項目 | 内容 |
| --- | --- |
| 画像 | `image_manifest.json` と `pvnm_cache/*.npy` を外部assets側へ移動 |
| 音声 | 外部assets側へコピー |
| marker | `.pyxapp` 内に `external_assets.json` を入れる |
| 実行時 | assetsフォルダを隣に置くか、`PVNM_ASSET_ROOT` で指定 |

携帯機や検証環境では、`.pyxapp` 内部を毎回大きく展開するより、重い素材を外に置いた方が扱いやすい場合があります。この形式はそのためのものです。

## Web HTMLエクスポート

Web HTMLは最も段数が多い形式です。

```text
_write_runtime_tree()
  ↓
画像cacheを Web assets/image_cache へ外部化
  ↓
pyxel package
  ↓
pyxel app2html
  ↓
音声assetsを準備
  ↓
viewport / screen container / loading overlay を注入
  ↓
WebAudio bridge を注入
  ↓
storage bridge を注入
  ↓
startup timing bridge を注入
  ↓
input bridge を注入
  ↓
pyxapp本体を assets/app へ外部化
  ↓
Pyxel Web runtime をローカル化
  ↓
HTML、assets、pyxel/ を出力先へコピー
```

Web版では、HTMLにすべてをbase64で埋めると巨大化します。PVNMは重いものを外部assetsへ逃がします。

| 外部化対象 | 置き場所 |
| --- | --- |
| 画像cache `.npy` | `<name>_assets/image_cache/` |
| `.pyxapp` 本体 | `<name>_assets/app/` |
| 音声 | `<name>_assets/audio/` |
| loading画像 | `<name>_assets/ui/loading.png` |
| Pyxel/Pyodide runtime | `pyxel/` |

`image_manifest.json` 自体はパッケージ内に残ります。ランタイムが最初にmanifestを読む必要があるためです。ただしmanifest内の `external_cache` に、同一オリジンで読むcache URLが書かれます。

## Web用ブリッジ

PVNMは `pyxel app2html` の出力に、複数のJavaScriptブリッジを注入します。

| bridge | 目的 |
| --- | --- |
| `pvnm_audio_bridge.js` | WebAudioで音声assetsを再生 |
| `pvnm_storage_bridge.js` | Web/Capacitor向けセーブ保存 |
| `pvnm_input_bridge.js` | タッチ/ゲームパッド/ブラウザ入力の補助 |
| `pvnm_startup_bridge.js` | 起動タイミング計測やloading表示制御 |
| `pvnm_webview_compat.js` | WebView互換性チェック |

これらはPyxel本体を改造せず、生成HTMLへ注入する形です。Pyxel更新の影響範囲を小さくし、PVNM固有の挙動を分離するためです。

## Android/Capacitor

AndroidはWeb版を土台にしています。

```text
export_web_bundle(..., output_dir/www)
  ↓
package.json / capacitor.config.json / build scripts を生成
  ↓
Android用診断ページやチェックリストを生成
  ↓
必要なら Gradle でAPK build
  ↓
APKを指定出力先へコピー
```

`[ANDROID PROJECT]` は中間プロジェクトを作るだけです。`[ANDROID APK DEBUG]` と `[ANDROID APK RELEASE]` は、その中間プロジェクトを作ったうえで `build_android.sh` を呼び、Gradleの成果物をコピーします。

Release APKでは、出力APKの横に `.sha256` を作ります。配布ファイルの検証用です。

## Windows EXEとmacOS APP

WindowsとmacOSはPyInstallerを使います。

共通の流れは次の通りです。

```text
_write_runtime_tree()
  ↓
PyInstaller onedir
  ↓
成果物フォルダまたは .app をコピー
  ↓
ライセンス通知を入れる
  ↓
Windowsは必要に応じてzip化
```

Windows EXEはWindows上でのみ実行できます。macOSからWindows用を作る場合は、GitHub ActionsなどWindows runnerで `tools/build_windows_exe.py` を使う想定です。

macOS `.app` はmacOS上でのみ実行できます。アイコンがあれば `.icns` を生成し、AVFoundation関連モジュールがある場合はPyInstallerへhidden importを追加します。

## ライセンス通知

各エクスポート成果物には、PVNMランタイムと第三者コンポーネントの通知ファイルが入ります。

| ファイル | 内容 |
| --- | --- |
| `PVNM_LICENSE.txt` | PVNMランタイムコードのライセンス |
| `PVNM_THIRD_PARTY_NOTICES.md` | フォント、Pyxel、Pyodideなど第三者コンポーネント |
| `PVNM_EXPORT_LICENSE_README.txt` | これらの通知が作品本編のライセンスではないことの説明 |

これは、作品のシナリオ、画像、音楽、キャラクターのライセンスを定義するものではありません。作品側の権利表示は制作者が別途用意します。

## 速度設計

エクスポートの速度は、主に次の方針で確保しています。

| 方針 | 内容 |
| --- | --- |
| ランタイムtreeは一時ディレクトリで構築 | 成功後に成果物だけを移動/コピー |
| 画像は事前に `.npy` 化 | 実行環境でPillow量子化を避ける |
| story.jsonはコンパクト出力 | 大規模シナリオの空白書き込みを減らす |
| worker分離 | GUIプロセスの状態と重い処理を分ける |
| pipeline log | 遅いstageを特定できる |
| Webは重いassetsを外部化 | HTML巨大化と起動時展開を避ける |
| gallery thumbnailは派生生成 | 詳細画像cacheから小画像を作り、元画像の再読込を減らす |

## 失敗しやすいポイント

| 症状 | 見る場所 |
| --- | --- |
| 画像が出ない | `image_manifest.json` に該当path/size/paletteがあるか、`pvnm_cache` に `.npy` があるか |
| Webだけ画像が出ない | manifestの `external_cache.base_url` と実際のassets配置 |
| 音が出ない | WebAudio bridgeのasset map、`<name>_assets/audio/` |
| エクスポートが止まる/遅い | `.pvnm_export_logs/export_pipeline.latest.jsonl` と `image_prebuild_report.latest.json` |
| Windows EXEが作れない | Windows上か、PyInstallerとrequirements-buildが入っているか |
| Android APKが作れない | `build_android.sh`、Gradle、Android SDK、署名設定 |
| 話者色が変わる | `settings.json` の `dialog_role_indices` / `speaker_colors` がruntime settingsへ入っているか |

## 設計上のメリット

現在のエクスポート設計の強みは、形式ごとの差分を包装層に閉じ込めていることです。シーン再生、パレット、画像cache、音声抽象化、設定読込は、できるだけ同じランタイムコードを使います。

その結果、デスクトップでは出るがWebでは出ない、Androidだけ色が違う、といった差分を減らせます。もちろんWebViewやブラウザの制約は残りますが、少なくともPVNM内部のストーリー解釈と画像cache生成は共有されています。

## 設計上のデメリット

| デメリット | 理由 |
| --- | --- |
| エクスポート処理が長い | 画像cacheを先に作るため |
| 成果物構造が複雑 | Web/AndroidではHTML、assets、runtimeが分かれるため |
| cache不整合の診断が必要 | path、size、palettehashのどれかが違うと別cacheになる |
| worker越しのデバッグが少し面倒 | 標準出力、result JSON、ログファイルを見る必要がある |
| PyInstaller/Gradleなど外部ツール依存 | 形式ごとにホスト環境の制約がある |

ただし、ランタイム起動後に毎回画像を減色する方式に比べると、配布物としての安定性と再生速度は高くなります。PVNMでは、エクスポート時に重く、プレイ時に軽い、という方向へ寄せています。
