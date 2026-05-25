# Release Distribution

This page explains how to think about temporary builds and official release builds.

Japanese version: [リリース配布](../ja/releases.md)

## Temporary Builds and Release Builds

| Type | Location | Use |
| --- | --- | --- |
| Actions Artifact | Output of a GitHub Actions run | Testing and temporary confirmation |
| GitHub Release Asset | File attached to a GitHub Release | Official distribution |

Artifacts are usually downloaded by project owners or collaborators while checking a build. Release Assets are the files you link from a public website or release page.

## Recommended Flow

1. Export or build the target format.
2. Test the result locally or from Actions Artifacts.
3. Create a public version tag such as `v1.0.0`.
4. Create a GitHub Release for that tag.
5. Upload Windows zip, macOS zip, Web zip, Android APK, and any `.sha256` files as Release Assets.
6. Link your website or announcement to the Release or specific Release Assets.

## Distributing From Another Repository

It is fine to build a project in one repository and upload the resulting files to a different public website or distribution repository. This is useful when the project repository is private but the website and downloads are public.

Make sure the public Release contains only distribution files, not private source assets, signing keys, or work-in-progress project data.

## Tags

Use tags such as `v1.0.0` as public release versions. Tags such as `pvnm-windows-build-*` are temporary triggers used by PVNM to start Windows EXE confirmation builds.

For official distribution, keep the visible user-facing version on a clear tag such as `v1.0.0`.

If the game repository has Release workflows, `v*` tags can be used to upload Windows EXE or Android Release APK files to GitHub Releases. `pvnm-windows-build-*` should remain a temporary Artifact trigger and should not create Release Assets.
