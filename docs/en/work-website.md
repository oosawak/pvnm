# Game Website Guide

When publishing a PVNM game, it is often useful to create a separate website for the game. This page uses the Last Emulator release flow as an example: a static website links to files hosted on GitHub Releases.

Japanese version: [作品紹介サイトの作り方](../ja/work-website.md)

## Overview

A game website can contain the game description, screenshots, download buttons, supported platforms, credits, and update notes. Instead of committing large zip or APK files directly into the website repository, put them on GitHub Releases and link to them from the site.

Last Emulator used this split:

| Role | Example | Purpose |
| --- | --- | --- |
| Production/build repository | `game-de-it/last-emulator-project` | PVNM project, assets, Windows EXE Actions, build work |
| Public website repository | `game-de-it/last-emulator-web` | Landing page, screenshots, download buttons, GitHub Pages settings |
| Distribution files | Releases of the website repository | Windows zip, macOS zip, Web zip, Android APK |

This keeps work-in-progress data private while making only the website and player-facing downloads public.

## 1. Prepare Exported Files

Export the formats you want to publish:

- Windows: `[WINDOWS EXE]`
- macOS: `[macOS APP]`
- Browser: `[WEB HTML]`
- Android: `[ANDROID APK RELEASE]`

Before publishing, use [Game Release Checklist](work-release-checklist.md) and test the zip or APK in the same shape players will download. For Web builds, keep `.html`, `<name>_assets/`, and `pyxel/` in the correct layout when zipping.

## 2. Choose Distribution Location

If you use GitHub Releases, choose a repository to host the release files. When you have a separate website repository, putting release files on that repository's Releases page keeps the public site and downloads together.

Check:

- [ ] You have a GitHub account.
- [ ] You have a distribution repository.
- [ ] You know whether it should be public or private.
- [ ] You have permission to create Releases.
- [ ] You have a public release tag such as `v1.0.0`.

`pvnm-windows-build-*` is a temporary tag for Windows EXE confirmation builds. Use user-facing tags such as `v1.0.0` for official downloads.

## 3. Create a GitHub Release

Create a new Release from GitHub's Releases page.

- Tag: public version such as `v1.0.0`
- Title: game title and version
- Description: changes, supported platforms, known issues
- Assets: Windows zip, macOS zip, Web zip, Android APK, and `.sha256` if needed

Example asset names:

```text
LastEmulator-windows-v1.0.0.zip
LastEmulator-macos-v1.0.0.zip
LastEmulator-web-v1.0.0.zip
LastEmulator-android-v1.0.0.apk
LastEmulator-android-v1.0.0.apk.sha256
```

## 4. Decide Website Content

Useful minimum content:

- Game title
- Tagline
- Short description
- Screenshots
- Download buttons
- Supported OS/environment
- Launch instructions
- Controls
- Streaming/video policy
- Asset credits
- Changelog
- Contact or bug report location

The game files do not need to live inside the website repository. Download buttons can link to GitHub Release Assets.

## 5. Last Emulator-Style Publishing Flow

Generalized for PVNM games:

1. Finish the game in PVNM.
2. Export Windows/Web/Android and other target files.
3. Test Windows EXE through a GitHub Actions confirmation Artifact if needed.
4. Prepare official zips and APKs.
5. Upload distribution files to GitHub Releases in the public website repository.
6. Link website download buttons to those Release Assets.
7. Publish the website with GitHub Pages or another static host.
8. Download from the public page and test the files again.

This flow does not require the production project repository to be public. Only the website and player-facing distribution files need to be public.

## 6. Publishing With GitHub Pages

GitHub Pages can publish a static website directly from a repository. The Last Emulator website project at `~/last-emulator-web` is a simple example:

```text
last-emulator-web/
  index.html
  styles.css
  assets/
```

With this structure, set GitHub Pages to publish from the `main` branch and `/ (root)`.

Steps:

1. Create a repository for the game website.
2. Commit and push `index.html`, `styles.css`, `assets/`, and related files.
3. Open repository `Settings`.
4. Open `Pages`.
5. Under `Build and deployment`, choose `Deploy from a branch`.
6. Select `main` and `/ (root)`, then save.
7. Open the Pages URL shown by GitHub.

Project Pages URLs usually look like `https://<account>.github.io/<repository>/`. For example, `game-de-it/last-emulator-web` would be similar to `https://game-de-it.github.io/last-emulator-web/`.

GitHub's UI can change, so see the official GitHub Pages documentation if the settings differ.

## 7. Check Download Links

- [ ] The website opens.
- [ ] Download buttons point to Release Assets.
- [ ] Windows/macOS/Web/Android links are not mixed up.
- [ ] Release Assets download correctly.
- [ ] Downloaded files can be extracted or installed and started.
- [ ] Website version text matches the Release tag.

If you replace Release Assets, confirm the website does not still point to an old file.

## 8. Notes

- Do not put PVNM project files, signing keys, tokens, or private assets in the public website repository.
- When zipping Web builds, keep `.html`, `<name>_assets/`, and `pyxel/` in the correct layout.
- Use the same signing key when updating Android Release APKs.
- If downloads are split across multiple services, make the official distribution location clear.
