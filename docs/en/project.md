# Project Management

This page covers creating, saving, opening, and importing PVNM projects.

Japanese version: [プロジェクト管理](../ja/project.md)

## New Project

Create a new project with `Cmd/Ctrl+N`. PVNM starts with a default sample scene.

## Save

Save with `Cmd/Ctrl+S` or `SETTINGS > PROJECT > SAVE PROJECT`. Use `SAVE AS` when you want to choose a new `.pvnm` file.

## Open

Use `OPEN` or `Cmd/Ctrl+O` to select a `.pvnm` project file.

## Import From Markdown

`IMPORT MD` imports a script from `.md`, `.markdown`, or `.txt`.

The import creates Part / Chapter / Scene structure from Markdown headings and turns body text into scene text. Use this as a starting point, then assign backgrounds, character images, audio, and branches in the editor.

## Markdown Format

Example:

```markdown
# Part Name
## Chapter Name
### Scene Name

Alice: Hello.

Bob: Hi.
```

The exact imported result depends on the script structure, so check the generated scenes after import.

## Project Files

A `.pvnm` file stores scene data, project settings, and asset references. It does not turn every source asset into a standalone public release by itself. Export creates the distribution files for each target.

When building Windows EXE through GitHub Actions, commit and push the project state you want to build. Actions cannot see uncommitted local changes.
