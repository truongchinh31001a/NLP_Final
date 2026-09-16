from __future__ import annotations

import hashlib
from typing import Iterable

from knowledge_core.mapping.egp.models import EGPCanonicalMapping
from knowledge_core.mapping.egp.rules import decide_mapping
from knowledge_core.sources.egp.models import RawEGPRecord


def create_mappings(records: Iterable[RawEGPRecord]) -> list[EGPCanonicalMapping]:
    mappings: list[EGPCanonicalMapping] = []
    for index, record in enumerate(records, start=1):
        source_record_id = record.source_record_id or f"missing_source_record_{index}"
        decision = decide_mapping(record)
        mappings.append(
            EGPCanonicalMapping(
                mapping_id=deterministic_mapping_id(source_record_id),
                source_record_id=source_record_id,
                canonical_skill=decision.canonical_skill,
                secondary_candidates=list(decision.secondary_candidates),
                status=decision.status,  # type: ignore[arg-type]
                confidence=decision.confidence,
                reason=decision.reason,
                matched_terms=list(decision.matched_terms),
                review_status=_review_status(decision.status),
            ),
        )
    return mappings


def deterministic_mapping_id(source_record_id: str) -> str:
    digest = hashlib.sha256(source_record_id.encode("utf-8")).hexdigest()
    return f"egp_map_{digest}"


def _review_status(mapping_status: str) -> str:
    if mapping_status == "exact":
        return "approved"
    if mapping_status == "candidate":
        return "pending"
    return "needs_review"
