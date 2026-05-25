# Contributing

Contributions, bug reports, documentation fixes, and implementation notes are welcome.

Japanese users can start from [README.ja.md](README.ja.md) and [docs/ja/](docs/ja/).

## Principles

- Check the existing implementation and UI before changing behavior.
- Keep README and docs aligned with features that actually exist in PVNM.
- Do not commit game project data, signing keys, tokens, private assets, or local-only settings.
- For large changes, open an Issue or Discussion first so the purpose and scope are clear.
- Keep changes focused. Avoid unrelated refactors when fixing a specific issue.

## Development Environment

Python 3.12 is recommended.

```bash
python3 -m pip install -r requirements.txt
python3 main.py
```

If your platform has multiple Python installations, run PVNM with an explicit Python path.

```bash
/path/to/python3 main.py
```

For local PyInstaller-based builds, install the build requirements.

```bash
python3 -m pip install -r requirements-build.txt
```

On macOS, optional AVFoundation audio dependencies are listed separately.

```bash
python3 -m pip install -r requirements-macos-avfoundation.txt
```

## How To Work On Changes

1. Define the goal of the change.
2. Read the relevant code in `engine/`, `ui/`, `tools/`, and `docs/`.
3. Keep the change small enough to review.
4. Run checks that match the changed area.
5. Update README/docs when behavior, setup, or export flows change.

## Checks

For simple Python changes, at least compile the touched entry points or modules.

```bash
python3 -m py_compile main.py
```

For multi-file changes, pass each touched Python file to `py_compile`.

For documentation-only changes, check Markdown links and make sure the English and Japanese structures still point to valid pages.

For export-related changes, test the affected export format when practical:

- `[PYXAPP]`
- `[PYXAPP + ASSETS]`
- `[macOS APP]`
- `[WINDOWS EXE]`
- `[WEB HTML]`
- `[ANDROID PROJECT]`
- `[ANDROID APK DEBUG]`
- `[ANDROID APK RELEASE]`

If a target cannot be tested locally, describe what was not tested in the Pull Request.

## Pull Requests

Please include:

- What changed
- Why it changed
- What you tested
- What you could not test

If the UI or exported output changes, screenshots or notes from the generated build are helpful.

## License

By contributing to PVNM, you agree that your contribution is provided under the same MIT License as PVNM.

If you add third-party code, fonts, assets, or generated files, include the source and license information. Do not add material that cannot be redistributed with an MIT-licensed project.
