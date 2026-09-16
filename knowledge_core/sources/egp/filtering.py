from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from knowledge_core.sources.egp.models import (
    CEFR_LEVELS,
    EGPConfig,
    RawEGPRecord,
    SourceRecordExclusion,
)
from knowledge_core.sources.egp.normalizer import normalize_empty
from knowledge_core.sources.egp.paths import DEFAULT_EGP_REPORTS_DIR


SOURCE_EXCLUSION_REPORT_NAME = "source_exclusion_report.json"


@dataclass(slots=True)
class V1RecordPartition:
    included_records: list[RawEGPRecord]
    excluded_records: list[SourceRecordExclusion]


def partition_v1_category_records(
    records: Sequence[RawEGPRecord],
    config: EGPConfig,
) -> V1RecordPartition:
    categories = config.category_by_id()
    included: list[RawEGPRecord] = []
    excluded: list[SourceRecordExclusion] = []

    for record in records:
        category = categories.get(record.category_id)
        reason_codes: list[str] = []
        expected_super = category.expected_super_category if category else None
        expected_sub = category.expected_sub_category if category else None

        if category is None:
            reason_codes.append("unknown_category")
        if category and expected_super and not _labels_match(
            record.super_category,
            expected_super,
        ):
            reason_codes.append("category_mismatch")
        if category and expected_sub and not _labels_match(record.sub_category, expected_sub):
            reason_codes.append("category_mismatch")
        if record.cefr_level not in CEFR_LEVELS:
            reason_codes.append("invalid_cefr_level")
        if not record.can_do_statement.strip():
            reason_codes.append("empty_can_do_statement")

        if reason_codes:
            excluded.append(
                SourceRecordExclusion(
                    source_record_id=record.source_record_id,
                    category_id=record.category_id,
                    source_file=record.source_file,
                    source_row_number=record.source_row_number,
                    reason_codes=sorted(set(reason_codes)),
                    expected_super_category=expected_super,
                    actual_super_category=record.super_category,
                    expected_sub_category=expected_sub,
                    actual_sub_category=record.sub_category,
                    cefr_level=record.cefr_level,
                    feature_type=record.feature_type,
                    feature_name=record.feature_name,
                    can_do_statement=normalize_empty(record.can_do_statement),
                ),
            )
        else:
            included.append(record)

    return V1RecordPartition(included_records=included, excluded_records=excluded)


def build_source_exclusion_report(
    exclusions: Sequence[SourceRecordExclusion],
    *,
    raw_record_count: int,
    included_record_count: int,
) -> dict[str, Any]:
    reason_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    for exclusion in exclusions:
        category_counts[exclusion.category_id] += 1
        for reason in exclusion.reason_codes:
            reason_counts[reason] += 1
    return {
        "raw_records": raw_record_count,
        "included_v1_records": included_record_count,
        "excluded_records": len(exclusions),
        "reason_counts": dict(sorted(reason_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "records": [exclusion.model_dump(mode="json") for exclusion in exclusions],
    }


def write_source_exclusion_report(
    report: dict[str, Any],
    reports_dir: str | Path = DEFAULT_EGP_REPORTS_DIR,
) -> Path:
    path = Path(reports_dir) / SOURCE_EXCLUSION_REPORT_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _labels_match(actual: str | None, expected: str | None) -> bool:
    return _normalize_label(actual) == _normalize_label(expected)


def _normalize_label(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.strip().casefold().split())
