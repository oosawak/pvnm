# Palette Visual Novel Maker (PVNM)

Palette Visual Novel Maker (PVNM) は、Pyxelで動くノベルゲーム制作ツールです。シーン、背景、立ち絵、BGM/SE、選択肢、エンディング、EXTRASなどをGUIで編集し、macOS / Windows / Web / Android向けに書き出せます。

English README is available at [README.md](README.md).

このREADMEは日本語版の「入口」です。詳しい操作は `docs/ja/` に分けています。

## まず動かす

詳しい手順は [初回セットアップ](docs/ja/setup.md) を見てください。

```bash
python3 -m pip install -r requirements.txt
python3 main.py
```

macOSでは `python3` の実体が環境によって違うため、必要に応じてPython 3.12のパスを明示します。

```bash
/path/to/python3 main.py
```

## ドキュメント

| やりたいこと | ページ |
| --- | --- |
| PVNMを起動できる状態にする | [初回セットアップ](docs/ja/setup.md) |
| 画面構成や基本操作を知る | [画面と基本操作](docs/ja/editor-overview.md) |
| プロジェクトを保存/開く/Markdownから取り込む | [プロジェクト管理](docs/ja/project.md) |
| シーン、会話、分岐を作る | [シーン制作](docs/ja/scenes.md) |
| 背景、立ち絵、BGM、SEを使う | [素材と音声](docs/ja/assets-and-audio.md) |
| タイトル、エンディング、EXTRASを設定する | [タイトルとEXTRAS](docs/ja/title-extras.md) |
| UI色、話者色、減色を調整する | [色とツール](docs/ja/colors-and-tools.md) |
| 書き出し形式を選ぶ | [エクスポート概要](docs/ja/export.md) |
| Windows EXEを書き出す | [Windows EXEエクスポート](docs/ja/export-windows.md) |
| Web HTMLを書き出す | [Web HTMLエクスポート](docs/ja/export-web.md) |
| Android APKを書き出す | [Androidエクスポート](docs/ja/export-android.md) |
| GitHub Releasesで配布する | [リリース配布](docs/ja/releases.md) |
| 作品を紹介するWebサイトを作る | [作品紹介サイトの作り方](docs/ja/work-website.md) |
| PVNMで作った作品を公開前に確認する | [作品公開前チェックリスト](docs/ja/work-release-checklist.md) |
| PVNM本体を公開する流れを知る | [PVNM本体を公開する流れ](docs/ja/pvnm-publication.md) |
| PVNM本体を公開前に確認する | [PVNM本体公開前チェックリスト](docs/ja/pvnm-release-checklist.md) |
| よくある質問を短く確認する | [FAQ](docs/ja/faq.md) |
| よくある詰まりどころを見る | [トラブルシュート](docs/ja/troubleshooting.md) |

## やりたいことから探す

### セットアップ

| やりたいこと | 見る場所 |
| --- | --- |
| Windows / macOSで必要なものを知りたい | [初回セットアップ](docs/ja/setup.md) |
| `python3 main.py` の意味を知りたい | [初回セットアップ](docs/ja/setup.md) |
| Android書き出しに必要なものを知りたい | [Androidエクスポート](docs/ja/export-android.md) |

### プロジェクト

| やりたいこと | 見る場所 |
| --- | --- |
| プロジェクトを保存したい | [プロジェクト管理](docs/ja/project.md) |
| 既存プロジェクトを開きたい | [プロジェクト管理](docs/ja/project.md) |
| Markdown台本からシーンを作りたい | [プロジェクト管理](docs/ja/project.md) |

### シーン制作

| やりたいこと | 見る場所 |
| --- | --- |
| 会話シーンを追加したい | [シーン制作](docs/ja/scenes.md) |
| 次のシーンへ進ませたい | [シーン制作](docs/ja/scenes.md) |
| 選択肢で分岐させたい | [シーン制作](docs/ja/scenes.md) |
| 背景や立ち絵を表示したい | [素材と音声](docs/ja/assets-and-audio.md) |
| BGMやSEを鳴らしたい | [素材と音声](docs/ja/assets-and-audio.md) |

### タイトルとおまけ

| やりたいこと | 見る場所 |
| --- | --- |
| タイトル画面を設定したい | [タイトルとEXTRAS](docs/ja/title-extras.md) |
| エンディングを登録したい | [タイトルとEXTRAS](docs/ja/title-extras.md) |
| CGギャラリーを作りたい | [タイトルとEXTRAS](docs/ja/title-extras.md) |
| EXTRASのテキストを編集したい | [タイトルとEXTRAS](docs/ja/title-extras.md) |

### 見た目

| やりたいこと | 見る場所 |
| --- | --- |
| UIカラーを変えたい | [色とツール](docs/ja/colors-and-tools.md) |
| 話者ごとに名前や本文の色を変えたい | [色とツール](docs/ja/colors-and-tools.md) |
| 画像をPVNM向けの色味に減色したい | [色とツール](docs/ja/colors-and-tools.md) |
| ローディング画像やアプリアイコンを設定したい | [素材と音声](docs/ja/assets-and-audio.md) |

### エクスポートと配布

| やりたいこと | 見る場所 |
| --- | --- |
| どの形式で書き出せるか知りたい | [エクスポート概要](docs/ja/export.md) |
| Windows向けに配布したい | [Windows EXEエクスポート](docs/ja/export-windows.md) |
| ブラウザ向けに配布したい | [Web HTMLエクスポート](docs/ja/export-web.md) |
| Android APKを作りたい | [Androidエクスポート](docs/ja/export-android.md) |
| GitHub Releasesで公開したい | [リリース配布](docs/ja/releases.md) |
| 作品紹介サイトを作りたい | [作品紹介サイトの作り方](docs/ja/work-website.md) |
| 作品公開前に確認漏れを潰したい | [作品公開前チェックリスト](docs/ja/work-release-checklist.md) |
| PVNM本体をGitHubで公開したい | [PVNM本体を公開する流れ](docs/ja/pvnm-publication.md) |
| PVNM本体公開前に確認漏れを潰したい | [PVNM本体公開前チェックリスト](docs/ja/pvnm-release-checklist.md) |

### 困ったとき

| やりたいこと | 見る場所 |
| --- | --- |
| よくある質問を短く確認したい | [FAQ](docs/ja/faq.md) |
| エラーや詰まりどころを確認したい | [トラブルシュート](docs/ja/troubleshooting.md) |

## エクスポート早見表

| メニュー | 出力 | 主な用途 |
| --- | --- | --- |
| `[PYXAPP]` | `.pyxapp` | Pyxelで実行する単体パッケージ |
| `[PYXAPP + ASSETS]` | `.pyxapp` と `<name>_assets/` | 外部素材フォルダを並べて使う携帯機/検証用 |
| `[macOS APP]` | `.app` | macOS向け配布 |
| `[WINDOWS EXE]` | Windows zip | Windows向け配布 |
| `[WEB HTML]` | `.html`、`<name>_assets/`、`pyxel/` | ブラウザ向け配布 |
| `[ANDROID PROJECT]` | Androidプロジェクト | Android Studio / Gradle向け |
| `[ANDROID APK DEBUG]` | Debug APK | 端末確認用 |
| `[ANDROID APK RELEASE]` | Release APK と `.sha256` | 署名済み配布候補 |

詳細は [エクスポート概要](docs/ja/export.md) から各形式のページへ進んでください。

## リポジトリ内の主なファイル

```text
main.py                         PVNM本体の起動ファイル
engine/                         プレイヤー、エクスポート、プロジェクト処理
ui/                             エディタ画面
tools/                          補助ツール、ビルドスクリプト
assets/                         PVNM本体で使う素材
resources/                      エクスポート成果物で使うランタイム素材
docs/en/                        英語ドキュメント
docs/ja/                        日本語ドキュメント
```

## 依存パッケージ

通常の起動に必要なPythonパッケージは `requirements.txt` にあります。Windows EXEビルド用の追加依存は `requirements-build.txt` を使います。

詳しくは [初回セットアップ](docs/ja/setup.md) を参照してください。

## ライセンス

PVNMはMITライセンスで配布します。MITライセンスでは、著作権表示とライセンス本文を残すことで、誰でも自由に利用、複製、改変、再配布、商用利用できます。PVNMを改変した版を自分のツールとして公開することも可能です。

第三者フォント、Pyxel、Pyodide、Python依存パッケージなどのライセンスは [Third-Party Notices](THIRD_PARTY_NOTICES.md) を参照してください。
