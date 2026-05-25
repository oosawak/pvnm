# Publishing PVNM

This page outlines the steps for publishing PVNM itself on GitHub or a similar service.

Japanese version: [PVNM本体を公開する流れ](../ja/pvnm-publication.md)

For the final checklist, see [PVNM Release Checklist](pvnm-release-checklist.md).

## Overview

Publishing PVNM itself is separate from distributing a game exported by PVNM. The public target is PVNM source code, documentation, and optionally packaged PVNM application files.

Recommended flow:

1. Decide the public scope.
2. Align README and docs with the current implementation.
3. Prepare MIT License publication.
4. Remove files that should not be public.
5. Publish the GitHub repository.
6. Create a GitHub Release if needed.
7. Test setup as a new user.

## 1. Decide Public Scope

- [ ] Publish PVNM source code.
- [ ] Publish docs together with the source.
- [ ] Decide whether to include a sample project.
- [ ] Decide whether to attach packaged PVNM binaries as Release Assets.
- [ ] Do not include work-in-progress game data or private assets.

Source-only publication is enough for users to run PVNM from the README. If you also distribute packaged binaries, put them in Release Assets.

## 2. Prepare README and Docs

README should stay short as the entry point, with detailed pages under `docs/`.

- [ ] README links to first-time setup.
- [ ] README links to main feature pages.
- [ ] Docs do not describe features that are not present in the current UI.
- [ ] Windows/macOS requirements are clear.
- [ ] Export format differences are clear.
- [ ] Game publication and PVNM publication are documented separately.

Useful pages:

- [First-Time Setup](setup.md)
- [Export Overview](export.md)
- [Game Release Checklist](work-release-checklist.md)
- [PVNM Release Checklist](pvnm-release-checklist.md)

## 3. Prepare MIT License

PVNM is published under the MIT License. Put the MIT License text in `LICENSE` at the repository root.

The release page or README should communicate this:

> PVNM is released under the MIT License. With the copyright notice and license text preserved, anyone may use, copy, modify, redistribute, and use PVNM commercially. Publishing your own modified version of PVNM is also allowed.

Check:

- [ ] `LICENSE` exists.
- [ ] `THIRD_PARTY_NOTICES.md` summarizes third-party licenses.
- [ ] README explains the license.
- [ ] Copyright year/name are correct.
- [ ] Game assets with different licenses are not mixed into the PVNM source release.

## 4. Exclude Files That Should Not Be Public

Before making a repository public, check for private information.

Examples:

- Signing keys
- Tokens
- API keys
- Personal local paths
- Work-in-progress game data
- Private assets
- Large temporary files
- OS metadata files

Useful checks:

```bash
git status
git log --oneline -5
```

Use `rg` for words such as `token`, `password`, `secret`, personal names, and local paths.

## 5. Publish The GitHub Repository

You can make a private repository public, or push a clean snapshot to a new public repository.

If converting private to public:

- [ ] Latest commit is pushed.
- [ ] `LICENSE`, README, and docs are ready.
- [ ] Private data is not present.
- [ ] Change repository visibility to public in GitHub settings.
- [ ] Open README and docs from the public page.

If using a separate public repository:

- [ ] Decide the public repository name.
- [ ] Confirm `origin` points to the intended repository.
- [ ] Decide which branch to push.
- [ ] Keep the roles of private and public repositories clear.

If the private repository history contained private assets, use a clean initial public commit instead of pushing the old history.

## 6. Create a GitHub Release

Use GitHub Releases to communicate PVNM milestones.

Release description should include:

- Version
- Main changes
- Known limitations
- Supported environment
- Link to setup docs
- Packaged binaries if provided

Use public tags such as `v1.0.0`. Keep temporary build tags separate from official distribution tags.

## 7. Check After Publishing

- [ ] Public README is readable.
- [ ] README links to [First-Time Setup](setup.md).
- [ ] Dependencies install from `requirements.txt`.
- [ ] `python3 main.py` or an explicit Python path starts PVNM.
- [ ] SETTINGS, PLAY, save/open, and core editor actions work.
- [ ] Release Assets, if any, can be downloaded and extracted.

If problems appear after publication, push a fix and create a new Release if needed.
