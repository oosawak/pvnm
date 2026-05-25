# PVNM本体公開前チェックリスト

PVNM本体のソースコードや配布物を公開する前に確認する項目です。PVNMで作った作品の公開準備は [作品公開前チェックリスト](work-release-checklist.md) を見てください。

公開までの作業順を知りたい場合は、先に [PVNM本体を公開する流れ](pvnm-publication.md) を見てください。

## 1. リポジトリ状態

- [ ] `git status` が意図した状態になっている。
- [ ] 公開したい変更がcommit済み。
- [ ] GitHubへpush済み。
- [ ] private情報、署名鍵、token、個人用パスがcommitされていない。
- [ ] 作業用のprivateリポジトリと公開用リポジトリを分ける場合、どちらを正規の配布元にするか決めている。

確認コマンド:

```bash
git status
git log -1 --oneline
```

## 2. ライセンス

- [ ] `LICENSE` にMIT License本文を置いている。
- [ ] `THIRD_PARTY_NOTICES.md` にフォント、Pyxel、Pyodide、依存パッケージのライセンス表記をまとめている。
- [ ] READMEや配布ページから、PVNMがMITライセンスであることが分かる。
- [ ] 著作権表示とライセンス本文を残す必要があることを利用者が確認できる。

公開ページに入れる文章例:

> PVNMはMITライセンスで公開しています。著作権表示とライセンス本文を残すことで、誰でも自由に利用、複製、改変、再配布、商用利用できます。PVNMを改変した版を自分のツールとして公開することも可能です。

## 3. ドキュメント

- [ ] READMEから主要ページへ辿れる。
- [ ] [初回セットアップ](setup.md) の手順で起動できる。
- [ ] [画面と基本操作](editor-overview.md) のショートカットやボタン名が現行UIと合っている。
- [ ] [エクスポート概要](export.md) と各形式のページが、現在の配布方針と合っている。
- [ ] [リリース配布](releases.md) に、ArtifactとRelease Assetの違いが書かれている。
- [ ] [トラブルシュート](troubleshooting.md) に、既知の詰まりどころが載っている。
- [ ] 現行画面にない機能を案内していない。

公開リポジトリとして整える場合は、必要に応じて次も用意します。

- [ ] `CHANGELOG.md`
- [ ] `CONTRIBUTING.md`
- [ ] `SECURITY.md`

## 4. ローカル起動

- [ ] macOSで `python3 main.py` または明示したPythonパスで起動できる。
- [ ] Windowsで起動確認する場合、Python 3.12系と `requirements.txt` の依存が入っている。
- [ ] `SETTINGS` が開ける。
- [ ] `PLAY` でプレビュー開始できる。
- [ ] サンプルまたは実プロジェクトを保存/読込できる。

macOSでPythonを明示する例:

```bash
/path/to/python3 main.py
```

## 5. エクスポート機能

| 形式 | 確認 |
| --- | --- |
| `[PYXAPP]` | `.pyxapp` を生成できる。 |
| `[PYXAPP + ASSETS]` | `.pyxapp` と `<name>_assets/` を生成できる。 |
| `[macOS APP]` | `.app` を生成できる。 |
| `[WINDOWS EXE]` | GitHub Actionsを起動できる。 |
| `[WEB HTML]` | `.html`、`<name>_assets/`、`pyxel/` を生成できる。 |
| `[ANDROID PROJECT]` | Androidプロジェクトを生成できる。 |
| `[ANDROID APK DEBUG]` | Debug APKを生成できる。 |
| `[ANDROID APK RELEASE]` | Release APKと `.sha256` を生成できる。 |

すべての形式を公開直前に毎回確認できない場合でも、変更した範囲に近い形式は実行しておきます。

## 6. GitHub Actions

- [ ] PVNM本体リポジトリにActions workflowを同梱するか、作品リポジトリ側のサンプルとして案内するかを決めている。
- [ ] Windows EXE Actionsを使う場合、`.github/workflows/windows-exe.yml` の置き場所と使い方を説明できる。
- [ ] Android Release APK Actionsを案内する場合、署名用Secretsと起動方法を説明できる。
- [ ] Actions Artifactは確認用、Release Assetは正規配布用として説明できる。
- [ ] Release Assetアップロードを自動化する場合、`v*` タグで動く設計になっている。
- [ ] `pvnm-windows-build-*` は確認用の一時タグとして扱い、正規配布タグにしない。

Android Release APK用Secrets:

| Secret | 内容 |
| --- | --- |
| `ANDROID_KEYSTORE_BASE64` | keystoreをbase64化した文字列 |
| `ANDROID_KEYSTORE_PASSWORD` | keystoreパスワード |
| `ANDROID_KEY_ALIAS` | key alias |
| `ANDROID_KEY_PASSWORD` | key password |

## 7. GitHub Releases

- [ ] Releaseタグは `v1.0.0` のような利用者向けの名前にする。
- [ ] Releaseノートに主な変更点、既知の制限、動作環境を書く。
- [ ] ソースコード公開だけでよいか、macOS/Windows/Androidなどの実行用成果物も置くか決めている。
- [ ] Release Asset名が利用者に分かりやすい。
- [ ] `.sha256` を置く場合、対応する本体ファイルと同じReleaseに置く。
- [ ] README、Webサイト、SNSなどから正しいReleaseへリンクしている。

## 8. 最終確認

- [ ] 新規環境でREADMEの手順を見ながら起動できる。
- [ ] Release Assetをダウンロードして展開/起動できる。
- [ ] 公開ページからダウンロードリンクへ辿れる。
- [ ] 公開後に差し替えが必要な場合の手順を決めている。
- [ ] 署名鍵、token、private素材を公開していない。

ここまで確認できたら、GitHub Releaseを公開状態にして配布できます。
