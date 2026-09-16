from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Mapping

from knowledge_core.alignment.models import SkillSourceEvidence
from knowledge_core.mapping.egp.models import EGPCanonicalMapping
from knowledge_core.sources.egp.models import RawEGPRecord


@dataclass(slots=True)
class EGPEvidenceBundle:
    direct_evidence: list[SkillSourceEvidence]
    direct_by_skill: dict[str, list[SkillSourceEvidence]] = field(default_factory=dict)
    ambiguous_by_skill: dict[str, list[EGPCanonicalMapping]] = field(default_factory=dict)
    unmapped_mappings: list[EGPCanonicalMapping] = field(default_factory=list)
    missing_source_record_ids: list[str] = field(default_factory=list)


def collect_egp_evidence(
    records: Iterable[RawEGPRecord],
    mappings: Iterable[EGPCanonicalMapping],
    *,
    establishing_statuses: set[str],
    ambiguous_statuses: set[str],
    status_weights: Mapping[str, float],
) -> EGPEvidenceBundle:
    records_by_id = {
        record.source_record_id: record
        for record in records
        if record.source_record_id
    }
    direct_evidence: list[SkillSourceEvidence] = []
    direct_by_skill: dict[str, list[SkillSourceEvidence]] = defaultdict(list)
    ambiguous_by_skill: dict[str, list[EGPCanonicalMapping]] = defaultdict(list)
    unmapped_mappings: list[EGPCanonicalMapping] = []
    missing_source_record_ids: list[str] = []

    for mapping in mappings:
        record = records_by_id.get(mapping.source_record_id)
        if record is None:
            missing_source_record_ids.append(mapping.source_record_id)
            continue

        if mapping.status in establishing_statuses:
            if mapping.canonical_skill:
                evidence = _evidence_from_mapping(
                    record,
                    mapping,
                    canonical_skill_id=mapping.canonical_skill,
                    status_weights=status_weights,
                    relationship="primary",
                    confidence_multiplier=1.0,
                )
                direct_evidence.append(evidence)
                direct_by_skill[mapping.canonical_skill].append(evidence)
            for secondary_skill_id in mapping.secondary_candidates:
                evidence = _evidence_from_mapping(
                    record,
                    mapping,
                    canonical_skill_id=secondary_skill_id,
                    status_weights=status_weights,
                    relationship="secondary_candidate",
                    confidence_multiplier=0.5,
                )
                direct_evidence.append(evidence)
                direct_by_skill[secondary_skill_id].append(evidence)
            continue

        if mapping.status in ambiguous_statuses:
            for skill_id in mapping.secondary_candidates:
                ambiguous_by_skill[skill_id].append(mapping)
            continue

        if mapping.status == "unmapped":
            unmapped_mappings.append(mapping)

    return EGPEvidenceBundle(
        direct_evidence=direct_evidence,
        direct_by_skill={key: list(value) for key, value in direct_by_skill.items()},
        ambiguous_by_skill={key: list(value) for key, value in ambiguous_by_skill.items()},
        unmapped_mappings=unmapped_mappings,
        missing_source_record_ids=missing_source_record_ids,
    )


def _evidence_from_mapping(
    record: RawEGPRecord,
    mapping: EGPCanonicalMapping,
    *,
    canonical_skill_id: str,
    status_weights: Mapping[str, float],
    relationship: str,
    confidence_multiplier: float,
) -> SkillSourceEvidence:
    return SkillSourceEvidence(
        evidence_id=deterministic_evidence_id(
            "egp_direct",
            canonical_skill_id,
            mapping.source_record_id,
            f"{mapping.mapping_id}:{relationship}",
        ),
        canonical_skill_id=canonical_skill_id,
        source=record.source,
        source_record_id=mapping.source_record_id,
        evidence_type="egp_direct",
        source_cefr_level=record.cefr_level,
        confidence=min(
            mapping.confidence
            * status_weights.get(mapping.status, 1.0)
            * confidence_multiplier,
            1.0,
        ),
        status=mapping.status,
        provenance={
            "relationship": relationship,
            "mapping_id": mapping.mapping_id,
            "mapping_status": mapping.status,
            "mapping_confidence": mapping.confidence,
            "review_status": mapping.review_status,
            "reason": mapping.reason,
            "matched_terms": mapping.matched_terms,
            "category_id": record.category_id,
            "source_file": record.source_file,
            "source_row_number": record.source_row_number,
        },
    )


def deterministic_evidence_id(
    evidence_type: str,
    canonical_skill_id: str,
    source_record_id: str,
    salt: str = "",
) -> str:
    raw_key = "\x1f".join([evidence_type, canonical_skill_id, source_record_id, salt])
    return "align_ev_" + hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
