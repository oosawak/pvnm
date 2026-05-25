# First-Time Setup

This page explains how to get PVNM running.

Japanese version: [初回セットアップ](../ja/setup.md)

## Supported Environment

PVNM is a desktop application written in Python and powered by Pyxel.

| OS | Expected environment |
| --- | --- |
| macOS | Python 3.12 and a Pyxel-compatible environment |
| Windows | Python 3.12 and a Pyxel-compatible environment |

You edit projects locally on macOS or Windows. Windows EXE export uses a Windows environment: from macOS this is usually a GitHub Actions Windows runner, while on Windows it can run locally through PyInstaller.

## What To Install

### Python 3

PVNM itself is written in Python, so Python 3 is required. If you have multiple Python installations, check which one your shell is using.

```bash
which python3
python3 --version
```

If needed, run PVNM with an explicit Python path.

```bash
/path/to/python3 main.py
```

### Python packages

Install Pyxel, pygame, numpy, Pillow, and the other packages PVNM needs for the editor, audio playback, and image processing.

```bash
python3 -m pip install -r requirements.txt
```

On macOS, if you want the AVFoundation audio backend, install the extra requirements.

```bash
python3 -m pip install -r requirements-macos-avfoundation.txt
```

PyInstaller is not required for normal editor use. Install the build requirements only when you need macOS app export or local Windows EXE builds.

```bash
python3 -m pip install -r requirements-build.txt
```

### Git

Git is needed when you want to push a project to GitHub for Windows EXE export or GitHub Releases distribution.

```bash
git --version
```

### GitHub CLI or SSH

If you want PVNM to trigger GitHub Actions from the export menu, the project repository must be authenticated with GitHub. One option is GitHub CLI:

```bash
gh auth login
```

Another option is registering an SSH key with GitHub and confirming that `git push` works.

### Android Studio

Android Studio is only required for Android export. Android Project, Debug APK, and Release APK export use Android SDK, Gradle, Node.js/npm, and the Android Studio bundled JDK or Java 17.

## Run PVNM

After installing the dependencies, run PVNM from the repository root.

```bash
python3 main.py
```

This means: start the Python interpreter named `python3`, then run the file `main.py`, which is PVNM's editor entry point.

If `python3` points to the wrong Python installation, use the full path to the Python you installed.

```bash
/path/to/python3 main.py
```

## If It Does Not Start

### `python3` is not found

Install Python 3 and make sure it is available from your terminal.

### `pyxel` is not found

Install the runtime requirements again.

```bash
python3 -m pip install -r requirements.txt
```

### macOS uses the wrong Python

Check `which python3` and run PVNM with the full Python path if necessary.

```bash
/path/to/python3 main.py
```
