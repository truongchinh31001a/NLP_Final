from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from knowledge_core.sources.egp.models import (
    CEFR_LEVELS,
    EGPConfig,
    RawEGPRecord,
    ValidationIssue,
    ValidationResult,
)


DEFAULT_CANONICAL_PARENT_HINTS = {
    "grammar.tenses.present_simple",
    "grammar.tenses.present_continuous",
    "grammar.tenses.past_simple",
    "grammar.tenses.past_continuous",
    "grammar.tenses.present_perfect",
    "grammar.future.will",
    "grammar.modality",
    "grammar.determiners.articles",
    "grammar.clauses.conditionals",
    "grammar.passives",
}


def validate_records(
    records: Iterable[RawEGPRecord],
    config: EGPConfig,
    *,
    canonical_parent_hints: set[str] | None = None,
) -> ValidationResult:
    record_list = list(records)
    categories = config.category_by_id()
    valid_hints = canonical_parent_hints or known_canonical_parent_hints()
    issues: list[ValidationIssue] = []
    duplicate_groups: dict[str, list[RawEGPRecord]] = defaultdict(list)
    source_record_id_groups: dict[str, list[RawEGPRecord]] = defaultdict(list)

    for record in record_list:
        category = categories.get(record.category_id)
        issue_context = {
            "category_id": record.category_id,
            "source_file": record.source_file,
            "source_row_number": record.source_row_number,
            "source_record_id": record.source_record_id,
        }

        if record.cefr_level not in CEFR_LEVELS:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="invalid_cefr_level",
                    message=f"Invalid CEFR level: {record.cefr_level!r}",
                    **issue_context,
                ),
            )

        if not record.source_record_id:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="missing_source_record_id",
                    message="source_record_id must not be empty",
                    **issue_context,
                ),
            )
        else:
            source_record_id_groups[record.source_record_id].append(record)

        if not record.can_do_statement.strip():
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="empty_can_do_statement",
                    message="Can-do statement must not be empty",
                    **issue_context,
                ),
            )

        if category is None:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="unknown_category_id",
                    message=f"category_id is not configured: {record.category_id}",
                    **issue_context,
                ),
            )
        else:
            if category.expected_super_category and not _matches_source_label(
                record.super_category,
                category.expected_super_category,
            ):
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        code="expected_super_category_mismatch",
                        message=(
                            "Expected super_category "
                            f"{category.expected_super_category!r}, got "
                            f"{record.super_category!r}"
                        ),
                        **issue_context,
                    ),
                )
            if category.expected_sub_category and not _matches_source_label(
                record.sub_category,
                category.expected_sub_category,
            ):
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        code="expected_sub_category_mismatch",
                        message=(
                            "Expected sub_category "
                            f"{category.expected_sub_category!r}, got "
                            f"{record.sub_category!r}"
                        ),
                        **issue_context,
                    ),
                )

        if record.source_file and not Path(record.source_file).exists():
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="missing_source_file",
                    message=f"source_file does not exist: {record.source_file}",
                    **issue_context,
                ),
            )

        if record.canonical_parent_hint and record.canonical_parent_hint not in valid_hints:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="invalid_canonical_parent_hint",
                    message=(
                        "canonical_parent_hint is not a known V1 parent hint: "
                        f"{record.canonical_parent_hint}"
                    ),
                    **issue_context,
                ),
            )

        duplicate_groups[duplicate_key(record)].append(record)

    for source_record_id, source_records in sorted(source_record_id_groups.items()):
        if len(source_records) < 2:
            continue
        for record in source_records:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="duplicate_source_record_id",
                    message=(
                        "source_record_id must be unique; duplicate id "
                        f"{source_record_id!r} appears {len(source_records)} times"
                    ),
                    category_id=record.category_id,
                    source_file=record.source_file,
                    source_row_number=record.source_row_number,
                    source_record_id=source_record_id,
                ),
            )

    for key, duplicate_records in sorted(duplicate_groups.items()):
        if len(duplicate_records) < 2:
            continue
        for record in duplicate_records:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="duplicate_record",
                    message=(
                        f"Duplicate EGP source record detected in a group of "
                        f"{len(duplicate_records)}"
                    ),
                    category_id=record.category_id,
                    source_file=record.source_file,
                    source_row_number=record.source_row_number,
                    duplicate_key=key,
                    source_record_id=record.source_record_id,
                ),
            )

    return ValidationResult(total_records=len(record_list), issues=issues)


def duplicate_key(record: RawEGPRecord) -> str:
    parts = [
        record.source,
        record.super_category,
        record.sub_category,
        record.cefr_level,
        record.can_do_statement,
        record.example,
    ]
    raw_key = "\x1f".join(_normalize_duplicate_part(part) for part in parts)
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def known_canonical_parent_hints() -> set[str]:
    hints = set(DEFAULT_CANONICAL_PARENT_HINTS)
    try:
        from app.learner.skill_graph import DEFAULT_SKILL_GRAPH
    except Exception:
        return hints
    hints.update(DEFAULT_SKILL_GRAPH.nodes.keys())
    return hints


def _normalize_duplicate_part(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().casefold().split())


def _matches_source_label(actual: str | None, expected: str | None) -> bool:
    return _normalize_duplicate_part(actual) == _normalize_duplicate_part(expected)
