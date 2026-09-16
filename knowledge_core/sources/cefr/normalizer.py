from __future__ import annotations

import re
from typing import Any


LEVEL_ALIASES = {
    "prea1": "Pre-A1",
    "pre-a1": "Pre-A1",
    "a1": "A1",
    "a2": "A2",
    "a2+": "A2+",
    "b1": "B1",
    "b1+": "B1+",
    "b2": "B2",
    "b2+": "B2+",
    "c1": "C1",
    "c2": "C2",
}


def normalize_empty(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in {"nan", "none", "null"}:
        return None
    return text


def normalize_whitespace(value: Any) -> str:
    text = normalize_empty(value)
    if text is None:
        return ""
    return " ".join(text.replace("\xa0", " ").split())


def normalize_table_title(value: Any) -> str:
    return normalize_whitespace(value).casefold()


def normalize_cefr_level(value: Any) -> str:
    text = normalize_whitespace(value).replace(" ", "-")
    if not text:
        return ""
    return LEVEL_ALIASES.get(text.casefold(), text.upper())


def scale_id_from_name(value: str) -> str:
    text = normalize_whitespace(value).casefold()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def normalize_domain(value: Any) -> str:
    return scale_id_from_name(normalize_whitespace(value))

