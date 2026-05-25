# PVNM Release Checklist

Use this before publishing PVNM itself. For games exported from PVNM, see [Game Release Checklist](work-release-checklist.md).

Japanese version: [PVNM本体公開前チェックリスト](../ja/pvnm-release-checklist.md)

## 1. Repository State

- [ ] Public repository name and description are decided.
- [ ] The default branch is correct.
- [ ] The current tree does not include private game project files.
- [ ] `.gitignore` excludes local settings, work notes, build outputs, exported files, and game assets.
- [ ] If old history contains private assets, the public repository will use a clean initial commit.

## 2. License

- [ ] `LICENSE` contains the MIT License.
- [ ] README says PVNM is MIT licensed and may be modified and redistributed.
- [ ] `THIRD_PARTY_NOTICES.md` covers bundled fonts, Pyxel, Pyodide, and relevant dependencies.
- [ ] Exported PVNM license notices are included in exported games.

## 3. Documentation

- [ ] Root README is an entry point.
- [ ] Japanese docs are under `docs/ja/`.
- [ ] English docs are under `docs/en/`.
- [ ] Setup, editor basics, project management, scenes, assets, title/EXTRAS, colors, exports, release distribution, website guide, FAQ, and troubleshooting are linked.
- [ ] Docs match the current UI and do not mention removed features as available.

## 4. Local Startup

- [ ] Dependencies install with `requirements.txt`.
- [ ] `python3 main.py` starts PVNM, or the README explains how to use an explicit Python path.
- [ ] A new project starts with clean default settings.
- [ ] Save/open works.
- [ ] PLAY preview works.

## 5. Export Features

- [ ] `[PYXAPP]` exports.
- [ ] `[PYXAPP + ASSETS]` exports.
- [ ] `[macOS APP]` exports on macOS when build dependencies are installed.
- [ ] `[WINDOWS EXE]` behavior is documented for macOS Actions and Windows local builds.
- [ ] `[WEB HTML]` exports and runs through a local server.
- [ ] `[ANDROID PROJECT]` exports.
- [ ] `[ANDROID APK DEBUG]` builds for testing.
- [ ] `[ANDROID APK RELEASE]` creates a signed APK and `.sha256`.

If you cannot test every format before a release, test the formats closest to the changes you made.

## 6. GitHub Actions

- [ ] Decide whether Actions workflows belong in the PVNM repository or are documented as game-repository samples.
- [ ] If using Windows EXE Actions, document where `.github/workflows/windows-exe.yml` lives and how it is triggered.
- [ ] If documenting Android Release APK Actions, document required signing Secrets and trigger method.
- [ ] Actions Artifacts are explained as confirmation builds, and Release Assets as official distribution files.
- [ ] If Release upload is automated, it runs from `v*` tags.
- [ ] `pvnm-windows-build-*` stays a temporary confirmation tag and is not used as an official release tag.

## 7. GitHub Releases

- [ ] Use a user-facing tag such as `v1.0.0`.
- [ ] Release notes include supported environment and known limitations.
- [ ] Attach packaged PVNM binaries only if you intend to distribute them.
- [ ] Source code release does not contain private game data.

## 8. Final Check

- [ ] Open the public repository in a browser.
- [ ] README links work.
- [ ] English and Japanese docs are reachable.
- [ ] Clone the public repository into a clean directory and start PVNM.
- [ ] No local-only paths or private project names are present in tracked files.
