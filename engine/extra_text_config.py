"""EXTRA TEXT configuration helpers."""
from __future__ import annotations

from engine.extra_text_colors import normalize_extra_text_colors


EXTRA_TEXT_SIZE_OPTIONS = tuple(range(16, 25))
DEFAULT_EXTRA_TEXT_SIZE = 18


def normalize_extra_text_size(value) -> int:
    """Return a valid EXTRA TEXT body size in the 16-24 range."""
    try:
        n = int(value)
    except Exception:
        n = DEFAULT_EXTRA_TEXT_SIZE
    return max(min(n, max(EXTRA_TEXT_SIZE_OPTIONS)), min(EXTRA_TEXT_SIZE_OPTIONS))


def new_extra_text_page(title: str = "", text: str = "") -> dict:
    """Return a blank EXTRA TEXT page."""
    return {
        "title": title or "PAGE",
        "text": text or "",
    }


def normalize_extra_text_config(value: dict | None = None) -> dict:
    """Return a complete, sanitized EXTRA TEXT config."""
    pages: list[dict] = []
    colors = normalize_extra_text_colors()
    text_size = DEFAULT_EXTRA_TEXT_SIZE
    if isinstance(value, dict):
        colors = normalize_extra_text_colors(value.get("colors"))
        text_size = normalize_extra_text_size(value.get("text_size"))
        src_pages = value.get("pages", [])
    else:
        src_pages = []
    if isinstance(src_pages, list):
        for i, page in enumerate(src_pages):
            if not isinstance(page, dict):
                continue
            title = str(page.get("title") or f"PAGE {i + 1}")
            text = str(page.get("text") or "")
            pages.append({"title": title, "text": text})
    return {
        "extras_button": bool(pages),
        "pages": pages,
        "colors": colors,
        "text_size": text_size,
    }


def has_extra_text_pages(value: dict | None) -> bool:
    return bool(normalize_extra_text_config(value).get("pages"))
