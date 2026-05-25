# FAQ

Short answers for common PVNM questions.

Japanese version: [FAQ](../ja/faq.md)

## Startup and Setup

### `python3 main.py` does not work

Check that Python 3 is installed and points to the expected version.

```bash
which python3
python3 --version
python3 -m pip install -r requirements.txt
python3 main.py
```

If macOS uses a different Python than expected, run PVNM with the full Python path.

```bash
/path/to/python3 main.py
```

### `ModuleNotFoundError` appears

Install dependencies again with `python3 -m pip install -r requirements.txt`.

### Does PVNM itself run on Windows?

Yes. PVNM is intended to run locally on macOS and Windows when Python/Pyxel dependencies are installed.

## Windows EXE

### Windows EXE Actions do not start

When running `[WINDOWS EXE]` from macOS, the build runs on GitHub Actions. Commit and push the project first because Actions cannot see local uncommitted changes. See [Windows EXE Export](export-windows.md).

### PVNM says GitHub authentication is missing

Run `gh auth login`, set `PVNM_GITHUB_TOKEN`, or make sure SSH `git push` works.

### Actions is Success but error annotations are visible

Check whether the job result is Success and whether the Artifact exists. Some warnings or intermediate command messages can appear as annotations even when the final build succeeded.

### The Artifact zip contains another folder level

This is normal. GitHub downloads Artifacts as zip files, and the artifact itself usually contains a folder such as `<ProjectName>/<ProjectName>.exe`.

## Android

### Android APK does not appear

Check Android Studio/SDK, Java/JDK, Node.js/npm, Gradle, signing settings, and output permissions. If an intermediate Android project exists, run `./build_android.sh build-debug` or `./build_android.sh build-release` there.

### Does Release APK need signing?

Yes. Release APKs must be signed. PVNM creates a local signing key on first local Release build if you do not provide one. Back it up.

### What is the difference between Debug APK and Release APK?

Debug APK is for testing. Release APK is signed for distribution and should be used for public downloads.

## Web HTML

### Web audio does not play

Browsers often block audio before the first user interaction. Click or press a key first, then test BGM/SE.

### Web images or assets do not appear

Keep `.html`, `<name>_assets/`, and `pyxel/` together. Moving only the HTML file breaks asset loading.

### How do I test Web locally?

Use a local server.

```bash
python3 -m http.server 8133
```

Then open `http://127.0.0.1:8133/<exported-html-name>`.

## Images and Audio

### Image colors differ between macOS and Windows

Final colors can vary by display environment and export path. Use VN Palette Tool and confirm on the actual target platform.

### Are original images included in exports?

PVNM exports usually run from the converted/runtime assets needed by the target format. Do not manually add source originals or work files to distribution zips unless you intentionally want to distribute them.

### Are PVNM license files the game's license?

No. PVNM license notice files cover PVNM and bundled third-party components. Your game still needs its own copyright notice, terms, and asset credits.

### Some BGM/SE files do not play

Check file path, extension, volume, and target environment. Web and Android can have different audio restrictions than desktop.

## Game Content

### EXTRAS does not unlock

EXTRAS unlocks after all registered endings are reached through natural ending completion. Check ending names and scene `GOTO ENDING` settings.

### Should save/load be tested?

Yes. Test save/load in each distribution target, especially Web and Android.

## Distribution

### What is the difference between Actions Artifact and Release Asset?

Actions Artifacts are temporary confirmation files from workflow runs. Release Assets are official files attached to a GitHub Release.

### What is the difference between `v1.0.0` and `pvnm-windows-build-*`?

`v*` tags such as `v1.0.0` are public release tags. `pvnm-windows-build-*` is a temporary trigger tag used by PVNM for Windows EXE confirmation Actions.

### I want to make a game website

See [Game Website Guide](work-website.md). A common flow is to host the website with GitHub Pages and put downloads on GitHub Releases.

### Can I publish a game website with GitHub Pages?

Yes. Put `index.html`, CSS, and assets in a repository, enable GitHub Pages, and link download buttons to Release Assets.

## Publishing PVNM

### What is the flow for publishing PVNM itself?

See [Publishing PVNM](pvnm-publication.md) and [PVNM Release Checklist](pvnm-release-checklist.md).

### Can I modify and publish PVNM?

Yes. PVNM is MIT licensed. Keep the copyright notice and license text, and you may use, modify, redistribute, and publish modified versions.

### What standard files should a public repository include?

Common files are `LICENSE`, `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, `THIRD_PARTY_NOTICES.md`, README, and docs.
