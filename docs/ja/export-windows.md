# Windows EXEエクスポート

Windows EXEは、実行しているOSによって流れが変わります。

| 実行環境 | 動き |
| --- | --- |
| macOS | GitHub Actions上のWindowsランナーでビルドする |
| Windows | ローカルのPyInstallerでWindows zipを作る |

macOSから直接Windows用EXEを作るのではなく、GitHub上でWindows環境を使って成果物を作ります。

プロジェクトに `assets/images/ui/app_icon.png` がある場合、Windows EXEのアイコンとして使われます。詳しくは [素材と音声](assets-and-audio.md) を見てください。

## macOSから実行する流れ

1. PVNMプロジェクトを保存する。
2. 変更内容をcommitする。
3. GitHubへpushする。
4. `SETTINGS` の `EXPORT` から `[WINDOWS EXE]` を実行する。
5. PVNMがGitHub Actionsを起動する。
6. ActionsのArtifactsから `<ProjectName>-windows` をダウンロードする。

PVNMはまず `gh workflow run` を試し、次に `PVNM_GITHUB_TOKEN` / `GH_TOKEN` / `GITHUB_TOKEN` によるAPI実行を試します。それらが使えない場合でも、SSHなどで `git push` が通る状態なら `pvnm-windows-build-*` の一時タグをpushしてActionsを起動します。

一時タグで起動した場合、workflow側でリモートタグは削除されます。ローカルタグもPVNM側で削除されるため、通常はユーザーがタグを管理する必要はありません。

## Windows上で実行する流れ

1. `python -m pip install -r requirements-build.txt` でPyInstallerを入れる。
2. PVNMをWindows上で起動する。
3. `SETTINGS` の `EXPORT` から `[WINDOWS EXE]` を実行する。
4. 保存先を選ぶ。
5. 指定した場所にWindows向けフォルダとzipが生成される。

## 実行に必要なもの

| 必要なもの | 理由 |
| --- | --- |
| GitHubリポジトリ | macOSからActionsを実行するため |
| `.github/workflows/windows-exe.yml` | Windowsビルド手順を定義するため |
| GitHub認証 | PVNMからworkflow_dispatch、API dispatch、または一時タグpushを行うため |
| commit済みのプロジェクト | ActionsはGitHub上の内容をビルドするため |
| `requirements-build.txt` | Windows上でローカルビルドする場合のPyInstaller依存 |

## 認証

PVNMからGitHub Actionsを起動するには、次のいずれかで認証しておきます。

```bash
gh auth login
```

または、`PVNM_GITHUB_TOKEN` にGitHub tokenを設定します。SSHキーをGitHubへ登録し、`git push` が通る状態にしておく方法でも、一時タグpushによる起動ができます。

## ローカル変更がある場合

macOSからGitHub Actionsでビルドする場合、未commitの変更がある状態ではPVNMはWindowsビルドを開始しません。これは、GitHub Actionsがローカルの未保存変更を読めないためです。

変更をビルドに含めたい場合は、commitしてpushしてください。

```bash
git status
git add .
git commit -m "Update project"
git push
```

## 成果物

GitHub ActionsのArtifactsには、`<ProjectName>-windows` のような名前の成果物が生成されます。GitHubがArtifactをzipとしてダウンロードさせるため、ダウンロードしたzipの中に `<ProjectName>/<ProjectName>.exe` のようなフォルダが入ります。

Artifactsは一時的なビルド成果物です。正規配布には [リリース配布](releases.md) を使うのがわかりやすいです。

## Release用ビルド

`v1.0.0` のような `v*` タグをpushすると、`windows-exe.yml` はRelease用のzipと `.sha256` を作り、同じタグのGitHub Releaseへアップロードします。Releaseがなければdraft Releaseを作成します。

PVNMメニューから起動する通常のWindows EXEエクスポートは、確認用Artifactを作る流れです。正規配布にする場合は、そのArtifactをReleaseへアップロードするか、`v*` タグでRelease用ビルドを走らせてください。
