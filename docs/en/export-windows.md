# Windows EXE Export

Windows EXE export behaves differently depending on the OS running PVNM.

Japanese version: [Windows EXEエクスポート](../ja/export-windows.md)

| Environment | Behavior |
| --- | --- |
| macOS | Builds on a GitHub Actions Windows runner |
| Windows | Builds locally with PyInstaller |

PVNM does not cross-compile a Windows executable directly on macOS. It uses a Windows environment through GitHub Actions.

If the project contains `assets/images/ui/app_icon.png`, it is used as the Windows EXE icon. See [Assets and Audio](assets-and-audio.md).

## Flow From macOS

1. Save the PVNM project.
2. Commit changes.
3. Push to GitHub.
4. Run `[WINDOWS EXE]` from `SETTINGS > EXPORT`.
5. PVNM triggers GitHub Actions.
6. Download `<ProjectName>-windows` from Actions Artifacts.

PVNM first tries `gh workflow run`, then tries API dispatch with `PVNM_GITHUB_TOKEN` / `GH_TOKEN` / `GITHUB_TOKEN`. If those are not available but SSH `git push` works, PVNM pushes a temporary `pvnm-windows-build-*` tag to trigger Actions.

When a temporary tag starts the workflow, the workflow is expected to delete the remote tag. PVNM also deletes the local tag, so users normally do not manage these tags manually.

## Flow On Windows

1. Install PyInstaller with `python -m pip install -r requirements-build.txt`.
2. Start PVNM on Windows.
3. Run `[WINDOWS EXE]` from `SETTINGS > EXPORT`.
4. Choose the output location.
5. PVNM creates the Windows folder and zip at the selected location.

## Requirements

| Requirement | Reason |
| --- | --- |
| GitHub repository | Required for Actions builds from macOS |
| `.github/workflows/windows-exe.yml` in the game repository | Defines the Windows build job |
| GitHub authentication | Allows PVNM to use workflow dispatch, API dispatch, or temporary tag push |
| Committed project state | Actions builds GitHub contents, not local uncommitted changes |
| `requirements-build.txt` | PyInstaller dependencies for local Windows builds |

## Authentication

To trigger GitHub Actions from PVNM, authenticate with one of these methods.

```bash
gh auth login
```

Or set `PVNM_GITHUB_TOKEN`. Registering an SSH key and confirming that `git push` works can also allow the temporary tag trigger path.

## Local Changes

When building through GitHub Actions, PVNM does not start the Windows build if the working tree has uncommitted changes. GitHub Actions cannot read your local uncommitted files.

Commit and push the state you want to build.

```bash
git status
git add .
git commit -m "Update project"
git push
```

## Artifacts

GitHub Actions creates an artifact such as `<ProjectName>-windows`. GitHub downloads artifacts as zip files, so the downloaded zip may contain a folder such as `<ProjectName>/<ProjectName>.exe`.

Artifacts are temporary build results. For public distribution, [Release Distribution](releases.md) is usually clearer.

## Release Builds

If your workflow supports it, pushing a `v*` tag such as `v1.0.0` can create a release zip and `.sha256`, then upload them to the GitHub Release for that tag. If the Release does not exist, the workflow may create a draft Release depending on its design.

The normal Windows EXE export launched from PVNM is a confirmation Artifact flow. For official distribution, either upload the tested Artifact to a Release, or run a Release-oriented workflow with a public version tag.
