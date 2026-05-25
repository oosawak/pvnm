# FAQ

PVNMでよくある質問を短く逆引きするページです。詳しい手順はリンク先のページを見てください。

## 起動とセットアップ

### `python3 main.py` が動かない

先に依存パッケージを入れてください。

```bash
python3 -m pip install -r requirements.txt
python3 main.py
```

macOSで `python3` の向き先が違う場合は、Python 3.12を明示します。

```bash
/path/to/python3 main.py
```

詳しくは [初回セットアップ](setup.md) を見てください。

### `ModuleNotFoundError` が出る

`requirements.txt` の依存パッケージが入っていない可能性があります。使っているPythonに対して `python3 -m pip install -r requirements.txt` を実行してください。

### WindowsでもPVNM本体は動く？

動作対象です。Python 3.12系を入れて、`requirements.txt` の依存を入れてから `python main.py` で起動します。Windows EXEを書き出す場合は、追加で `requirements-build.txt` の依存が必要です。

## Windows EXE

### Windows EXEのActionsが始まらない

macOSから `[WINDOWS EXE]` を実行する場合、GitHub Actions上でビルドします。未commitの変更はActionsから見えないため、必要な変更をcommitしてpushしてください。詳しくは [Windows EXEエクスポート](export-windows.md) を見てください。

### GitHub認証がないと言われる

`gh auth login`、`PVNM_GITHUB_TOKEN`、またはSSHキーによる `git push` のいずれかを使える状態にしてください。PVNMは可能な方法でActions起動を試します。

### ActionsはSuccessなのにエラー表示が見える

GitHubのAnnotationsに古い失敗や警告が残って見える場合があります。ビルド全体がSuccessで、ArtifactやRelease Assetが生成されていれば成果物を確認できます。

### Artifactのzipの中にフォルダがもう一段ある

正常です。GitHub ActionsのArtifactは、ダウンロード時にGitHub側でzipになります。中に `LastEmulator/LastEmulator.exe` のようなフォルダが入る形になります。

## Android

### Android APKが出ない

Android SDK、Java/JDK、Node.js/npm、Gradle、署名設定、出力先の権限を確認してください。中間Androidプロジェクトが生成されている場合は、その中で `./build_android.sh build-debug` または `./build_android.sh build-release` を実行すると原因を追いやすいです。詳しくは [Androidエクスポート](export-android.md) を見てください。

### Release APKには署名が必要？

必要です。ローカルReleaseビルドでは `pvnm-signing/release.jks` と `pvnm-release-signing.properties` が使われます。初回生成後は必ずバックアップしてください。ActionsでRelease APKを作る場合は、GitHub Secretsに署名鍵情報を設定します。

### Debug APKとRelease APKは何が違う？

Debug APKは手元確認用です。一般配布には、署名済みのRelease APKを使います。

## Web HTML

### Webで音が鳴らない

ブラウザでは、ユーザー操作前に音声が再生されないことがあります。クリック、タップ、キー入力などの後にBGM/SEを確認してください。

### Webで画像や素材が表示されない

HTMLだけを移動している可能性があります。`.html`、`<name>_assets/`、`pyxel/` を同じ階層関係で配置してください。詳しくは [Web HTMLエクスポート](export-web.md) を見てください。

### Web版をローカルで確認したい

出力先フォルダでHTTPサーバーを起動し、ブラウザからHTMLを開きます。

```bash
python3 -m http.server 8133
```

## 画像と音声

### 画像の色味がmacOSとWindowsで違う

表示環境やエクスポート形式によって見え方が変わることがあります。VN Palette Toolで調整し、最終的には配布対象の環境で確認してください。詳しくは [色とツール](colors-and-tools.md) を見てください。

### エクスポート成果物にオリジナル画像は入る？

形式や設定によって扱いが違います。現在の軽量エクスポートでは、配布時に `image_manifest.json` と `pvnm_cache/*.npy` のキャッシュで動く構成があります。公開前は [作品公開前チェックリスト](work-release-checklist.md) に沿って、不要な制作途中ファイルを手で混ぜていないか確認してください。

### エクスポート成果物に入るライセンスファイルは作品のライセンス？

いいえ。`PVNM_LICENSE.txt`、`PVNM_THIRD_PARTY_NOTICES.md`、`PVNM_EXPORT_LICENSE_README.txt` は、PVNMランタイムや同梱第三者コンポーネントの通知です。作品本編のシナリオ、画像、音楽、キャラクターなどの著作権表示や利用規約は、作品ごとに別途用意してください。

### BGM/SEが一部だけ鳴らない

ファイルパス、対応拡張子、音量、ブラウザの音声制限を確認してください。Web/Androidでは、初回操作後に再生されるかも見ます。

## 作品内容

### EXTRASが開放されない

登録済みエンディングへ自然到達しているか確認してください。EXTRASはタイトル設定、エンディング設定、CG GALLERY、EXTRA TEXTの内容とも関係します。詳しくは [タイトルとEXTRAS](title-extras.md) を見てください。

### セーブ/ロードの確認は必要？

必要です。配布形式ごとに保存先やブラウザ/端末の制約が変わるため、公開対象の環境でセーブ/ロードを確認してください。

## 配布と公開

### Actions ArtifactとRelease Assetは何が違う？

Actions Artifactは確認用の一時ビルドです。GitHub Release Assetは正規配布に向いています。公開サイトやSNSから案内する場合は、Release Assetへリンクするのがおすすめです。詳しくは [リリース配布](releases.md) を見てください。

### `v1.0.0` と `pvnm-windows-build-*` は何が違う？

`v1.0.0` のような `v*` タグは利用者に見せる正規リリース用です。`pvnm-windows-build-*` はPVNMからWindows EXE確認用Actionsを起動する一時タグです。

### 作品紹介サイトを作りたい

[作品紹介サイトの作り方](work-website.md) を見てください。Last Emulatorの例では、制作/ビルド用リポジトリと公開サイト用リポジトリを分け、公開サイト側のGitHub Releasesへ配布ファイルを置く流れにしています。

### GitHub Pagesで作品紹介サイトを公開できる？

できます。`index.html`、`styles.css`、`assets/` のような静的サイトなら、GitHub Pagesで `main` ブランチの `/ (root)` を公開元にできます。詳しくは [作品紹介サイトの作り方](work-website.md) を見てください。

## PVNM本体公開

### PVNM本体を公開する流れは？

[PVNM本体を公開する流れ](pvnm-publication.md) を見てください。公開範囲、README/docs、MITライセンス、private情報の確認、GitHub Releaseまでを順番に整理しています。

### PVNMは改変して公開していい？

PVNMはMITライセンスで公開します。著作権表示とライセンス本文を残すことで、利用、複製、改変、再配布、商用利用ができます。改変版を自分のツールとして公開することも可能です。

### 公開リポジトリ向けの定番ファイルは？

最低限は `README.md` と `LICENSE` です。PVNMのように第三者フォントやランタイムを含む場合は `THIRD_PARTY_NOTICES.md` も置きます。必要に応じて、変更履歴の `CHANGELOG.md`、貢献方法の `CONTRIBUTING.md`、脆弱性報告窓口の `SECURITY.md` を用意します。詳しくは [PVNM本体公開前チェックリスト](pvnm-release-checklist.md) を見てください。
