# Changelog

This file records notable PVNM changes. After the first public release, user-facing changes should be added here for each version.

## Unreleased

### Added

- Added the MIT License for PVNM.
- Added `THIRD_PARTY_NOTICES.md` for bundled fonts, runtimes, and dependency notices.
- Added public-repository support files: `CONTRIBUTING.md` and `SECURITY.md`.
- Added the English README and English documentation under `docs/en/`.

### Changed

- Moved the Japanese README entry point to `README.ja.md`.
- Moved Japanese documentation under `docs/ja/`.
- Reworked the root README as the English public entry point.
- Rewrote repository policy files in English for public GitHub publication.

### Notes

- PVNM has not had its first public versioned release yet.
- For the first public release, create a user-facing tag such as `v1.0.0` and a GitHub Release, then replace this section with a dated release entry.

## 2026-05-25 - Documentation preparation

### Added

- Added documentation for first-time setup, editor overview, project management, scene editing, assets/audio, title/EXTRAS, colors/tools, export flows, distribution, FAQ, and troubleshooting.
- Added separate checklists for publishing games made with PVNM and publishing PVNM itself.
- Added a guide for creating a game website, including a GitHub Pages example and a Last Emulator-style publication flow.
- Added a guide for publishing PVNM itself.

### Changed

- Reworked README as an entry page and moved detailed operation notes into docs.
- Kept documentation aligned with implemented features only, removing outdated or unavailable UI references.

## 2026-05-24 - Export workflows

### Added

- Added a flow for triggering Windows EXE builds through GitHub Actions from macOS.
- Organized signed Android Release APK export behavior.
- Documented GitHub Releases as the recommended official distribution route.

### Changed

- Clarified distribution outputs and verification steps for Windows EXE, Web HTML, and Android APK exports.

## 2026-05-14 - Cache-based image export

### Added

- Added support for restoring images from `image_manifest.json` and `pvnm_cache/*.npy` in distributed environments without original source images.

### Changed

- Reduced distribution size by avoiding unnecessary original full-size image files in lightweight exports.
