from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILL_SET
from knowledge_core.mapping.egp.models import (
    EGPCanonicalMapping,
    MappingValidationIssue,
    MappingValidationResult,
)
from knowledge_core.sources.egp.models import RawEGPRecord


VALID_MAPPING_STATUSES = {"exact", "candidate", "ambiguous", "unmapped"}
VALID_REVIEW_STATUSES = {"pending", "approved", "rejected", "needs_review"}


def validate_mappings(
    records: Iterable[RawEGPRecord],
    mappings: Iterable[EGPCanonicalMapping],
    *,
    canonical_skills: set[str] | frozenset[str] = CANONICAL_GRAMMAR_V1_SKILL_SET,
) -> MappingValidationResult:
    record_list = list(records)
    mapping_list = list(mappings)
    issues: list[MappingValidationIssue] = []

    source_ids = [record.source_record_id for record in record_list if record.source_record_id]
    source_id_set = set(source_ids)
    mappings_by_source: dict[str, list[EGPCanonicalMapping]] = defaultdict(list)
    mappings_by_id: dict[str, list[EGPCanonicalMapping]] = defaultdict(list)

    for mapping in mapping_list:
        mappings_by_source[mapping.source_record_id].append(mapping)
        mappings_by_id[mapping.mapping_id].append(mapping)
        issues.extend(_validate_mapping_fields(mapping, canonical_skills))

    for mapping_id, duplicate_mappings in mappings_by_id.items():
        if len(duplicate_mappings) > 1:
            issues.append(
                MappingValidationIssue(
                    severity="error",
                    code="duplicate_mapping_id",
                    message=(
                        f"mapping_id {mapping_id!r} appears "
                        f"{len(duplicate_mappings)} times"
                    ),
                    mapping_id=mapping_id,
                ),
            )

    for source_record_id in sorted(source_id_set):
        count = len(mappings_by_source.get(source_record_id, []))
        if count != 1:
            issues.append(
                MappingValidationIssue(
                    severity="error",
                    code="source_record_mapping_count",
                    message=(
                        f"source_record_id {source_record_id!r} must have exactly "
                        f"one mapping, found {count}"
                    ),
                    source_record_id=source_record_id,
                ),
            )

    for source_record_id in sorted(mappings_by_source.keys() - source_id_set):
        issues.append(
            MappingValidationIssue(
                severity="error",
                code="mapping_without_source_record",
                message=f"mapping references unknown source_record_id {source_record_id!r}",
                source_record_id=source_record_id,
            ),
        )

    return MappingValidationResult(
        total_records=len(record_list),
        total_mappings=len(mapping_list),
        issues=issues,
    )


def _validate_mapping_fields(
    mapping: EGPCanonicalMapping,
    canonical_skills: set[str] | frozenset[str],
) -> list[MappingValidationIssue]:
    issues: list[MappingValidationIssue] = []
    context = {
        "mapping_id": mapping.mapping_id,
        "source_record_id": mapping.source_record_id,
        "canonical_skill": mapping.canonical_skill,
    }

    if mapping.status not in VALID_MAPPING_STATUSES:
        issues.append(
            MappingValidationIssue(
                severity="error",
                code="invalid_mapping_status",
                message=f"Invalid mapping status: {mapping.status!r}",
                **context,
            ),
        )

    if mapping.review_status not in VALID_REVIEW_STATUSES:
        issues.append(
            MappingValidationIssue(
                severity="error",
                code="invalid_review_status",
                message=f"Invalid review status: {mapping.review_status!r}",
                **context,
            ),
        )

    if mapping.canonical_skill and mapping.canonical_skill not in canonical_skills:
        issues.append(
            MappingValidationIssue(
                severity="error",
                code="invalid_canonical_skill",
                message=f"canonical_skill is not in Grammar V1: {mapping.canonical_skill}",
                **context,
            ),
        )

    for secondary in mapping.secondary_candidates:
        if secondary not in canonical_skills:
            issues.append(
                MappingValidationIssue(
                    severity="error",
                    code="invalid_secondary_candidate",
                    message=f"secondary candidate is not in Grammar V1: {secondary}",
                    **context,
                ),
            )

    if mapping.status == "unmapped" and mapping.canonical_skill is not None:
        issues.append(
            MappingValidationIssue(
                severity="error",
                code="unmapped_has_canonical_skill",
                message="unmapped records must not have canonical_skill",
                **context,
            ),
        )

    if mapping.review_status == "approved" and mapping.canonical_skill is None:
        issues.append(
            MappingValidationIssue(
                severity="error",
                code="approved_without_canonical_skill",
                message="approved mappings must have canonical_skill",
                **context,
            ),
        )

    if mapping.status in {"exact", "candidate"} and mapping.canonical_skill is None:
        issues.append(
            MappingValidationIssue(
                severity="error",
                code="mapped_status_without_canonical_skill",
                message="exact and candidate mappings must have canonical_skill",
                **context,
            ),
        )

    return issues
