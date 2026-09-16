from __future__ import annotations

import hashlib
from typing import Iterable, Sequence

from knowledge_core.sources.cefr.models import (
    CEFRDescriptorRecord,
    CEFRLearningObjectiveCandidate,
    PRIMARY_CEFR_LEVELS,
)
from knowledge_core.sources.cefr.normalizer import normalize_whitespace


OBJECTIVE_DESCRIPTOR_TYPES = {
    "communicative_activity",
    "communicative_strategy",
    "linguistic_competence",
    "assessment_descriptor",
}


def extract_learning_objective_candidates(
    records: Iterable[CEFRDescriptorRecord],
    *,
    include_levels: Sequence[str] | None = None,
) -> list[CEFRLearningObjectiveCandidate]:
    accepted_levels = set(include_levels or sorted(PRIMARY_CEFR_LEVELS))
    candidates: list[CEFRLearningObjectiveCandidate] = []
    for record in records:
        if not record.descriptor_available:
            continue
        if record.cefr_level not in accepted_levels:
            continue
        if record.descriptor_type not in OBJECTIVE_DESCRIPTOR_TYPES:
            continue
        objective_text = normalize_whitespace(record.descriptor_text)
        if not objective_text:
            continue
        candidates.append(
            CEFRLearningObjectiveCandidate(
                objective_id=deterministic_objective_id(
                    record.source_record_id,
                    objective_text,
                ),
                source_record_id=record.source_record_id,
                cefr_level=record.cefr_level,
                domain=record.domain,
                scale_name=record.scale_name,
                objective_text=objective_text,
                source_descriptor_text=record.descriptor_text,
                status="exact_source",
                confidence=1.0,
                canonical_skill_hint=None,
            ),
        )
    return candidates


def deterministic_objective_id(source_record_id: str, objective_text: str) -> str:
    raw_key = "\x1f".join([source_record_id, normalize_whitespace(objective_text)])
    return "cefr_obj_" + hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

