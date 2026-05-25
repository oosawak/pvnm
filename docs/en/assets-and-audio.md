# Assets and Audio

This page explains how PVNM handles backgrounds, character images, BGM, and SE.

Japanese version: [素材と音声](../ja/assets-and-audio.md)

## Asset Folders

The file picker starts from a default folder for each asset type.

| Use | Default folder |
| --- | --- |
| Background images | `assets/images/bg/` |
| Character images | `assets/images/chars/` |
| BGM | `assets/sounds/bgm/` |
| SE | `assets/sounds/se/` |

You may create subfolders inside these folders. The file picker lets you move inside the selected root folder.

## Supported Files

| Type | Extensions |
| --- | --- |
| Images | `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp` |
| Audio | `.mp3`, `.ogg`, `.wav` |

Markdown import accepts `.md`, `.markdown`, and `.txt`. Project open accepts `.pvnm`.

## File Picker

The file picker shows files and folders on the left and a preview on the right.

| Action | Result |
| --- | --- |
| Click | Select a file or folder |
| `OK` | Apply the selected file |
| `CANCEL` / `Esc` | Cancel selection |
| `Enter` | Confirm the selected file, or enter the selected folder |
| Up/down keys | Move selection |
| Mouse wheel | Scroll the list |

Image previews show the palette-processed appearance used by PVNM. Audio files can be auditioned with `PLAY` / `STOP`.

## Background Images

Choose a background from `[BACKGROUND IMAGE]` in the `SCENE` tab. The selected path is stored as `./assets/images/bg/...`.

| State | Behavior |
| --- | --- |
| Image set | Use it as the background from this scene onward |
| Empty | Inherit the previous background |
| `HIDE BACKGROUND` | Stop inheritance and hide the background |

`BACKGROUND FULLSCREEN` fits the image to the whole screen. `BG SAFE AREA` keeps the image above the dialogue area so the lower part is less likely to be covered.

## Character Images

Character images are selected from `[FILE]` in the `LEFT`, `CENTER`, or `RIGHT` subtabs of `CHARACTERS`. The selected path is stored as `./assets/images/chars/...`.

| State | Behavior |
| --- | --- |
| Image set | Use it in the same slot from this scene onward |
| Empty | Inherit the previous image for that slot |
| `HIDE CHARACTER` | Stop inheritance and hide the slot |

Each slot can set scale, x/y position, color key, horizontal flip, vertical flip, and animation.

## COLOR KEY

`COLOR KEY` controls transparency for character images.

| Value | Meaning |
| --- | --- |
| `AUTO` | Use alpha or a safe automatic transparent color handling |
| `NONE` | Do not use a transparent color |
| `0` - `255` | Use a Pyxel palette index as transparent color |

Start with `AUTO` and adjust only if the image loses pixels unexpectedly.

## BGM

Choose BGM from `[BACKGROUND MUSIC FILE]` in the `SCENE` tab. The selected path is stored as `./assets/sounds/bgm/...`.

| State | Behavior |
| --- | --- |
| BGM set | Start playing BGM from this scene |
| Empty | Inherit the previous BGM |
| `STOP BGM` | Stop inherited BGM |
| `PLAY BGM ONCE` | Play once without looping |

Use `BACKGROUND MUSIC VOLUME` to adjust volume. `BGM FADE OUT` sets transition fade-out frames.

## SE

Choose SE from `[SOUND EFFECT FILE]` in the `SCENE` tab. The selected path is stored as `./assets/sounds/se/...`.

SE plays when the scene starts and is not inherited like BGM.

| Item | Purpose |
| --- | --- |
| `SOUND EFFECT VOLUME` | SE volume |
| `SOUND EFFECT REPEAT (0=once)` | Repeat count. `0` means one playback |

## Clearing Assets

Right-click file fields to clear selected background, character, BGM, or SE files. Empty background, character, and BGM fields inherit from previous scenes, so use `HIDE BACKGROUND`, `HIDE CHARACTER`, or `STOP BGM` when you want to explicitly remove something.

## Loading Image and App Icon

If you place PNG files with specific names in the project folder, PVNM automatically uses them in some exports. These are not selected from an editor setting; they are detected by file name and location.

| File | Use | Export targets |
| --- | --- | --- |
| `assets/images/ui/loading.png` | Startup loading image | Web HTML, Android Project/APK |
| `assets/images/ui/app_icon.png` | App/executable icon | macOS APP, Windows EXE, Android Project/APK |

Both files are optional. If they do not exist, PVNM uses its bundled defaults.

The loading image appears while Web or Android startup waits for PVNM's first draw. The app icon is used by PyInstaller for macOS/Windows and converted into Android launcher icon sizes for Android.

Use PNG files. A square app icon usually converts most reliably across platforms.

| Target | See |
| --- | --- |
| Web | [Web HTML Export](export-web.md) |
| Android | [Android Export](export-android.md) |
| Windows | [Windows EXE Export](export-windows.md) |

## Checking Colors

Use [Colors and Tools](colors-and-tools.md) and VN Palette Tool when you want to tune images for PVNM's palette. Always check the final appearance in PVNM preview and in the target export environment.
