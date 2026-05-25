# 初回セットアップ

このページでは、PVNMを起動できる状態にするまでの手順を説明します。

## 動作環境

PVNMはPythonとPyxelで動くデスクトップアプリです。

| OS | 想定 |
| --- | --- |
| macOS | Python 3.12系、Pyxelが動作する環境 |
| Windows | Python 3.12系、Pyxelが動作する環境 |

PVNMの編集作業はmacOS / Windowsのローカル環境で行います。Windows EXEは、macOSから実行する場合はGitHub Actions上のWindowsランナーでビルドし、Windows上で実行する場合はローカルのPyInstallerでビルドします。

## インストールするもの

### Python 3

PVNM本体はPythonで書かれているため、Python 3が必要です。macOSで複数のPythonが入っている場合は、どのPythonで起動しているかを確認してください。

```bash
which python3
python3 --version
```

環境によっては、次のようにPythonのパスを明示して起動します。

```bash
/path/to/python3 main.py
```

### 依存パッケージ

Pyxel、pygame、numpy、Pillowなど、PVNMの起動、音声再生、画像処理に必要なパッケージを入れます。

```bash
python3 -m pip install -r requirements.txt
```

このコマンドは、PVNMが使うPythonライブラリをまとめてインストールします。

macOSでAVFoundation系の音声バックエンドを使う場合は、追加で次の依存を入れます。

```bash
python3 -m pip install -r requirements-macos-avfoundation.txt
```

macOS `.app` やWindows上でのローカルEXEビルドに必要なPyInstallerは、通常起動には不要です。必要になった時点で次を入れます。

```bash
python3 -m pip install -r requirements-build.txt
```

### Git

Windows EXEエクスポートやGitHub Releasesでの配布を行う場合、プロジェクトをGitHubへpushできる状態にしておきます。

```bash
git --version
```

### GitHub CLIまたはSSH

PVNMのエクスポートメニューからGitHub Actionsを実行する場合、GitHubへ認証できる必要があります。認証方法は次のどちらかです。

```bash
gh auth login
```

または、SSHキーをGitHubへ登録して `git push` できる状態にします。

### Android Studio

Android向けに書き出す場合だけ必要です。Androidプロジェクト生成、Debug APK、Release APKのビルドにGradle、Android SDK、Android Studio同梱JDKを使います。

## 起動する

依存パッケージを入れたら、リポジトリのルートで起動します。

```bash
python3 main.py
```

`python3 main.py` は「Python 3で `main.py` を実行する」という意味です。`main.py` がPVNM本体の入口です。

## 起動できないとき

### `python3` が見つからない

Python 3がインストールされていないか、PATHが通っていません。Pythonをインストールし、ターミナルで `python3 --version` が動くか確認してください。

### `pyxel` が見つからない

依存パッケージが入っていない可能性があります。

```bash
python3 -m pip install -r requirements.txt
```

### macOSで別のPythonが使われる

`which python3` で実体を確認し、必要ならPythonのフルパスで起動してください。

```bash
/path/to/python3 main.py
```
