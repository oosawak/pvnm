# Troubleshooting

This page summarizes common problems.

Japanese version: [トラブルシュート](../ja/troubleshooting.md)

For shorter reverse lookup, see [FAQ](faq.md).

## Windows EXE Export Does Not Start

When there are uncommitted changes, GitHub Actions cannot build your local state. Check `git status`, commit the changes you need, and push.

## `GitHub authentication is not configured`

PVNM cannot trigger GitHub Actions. Run `gh auth login`, set `PVNM_GITHUB_TOKEN`, or register an SSH key with GitHub and confirm that `git push` works.

## Actions Shows Errors But The Run Is Success

If the overall job status is Success, Artifacts may still be generated. GitHub can show annotations from warnings or previous command failures. Check the final job result and whether the artifact exists.

## Web HTML Assets Do Not Show

You may have moved only the HTML file. Keep `.html`, `<name>_assets/`, and `pyxel/` in the same relative layout.

## Android APK Is Not Generated

Check Android SDK, Java/JDK, Node.js/npm, Gradle, signing settings, and output directory permissions. For Release APK, signing is required.

If an intermediate Android project exists, run `./build_android.sh build-debug` or `./build_android.sh build-release` inside it to see the failing step.

## Android Release Signing Fails

Local Release builds need `pvnm-signing/release.jks` and `pvnm-release-signing.properties`. Back them up after first generation. For Actions builds, check signing Secrets such as `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, and `ANDROID_KEY_PASSWORD`.

## Image Colors Differ Across Environments

Display environment and export format can affect the final look. Tune images with VN Palette Tool, then confirm on the target platform.
