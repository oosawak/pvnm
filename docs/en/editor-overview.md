# Editor Overview

This page explains the main areas you see after starting PVNM and the basic workflow.

Japanese version: [画面と基本操作](../ja/editor-overview.md)

## Main Areas

After startup, PVNM shows the scene list on the left, the preview in the center, the edit panel on the right, and the toolbar at the bottom.

| Area | Purpose |
| --- | --- |
| Bottom toolbar | Switch `SCENE` / `FLOW`, show the file name, `IMPORT MD`, `SETTINGS`, `OPEN`, `QUIT`, `PLAY` |
| Scene list | Select Part / Chapter, select scenes, `+ADD`, `COPY`, `DEL` |
| Edit panel | Edit the selected scene: text, background, characters, BGM, SE, flow, choices |
| SETTINGS | Configure project settings, title, endings, colors, EXTRAS, and exports |

## Basic Workflow

1. Create a new project with `Cmd/Ctrl+N`, or open an existing project with `OPEN`.
2. Add scenes with `+ADD`.
3. Set text, background, character images, BGM, SE, and flow for each scene.
4. Preview with `PLAY`.
5. Save with `Cmd/Ctrl+S` or `SETTINGS > PROJECT > SAVE PROJECT`.
6. Export from `SETTINGS > EXPORT`.

## SETTINGS

| Item | Purpose |
| --- | --- |
| `PROJECT` | Check and edit project information |
| `TITLE CONFIG` | Configure the title screen |
| `ENDING CONFIG` | Register and edit endings |
| `CG GALLERY` | Configure CG gallery images for EXTRAS |
| `EXTRA TEXT` | Configure text pages for EXTRAS |
| `COLOR CONFIG` | Configure global UI colors |
| `SPEAKER COLORS` | Configure speaker-specific name and text colors |
| `TOOLS` | Open helper tools |
| `EXPORT` | Export to each supported format |

## Keyboard Shortcuts

| Action | macOS | Windows |
| --- | --- | --- |
| NEW | `Cmd+N` | `Ctrl+N` |
| OPEN | `Cmd+O` | `Ctrl+O` |
| SAVE | `Cmd+S` | `Ctrl+S` |
| SAVE AS | `Cmd+Shift+S` | `Ctrl+Shift+S` |
| PLAY | `1` | `1` |
| QUIT | `Cmd+Q` | `Ctrl+Q` |
| Export PYXAPP | `Cmd+E` | `Ctrl+E` |
| Export macOS APP | `Cmd+Shift+E` | `Ctrl+Shift+E` |
| Export Web HTML | `Cmd+Option+E` | `Ctrl+Alt+E` |
| Export Android Project | `Cmd+Option+Shift+E` | `Ctrl+Alt+Shift+E` |

`SETTINGS`, `IMPORT MD`, `+ADD`, `COPY`, `DEL`, `WINDOWS EXE`, `ANDROID APK DEBUG`, and `ANDROID APK RELEASE` are currently run from on-screen buttons or `SETTINGS > EXPORT`.

## Player Controls

In exported games, click, Enter, or Space advances text. When choices are visible, click a choice to branch.
