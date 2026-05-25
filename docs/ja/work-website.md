# 作品紹介サイトの作り方

PVNMで作った作品を配布するときは、エクスポート成果物そのものとは別に、作品を紹介するWebサイトを用意すると案内しやすくなります。このページでは、Last Emulatorの公開で使った流れを例に、静的なWebサイトからGitHub Releasesの配布ファイルへリンクする形を説明します。

## 全体像

作品紹介サイトは、作品の説明、スクリーンショット、ダウンロード導線、動作環境、クレジットを置く場所です。ゲーム本体のzipやAPKは、サイトのリポジトリに直接置くより、GitHub Releasesなどの配布先に置いて、サイトからリンクする方が扱いやすくなります。

Last Emulatorでは、次のように役割を分ける流れを採りました。

| 役割 | 例 | 内容 |
| --- | --- | --- |
| 制作/ビルド用リポジトリ | `game-de-it/last-emulator-project` | PVNMプロジェクト、素材、Windows EXEビルド用Actionsなどを管理する。 |
| 公開サイト用リポジトリ | `game-de-it/last-emulator-web` | 作品紹介ページ、スクリーンショット、ダウンロードボタン、GitHub Pages設定などを管理する。 |
| 配布ファイル置き場 | 公開サイト用リポジトリのGitHub Releases | Windows zip、macOS zip、Web zip、Android APKなどをRelease Assetとして置く。 |

この分け方にすると、制作途中のデータを非公開にしたまま、公開用Webサイトと配布ファイルだけを見せられます。

## 1. 配布する成果物を用意する

まずPVNMから、公開したい形式をエクスポートします。

- Windows向け: `[WINDOWS EXE]`
- macOS向け: `[macOS APP]`
- ブラウザ向け: `[WEB HTML]`
- Android向け: `[ANDROID APK RELEASE]`

公開前に [作品公開前チェックリスト](work-release-checklist.md) を見ながら、zipやAPKをダウンロード時と同じ形で起動確認してください。Web版は `.html`、`<name>_assets/`、`pyxel/` の階層を崩さずzip化します。

## 2. 配布先を決める

GitHub Releasesを使う場合は、配布用リポジトリを1つ決めます。Last Emulatorのように作品紹介サイト用リポジトリを持つ場合は、そのリポジトリのReleasesへ配布ファイルを置くと、サイトとダウンロード先の管理がまとまります。

確認すること:

- [ ] GitHubアカウントを持っている。
- [ ] 配布用リポジトリを作っている。
- [ ] リポジトリをpublicにするかprivateにするか決めている。
- [ ] Releaseを作成できる権限がある。
- [ ] 正規配布に使うReleaseタグを決めている。例: `v1.0.0`。

`pvnm-windows-build-*` はWindows EXE確認用の一時タグです。公開サイトからリンクする正規配布には、`v1.0.0` のような利用者向けタグのReleaseを使います。

## 3. GitHub Releaseを作る

GitHubのReleases画面から、新しいReleaseを作ります。

- Tag: `v1.0.0` のような公開バージョン
- Title: 作品名とバージョン
- Description: 更新内容、対応環境、既知の問題
- Assets: Windows zip、macOS zip、Web zip、Android APK、必要なら `.sha256`

Release Assetの名前は、サイトのボタンや説明と揃えます。

例:

```text
LastEmulator-windows-v1.0.0.zip
LastEmulator-macos-v1.0.0.zip
LastEmulator-web-v1.0.0.zip
LastEmulator-android-v1.0.0.apk
LastEmulator-android-v1.0.0.apk.sha256
```

## 4. Webサイトに載せる内容を決める

作品紹介サイトには、最低限次の情報があると利用者が迷いにくくなります。

- 作品名
- キャッチコピー
- 短い紹介文
- スクリーンショット
- ダウンロードボタン
- 対応OS/環境
- 起動方法
- 操作方法
- 実況/配信可否
- 素材クレジット
- 更新履歴
- 問い合わせ先または不具合報告先

Webサイト上にゲーム本体を置く必要はありません。ダウンロードボタンはGitHub ReleasesのRelease Assetへリンクします。

## 5. Last Emulator型の公開フロー

Last Emulatorで使った流れを、PVNM作品向けに一般化すると次の形です。

1. PVNMで作品を完成させる。
2. PVNMからWindows/Web/Androidなどの成果物をエクスポートする。
3. Windows EXEはGitHub Actionsの確認用Artifactで動作確認する。
4. 正規配布用のzipやAPKを用意する。
5. 公開サイト用リポジトリのGitHub Releasesに、配布ファイルをRelease Assetとしてアップロードする。
6. 公開サイトのダウンロードボタンから、そのRelease Assetへリンクする。
7. GitHub Pagesなどで作品紹介サイトを公開する。
8. 公開ページからダウンロードし直して、展開/起動できるか最終確認する。

この流れでは、制作データを含むリポジトリを公開する必要はありません。公開するのは、作品紹介サイトと、利用者向けの配布ファイルだけです。

## 6. GitHub Pagesで公開する場合

GitHub Pagesを使うと、GitHub上のリポジトリから静的なWebサイトを公開できます。Last Emulatorの公開サイトは、`~/last-emulator-web` にある次のようなシンプルな構成を例にできます。

```text
last-emulator-web/
  index.html
  styles.css
  assets/
```

この形なら、GitHub Pagesの公開元を `main` ブランチの `/` にして、リポジトリ直下の `index.html` を公開できます。

手順:

1. 作品紹介サイト用のリポジトリをGitHubに作る。
2. `index.html`、`styles.css`、`assets/` などをcommitしてpushする。
3. GitHubのリポジトリ画面で `Settings` を開く。
4. 左側の `Pages` を開く。
5. `Build and deployment` の `Source` で `Deploy from a branch` を選ぶ。
6. `Branch` で `main` と `/ (root)` を選んで保存する。
7. Pagesの画面に表示される公開URLを開いて確認する。

プロジェクト用サイトの場合、URLは通常 `https://<account>.github.io/<repository>/` の形になります。たとえば `game-de-it/last-emulator-web` なら、公開URLは `https://game-de-it.github.io/last-emulator-web/` のような形になります。

GitHub Pagesの設定画面や公開元の選び方はGitHub側で変わることがあるため、詰まった場合は [GitHub Pagesの公式ドキュメント](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site) も確認してください。

## 7. ダウンロードリンクの確認

公開後は、必ず利用者と同じ導線で確認します。

- [ ] 作品紹介サイトを開ける。
- [ ] ダウンロードボタンがRelease Assetへ向いている。
- [ ] Windows/macOS/Web/Androidのリンク先が入れ替わっていない。
- [ ] Release Assetをダウンロードできる。
- [ ] ダウンロードしたファイルを展開/インストールして起動できる。
- [ ] サイト上のバージョン表記とReleaseタグが一致している。

Release Assetを差し替えた場合は、サイト側のリンク先が古いファイルを指していないかも確認してください。

## 8. 注意点

- 制作途中のPVNMプロジェクト、署名鍵、token、private素材は公開サイト用リポジトリへ入れない。
- Web版zipを作るときは `.html`、`<name>_assets/`、`pyxel/` の階層を崩さない。
- AndroidのRelease APKを更新して配る場合は、同じ署名鍵を使う。
- 配布先を複数に分ける場合は、どこが正規配布なのかをサイト上で明確にする。
- GitHub Releases以外の配布先を使う場合も、サイトから「最新版の配布ファイル」へ迷わず辿れる導線にする。
