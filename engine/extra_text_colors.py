"""Color roles for EXTRA TEXT pages."""
from __future__ import annotations


EXTRA_TEXT_COLOR_ROLES = (
    ("bg", "BG", "Screen background", 0),
    ("panel_bg", "PANEL BG", "Reading panel background", 1),
    ("border", "BORDER", "Panel/button border", 5),
    ("text", "TEXT", "Main body text", 7),
    ("text_dim", "TEXT DIM", "Small page/hint text", 6),
    ("accent", "ACCENT", "Page title/accent", 9),
    ("button_bg", "BUTTON BG", "Button background", 2),
    ("button_text", "BUTTON TEXT", "Button text", 7),
    ("button_hover", "BUTTON HOVER", "Hovered button background", 8),
)

EXTRA_TEXT_COLOR_DEFAULTS = {
    key: default for key, _label, _desc, default in EXTRA_TEXT_COLOR_ROLES
}


def normalize_extra_text_colors(value: dict | None = None) -> dict:
    """Return a complete EXTRA TEXT color mapping."""
    out = dict(EXTRA_TEXT_COLOR_DEFAULTS)
    if isinstance(value, dict):
        for key in out:
            idx = value.get(key)
            if isinstance(idx, int) and 0 <= idx <= 255:
                out[key] = idx
    return out


def extra_text_color_index(colors: dict | None, role: str) -> int:
    """Return the palette index for an EXTRA TEXT color role."""
    return normalize_extra_text_colors(colors).get(
        role, EXTRA_TEXT_COLOR_DEFAULTS.get(role, 0))


def extra_text_color_indices(colors: dict | None) -> set[int]:
    """Return palette indices used by EXTRA TEXT chrome."""
    return set(normalize_extra_text_colors(colors).values())
