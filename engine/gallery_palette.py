"""Palette helpers for CG gallery thumbnails."""
from __future__ import annotations

try:
    import numpy as np
    if not all(hasattr(np, name) for name in ("asarray", "uint8", "zeros")):
        raise ImportError("incomplete numpy module")
except Exception:
    from engine import mini_numpy as np

from engine import palette as _palette_mod


def build_sepia_palette(settings: dict | None = None) -> "np.ndarray":
    """Build a fixed sepia thumbnail palette while preserving UI colors.

    Pyxel can only display one 256-color palette at a time. Gallery thumbnails
    therefore use a shared sepia palette instead of each image's scene palette.
    UI/reserved indices stay at MasterColor values, while all free slots become
    a dark-to-paper sepia luminance ramp.
    """
    master = _palette_mod.as_array()
    if master is None:
        try:
            master = _palette_mod.load_array_only()
        except Exception:
            master = np.zeros((256, 3), dtype=np.uint8)
    base = np.asarray(master, dtype=np.uint8)
    try:
        pal = base.copy()
    except AttributeError:
        pal = np.asarray([tuple(row) for row in base], dtype=np.uint8)
    reserved = reserved_indices(settings)
    free = [i for i in range(256) if i not in reserved]
    if not free:
        return pal
    steps = len(free)
    for n, idx in enumerate(free):
        t = 0.0 if steps <= 1 else n / (steps - 1)
        pal[idx] = _sepia_rgb(t)
    return pal


def reserved_indices(settings: dict | None) -> set[int]:
    """Return palette indices reserved for UI/text while drawing galleries."""
    reserved = set(range(16))
    try:
        for idx in _palette_mod.reserved_from_settings(settings or {}):
            if isinstance(idx, int) and 0 <= idx <= 255:
                reserved.add(idx)
    except Exception:
        pass
    try:
        from ui import colors as _colors
        for role in _colors.role_names():
            idx = _colors.current_index(role)
            if isinstance(idx, int) and 0 <= idx <= 255:
                reserved.add(idx)
    except Exception:
        pass
    return reserved


def sepia_image_indices(settings: dict | None) -> set[int]:
    """Return palette indices that thumbnails may use for image pixels only."""
    return {i for i in range(256) if i not in reserved_indices(settings)}


def _sepia_rgb(t: float) -> tuple[int, int, int]:
    """Piecewise sepia ramp from burned umber to warm paper."""
    t = max(0.0, min(1.0, float(t)))
    dark = (26, 16, 8)
    mid = (136, 98, 58)
    light = (232, 211, 163)
    if t < 0.62:
        local = t / 0.62
        a, b = dark, mid
    else:
        local = (t - 0.62) / 0.38
        a, b = mid, light
    return tuple(
        max(0, min(255, int(round(a[i] + (b[i] - a[i]) * local))))
        for i in range(3)
    )
