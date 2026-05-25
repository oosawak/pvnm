# Game Release Checklist

Use this checklist before publishing files exported from PVNM. The focus is the exported game data. GitHub Releases is included only as one possible distribution target.

Japanese version: [作品公開前チェックリスト](../ja/work-release-checklist.md)

For PVNM itself, see [PVNM Release Checklist](pvnm-release-checklist.md).

## 1. Choose What To Publish

- [ ] You have decided the target platforms: Windows, macOS, Web, Android, or others.
- [ ] You chose the matching PVNM export format.
- [ ] You re-exported from the final project data.
- [ ] You decided whether file names include version and game title.
- [ ] Old exports and new exports are not mixed together.

## 2. Check Export Contents

| Format | What to check |
| --- | --- |
| `[PYXAPP]` | `.pyxapp` exists |
| `[PYXAPP + ASSETS]` | `.pyxapp` and `<name>_assets/` can be distributed together |
| `[macOS APP]` | `.app` exists. Zip it before distribution |
| `[WINDOWS EXE]` | Windows zip contains `.exe` and required runtime files |
| `[WEB HTML]` | `.html`, `<name>_assets/`, and `pyxel/` are present together |
| `[ANDROID APK RELEASE]` | Signed APK and `.sha256` exist |

`[ANDROID PROJECT]` and `[ANDROID APK DEBUG]` are mainly for testing. Public Android distribution usually uses signed `[ANDROID APK RELEASE]`.

## 3. Startup and Full Playthrough

- [ ] The zip or APK starts in the same shape users will download.
- [ ] Title image and title BGM work.
- [ ] The game can be played from start to ending.
- [ ] Backgrounds, character images, BGM, and SE behave as expected.
- [ ] Choices and branches behave as expected.
- [ ] EXTRAS unlocks after all endings.
- [ ] CG GALLERY and EXTRA TEXT display correctly.
- [ ] Save/load works.
- [ ] You tested on an environment close to the target, such as real Windows or an Android device/emulator.

## 4. Images and Audio

- [ ] Image colors are acceptable on the target platform.
- [ ] Images, BGM, and SE are not missing from the export.
- [ ] You did not manually add unnecessary original images or work files to the distribution package.
- [ ] BGM/SE volume balance is acceptable.
- [ ] Web/Android audio plays after the first user interaction.

If colors look wrong, use [Colors and Tools](colors-and-tools.md) and test on the actual target.

## 5. Distribution Files

- [ ] Windows/macOS/Web are zipped in the unit users will download.
- [ ] Web zip preserves `.html`, `<name>_assets/`, and `pyxel/` layout.
- [ ] Android distribution uses Release APK.
- [ ] If distributing `.sha256`, it matches the main file and is placed beside it.
- [ ] File names are easy to understand, such as `MyGame-windows-v1.0.0.zip`.
- [ ] PVNM license notice files included in the export are not removed.

## 6. Game-Specific Information

- [ ] Game title, version, and supported OS/environment are written.
- [ ] Launch instructions are written.
- [ ] Controls and save/load behavior are explained.
- [ ] Terms of use, streaming/video policy, asset credits, and other game-specific notices are prepared.
- [ ] The game has its own copyright notice or terms, separate from PVNM's license notices.
- [ ] A contact or bug report location is decided.

For a game website, see [Game Website Guide](work-website.md).

## 7. If Using GitHub Releases

GitHub Releases is one possible distribution target. If you use another service such as itch.io, Booth, Google Drive, or your own site, adapt this section.

- [ ] You have a GitHub account.
- [ ] You have a distribution repository.
- [ ] You decided whether the repository should be public.
- [ ] You have permission to create Releases.
- [ ] The Release tag is user-facing, such as `v1.0.0`.
- [ ] Release title and description include game title, version, changes, and supported platforms.
- [ ] Release Assets include the files users should download.

## 8. Final Check

- [ ] Download from the public route and test again.
- [ ] Links on the game website or announcement point to the intended files.
- [ ] The latest version is clear to users.
