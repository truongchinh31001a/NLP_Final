from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Sequence

from knowledge_core.alignment.models import (
    CanonicalSkillEvidenceProfile,
    SkillCEFRAlignment,
)
from knowledge_core.relationships.models import (
    GrammarRelationshipConfig,
    RelationshipEvidence,
    RelationshipRule,
    SkillRelationship,
    dependency_strength_for_relation,
    is_bidirectional_relation,
)
from knowledge_core.relationships.taxonomy import GrammarTaxonomy


@dataclass(slots=True)
class BuiltRelationshipDataset:
    relationships: list[SkillRelationship]
    taxonomy: GrammarTaxonomy


def build_relationships(
    *,
    taxonomy: GrammarTaxonomy,
    config: GrammarRelationshipConfig,
    skill_profiles: Sequence[CanonicalSkillEvidenceProfile],
    skill_alignments: Sequence[SkillCEFRAlignment],
) -> BuiltRelationshipDataset:
    profile_by_skill = {
        profile.canonical_skill_id: profile for profile in skill_profiles
    }
    alignment_by_skill = {
        alignment.canonical_skill_id: alignment for alignment in skill_alignments
    }
    relationships = _structural_relationships(taxonomy, config)
    relationships.extend(
        _curated_relationships(
            config.curated_relationships,
            config=config,
            profile_by_skill=profile_by_skill,
            alignment_by_skill=alignment_by_skill,
        ),
    )
    relationships = _deduplicate_relationships(relationships)
    return BuiltRelationshipDataset(relationships=relationships, taxonomy=taxonomy)


def _structural_relationships(
    taxonomy: GrammarTaxonomy,
    config: GrammarRelationshipConfig,
) -> list[SkillRelationship]:
    relationships: list[SkillRelationship] = []
    for parent_id, children in sorted(taxonomy.children_by_parent.items()):
        for child_id in children:
            relationships.append(
                SkillRelationship(
                    relationship_id=deterministic_relationship_id(
                        parent_id,
                        child_id,
                        "parent_of",
                        bidirectional=False,
                    ),
                    source_skill_id=parent_id,
                    target_skill_id=child_id,
                    relation_type="parent_of",
                    dependency_strength="none",
                    confidence=config.defaults.structural_confidence,
                    status="accepted",
                    reason="Structural parent relationship from the canonical Grammar V1 taxonomy.",
                    evidence=[
                        RelationshipEvidence(
                            evidence_type="taxonomy_structure",
                            source="canonical_grammar_v1_taxonomy",
                            source_record_ids=[],
                            note=(
                                "Generated from canonical skill id namespace; "
                                "no grammar skills were added."
                            ),
                        ),
                    ],
                    bidirectional=False,
                    review_status="approved",
                    created_by=config.metadata.created_by,
                    version=config.metadata.version,
                ),
            )
    return relationships


def _curated_relationships(
    rules: Sequence[RelationshipRule],
    *,
    config: GrammarRelationshipConfig,
    profile_by_skill: dict[str, CanonicalSkillEvidenceProfile],
    alignment_by_skill: dict[str, SkillCEFRAlignment],
) -> list[SkillRelationship]:
    relationships: list[SkillRelationship] = []
    for rule in rules:
        source_id, target_id = _canonical_direction(rule.source, rule.target, rule.relation_type)
        relation_type = rule.relation_type
        confidence = rule.confidence or _default_confidence(relation_type, config)
        bidirectional = is_bidirectional_relation(relation_type)
        evidence_type = (
            "linguistic_structure"
            if relation_type == "prerequisite_of"
            else "curated_pedagogy"
        )
        evidence = [
            RelationshipEvidence(
                evidence_type=evidence_type,
                source="grammar_relationship_rules_v1",
                source_record_ids=[],
                note=rule.reason,
            ),
        ]
        evidence.extend(
            _supporting_alignment_evidence(
                source_id,
                target_id,
                relation_type=relation_type,
                profile_by_skill=profile_by_skill,
                alignment_by_skill=alignment_by_skill,
            ),
        )
        relationships.append(
            SkillRelationship(
                relationship_id=deterministic_relationship_id(
                    source_id,
                    target_id,
                    relation_type,
                    bidirectional=bidirectional,
                ),
                source_skill_id=source_id,
                target_skill_id=target_id,
                relation_type=relation_type,
                dependency_strength=dependency_strength_for_relation(relation_type),  # type: ignore[arg-type]
                confidence=confidence,
                status=rule.status or config.defaults.non_structural_status,
                reason=rule.reason,
                evidence=evidence,
                bidirectional=bidirectional,
                review_status=(
                    rule.review_status or config.defaults.non_structural_review_status
                ),
                created_by=config.metadata.created_by,
                version=config.metadata.version,
            ),
        )
    return relationships


def deterministic_relationship_id(
    source_skill_id: str,
    target_skill_id: str,
    relation_type: str,
    *,
    bidirectional: bool,
) -> str:
    if bidirectional:
        left, right = sorted([source_skill_id, target_skill_id])
        source_skill_id, target_skill_id = left, right
    raw_key = "\x1f".join([source_skill_id, target_skill_id, relation_type])
    return "rel_" + hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def relationship_key(relationship: SkillRelationship) -> tuple[str, str, str]:
    source_id = relationship.source_skill_id
    target_id = relationship.target_skill_id
    if relationship.bidirectional:
        source_id, target_id = sorted([source_id, target_id])
    return source_id, target_id, relationship.relation_type


def inverse_relationship_key(relationship: SkillRelationship) -> tuple[str, str, str]:
    return (
        relationship.target_skill_id,
        relationship.source_skill_id,
        relationship.relation_type,
    )


def _supporting_alignment_evidence(
    source_skill_id: str,
    target_skill_id: str,
    *,
    relation_type: str,
    profile_by_skill: dict[str, CanonicalSkillEvidenceProfile],
    alignment_by_skill: dict[str, SkillCEFRAlignment],
) -> list[RelationshipEvidence]:
    evidence: list[RelationshipEvidence] = []
    source_profile = profile_by_skill.get(source_skill_id)
    target_profile = profile_by_skill.get(target_skill_id)
    if source_profile and target_profile:
        source_level = source_profile.cefr_primary_level
        target_level = target_profile.cefr_primary_level
        if source_level and target_level:
            evidence.append(
                RelationshipEvidence(
                    evidence_type="cefr_alignment",
                    source="cefr_egp_alignment",
                    source_record_ids=[],
                    note=(
                        f"Source skill aligns to {source_level}; target skill "
                        f"aligns to {target_level}. CEFR levels support context "
                        "only and did not create this relationship."
                    ),
                ),
            )
        source_records = source_profile.egp_source_record_ids
        target_records = target_profile.egp_source_record_ids
        if source_records and target_records and relation_type in {
            "prerequisite_of",
            "recommended_before",
            "supports",
        }:
            evidence.append(
                RelationshipEvidence(
                    evidence_type="egp_progression",
                    source="english_grammar_profile_alignment",
                    source_record_ids=sorted(set(source_records + target_records)),
                    note=(
                        "Both skills have EGP-aligned evidence; this supports "
                        "review of the curated relationship but does not infer it."
                    ),
                ),
            )

    source_alignment = alignment_by_skill.get(source_skill_id)
    target_alignment = alignment_by_skill.get(target_skill_id)
    if source_alignment and target_alignment:
        descriptor_ids = sorted(
            set(source_alignment.grammatical_accuracy_descriptor_ids)
            | set(target_alignment.grammatical_accuracy_descriptor_ids),
        )
        if descriptor_ids:
            evidence.append(
                RelationshipEvidence(
                    evidence_type="cefr_alignment",
                    source="cefr_grammatical_accuracy_context",
                    source_record_ids=descriptor_ids,
                    note=(
                        "CEFR grammatical accuracy context is attached to one "
                        "or both aligned skills as proficiency context."
                    ),
                ),
            )
    return evidence


def _default_confidence(
    relation_type: str,
    config: GrammarRelationshipConfig,
) -> float:
    if relation_type == "prerequisite_of":
        return config.defaults.prerequisite_confidence
    if relation_type == "recommended_before":
        return config.defaults.recommended_confidence
    if relation_type == "supports":
        return config.defaults.supports_confidence
    if relation_type in {"related_to", "contrast_with", "commonly_confused_with"}:
        return config.defaults.semantic_confidence
    return config.defaults.structural_confidence


def _canonical_direction(
    source_skill_id: str,
    target_skill_id: str,
    relation_type: str,
) -> tuple[str, str]:
    if not is_bidirectional_relation(relation_type):
        return source_skill_id, target_skill_id
    return tuple(sorted([source_skill_id, target_skill_id]))  # type: ignore[return-value]


def _deduplicate_relationships(
    relationships: Iterable[SkillRelationship],
) -> list[SkillRelationship]:
    by_key: dict[tuple[str, str, str], SkillRelationship] = {}
    evidence_by_key: dict[tuple[str, str, str], list[RelationshipEvidence]] = defaultdict(list)
    for relationship in relationships:
        key = relationship_key(relationship)
        if key not in by_key:
            by_key[key] = relationship
        evidence_by_key[key].extend(relationship.evidence)

    deduplicated: list[SkillRelationship] = []
    for key, relationship in sorted(by_key.items()):
        merged_evidence = _deduplicate_evidence(evidence_by_key[key])
        deduplicated.append(relationship.model_copy(update={"evidence": merged_evidence}))
    return deduplicated


def _deduplicate_evidence(
    evidence: Sequence[RelationshipEvidence],
) -> list[RelationshipEvidence]:
    seen: set[tuple[str, str, tuple[str, ...], str | None]] = set()
    deduplicated: list[RelationshipEvidence] = []
    for item in evidence:
        key = (
            item.evidence_type,
            item.source,
            tuple(item.source_record_ids),
            item.note,
        )
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(item)
    return deduplicated

