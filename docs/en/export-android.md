# Android Export

PVNM can export Android Project, Debug APK, and Release APK.

Japanese version: [Androidエクスポート](../ja/export-android.md)

If the project contains `assets/images/ui/loading.png`, it is used as the loading image while the Android app starts its Web runtime. If `assets/images/ui/app_icon.png` exists, it is converted into Android launcher icons. See [Assets and Audio](assets-and-audio.md).

## Menus

| Menu | Output | Use |
| --- | --- | --- |
| `[ANDROID PROJECT]` | Android project | Android Studio / Gradle workflow |
| `[ANDROID APK DEBUG]` | Debug APK | Local device testing |
| `[ANDROID APK RELEASE]` | Release APK and `.sha256` | Signed distribution candidate |

## Requirements

Android export requires Android Studio, Android SDK, Android Studio bundled JDK or Java 17, Node.js/npm, and Python dependencies. Release APK export also requires signing configuration.

## Android Project

`[ANDROID PROJECT]` creates a Capacitor-based Android project. The output includes the game's Web files, helper scripts, and generated documentation.

| File | Purpose |
| --- | --- |
| `www/index.html` | Normal startup Web app |
| `www/pvnm_diagnostics.html` | Diagnostics page for storage/audio/input |
| `www/pvnm_debug.html` | Startup page with debug HUD |
| `serve_web.sh` | Test the Web build locally before Android build |
| `build_android.sh` | Run `sync`, `open`, `run`, `build-debug`, `build-release` |
| `android_log.sh` | Check device and WebView logs |
| `README_PVNM_CAPACITOR.md` | Generated project guide |

After generation, first test:

```bash
./serve_web.sh diagnostics
./serve_web.sh debug
```

To open in Android Studio:

```bash
./build_android.sh open
```

## Debug APK

`[ANDROID APK DEBUG]` is for device testing. PVNM creates an intermediate Android project, runs the equivalent of `build_android.sh build-debug`, and copies the generated `app-debug.apk` to the selected output location.

Install it on an Android device and check display, audio, saves, and EXTRAS.

## Release APK

`[ANDROID APK RELEASE]` is the distribution candidate flow. PVNM creates an intermediate Android project, runs the equivalent of `build_android.sh build-release`, and copies the signed `app-release.apk` to the selected output location. A `.sha256` file is created beside it.

On the first local Release build, PVNM creates `pvnm-signing/release.jks` and `pvnm-release-signing.properties` inside the intermediate Android project. This signing key is required for future updates. Back it up and do not commit it.

Changing the output location can also change the intermediate Android project location, which can create a different signing key. If you want to keep updating the same app, reuse the same intermediate project or provide the existing signing key through environment variables.

Existing signing keys can be passed through environment variables.

| Environment variable | Purpose |
| --- | --- |
| `PVNM_ANDROID_KEYSTORE_BASE64` | Base64-encoded keystore |
| `PVNM_ANDROID_KEYSTORE_FILE` / `PVNM_ANDROID_KEYSTORE_PATH` | Existing keystore path |
| `PVNM_ANDROID_KEYSTORE_PASSWORD` | Keystore password |
| `PVNM_ANDROID_KEY_ALIAS` | Key alias. Defaults to `pvnm` |
| `PVNM_ANDROID_KEY_PASSWORD` | Key password. Defaults to the keystore password |

Before distribution, confirm the APK is signed and upload it to GitHub Releases or your chosen distribution channel.

| Check | What to verify |
| --- | --- |
| Startup | Title screen appears |
| Images | Backgrounds, characters, and CGs display |
| Audio | BGM and SE play |
| Controls | Text advance, choices, and menus work |
| Save | Save/load works |
| EXTRAS | Unlocks after endings |

## If Output Is Missing

If the selected output location appears empty, the build may have failed before the final copy step. Check Android SDK, Java/JDK, Node.js/npm, Gradle, signing settings, and output permissions.

If the intermediate Android project exists, run these commands there to inspect the failure:

```bash
./build_android.sh build-debug
./build_android.sh build-release
./android_log.sh pvnm
```

## Building Release APK With GitHub Actions

PVNM does not currently trigger Android GitHub Actions directly from the menu. If you want to build signed Release APKs in Actions, prepare an Android build workflow in the game repository and run it manually from GitHub or by pushing `v*` tags.

Actions signing usually uses GitHub Secrets.

| Secret | Required | Purpose |
| --- | --- | --- |
| `ANDROID_KEYSTORE_BASE64` | Required | Base64-encoded keystore |
| `ANDROID_KEYSTORE_PASSWORD` | Required | Keystore password |
| `ANDROID_KEY_ALIAS` | Optional | Key alias. Defaults to `pvnm` |
| `ANDROID_KEY_PASSWORD` | Optional | Key password. Defaults to the keystore password |

If your workflow includes Release upload, a tag such as `v1.0.0` can upload the APK and `.sha256` to the GitHub Release for that tag. For manual runs, using Actions Artifacts for confirmation is often easier.
