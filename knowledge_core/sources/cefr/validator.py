from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Sequence

from knowledge_core.sources.cefr.models import (
    CEFRConfig,
    CEFRDescriptorRecord,
    CEFRLearningObjectiveCandidate,
    CEFRValidationIssue,
    CEFRValidationResult,
    DOMAIN_NAMES,
    VALID_CEFR_LEVELS,
)
from knowledge_core.sources.cefr.normalizer import normalize_whitespace
from knowledge_core.sources.cefr.table_parser import (
    descriptor_availability,
    descriptor_is_table_like,
)


def validate_records(
    records: Iterable[CEFRDescriptorRecord],
    config: CEFRConfig,
    *,
    candidates: Sequence[CEFRLearningObjectiveCandidate] = (),
) -> CEFRValidationResult:
    record_list = list(records)
    candidate_list = list(candidates)
    issues: list[CEFRValidationIssue] = []

    known_scale_ids = set(config.scale_by_id()) | {"common_reference_levels"}
    known_domains = config.known_domains() | DOMAIN_NAMES
    valid_levels = config.levels.valid | VALID_CEFR_LEVELS
    records_by_id: dict[str, list[CEFRDescriptorRecord]] = defaultdict(list)
    duplicate_groups: dict[str, list[CEFRDescriptorRecord]] = defaultdict(list)

    for record in record_list:
        records_by_id[record.source_record_id].append(record)
        duplicate_groups[duplicate_key(record)].append(record)
        context = _record_context(record)

        if record.cefr_level not in valid_levels:
            issues.append(
                CEFRValidationIssue(
                    severity="error",
                    code="invalid_cefr_level",
                    message=f"Invalid CEFR level: {record.cefr_level!r}",
                    **context,
                ),
            )
        if not record.scale_name:
            issues.append(
                CEFRValidationIssue(
                    severity="error",
                    code="missing_scale_name",
                    message="scale_name must not be empty",
                    **context,
                ),
            )
        elif record.scale_name not in known_scale_ids:
            issues.append(
                CEFRValidationIssue(
                    severity="error",
                    code="unknown_scale_name",
                    message=f"scale_name is not configured: {record.scale_name}",
                    **context,
                ),
            )
        if record.domain not in known_domains:
            issues.append(
                CEFRValidationIssue(
                    severity="error",
                    code="unknown_domain",
                    message=f"domain is not configured: {record.domain}",
                    **context,
                ),
            )
        if not record.descriptor_text.strip() and record.descriptor_available:
            issues.append(
                CEFRValidationIssue(
                    severity="error",
                    code="empty_descriptor_text",
                    message="descriptor_text must not be empty when available",
                    **context,
                ),
            )

        available_from_text, reference_level = descriptor_availability(
            record.descriptor_text,
        )
        if available_from_text != record.descriptor_available:
            issues.append(
                CEFRValidationIssue(
                    severity="error",
                    code="descriptor_availability_mismatch",
                    message="descriptor_available does not match descriptor_text",
                    **context,
                ),
            )
        if not record.descriptor_available and record.reference_level != reference_level:
            issues.append(
                CEFRValidationIssue(
                    severity="warning",
                    code="reference_level_mismatch",
                    message="reference_level does not match the no-descriptor text",
                    **context,
                ),
            )

        if record.descriptor_available and record.descriptor_type != "level_summary":
            if not descriptor_is_table_like(
                record.descriptor_text,
                descriptor_available=True,
            ):
                issues.append(
                    CEFRValidationIssue(
                        severity="error",
                        code="non_descriptor_like_text",
                        message=(
                            "Descriptor text does not start like a CEFR table "
                            "descriptor; possible explanatory prose extraction"
                        ),
                        **context,
                    ),
                )

        if record.page_number is None:
            issues.append(
                CEFRValidationIssue(
                    severity="error",
                    code="missing_page_number",
                    message="page_number must be preserved",
                    **context,
                ),
            )
        if not record.source_file:
            issues.append(
                CEFRValidationIssue(
                    severity="error",
                    code="missing_source_file",
                    message="source_file must be preserved",
                    **context,
                ),
            )
        elif not Path(record.source_file).exists():
            issues.append(
                CEFRValidationIssue(
                    severity="error",
                    code="missing_source_file",
                    message=f"source_file does not exist: {record.source_file}",
                    **context,
                ),
            )
        if record.scale_name == "grammatical_accuracy":
            if record.domain != "linguistic_competence" or record.subdomain != "grammar":
                issues.append(
                    CEFRValidationIssue(
                        severity="error",
                        code="grammatical_accuracy_domain_mismatch",
                        message=(
                            "Grammatical accuracy records must be tagged as "
                            "linguistic_competence/grammar"
                        ),
                        **context,
                    ),
                )

    for source_record_id, grouped_records in sorted(records_by_id.items()):
        if len(grouped_records) < 2:
            continue
        for record in grouped_records:
            issues.append(
                CEFRValidationIssue(
                    severity="error",
                    code="duplicate_source_record_id",
                    message=(
                        "source_record_id must be unique; duplicate id "
                        f"{source_record_id!r} appears {len(grouped_records)} times"
                    ),
                    **_record_context(record),
                ),
            )

    for key, grouped_records in sorted(duplicate_groups.items()):
        if len(grouped_records) < 2:
            continue
        for record in grouped_records:
            issues.append(
                CEFRValidationIssue(
                    severity="warning",
                    code="duplicate_descriptor_row",
                    message=(
                        "Duplicate CEFR descriptor row preserved in source "
                        f"context group of {len(grouped_records)}"
                    ),
                    duplicate_key=key,
                    **_record_context(record),
                ),
            )

    issues.extend(_validate_candidates(candidate_list, record_list, config))
    return CEFRValidationResult(
        total_records=len(record_list),
        total_candidates=len(candidate_list),
        issues=issues,
    )


def duplicate_key(record: CEFRDescriptorRecord) -> str:
    parts = [
        record.source_document,
        record.domain,
        record.scale_name,
        record.cefr_level,
        record.descriptor_text,
        record.page_number,
    ]
    raw_key = "\x1f".join(_normalize_duplicate_part(part) for part in parts)
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _validate_candidates(
    candidates: Sequence[CEFRLearningObjectiveCandidate],
    records: Sequence[CEFRDescriptorRecord],
    config: CEFRConfig,
) -> list[CEFRValidationIssue]:
    issues: list[CEFRValidationIssue] = []
    records_by_id = {record.source_record_id: record for record in records}
    candidate_ids: dict[str, list[CEFRLearningObjectiveCandidate]] = defaultdict(list)
    for candidate in candidates:
        candidate_ids[candidate.objective_id].append(candidate)
        record = records_by_id.get(candidate.source_record_id)
        context = _candidate_context(candidate)
        if candidate.cefr_level not in config.levels.include:
            issues.append(
                CEFRValidationIssue(
                    severity="error",
                    code="candidate_outside_primary_level_scope",
                    message="V1 objective candidates must use primary A1-C2 levels",
                    **context,
                ),
            )
        if record is None:
            issues.append(
                CEFRValidationIssue(
                    severity="error",
                    code="candidate_missing_source_record",
                    message="Objective candidate references an unknown source_record_id",
                    **context,
                ),
            )
            continue
        if not record.descriptor_available:
            issues.append(
                CEFRValidationIssue(
                    severity="error",
                    code="candidate_from_no_descriptor_row",
                    message="No-descriptor rows must not become objective candidates",
                    **context,
                ),
            )
        if record.descriptor_type == "level_summary":
            issues.append(
                CEFRValidationIssue(
                    severity="error",
                    code="candidate_from_level_summary",
                    message="Level summaries are supporting evidence, not V1 objectives",
                    **context,
                ),
            )
        if normalize_whitespace(candidate.source_descriptor_text) != normalize_whitespace(
            record.descriptor_text,
        ):
            issues.append(
                CEFRValidationIssue(
                    severity="warning",
                    code="candidate_text_differs_from_source",
                    message="Objective text differs from CEFR source descriptor text",
                    **context,
                ),
            )

    for objective_id, grouped_candidates in sorted(candidate_ids.items()):
        if len(grouped_candidates) < 2:
            continue
        for candidate in grouped_candidates:
            issues.append(
                CEFRValidationIssue(
                    severity="error",
                    code="duplicate_objective_id",
                    message=(
                        "objective_id must be unique; duplicate id "
                        f"{objective_id!r} appears {len(grouped_candidates)} times"
                    ),
                    **_candidate_context(candidate),
                ),
            )
    return issues


def _record_context(record: CEFRDescriptorRecord) -> dict[str, object]:
    return {
        "source_record_id": record.source_record_id,
        "cefr_level": record.cefr_level,
        "domain": record.domain,
        "scale_name": record.scale_name,
        "page_number": record.page_number,
    }


def _candidate_context(
    candidate: CEFRLearningObjectiveCandidate,
) -> dict[str, object]:
    return {
        "source_record_id": candidate.source_record_id,
        "objective_id": candidate.objective_id,
        "cefr_level": candidate.cefr_level,
        "domain": candidate.domain,
        "scale_name": candidate.scale_name,
    }


def _normalize_duplicate_part(value: object) -> str:
    if value is None:
        return ""
    return normalize_whitespace(value).casefold()

