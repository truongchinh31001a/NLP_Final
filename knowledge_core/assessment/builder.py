from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Sequence

from knowledge_core.alignment.models import (
    CanonicalSkillEvidenceProfile,
    SkillCEFRAlignment,
)
from knowledge_core.assessment.models import (
    AssessmentCriterion,
    AssessmentEvidence,
    GrammarAssessmentConfig,
    SkillAssessmentProfile,
)
from knowledge_core.assessment.rules import (
    SKILL_ASSESSMENT_SPECS,
    confidence_for_criterion,
    criterion_types_for_skill,
    description_for_criterion,
    evidence_requirements_for_criterion,
    failure_signals_for_criterion,
    name_for_criterion,
    observable_for_criterion,
    task_types_for_criterion,
)
from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILLS
from knowledge_core.relationships.models import SkillRelationship
from knowledge_core.relationships.taxonomy import build_grammar_taxonomy
from knowledge_core.sources.cefr.models import CEFRDescriptorRecord
from knowledge_core.sources.egp.models import RawEGPRecord


@dataclass(slots=True)
class AssessmentInputArtifacts:
    skill_profiles: list[CanonicalSkillEvidenceProfile]
    skill_alignments: list[SkillCEFRAlignment]
    relationships: list[SkillRelationship]
    cefr_descriptors: list[CEFRDescriptorRecord]
    egp_records: list[RawEGPRecord]


@dataclass(slots=True)
class BuiltAssessmentDataset:
    criteria: list[AssessmentCriterion]
    profiles: list[SkillAssessmentProfile]
    taxonomy_hash: str


def build_assessment_dataset(
    *,
    config: GrammarAssessmentConfig,
    artifacts: AssessmentInputArtifacts,
    canonical_skill_ids: Sequence[str] = CANONICAL_GRAMMAR_V1_SKILLS,
) -> BuiltAssessmentDataset:
    taxonomy = build_grammar_taxonomy(canonical_skill_ids)
    profile_by_skill = {
        profile.canonical_skill_id: profile
        for profile in artifacts.skill_profiles
    }
    alignment_by_skill = {
        alignment.canonical_skill_id: alignment
        for alignment in artifacts.skill_alignments
    }
    ga_descriptor_ids_by_level = _grammatical_accuracy_descriptor_ids_by_level(
        artifacts.cefr_descriptors,
    )
    incoming_relationships_by_skill = _incoming_context_relationships(
        artifacts.relationships,
    )
    hard_prerequisites_by_skill = _hard_prerequisites_by_skill(
        artifacts.relationships,
    )

    criteria: list[AssessmentCriterion] = []
    profiles: list[SkillAssessmentProfile] = []
    for skill_id in canonical_skill_ids:
        if skill_id not in SKILL_ASSESSMENT_SPECS:
            raise KeyError(f"missing assessment spec for canonical skill: {skill_id}")

        skill_criteria = _criteria_for_skill(
            skill_id=skill_id,
            config=config,
            profile=profile_by_skill.get(skill_id),
            alignment=alignment_by_skill.get(skill_id),
            ga_descriptor_ids_by_level=ga_descriptor_ids_by_level,
            incoming_relationships=incoming_relationships_by_skill.get(skill_id, []),
        )
        criteria.extend(skill_criteria)
        profiles.append(
            _profile_for_skill(
                skill_id=skill_id,
                criteria=skill_criteria,
                cefr_primary_level=_cefr_primary_level(
                    profile_by_skill.get(skill_id),
                    alignment_by_skill.get(skill_id),
                ),
                prerequisite_context=hard_prerequisites_by_skill.get(skill_id, []),
                config=config,
            ),
        )

    return BuiltAssessmentDataset(
        criteria=criteria,
        profiles=profiles,
        taxonomy_hash=taxonomy.taxonomy_hash,
    )


def deterministic_criterion_id(
    canonical_skill_id: str,
    criterion_type: str,
    name: str,
) -> str:
    raw_key = "\x1f".join([canonical_skill_id, criterion_type, name])
    return "crit_" + hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _criteria_for_skill(
    *,
    skill_id: str,
    config: GrammarAssessmentConfig,
    profile: CanonicalSkillEvidenceProfile | None,
    alignment: SkillCEFRAlignment | None,
    ga_descriptor_ids_by_level: dict[str, list[str]],
    incoming_relationships: Sequence[SkillRelationship],
) -> list[AssessmentCriterion]:
    spec = SKILL_ASSESSMENT_SPECS[skill_id]
    cefr_level = _cefr_primary_level(profile, alignment)
    cefr_context_descriptor_ids = _cefr_context_descriptor_ids(
        cefr_level=cefr_level,
        profile=profile,
        alignment=alignment,
        ga_descriptor_ids_by_level=ga_descriptor_ids_by_level,
    )
    criteria: list[AssessmentCriterion] = []
    for criterion_type in criterion_types_for_skill(skill_id):
        threshold = config.thresholds.for_type(criterion_type)
        name = name_for_criterion(spec, criterion_type)
        criteria.append(
            AssessmentCriterion(
                criterion_id=deterministic_criterion_id(
                    skill_id,
                    criterion_type,
                    name,
                ),
                canonical_skill_id=skill_id,
                criterion_type=criterion_type,
                name=name,
                description=description_for_criterion(spec, criterion_type),
                observable_behavior=observable_for_criterion(spec, criterion_type),
                evidence_requirements=list(
                    evidence_requirements_for_criterion(spec, criterion_type),
                ),
                acceptable_task_types=list(task_types_for_criterion(criterion_type)),
                failure_signals=list(
                    failure_signals_for_criterion(spec, criterion_type),
                ),
                cefr_level=cefr_level,
                cefr_context_descriptor_ids=cefr_context_descriptor_ids,
                recommended_threshold=threshold.recommended_threshold,
                recommended_min_items=threshold.recommended_min_items,
                threshold_source=config.defaults.threshold_source,
                confidence=confidence_for_criterion(criterion_type),
                status=config.defaults.status,
                review_status=config.defaults.review_status,
                reason=(
                    f"Deterministic Assessment Criteria V1 rule for {spec.label}. "
                    "Recommended thresholds are curated guidance, not mastery decisions."
                ),
                provenance=_criterion_provenance(
                    profile=profile,
                    cefr_level=cefr_level,
                    cefr_context_descriptor_ids=cefr_context_descriptor_ids,
                    incoming_relationships=incoming_relationships,
                ),
                version=config.metadata.version,
            ),
        )
    return criteria


def _profile_for_skill(
    *,
    skill_id: str,
    criteria: Sequence[AssessmentCriterion],
    cefr_primary_level: str | None,
    prerequisite_context: Sequence[str],
    config: GrammarAssessmentConfig,
) -> SkillAssessmentProfile:
    return SkillAssessmentProfile(
        canonical_skill_id=skill_id,
        cefr_primary_level=cefr_primary_level,
        criterion_ids=[criterion.criterion_id for criterion in criteria],
        criterion_types=_dedupe_preserving_order(
            criterion.criterion_type for criterion in criteria
        ),
        recommended_task_types=_dedupe_preserving_order(
            task_type
            for criterion in criteria
            for task_type in criterion.acceptable_task_types
        ),
        prerequisite_context=list(prerequisite_context),
        assessment_coverage_status="covered" if criteria else "missing",
        review_status=config.defaults.review_status,
        version=config.metadata.version,
    )


def _criterion_provenance(
    *,
    profile: CanonicalSkillEvidenceProfile | None,
    cefr_level: str | None,
    cefr_context_descriptor_ids: Sequence[str],
    incoming_relationships: Sequence[SkillRelationship],
) -> list[AssessmentEvidence]:
    provenance = [
        AssessmentEvidence(
            evidence_type="curated_assessment_rule",
            source="grammar_assessment_rules_v1",
            source_record_ids=[],
            note=(
                "Generated from deterministic curated assessment rules. "
                "Failure signals are diagnostic hints; corpus-backed error "
                "evidence is not claimed."
            ),
        ),
    ]
    if profile and profile.egp_source_record_ids:
        provenance.append(
            AssessmentEvidence(
                evidence_type="egp_evidence",
                source="english_grammar_profile_alignment",
                source_record_ids=list(profile.egp_source_record_ids),
                note=(
                    "EGP evidence supports feature presence and progression "
                    "context; numeric thresholds are not derived from EGP."
                ),
            ),
        )
    if cefr_context_descriptor_ids:
        provenance.append(
            AssessmentEvidence(
                evidence_type="cefr_grammatical_accuracy",
                source="cefr_companion_volume",
                source_record_ids=list(cefr_context_descriptor_ids),
                note=(
                    f"CEFR {cefr_level} grammatical accuracy descriptor(s) "
                    "attached as general proficiency context, not as atomic "
                    "skill descriptors."
                ),
            ),
        )
    elif cefr_level:
        provenance.append(
            AssessmentEvidence(
                evidence_type="cefr_proficiency_context",
                source="cefr_egp_alignment",
                source_record_ids=[],
                note=(
                    f"CEFR {cefr_level} attached from alignment as general "
                    "proficiency context."
                ),
            ),
        )
    if incoming_relationships:
        provenance.append(
            AssessmentEvidence(
                evidence_type="relationship_context",
                source="grammar_relationships",
                source_record_ids=[
                    relationship.relationship_id
                    for relationship in incoming_relationships
                ],
                note=(
                    "Incoming prerequisite, recommendation, or support edges "
                    "are attached as context only; the criterion does not "
                    "require prerequisite mastery."
                ),
            ),
        )
    return provenance


def _cefr_primary_level(
    profile: CanonicalSkillEvidenceProfile | None,
    alignment: SkillCEFRAlignment | None,
) -> str | None:
    if profile and profile.cefr_primary_level:
        return profile.cefr_primary_level
    if alignment and alignment.inferred_primary_level:
        return alignment.inferred_primary_level
    return None


def _cefr_context_descriptor_ids(
    *,
    cefr_level: str | None,
    profile: CanonicalSkillEvidenceProfile | None,
    alignment: SkillCEFRAlignment | None,
    ga_descriptor_ids_by_level: dict[str, list[str]],
) -> list[str]:
    descriptor_ids: list[str] = []
    if profile:
        descriptor_ids.extend(profile.grammatical_accuracy_context)
    if alignment:
        descriptor_ids.extend(alignment.grammatical_accuracy_descriptor_ids)
    if cefr_level and not descriptor_ids:
        descriptor_ids.extend(ga_descriptor_ids_by_level.get(cefr_level, []))
    return _dedupe_preserving_order(descriptor_ids)


def _grammatical_accuracy_descriptor_ids_by_level(
    descriptors: Sequence[CEFRDescriptorRecord],
) -> dict[str, list[str]]:
    by_level: dict[str, list[str]] = {}
    for descriptor in descriptors:
        if descriptor.scale_name != "grammatical_accuracy":
            continue
        if not descriptor.descriptor_available:
            continue
        by_level.setdefault(descriptor.cefr_level, []).append(
            descriptor.source_record_id,
        )
    return {
        level: sorted(source_record_ids)
        for level, source_record_ids in by_level.items()
    }


def _incoming_context_relationships(
    relationships: Sequence[SkillRelationship],
) -> dict[str, list[SkillRelationship]]:
    by_target: dict[str, list[SkillRelationship]] = {}
    for relationship in relationships:
        if relationship.relation_type not in {
            "prerequisite_of",
            "recommended_before",
            "supports",
        }:
            continue
        by_target.setdefault(relationship.target_skill_id, []).append(relationship)
    return {
        skill_id: sorted(items, key=lambda relationship: relationship.relationship_id)
        for skill_id, items in by_target.items()
    }


def _hard_prerequisites_by_skill(
    relationships: Sequence[SkillRelationship],
) -> dict[str, list[str]]:
    by_target: dict[str, list[str]] = {}
    for relationship in relationships:
        if relationship.relation_type != "prerequisite_of":
            continue
        by_target.setdefault(relationship.target_skill_id, []).append(
            relationship.source_skill_id,
        )
    return {
        skill_id: sorted(source_skill_ids)
        for skill_id, source_skill_ids in by_target.items()
    }


def _dedupe_preserving_order(values) -> list:
    seen: set[object] = set()
    deduped: list = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
