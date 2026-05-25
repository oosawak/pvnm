# エクスポート概要

このページでは、PVNMから書き出せる形式の全体像を説明します。

## 早見表

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

各エクスポート成果物には、PVNMランタイムと同梱第三者コンポーネントの通知として `PVNM_LICENSE.txt`、`PVNM_THIRD_PARTY_NOTICES.md`、`PVNM_EXPORT_LICENSE_README.txt` が含まれます。これは作品本編のライセンスではないため、シナリオ、画像、音楽、キャラクターなど作品自体の著作権表示や利用規約は別途用意してください。

## ローカル生成とActions生成

PVNMのエクスポートは、形式によって実行場所が違います。

| 形式 | 実行場所 | 補足 |
| --- | --- | --- |
| `[PYXAPP]` | ローカル | `.pyxapp` を1つ作ります。 |
| `[PYXAPP + ASSETS]` | ローカル | `.pyxapp` と外部素材フォルダを同じ階層に置いて使います。 |
| `[macOS APP]` | macOSローカル | PyInstallerが必要です。Releaseへ載せる場合は `.app` をzip化して扱います。 |
| `[WINDOWS EXE]` | macOSではGitHub Actions、Windowsではローカル | macOSからはWindowsランナーでビルドします。 |
| `[WEB HTML]` | ローカル | HTML、assets、`pyxel/` を同じ関係で配置します。 |
| `[ANDROID PROJECT]` | ローカル | Capacitorプロジェクトを生成します。 |
| `[ANDROID APK DEBUG]` | ローカル | 中間Androidプロジェクトを作り、Debug APKをコピーします。 |
| `[ANDROID APK RELEASE]` | ローカル | 署名済みRelease APKと `.sha256` を作ります。 |

Windows EXEのActions連携は、作品リポジトリ側に `.github/workflows/windows-exe.yml` がある場合に使えます。PVNMのメニューから直接起動できるActions連携は現状 `[WINDOWS EXE]` です。Android Release APKはローカルの `[ANDROID APK RELEASE]` で作成できます。Android用Actionsを使いたい場合は、作品リポジトリ側で別途workflowを用意します。

## 形式別ページ

| 形式 | ページ |
| --- | --- |
| Windows EXE | [Windows EXEエクスポート](export-windows.md) |
| Web HTML | [Web HTMLエクスポート](export-web.md) |
| Android | [Androidエクスポート](export-android.md) |
| GitHub Releases配布 | [リリース配布](releases.md) |

## エクスポート前の確認

Windows EXEのようにGitHub Actionsを使う形式では、ローカルの未commit変更はビルドに含まれません。書き出したい状態を保存し、commitしてpushしてから実行してください。

WebやAndroidはローカルで成果物を生成できます。配布前には、実際の配布先に近い環境で起動確認を行ってください。

GitHub Releasesで正規配布する場合は、各形式の成果物をRelease Assetとして置きます。Actions Artifactは確認用、Release Assetは配布用、という分け方にすると混乱しにくいです。
