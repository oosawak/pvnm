# Palette Visual Novel Maker (PVNM)

Palette Visual Novel Maker (PVNM) is a Pyxel-based visual novel editor. It lets you edit scenes, backgrounds, character sprites, BGM/SE, choices, endings, and EXTRAS from a GUI, then export the project for macOS, Windows, Web, and Android.

Japanese README: [README.ja.md](README.ja.md)

This README is the entry point. Detailed guides are split into `docs/en/`.

## Quick Start

For the full setup flow, see [First-Time Setup](docs/en/setup.md).

```bash
python3 -m pip install -r requirements.txt
python3 main.py
```

On macOS, `python3` can point to different Python installations. If needed, run PVNM with an explicit Python 3.12 path.

```bash
/path/to/python3 main.py
```

## Documentation

| Goal | Page |
| --- | --- |
| Set up PVNM | [First-Time Setup](docs/en/setup.md) |
| Learn the editor layout and basic controls | [Editor Overview](docs/en/editor-overview.md) |
| Save, open, and import projects | [Project Management](docs/en/project.md) |
| Create scenes, dialogue, and branches | [Scene Editing](docs/en/scenes.md) |
| Use backgrounds, character images, BGM, and SE | [Assets and Audio](docs/en/assets-and-audio.md) |
| Configure the title screen, endings, and EXTRAS | [Title and EXTRAS](docs/en/title-extras.md) |
| Adjust UI colors, speaker colors, and palettes | [Colors and Tools](docs/en/colors-and-tools.md) |
| Understand PVNM internals, palette reduction, and export technology | [Technical Design Overview](docs/en/technical-overview.md) |
| Choose an export format | [Export Overview](docs/en/export.md) |
| Export a Windows build | [Windows EXE Export](docs/en/export-windows.md) |
| Export a Web build | [Web HTML Export](docs/en/export-web.md) |
| Export an Android build | [Android Export](docs/en/export-android.md) |
| Distribute builds with GitHub Releases | [Release Distribution](docs/en/releases.md) |
| Make a website for your game | [Game Website Guide](docs/en/work-website.md) |
| Check a PVNM game before publication | [Game Release Checklist](docs/en/work-release-checklist.md) |
| Publish PVNM itself | [Publishing PVNM](docs/en/pvnm-publication.md) |
| Check PVNM before public release | [PVNM Release Checklist](docs/en/pvnm-release-checklist.md) |
| Look up common questions quickly | [FAQ](docs/en/faq.md) |
| Troubleshoot common issues | [Troubleshooting](docs/en/troubleshooting.md) |

## Find By Goal

### Setup

| Goal | Page |
| --- | --- |
| Check the Windows/macOS requirements | [First-Time Setup](docs/en/setup.md) |
| Understand what `python3 main.py` does | [First-Time Setup](docs/en/setup.md) |
| Prepare Android export requirements | [Android Export](docs/en/export-android.md) |

### Project

| Goal | Page |
| --- | --- |
| Save a project | [Project Management](docs/en/project.md) |
| Open an existing project | [Project Management](docs/en/project.md) |
| Import a script from Markdown | [Project Management](docs/en/project.md) |

### Scene Editing

| Goal | Page |
| --- | --- |
| Add a dialogue scene | [Scene Editing](docs/en/scenes.md) |
| Move to the next scene | [Scene Editing](docs/en/scenes.md) |
| Branch with choices | [Scene Editing](docs/en/scenes.md) |
| Show backgrounds or character sprites | [Assets and Audio](docs/en/assets-and-audio.md) |
| Play BGM or SE | [Assets and Audio](docs/en/assets-and-audio.md) |

### Title and Extras

| Goal | Page |
| --- | --- |
| Configure the title screen | [Title and EXTRAS](docs/en/title-extras.md) |
| Register endings | [Title and EXTRAS](docs/en/title-extras.md) |
| Create a CG gallery | [Title and EXTRAS](docs/en/title-extras.md) |
| Edit EXTRA TEXT pages | [Title and EXTRAS](docs/en/title-extras.md) |

### Visuals

| Goal | Page |
| --- | --- |
| Change UI colors | [Colors and Tools](docs/en/colors-and-tools.md) |
| Set speaker-specific text colors | [Colors and Tools](docs/en/colors-and-tools.md) |
| Convert images into PVNM-style palette colors | [Colors and Tools](docs/en/colors-and-tools.md) |
| Set loading images and app icons | [Assets and Audio](docs/en/assets-and-audio.md) |

### Export and Distribution

| Goal | Page |
| --- | --- |
| Compare export formats | [Export Overview](docs/en/export.md) |
| Distribute a Windows build | [Windows EXE Export](docs/en/export-windows.md) |
| Distribute a browser build | [Web HTML Export](docs/en/export-web.md) |
| Build an Android APK | [Android Export](docs/en/export-android.md) |
| Publish files with GitHub Releases | [Release Distribution](docs/en/releases.md) |
| Make a game website | [Game Website Guide](docs/en/work-website.md) |
| Review a game before release | [Game Release Checklist](docs/en/work-release-checklist.md) |
| Publish PVNM on GitHub | [Publishing PVNM](docs/en/pvnm-publication.md) |
| Review PVNM before release | [PVNM Release Checklist](docs/en/pvnm-release-checklist.md) |

### Technical Design

| Goal | Page |
| --- | --- |
| Understand PVNM's internal structure | [Technical Design Overview](docs/en/technical-overview.md) |
| Understand quantization algorithms, scene palettes, and image cache | [Palette, Quantization, and Image Cache Design](docs/en/technical-palette.md) |
| Understand every VN Palette Tool setting and 0-10 parameter | [VN Palette Tool Detailed Design](docs/en/technical-vn-palette-tool.md) |
| Understand export workers, manifests, and Web/Android packaging | [Export Design](docs/en/technical-export.md) |

### When Something Goes Wrong

| Goal | Page |
| --- | --- |
| Check short answers | [FAQ](docs/en/faq.md) |
| Investigate common failures | [Troubleshooting](docs/en/troubleshooting.md) |

## Export Formats

| Menu | Output | Main use |
| --- | --- | --- |
| `[PYXAPP]` | `.pyxapp` | Single Pyxel package |
| `[PYXAPP + ASSETS]` | `.pyxapp` and `<name>_assets/` | Portable package with external assets |
| `[macOS APP]` | `.app` | macOS distribution |
| `[WINDOWS EXE]` | Windows zip | Windows distribution |
| `[WEB HTML]` | `.html`, `<name>_assets/`, `pyxel/` | Browser distribution |
| `[ANDROID PROJECT]` | Android project | Android Studio / Gradle workflow |
| `[ANDROID APK DEBUG]` | Debug APK | Device testing |
| `[ANDROID APK RELEASE]` | Release APK and `.sha256` | Signed distribution candidate |

See [Export Overview](docs/en/export.md) for details.

## Repository Layout

```text
main.py                         PVNM entry point
engine/                         Player, export, project, and runtime logic
ui/                             Editor screens
tools/                          Helper tools and build scripts
assets/                         PVNM built-in assets
resources/                      Runtime resources used by exports
docs/en/                        English documentation
docs/ja/                        Japanese documentation
```

## Dependencies

Runtime Python packages are listed in `requirements.txt`. Extra packages for macOS AVFoundation audio support are in `requirements-macos-avfoundation.txt`. Additional build-time packages for PyInstaller-based exports are in `requirements-build.txt`.

See [First-Time Setup](docs/en/setup.md) for the full installation flow.

## License

PVNM is released under the MIT License. With the copyright notice and license text preserved, anyone may use, copy, modify, redistribute, and use PVNM commercially. You may also publish your own modified version of PVNM.

Third-party font, Pyxel, Pyodide, and Python dependency notices are summarized in [Third-Party Notices](THIRD_PARTY_NOTICES.md).
