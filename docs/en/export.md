# Export Overview

PVNM can export projects into several distribution formats.

Japanese version: [エクスポート概要](../ja/export.md)

For internal details such as export workers, image cache prebuild, `image_manifest.json`, and Web/Android asset externalization, see [Export Design](technical-export.md).

## Quick Table

| Menu | Output | Main use |
| --- | --- | --- |
| `[PYXAPP]` | `.pyxapp` | Single Pyxel package |
| `[PYXAPP + ASSETS]` | `.pyxapp` and external assets folder | Portable package with assets beside it |
| `[macOS APP]` | `.app` | macOS distribution |
| `[WINDOWS EXE]` | Windows zip | Windows distribution |
| `[WEB HTML]` | HTML, assets, `pyxel/` | Browser distribution |
| `[ANDROID PROJECT]` | Capacitor Android project | Android Studio / Gradle workflow |
| `[ANDROID APK DEBUG]` | Debug APK | Device testing |
| `[ANDROID APK RELEASE]` | Signed Release APK and `.sha256` | Distribution candidate |

Each exported build includes PVNM runtime and bundled third-party notices such as `PVNM_LICENSE.txt`, `PVNM_THIRD_PARTY_NOTICES.md`, and `PVNM_EXPORT_LICENSE_README.txt`. These notices are not your game's own license. Prepare separate copyright, terms, and asset credits for your scenario, images, music, characters, and other original content.

## Local Builds and Actions Builds

| Format | Where it runs | Notes |
| --- | --- | --- |
| `[PYXAPP]` | Local | Creates one `.pyxapp` |
| `[PYXAPP + ASSETS]` | Local | Uses `.pyxapp` plus an external assets folder |
| `[macOS APP]` | Local macOS | Requires PyInstaller. Zip the `.app` for distribution |
| `[WINDOWS EXE]` | GitHub Actions on macOS, local on Windows | macOS uses a Windows runner |
| `[WEB HTML]` | Local | Keep HTML, assets, and `pyxel/` together |
| `[ANDROID PROJECT]` | Local | Generates a Capacitor project |
| `[ANDROID APK DEBUG]` | Local | Generates an intermediate Android project and copies a Debug APK |
| `[ANDROID APK RELEASE]` | Local | Generates a signed Release APK and `.sha256` |

Windows EXE Actions integration is available when the game repository contains `.github/workflows/windows-exe.yml`. The export menu currently triggers Actions directly only for `[WINDOWS EXE]`. Android Release APK can be built locally with `[ANDROID APK RELEASE]`; if you want Android Actions, prepare a workflow in the game repository.

## Per-Format Pages

| Format | Page |
| --- | --- |
| Windows EXE | [Windows EXE Export](export-windows.md) |
| Web HTML | [Web HTML Export](export-web.md) |
| Android | [Android Export](export-android.md) |
| Release distribution | [Release Distribution](releases.md) |

## Before Exporting

- Save the project.
- Make sure the target assets exist.
- For GitHub Actions builds, commit and push the state you want to build.
- For Release APK, back up the signing key.
- Test the exported result in the target environment.

Actions-based formats such as Windows EXE cannot see local uncommitted changes. Save, commit, and push before running them.
