# Title and EXTRAS

This page explains how to configure the title screen, endings, CG gallery, and EXTRA TEXT.

Japanese version: [タイトルとEXTRAS](../ja/title-extras.md)

## TITLE CONFIG

Use `SETTINGS > TITLE CONFIG` to configure the title screen shown before the game starts.

| Item | Purpose |
| --- | --- |
| `BACKGROUND IMAGE` | Select the title background image. Right-click to clear |
| `BACKGROUND FULLSCREEN` | Fit the background to the screen. When off, PVNM centers the original image and scales down only if needed |
| `BACKGROUND MUSIC` | Select title BGM. Right-click to clear |
| `BACKGROUND MUSIC VOLUME` | Adjust title BGM volume |
| `BACKGROUND MUSIC LOOP` | Toggle title BGM looping |
| `BUTTON COLORS` | Set title button colors using 256-color master palette indexes |

`BUTTON COLORS` lets you set normal and hover background, border, and text colors. These colors are reserved during title image palette reduction so button colors are less likely to be crushed by image conversion.

| Button | Action |
| --- | --- |
| `SAVE & CLOSE` | Save settings and close |
| `REVERT ALL` | Restore settings from when the editor opened |
| `CANCEL` / `ESC` | Close without saving. Unsaved changes show a discard confirmation |
| `PLAY PREVIEW` | Preview the title screen with current settings |

## ENDING CONFIG

`ENDING CONFIG` registers endings that can be reached in the game. Registered endings also affect EXTRAS unlock conditions.

Select an ending on the left, manage it with `ADD`, `COPY`, and `DEL`, then edit the selected ending on the right.

| Item | Purpose |
| --- | --- |
| `NAME` | Ending name. This name is recorded as reached for EXTRAS unlocks |
| `CREDITS` | Scrolling credits text |
| `FONT SIZE` | Credits font size |
| `SCROLL SPEED` | Credits scroll speed |
| `BACKGROUND MUSIC` | BGM for the ending |
| `BACKGROUND MUSIC VOLUME` | Ending BGM volume |
| `BGM LOOP` | Toggle BGM looping. Default is off |
| `GOTO ENDING` | Continue into another ending after natural completion |

An ending can contain multiple slides.

| Slide item | Purpose |
| --- | --- |
| `ADD SLIDE` / `DEL SLIDE` | Add or delete slides |
| `Image` | Select the displayed image |
| `TIME` | Time when the slide appears. If BGM exists, this syncs to BGM playback time |
| `PREVIEW` | Preview from that slide |
| `cut` / `fade` / `zoom` | Slide transition effect. Click to cycle |
| `E-DUR` | Effect duration for `fade` / `zoom` |
| `DUR` | Per-slide duration, kept for compatibility with time-based slides |

At the bottom of the ending screen, `FROM:<time>` sets the preview start time. If you return with `ESC` during preview, the current time can be applied to the slide with `APPLY TIME`.

To reach an ending from a scene, set `GOTO ENDING` in the scene `FLOW`. When an ending finishes naturally, it is saved as reached.

## CG GALLERY

`CG GALLERY` configures images shown in EXTRAS. The gallery uses pages with 3x3 slots. Empty slots appear as `LOCKED`.

| Button | Action |
| --- | --- |
| `ADD PAGE` | Add a 3x3 slot page |
| `DELETE PAGE` | Delete the current page |
| `PREV` / `NEXT` | Switch pages |
| `SET IMAGE` | Register an image in the selected slot |
| `CLEAR SLOT` | Clear the selected image. Right-clicking a slot also clears it |
| `IMPORT USED` | Import images used in the project |
| `PREVIEW` | Preview the actual CG gallery |

When at least one gallery page exists, the title screen becomes eligible to show EXTRAS.

`IMPORT USED` can import from different ranges and choose how to place results.

| Item | Meaning |
| --- | --- |
| `BG+ENDING` | Title background, scene backgrounds, background flipbooks, and ending slide images |
| `ALL` | `BG+ENDING` plus character images and character flipbooks |
| `APPEND` | Keep existing slots and add to empty slots. Duplicate images are skipped |
| `REPLACE` | Rebuild pages from the import result |

## EXTRA TEXT

`EXTRA TEXT` configures text pages shown in EXTRAS, such as post-clear notes or bonus material.

Each page has a title and body. When at least one page exists, the title screen becomes eligible to show EXTRAS.

| Button | Action |
| --- | --- |
| `ADD PAGE` | Add an EXTRA TEXT page |
| `DELETE PAGE` | Delete the current page |
| `PREV` / `NEXT` | Switch pages |
| `EDIT TEXT` | Edit the page body |
| `TEXT SIZE:<size>` | Change display text size. Left-click increases, right-click decreases |
| `PREVIEW` | Preview the actual EXTRA TEXT screen |

If the body does not fit on one page, preview shows `OVER LIMIT: SPLIT INTO PAGES`. Split the text into multiple pages.

`EXTRA TEXT` has its own color settings for background, panel, border, body text, dim text, accent, button background, button text, and button hover color.

## EXTRAS Unlock

EXTRAS becomes a title-screen target when CG gallery or EXTRA TEXT has at least one page. Before unlock, it is shown as `???` and cannot be opened.

EXTRAS unlocks after all registered ending names have been reached through natural ending completion. If no endings are registered, EXTRAS does not unlock.

Before release, test the path from start to each ending, EXTRAS unlock, CG gallery display, and EXTRA TEXT display.
