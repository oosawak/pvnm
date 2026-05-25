# Scene Editing

This page explains the main scene editing controls. The right-side edit panel has three tabs: `SCENE`, `CHARACTERS`, and `CHOICES`.

Japanese version: [シーン制作](../ja/scenes.md)

## Scene List

The left `SCENES` panel manages scenes in the current Part / Chapter.

| Control | Purpose |
| --- | --- |
| `[P:...]` | Select a Part |
| `[C:...]` | Select a Chapter |
| `<` / `>` | Move to the previous or next Part / Chapter |
| `+ADD` | Add a scene to the current Part / Chapter |
| `COPY` | Duplicate the selected scene |
| `DEL` | Delete the selected scene |

Scene names internally include Part / Chapter information, but the editor focuses on the display name.

## SCENE Tab

The `SCENE` tab controls dialogue text, background, audio, and normal flow.

### TEXT

| Item | Purpose |
| --- | --- |
| `[SPEAKER]` | Speaker name shown in the name badge |
| `[EDIT_TEXT]` | Dialogue text shown in the message window |
| `TEXT SIZE` | Text size for this scene. Reset returns to the default |

`TEXT SIZE` uses available BDF font sizes. In most cases, the default is fine.

### BACKGROUND

| Item | Purpose |
| --- | --- |
| `[BACKGROUND IMAGE]` | Select a background image |
| `BACKGROUND FULLSCREEN` | Fit the background to the full screen |
| `BG SAFE AREA` | Fit the background above the dialogue area |
| `HIDE BACKGROUND` | Stop background inheritance and hide the background |
| `HIDE DIALOG` | Hide the message window |
| `TRANSITION` | Use a fade transition to the next scene |

If the background field is empty, the previous scene's background is inherited. Turn on `HIDE BACKGROUND` when you explicitly want no background.

### AUDIO

| Item | Purpose |
| --- | --- |
| `[BACKGROUND MUSIC FILE]` | Select BGM |
| `STOP BGM` | Stop inherited BGM |
| `PLAY BGM ONCE` | Play the BGM once without looping |
| `BACKGROUND MUSIC VOLUME` | BGM volume |
| `BGM FADE OUT` | Fade-out frames on transition |
| `[SOUND EFFECT FILE]` | Select an SE played at scene start |
| `SOUND EFFECT VOLUME` | SE volume |
| `SOUND EFFECT REPEAT (0=once)` | SE repeat count. `0` means one playback |

If the BGM field is empty, the previous scene's BGM is inherited. SE plays only for the scene where it is set.

### FLOW

| Item | Purpose |
| --- | --- |
| `[GOTO]` | Next scene for normal progression |
| `[GOTO ENDING]` | Ending reached from this scene |
| `PAUSE AUTO` | Pause AUTO playback only for this scene |

Use `[GOTO]` for a linear route. Use `[GOTO ENDING]` when the scene should enter an ending.

## CHARACTERS Tab

The `CHARACTERS` tab assigns character images to three slots.

| Subtab | Position |
| --- | --- |
| `LEFT` | Left slot |
| `CENTER` | Center slot |
| `RIGHT` | Right slot |

Each slot has the same controls.

| Item | Purpose |
| --- | --- |
| `[FILE]` | Select a character image |
| `HIDE CHARACTER` | Stop inheritance for this slot and hide it |
| `[STORE POS]` | Store the current x/y/scale for the slot |
| `[APPLY POS]` | Apply the stored x/y/scale |
| `CHARACTER SCALING` | Image scale |
| `horizontal axis position` | Horizontal position |
| `vertical axis position` | Vertical position |
| `COLOR KEY` | Transparent color: `AUTO`, `NONE`, or palette index `0`-`255` |
| `FLIP HORIZONTAL` | Flip horizontally |
| `FLIP VERTICAL` | Flip vertically |

If a character file is empty, the previous scene's image for the same slot is inherited. Turn on `HIDE CHARACTER` to explicitly clear that slot.

## Animation

The lower part of the `CHARACTERS` tab contains per-slot animation settings.

| Item | Purpose |
| --- | --- |
| `KEEP ANIM NEXT` | Carry animation settings to the next scene |
| `HOLD MOTION END` | Carry the final motion position to the next scene |
| `CLEAR ANIM` | Clear animation settings |
| `SHAKE AMPLITUDE` | Shake amount |
| `SHAKE SPEED` | Shake speed |
| `ROTATION SPEED` | Rotation speed |
| `SCALE START` | Starting scale |
| `SCALE END` | Ending scale |
| `SCALE FRAMES` | Frames used for scale animation |
| `MOTION X` | Horizontal motion amount |
| `MOTION Y` | Vertical motion amount |
| `MOTION FRAMES` | Frames used for motion |
| `FLIPBOOK INTERVAL` | Image switching interval for flipbook animation |

Animations normally apply only to the current scene. Use `KEEP ANIM NEXT` or `HOLD MOTION END` only when the effect should continue.

## CHOICES Tab

The `CHOICES` tab creates branching choices.

| Control | Purpose |
| --- | --- |
| `+ ADD CHOICE` | Add a choice |
| `x` | Delete a choice |
| `[LABEL]` | Text shown for the choice |
| `[GOTO]` | Scene reached when the choice is selected |

PVNM supports editing up to 8 choices. Use `[GOTO]` in the `SCENE` tab for normal progression, and `CHOICES` when the player should choose a branch.

## Preview

Use `PLAY` or the `1` key to test the current project as a player. Before release, check text progression, branches, audio, images, endings, and EXTRAS unlocks from start to finish.
