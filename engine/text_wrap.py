"""Shared BDF-based text wrapping for editor previews and runtime player."""
from __future__ import annotations

import unicodedata

from ui.widgets import text_px_w

_DIALOG_TRACKING_SIZES = frozenset(range(17, 24))


def normalize_text(text: str) -> str:
    """Normalize text before measuring/drawing with BDF fonts."""
    if not text:
        return text
    try:
        return unicodedata.normalize("NFC", text)
    except Exception:
        return text


def dialog_letter_spacing(size: int) -> int:
    """Pixel tracking used for large generated BDF dialog body text."""
    try:
        n = int(size)
    except Exception:
        return 0
    return 1 if n in _DIALOG_TRACKING_SIZES else 0


def wrap_paragraph(paragraph: str, max_width: int, size: int,
                   letter_spacing: int = 0) -> list[str]:
    """Wrap one paragraph using the same pixel-width metric as BDF drawing."""
    paragraph = normalize_text(paragraph)
    if paragraph == "":
        return [""]
    if max_width <= 0:
        return list(paragraph)

    lines: list[str] = []
    line = ""
    for ch in paragraph:
        candidate = line + ch
        if line and text_px_w(candidate, size, letter_spacing) > max_width:
            lines.append(line)
            line = ch
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines or [""]


def wrap_text(text: str, max_width: int, size: int,
              letter_spacing: int = 0) -> list[str]:
    """Wrap text with explicit newlines preserved as paragraph breaks."""
    text = normalize_text(text or "")
    lines: list[str] = []
    for paragraph in text.split("\n"):
        lines.extend(wrap_paragraph(paragraph, max_width, size, letter_spacing))
    return lines
