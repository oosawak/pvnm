"""Title screen color roles.

Title buttons live on top of a title-specific image palette. These roles store
the palette indices that must be reserved when that palette is generated.
"""
from __future__ import annotations


TITLE_BUTTON_COLOR_ROLES = (
    ("normal_bg", "NORMAL BG", "Button background", 1),
    ("normal_border", "NORMAL BORDER", "Button border", 5),
    ("normal_text", "NORMAL TEXT", "Button text", 7),
    ("hover_bg", "HOVER BG", "Hovered button background", 8),
    ("hover_border", "HOVER BORDER", "Hovered button border", 10),
    ("hover_text", "HOVER TEXT", "Hovered button text", 0),
)

TITLE_BUTTON_COLOR_DEFAULTS = {
    key: default for key, _label, _desc, default in TITLE_BUTTON_COLOR_ROLES
}


def normalize_button_colors(value: dict | None = None) -> dict:
    """Return a complete title button color mapping."""
    out = dict(TITLE_BUTTON_COLOR_DEFAULTS)
    if isinstance(value, dict):
        for key in out:
            idx = value.get(key)
            if isinstance(idx, int) and 0 <= idx <= 255:
                out[key] = idx
    return out


def button_color_index(colors: dict | None, role: str) -> int:
    """Return the palette index for a title button role."""
    return normalize_button_colors(colors).get(
        role, TITLE_BUTTON_COLOR_DEFAULTS.get(role, 0))


def title_button_color_indices(colors: dict | None) -> set[int]:
    """Return palette indices used by title buttons."""
    return set(normalize_button_colors(colors).values())
