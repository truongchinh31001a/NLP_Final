from __future__ import annotations

import re
from typing import Any

from knowledge_core.sources.egp.models import RawEGPRecord


FEATURE_LABEL_PATTERN = re.compile(r"^\s*([A-Z][A-Z0-9/ &+\-]{1,40})\s*:\s*(.+?)\s*$")


def normalize_empty(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in {"nan", "none", "null"}:
        return None
    return text


def normalize_source_label(value: Any, *, uppercase: bool = False) -> str | None:
    text = normalize_empty(value)
    if text is None:
        return None
    normalized = " ".join(text.split())
    return normalized.upper() if uppercase else normalized


def normalize_cefr(value: Any) -> str:
    text = normalize_empty(value)
    return text.upper() if text else ""


def parse_feature_label(value: Any) -> tuple[str | None, str | None]:
    text = normalize_empty(value)
    if text is None:
        return None, None
    match = FEATURE_LABEL_PATTERN.match(text)
    if not match:
        return None, None
    feature_type = " ".join(match.group(1).split()).upper()
    feature_name = normalize_empty(match.group(2))
    return feature_type, feature_name


def normalize_record(record: RawEGPRecord) -> RawEGPRecord:
    feature_type = normalize_empty(record.feature_type)
    feature_name = normalize_empty(record.feature_name)
    if feature_type is None and feature_name is None:
        feature_type, feature_name = parse_feature_label(record.can_do_statement)

    return record.model_copy(
        update={
            "source": normalize_empty(record.source) or record.source,
            "source_record_id": normalize_empty(record.source_record_id),
            "category_id": normalize_empty(record.category_id) or record.category_id,
            "super_category": normalize_source_label(
                record.super_category,
                uppercase=True,
            ),
            "sub_category": normalize_source_label(record.sub_category),
            "cefr_level": normalize_cefr(record.cefr_level),
            "feature_type": feature_type,
            "feature_name": feature_name,
            "can_do_statement": normalize_empty(record.can_do_statement) or "",
            "example": normalize_empty(record.example),
            "details": normalize_empty(record.details),
            "source_file": normalize_empty(record.source_file) or record.source_file,
            "source_url": normalize_empty(record.source_url),
            "canonical_parent_hint": normalize_empty(record.canonical_parent_hint),
        },
    )
