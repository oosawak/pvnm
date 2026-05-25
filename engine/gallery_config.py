"""CG gallery configuration helpers."""
from __future__ import annotations


SLOTS_PER_GALLERY_PAGE = 9


def new_gallery_page(name: str = "") -> dict:
    """Return a blank 3x3 gallery page."""
    return {
        "name": name or "PAGE",
        "slots": [{"image": ""} for _ in range(SLOTS_PER_GALLERY_PAGE)],
    }


def normalize_gallery_config(value: dict | None = None) -> dict:
    """Return a complete, sanitized gallery config.

    The title screen's LOCKED button is intentionally derived from page
    existence, not from whether individual slots are filled. This matches the
    editor workflow: once the creator adds and saves a first page, the player can
    see that extras exist but are locked until clear.
    """
    pages: list[dict] = []
    if isinstance(value, dict):
        src_pages = value.get("pages", [])
    else:
        src_pages = []
    if isinstance(src_pages, list):
        for i, page in enumerate(src_pages):
            if not isinstance(page, dict):
                continue
            slots = []
            raw_slots = page.get("slots", [])
            if not isinstance(raw_slots, list):
                raw_slots = []
            for slot in raw_slots[:SLOTS_PER_GALLERY_PAGE]:
                if isinstance(slot, dict):
                    image = slot.get("image", "") or ""
                else:
                    image = ""
                slots.append({"image": str(image)})
            while len(slots) < SLOTS_PER_GALLERY_PAGE:
                slots.append({"image": ""})
            name = str(page.get("name") or f"PAGE {i + 1}")
            pages.append({"name": name, "slots": slots})
    return {
        "locked_button": bool(pages),
        "pages": pages,
    }


def has_gallery_pages(value: dict | None) -> bool:
    return bool(normalize_gallery_config(value).get("pages"))
