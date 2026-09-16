from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable, Sequence

from knowledge_core.alignment.egp_evidence import (
    EGPEvidenceBundle,
    collect_egp_evidence,
    deterministic_evidence_id,
)
from knowledge_core.alignment.models import (
    CanonicalSkillEvidenceProfile,
    KnowledgeAlignmentConfig,
    ObjectiveAlignment,
    SkillCEFRAlignment,
    SkillSourceEvidence,
    canonical_parent_from_skill_id,
)
from knowledge_core.alignment.objective_alignment import (
    LEVEL_ORDER,
    SkillLevelContext,
    align_objectives_for_skill,
)
from knowledge_core.mapping.egp.models import EGPCanonicalMapping
from knowledge_core.sources.cefr.models import (
    CEFRDescriptorRecord,
    CEFRLearningObjectiveCandidate,
)
from knowledge_core.sources.egp.models import RawEGPRecord


@dataclass(slots=True)
class KnowledgeAlignmentDataset:
    profiles: list[CanonicalSkillEvidenceProfile]
    alignments: list[SkillCEFRAlignment]
    source_evidence: list[SkillSourceEvidence]
    objective_alignments: list[ObjectiveAlignment]
    egp_bundle: EGPEvidenceBundle


@dataclass(slots=True, frozen=True)
class InferredLevelResult:
    min_level: str | None
    primary_level: str | None
    unique_levels: list[str]
    confidence: float
    reason: str
    status: str
    review_status: str
    conflicting: bool


def build_knowledge_alignment(
    *,
    canonical_skills: Sequence[str],
    egp_records: Sequence[RawEGPRecord],
    egp_mappings: Sequence[EGPCanonicalMapping],
    cefr_descriptors: Sequence[CEFRDescriptorRecord],
    cefr_objectives: Sequence[CEFRLearningObjectiveCandidate],
    config: KnowledgeAlignmentConfig,
) -> KnowledgeAlignmentDataset:
    egp_bundle = collect_egp_evidence(
        egp_records,
        egp_mappings,
        establishing_statuses=set(config.egp.establishing_statuses),
        ambiguous_statuses=set(config.egp.ambiguous_statuses),
        status_weights=config.egp.status_weights,
    )
    grammatical_accuracy_by_level = _grammatical_accuracy_by_level(
        cefr_descriptors,
        scale_name=config.cefr.grammatical_accuracy_scale,
    )

    profiles: list[CanonicalSkillEvidenceProfile] = []
    alignments: list[SkillCEFRAlignment] = []
    source_evidence: list[SkillSourceEvidence] = list(egp_bundle.direct_evidence)
    objective_alignments: list[ObjectiveAlignment] = []

    for skill_id in canonical_skills:
        direct_evidence = egp_bundle.direct_by_skill.get(skill_id, [])
        ambiguous_mappings = egp_bundle.ambiguous_by_skill.get(skill_id, [])
        inferred = infer_levels_from_egp_evidence(direct_evidence)
        ga_descriptors = (
            grammatical_accuracy_by_level.get(inferred.primary_level or "", [])
            if inferred.primary_level
            else []
        )
        level_context = SkillLevelContext(
            inferred_min_level=inferred.min_level,
            inferred_primary_level=inferred.primary_level,
        )
        skill_objective_alignments = align_objectives_for_skill(
            skill_id,
            cefr_objectives,
            config.objective_alignment,
            level_context=level_context,
        )
        direct_objective_ids = [
            alignment.objective_id
            for alignment in skill_objective_alignments
            if alignment.relevance == "direct"
        ]
        contextual_objective_ids = [
            alignment.objective_id
            for alignment in skill_objective_alignments
            if alignment.relevance == "contextual"
        ]
        objective_descriptor_ids = [
            alignment.source_record_id for alignment in skill_objective_alignments
        ]
        ga_descriptor_ids = [record.source_record_id for record in ga_descriptors]
        status = _final_status(
            inferred,
            ambiguous_mappings=ambiguous_mappings,
            objective_alignments=skill_objective_alignments,
            ga_descriptors=ga_descriptors,
        )
        confidence = _final_confidence(
            inferred,
            status=status,
            objective_alignments=skill_objective_alignments,
            ga_descriptors=ga_descriptors,
        )
        review_status = _review_status(
            status,
            confidence,
            conflicting=inferred.conflicting,
            ambiguous=bool(ambiguous_mappings),
        )
        reason = _final_reason(
            inferred,
            status=status,
            ambiguous_mappings=ambiguous_mappings,
            objective_alignments=skill_objective_alignments,
            ga_descriptors=ga_descriptors,
        )

        for record in ga_descriptors:
            source_evidence.append(
                SkillSourceEvidence(
                    evidence_id=deterministic_evidence_id(
                        "cefr_grammatical_accuracy",
                        skill_id,
                        record.source_record_id,
                    ),
                    canonical_skill_id=skill_id,
                    source=record.source,
                    source_record_id=record.source_record_id,
                    evidence_type="cefr_grammatical_accuracy",
                    source_cefr_level=record.cefr_level,
                    confidence=confidence,
                    status="context",
                    provenance={
                        "scale_name": record.scale_name,
                        "source_table": record.source_table,
                        "page_number": record.page_number,
                        "relationship_meaning": (
                            "At the aligned CEFR level, this skill should be "
                            "demonstrated within the general grammatical "
                            "accuracy expectations of that level."
                        ),
                    },
                ),
            )

        for alignment in skill_objective_alignments:
            source_evidence.append(
                SkillSourceEvidence(
                    evidence_id=deterministic_evidence_id(
                        "cefr_learning_objective",
                        skill_id,
                        alignment.source_record_id,
                        alignment.objective_id,
                    ),
                    canonical_skill_id=skill_id,
                    source="cefr_companion_volume",
                    source_record_id=alignment.source_record_id,
                    evidence_type="cefr_learning_objective",
                    source_cefr_level=alignment.cefr_level,
                    confidence=alignment.confidence,
                    status=alignment.relevance,
                    provenance={
                        "objective_id": alignment.objective_id,
                        "matched_terms": alignment.matched_terms,
                        "reason": alignment.reason,
                    },
                ),
            )

        objective_alignments.extend(skill_objective_alignments)
        egp_source_record_ids = [
            evidence.source_record_id for evidence in direct_evidence
        ]
        profile = CanonicalSkillEvidenceProfile(
            canonical_skill_id=skill_id,
            canonical_parent=canonical_parent_from_skill_id(skill_id),
            egp_evidence_count=len(direct_evidence),
            egp_levels=inferred.unique_levels,
            egp_source_record_ids=egp_source_record_ids,
            cefr_min_level=inferred.min_level,
            cefr_primary_level=inferred.primary_level,
            grammatical_accuracy_context=ga_descriptor_ids,
            direct_objective_ids=direct_objective_ids,
            contextual_objective_ids=contextual_objective_ids,
            evidence_status=status,  # type: ignore[arg-type]
            alignment_confidence=confidence,
            notes=reason,
            provenance={
                "taxonomy_source": "knowledge_core.mapping.egp.canonical.CANONICAL_GRAMMAR_V1_SKILLS",
                "egp_level_observations": [
                    {
                        "source_record_id": evidence.source_record_id,
                        "cefr_level": evidence.source_cefr_level,
                        "status": evidence.status,
                        "confidence": evidence.confidence,
                        "mapping_id": evidence.provenance.get("mapping_id"),
                    }
                    for evidence in direct_evidence
                ],
                "ambiguous_egp_source_record_ids": [
                    mapping.source_record_id for mapping in ambiguous_mappings
                ],
                "ambiguous_egp_secondary_candidates": [
                    {
                        "source_record_id": mapping.source_record_id,
                        "secondary_candidates": mapping.secondary_candidates,
                        "reason": mapping.reason,
                    }
                    for mapping in ambiguous_mappings
                ],
                "objective_alignments": [
                    alignment.model_dump(mode="json")
                    for alignment in skill_objective_alignments
                ],
                "source_evidence_ids": [
                    evidence.evidence_id for evidence in direct_evidence
                ],
                "conflicting_level_evidence": inferred.conflicting,
            },
        )
        profiles.append(profile)
        alignments.append(
            SkillCEFRAlignment(
                canonical_skill_id=skill_id,
                egp_levels=inferred.unique_levels,
                inferred_min_level=inferred.min_level,
                inferred_primary_level=inferred.primary_level,
                cefr_descriptor_ids=sorted(set(ga_descriptor_ids + objective_descriptor_ids)),
                objective_ids=sorted(set(direct_objective_ids + contextual_objective_ids)),
                grammatical_accuracy_descriptor_ids=ga_descriptor_ids,
                confidence=confidence,
                status=status,  # type: ignore[arg-type]
                reason=reason,
                review_status=review_status,  # type: ignore[arg-type]
            ),
        )

    return KnowledgeAlignmentDataset(
        profiles=profiles,
        alignments=alignments,
        source_evidence=source_evidence,
        objective_alignments=objective_alignments,
        egp_bundle=egp_bundle,
    )


def infer_levels_from_egp_evidence(
    evidence: Iterable[SkillSourceEvidence],
) -> InferredLevelResult:
    evidence_list = list(evidence)
    if not evidence_list:
        return InferredLevelResult(
            min_level=None,
            primary_level=None,
            unique_levels=[],
            confidence=0.0,
            reason="No direct exact/candidate EGP evidence establishes a CEFR level.",
            status="curated_only",
            review_status="needs_review",
            conflicting=False,
        )

    exact_evidence = [
        item for item in evidence_list if item.status == "exact" and item.source_cefr_level
    ]
    candidate_evidence = [
        item for item in evidence_list if item.status == "candidate" and item.source_cefr_level
    ]
    credible_for_min = exact_evidence or candidate_evidence
    unique_levels = _ordered_unique(
        item.source_cefr_level
        for item in evidence_list
        if item.source_cefr_level
    )
    min_level = _earliest_level(
        item.source_cefr_level
        for item in credible_for_min
        if item.source_cefr_level
    )
    primary_level = _weighted_primary_level(evidence_list)
    conflicting = _has_conflicting_level_evidence(unique_levels)
    confidence = _egp_level_confidence(
        evidence_list,
        exact_count=len(exact_evidence),
        candidate_count=len(candidate_evidence),
        conflicting=conflicting,
    )
    status = "aligned" if exact_evidence and not conflicting else "partial"
    review_status = (
        "accepted" if status == "aligned" and confidence >= 0.85 else "needs_review"
    )
    reason = _egp_level_reason(
        evidence_list,
        min_level=min_level,
        primary_level=primary_level,
        exact_count=len(exact_evidence),
        candidate_count=len(candidate_evidence),
        conflicting=conflicting,
    )
    return InferredLevelResult(
        min_level=min_level,
        primary_level=primary_level,
        unique_levels=unique_levels,
        confidence=confidence,
        reason=reason,
        status=status,
        review_status=review_status,
        conflicting=conflicting,
    )


def _grammatical_accuracy_by_level(
    cefr_descriptors: Sequence[CEFRDescriptorRecord],
    *,
    scale_name: str,
) -> dict[str, list[CEFRDescriptorRecord]]:
    grouped: dict[str, list[CEFRDescriptorRecord]] = defaultdict(list)
    for record in cefr_descriptors:
        if (
            record.scale_name == scale_name
            and record.descriptor_available
            and record.cefr_level
        ):
            grouped[record.cefr_level].append(record)
    return {key: list(value) for key, value in grouped.items()}


def _final_status(
    inferred: InferredLevelResult,
    *,
    ambiguous_mappings: Sequence[EGPCanonicalMapping],
    objective_alignments: Sequence[ObjectiveAlignment],
    ga_descriptors: Sequence[CEFRDescriptorRecord],
) -> str:
    if inferred.primary_level:
        if not ga_descriptors:
            return "no_cefr_evidence"
        return inferred.status
    if ambiguous_mappings:
        return "ambiguous"
    if objective_alignments:
        return "partial"
    return "curated_only"


def _final_confidence(
    inferred: InferredLevelResult,
    *,
    status: str,
    objective_alignments: Sequence[ObjectiveAlignment],
    ga_descriptors: Sequence[CEFRDescriptorRecord],
) -> float:
    if status == "curated_only":
        return 0.0
    if status == "ambiguous":
        return 0.45
    confidence = inferred.confidence
    if not inferred.primary_level and objective_alignments:
        confidence = max(confidence, max(alignment.confidence for alignment in objective_alignments) - 0.1)
    if inferred.primary_level and ga_descriptors:
        confidence += 0.03
    if objective_alignments:
        confidence += 0.02
    if status == "partial":
        confidence = min(confidence, 0.82)
    return round(min(max(confidence, 0.0), 1.0), 4)


def _review_status(
    status: str,
    confidence: float,
    *,
    conflicting: bool,
    ambiguous: bool,
) -> str:
    if status == "aligned" and confidence >= 0.85 and not conflicting and not ambiguous:
        return "accepted"
    if status in {"partial", "ambiguous", "no_cefr_evidence"}:
        return "needs_review"
    return "pending"


def _final_reason(
    inferred: InferredLevelResult,
    *,
    status: str,
    ambiguous_mappings: Sequence[EGPCanonicalMapping],
    objective_alignments: Sequence[ObjectiveAlignment],
    ga_descriptors: Sequence[CEFRDescriptorRecord],
) -> str:
    pieces: list[str] = []
    if inferred.primary_level:
        pieces.append(inferred.reason)
        if ga_descriptors:
            pieces.append(
                "CEFR grammatical accuracy context attached for "
                f"{inferred.primary_level}."
            )
        else:
            pieces.append(
                "No CEFR grammatical accuracy descriptor was available for "
                f"{inferred.primary_level}."
            )
    elif ambiguous_mappings:
        pieces.append(
            "Only ambiguous EGP mappings are available; they are preserved for "
            "review and do not establish a CEFR level."
        )
    elif objective_alignments:
        pieces.append(
            "No direct EGP level evidence; CEFR objective links are contextual "
            "or direct rule matches only."
        )
    else:
        pieces.append("No direct EGP or CEFR objective evidence found.")

    direct = sum(1 for alignment in objective_alignments if alignment.relevance == "direct")
    contextual = sum(
        1 for alignment in objective_alignments if alignment.relevance == "contextual"
    )
    if direct or contextual:
        pieces.append(
            f"Objective links: {direct} direct, {contextual} contextual."
        )
    if status != inferred.status and inferred.primary_level:
        pieces.append(f"Final alignment status adjusted to {status}.")
    return " ".join(pieces)


def _egp_level_confidence(
    evidence: Sequence[SkillSourceEvidence],
    *,
    exact_count: int,
    candidate_count: int,
    conflicting: bool,
) -> float:
    if not evidence:
        return 0.0
    level_counts = Counter(
        item.source_cefr_level for item in evidence if item.source_cefr_level
    )
    if exact_count and len(level_counts) == 1 and exact_count >= 2:
        confidence = 0.95
    elif exact_count and len(level_counts) == 1:
        confidence = 0.9
    elif exact_count:
        confidence = 0.84
    elif candidate_count and len(level_counts) == 1:
        confidence = 0.72
    else:
        confidence = 0.66
    if conflicting:
        confidence -= 0.12
    return round(max(confidence, 0.0), 4)


def _egp_level_reason(
    evidence: Sequence[SkillSourceEvidence],
    *,
    min_level: str | None,
    primary_level: str | None,
    exact_count: int,
    candidate_count: int,
    conflicting: bool,
) -> str:
    if not evidence:
        return "No direct EGP evidence."
    reason = (
        f"Direct EGP evidence first appears at {min_level} and weighted evidence "
        f"is concentrated at {primary_level}; {exact_count} exact and "
        f"{candidate_count} candidate mapping(s) contributed."
    )
    if conflicting:
        levels = ", ".join(_ordered_unique(item.source_cefr_level for item in evidence if item.source_cefr_level))
        reason += f" Level evidence spans multiple bands ({levels}), so review is required."
    return reason


def _weighted_primary_level(evidence: Sequence[SkillSourceEvidence]) -> str | None:
    scores: dict[str, float] = defaultdict(float)
    for item in evidence:
        if not item.source_cefr_level:
            continue
        scores[item.source_cefr_level] += item.confidence
    if not scores:
        return None
    return sorted(scores, key=lambda level: (-scores[level], LEVEL_ORDER.get(level, 99)))[0]


def _earliest_level(levels: Iterable[str]) -> str | None:
    level_list = [level for level in levels if level in LEVEL_ORDER]
    if not level_list:
        return None
    return sorted(level_list, key=lambda level: LEVEL_ORDER[level])[0]


def _ordered_unique(levels: Iterable[str | None]) -> list[str]:
    unique = {level for level in levels if level}
    return sorted(unique, key=lambda level: LEVEL_ORDER.get(level, 99))


def _has_conflicting_level_evidence(levels: Sequence[str]) -> bool:
    if len(levels) < 2:
        return False
    indexes = [LEVEL_ORDER[level] for level in levels if level in LEVEL_ORDER]
    if not indexes:
        return False
    return max(indexes) - min(indexes) > 2

