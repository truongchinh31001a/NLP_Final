from __future__ import annotations

from collections import defaultdict
from typing import Sequence

from knowledge_core.alignment.cefr_alignment import KnowledgeAlignmentDataset
from knowledge_core.alignment.models import (
    AlignmentValidationIssue,
    AlignmentValidationResult,
    CanonicalSkillEvidenceProfile,
    SkillCEFRAlignment,
    SkillSourceEvidence,
)
from knowledge_core.mapping.egp.models import EGPCanonicalMapping
from knowledge_core.sources.cefr.models import (
    CEFRDescriptorRecord,
    CEFRLearningObjectiveCandidate,
    VALID_CEFR_LEVELS,
)
from knowledge_core.sources.egp.models import RawEGPRecord


def validate_alignment(
    *,
    canonical_skills: Sequence[str],
    dataset: KnowledgeAlignmentDataset,
    egp_records: Sequence[RawEGPRecord],
    egp_mappings: Sequence[EGPCanonicalMapping],
    cefr_descriptors: Sequence[CEFRDescriptorRecord],
    cefr_objectives: Sequence[CEFRLearningObjectiveCandidate],
) -> AlignmentValidationResult:
    canonical_set = set(canonical_skills)
    profiles = dataset.profiles
    alignments = dataset.alignments
    source_evidence = dataset.source_evidence
    issues: list[AlignmentValidationIssue] = []

    issues.extend(_validate_complete_skill_set(canonical_set, profiles, alignments))
    issues.extend(_validate_source_evidence(
        canonical_set,
        source_evidence,
        egp_records=egp_records,
        cefr_descriptors=cefr_descriptors,
        cefr_objectives=cefr_objectives,
    ))
    issues.extend(_validate_profiles(
        canonical_set,
        profiles,
        source_evidence=source_evidence,
        egp_records=egp_records,
        cefr_descriptors=cefr_descriptors,
        cefr_objectives=cefr_objectives,
    ))
    issues.extend(_validate_alignments(
        canonical_set,
        alignments,
        cefr_descriptors=cefr_descriptors,
        cefr_objectives=cefr_objectives,
    ))
    issues.extend(_validate_ambiguous_mappings_do_not_establish_levels(
        profiles,
        egp_mappings,
    ))

    return AlignmentValidationResult(
        total_canonical_skills=len(canonical_skills),
        total_profiles=len(profiles),
        total_alignments=len(alignments),
        total_source_evidence=len(source_evidence),
        issues=issues,
    )


def _validate_complete_skill_set(
    canonical_set: set[str],
    profiles: Sequence[CanonicalSkillEvidenceProfile],
    alignments: Sequence[SkillCEFRAlignment],
) -> list[AlignmentValidationIssue]:
    issues: list[AlignmentValidationIssue] = []
    profile_ids = [profile.canonical_skill_id for profile in profiles]
    alignment_ids = [alignment.canonical_skill_id for alignment in alignments]
    profile_set = set(profile_ids)
    alignment_set = set(alignment_ids)
    for skill_id in sorted(canonical_set - profile_set):
        issues.append(
            AlignmentValidationIssue(
                severity="error",
                code="missing_skill_profile",
                message="Canonical skill is missing from grammar_skill_evidence output",
                canonical_skill_id=skill_id,
            ),
        )
    for skill_id in sorted(profile_set - canonical_set):
        issues.append(
            AlignmentValidationIssue(
                severity="error",
                code="unknown_profile_skill",
                message="Profile references a skill outside Grammar V1",
                canonical_skill_id=skill_id,
            ),
        )
    for skill_id in sorted(canonical_set - alignment_set):
        issues.append(
            AlignmentValidationIssue(
                severity="error",
                code="missing_skill_alignment",
                message="Canonical skill is missing from cefr_egp_alignment output",
                canonical_skill_id=skill_id,
            ),
        )
    for skill_id in sorted(alignment_set - canonical_set):
        issues.append(
            AlignmentValidationIssue(
                severity="error",
                code="unknown_alignment_skill",
                message="Alignment references a skill outside Grammar V1",
                canonical_skill_id=skill_id,
            ),
        )
    issues.extend(_duplicate_id_issues(profile_ids, "duplicate_skill_profile"))
    issues.extend(_duplicate_id_issues(alignment_ids, "duplicate_skill_alignment"))
    return issues


def _validate_source_evidence(
    canonical_set: set[str],
    source_evidence: Sequence[SkillSourceEvidence],
    *,
    egp_records: Sequence[RawEGPRecord],
    cefr_descriptors: Sequence[CEFRDescriptorRecord],
    cefr_objectives: Sequence[CEFRLearningObjectiveCandidate],
) -> list[AlignmentValidationIssue]:
    issues: list[AlignmentValidationIssue] = []
    egp_source_ids = {
        record.source_record_id for record in egp_records if record.source_record_id
    }
    cefr_descriptor_ids = {record.source_record_id for record in cefr_descriptors}
    objective_ids = {objective.objective_id for objective in cefr_objectives}
    evidence_ids: dict[str, list[SkillSourceEvidence]] = defaultdict(list)

    for evidence in source_evidence:
        evidence_ids[evidence.evidence_id].append(evidence)
        context = {
            "canonical_skill_id": evidence.canonical_skill_id,
            "source_record_id": evidence.source_record_id,
            "cefr_level": evidence.source_cefr_level,
            "evidence_id": evidence.evidence_id,
        }
        if evidence.canonical_skill_id not in canonical_set:
            issues.append(
                AlignmentValidationIssue(
                    severity="error",
                    code="unknown_evidence_skill",
                    message="Source evidence references a skill outside Grammar V1",
                    **context,
                ),
            )
        if evidence.source_cefr_level and evidence.source_cefr_level not in VALID_CEFR_LEVELS:
            issues.append(
                AlignmentValidationIssue(
                    severity="error",
                    code="invalid_evidence_cefr_level",
                    message=f"Invalid evidence CEFR level: {evidence.source_cefr_level}",
                    **context,
                ),
            )
        if evidence.evidence_type == "egp_direct":
            if evidence.source_record_id not in egp_source_ids:
                issues.append(
                    AlignmentValidationIssue(
                        severity="error",
                        code="missing_egp_source_record",
                        message="EGP evidence references a missing normalized EGP source record",
                        **context,
                    ),
                )
        elif evidence.evidence_type in {
            "cefr_learning_objective",
            "cefr_grammatical_accuracy",
            "cefr_proficiency",
        }:
            if evidence.source_record_id not in cefr_descriptor_ids:
                issues.append(
                    AlignmentValidationIssue(
                        severity="error",
                        code="missing_cefr_descriptor_record",
                        message="CEFR evidence references a missing descriptor record",
                        **context,
                    ),
                )
            objective_id = evidence.provenance.get("objective_id")
            if objective_id and objective_id not in objective_ids:
                issues.append(
                    AlignmentValidationIssue(
                        severity="error",
                        code="missing_cefr_objective",
                        message="CEFR evidence references a missing objective candidate",
                        objective_id=objective_id,
                        **context,
                    ),
                )

    for evidence_id, grouped in evidence_ids.items():
        if len(grouped) < 2:
            continue
        for evidence in grouped:
            issues.append(
                AlignmentValidationIssue(
                    severity="error",
                    code="duplicate_evidence_id",
                    message=f"evidence_id {evidence_id!r} appears {len(grouped)} times",
                    canonical_skill_id=evidence.canonical_skill_id,
                    source_record_id=evidence.source_record_id,
                    evidence_id=evidence_id,
                ),
            )
    return issues


def _validate_profiles(
    canonical_set: set[str],
    profiles: Sequence[CanonicalSkillEvidenceProfile],
    *,
    source_evidence: Sequence[SkillSourceEvidence],
    egp_records: Sequence[RawEGPRecord],
    cefr_descriptors: Sequence[CEFRDescriptorRecord],
    cefr_objectives: Sequence[CEFRLearningObjectiveCandidate],
) -> list[AlignmentValidationIssue]:
    issues: list[AlignmentValidationIssue] = []
    egp_source_ids = {
        record.source_record_id for record in egp_records if record.source_record_id
    }
    cefr_descriptors_by_id = {
        record.source_record_id: record for record in cefr_descriptors
    }
    objective_ids = {objective.objective_id for objective in cefr_objectives}
    evidence_by_skill: dict[str, list[SkillSourceEvidence]] = defaultdict(list)
    for evidence in source_evidence:
        evidence_by_skill[evidence.canonical_skill_id].append(evidence)

    for profile in profiles:
        context = {"canonical_skill_id": profile.canonical_skill_id}
        if profile.canonical_skill_id not in canonical_set:
            continue
        issues.extend(_validate_profile_levels(profile))
        for source_record_id in profile.egp_source_record_ids:
            if source_record_id not in egp_source_ids:
                issues.append(
                    AlignmentValidationIssue(
                        severity="error",
                        code="profile_missing_egp_source_record",
                        message="Profile references a missing normalized EGP source record",
                        source_record_id=source_record_id,
                        **context,
                    ),
                )
        for objective_id in profile.direct_objective_ids + profile.contextual_objective_ids:
            if objective_id not in objective_ids:
                issues.append(
                    AlignmentValidationIssue(
                        severity="error",
                        code="profile_missing_cefr_objective",
                        message="Profile references a missing CEFR objective candidate",
                        objective_id=objective_id,
                        **context,
                    ),
                )
        if profile.evidence_status == "curated_only":
            if (
                profile.egp_evidence_count
                or profile.egp_source_record_ids
                or profile.direct_objective_ids
                or profile.contextual_objective_ids
                or profile.grammatical_accuracy_context
                or evidence_by_skill.get(profile.canonical_skill_id)
            ):
                issues.append(
                    AlignmentValidationIssue(
                        severity="error",
                        code="curated_only_has_source_evidence",
                        message="curated_only profile must not contain source evidence",
                        **context,
                    ),
                )

        for descriptor_id in profile.grammatical_accuracy_context:
            descriptor = cefr_descriptors_by_id.get(descriptor_id)
            if descriptor is None:
                issues.append(
                    AlignmentValidationIssue(
                        severity="error",
                        code="missing_grammatical_accuracy_descriptor",
                        message="Profile references a missing grammatical accuracy descriptor",
                        source_record_id=descriptor_id,
                        **context,
                    ),
                )
                continue
            if descriptor.scale_name != "grammatical_accuracy":
                issues.append(
                    AlignmentValidationIssue(
                        severity="error",
                        code="non_grammatical_accuracy_descriptor_attached",
                        message="Grammatical accuracy context must use grammatical_accuracy records",
                        source_record_id=descriptor_id,
                        **context,
                    ),
                )
            if descriptor.cefr_level != profile.cefr_primary_level:
                issues.append(
                    AlignmentValidationIssue(
                        severity="error",
                        code="grammatical_accuracy_level_mismatch",
                        message="Attached grammatical accuracy descriptor does not match primary CEFR level",
                        source_record_id=descriptor_id,
                        cefr_level=descriptor.cefr_level,
                        **context,
                    ),
                )
    return issues


def _validate_alignments(
    canonical_set: set[str],
    alignments: Sequence[SkillCEFRAlignment],
    *,
    cefr_descriptors: Sequence[CEFRDescriptorRecord],
    cefr_objectives: Sequence[CEFRLearningObjectiveCandidate],
) -> list[AlignmentValidationIssue]:
    issues: list[AlignmentValidationIssue] = []
    descriptor_ids = {record.source_record_id for record in cefr_descriptors}
    objective_ids = {objective.objective_id for objective in cefr_objectives}
    for alignment in alignments:
        context = {"canonical_skill_id": alignment.canonical_skill_id}
        if alignment.canonical_skill_id not in canonical_set:
            continue
        for level in alignment.egp_levels:
            if level not in VALID_CEFR_LEVELS:
                issues.append(
                    AlignmentValidationIssue(
                        severity="error",
                        code="invalid_alignment_egp_level",
                        message=f"Invalid alignment EGP level: {level}",
                        cefr_level=level,
                        **context,
                    ),
                )
        for level in [alignment.inferred_min_level, alignment.inferred_primary_level]:
            if level and level not in VALID_CEFR_LEVELS:
                issues.append(
                    AlignmentValidationIssue(
                        severity="error",
                        code="invalid_alignment_cefr_level",
                        message=f"Invalid alignment CEFR level: {level}",
                        cefr_level=level,
                        **context,
                    ),
                )
        for descriptor_id in alignment.cefr_descriptor_ids + alignment.grammatical_accuracy_descriptor_ids:
            if descriptor_id not in descriptor_ids:
                issues.append(
                    AlignmentValidationIssue(
                        severity="error",
                        code="alignment_missing_cefr_descriptor",
                        message="Alignment references a missing CEFR descriptor",
                        source_record_id=descriptor_id,
                        **context,
                    ),
                )
        for objective_id in alignment.objective_ids:
            if objective_id not in objective_ids:
                issues.append(
                    AlignmentValidationIssue(
                        severity="error",
                        code="alignment_missing_cefr_objective",
                        message="Alignment references a missing CEFR objective",
                        objective_id=objective_id,
                        **context,
                    ),
                )
    return issues


def _validate_ambiguous_mappings_do_not_establish_levels(
    profiles: Sequence[CanonicalSkillEvidenceProfile],
    egp_mappings: Sequence[EGPCanonicalMapping],
) -> list[AlignmentValidationIssue]:
    ambiguous_skill_ids = {
        skill_id
        for mapping in egp_mappings
        if mapping.status == "ambiguous"
        for skill_id in mapping.secondary_candidates
    }
    issues: list[AlignmentValidationIssue] = []
    for profile in profiles:
        if profile.canonical_skill_id not in ambiguous_skill_ids:
            continue
        if profile.egp_evidence_count == 0 and (
            profile.cefr_min_level or profile.cefr_primary_level
        ):
            issues.append(
                AlignmentValidationIssue(
                    severity="error",
                    code="ambiguous_mapping_established_level",
                    message="Ambiguous EGP mapping must not establish CEFR levels automatically",
                    canonical_skill_id=profile.canonical_skill_id,
                    cefr_level=profile.cefr_primary_level,
                ),
            )
    return issues


def _validate_profile_levels(
    profile: CanonicalSkillEvidenceProfile,
) -> list[AlignmentValidationIssue]:
    issues: list[AlignmentValidationIssue] = []
    for level in profile.egp_levels:
        if level not in VALID_CEFR_LEVELS:
            issues.append(
                AlignmentValidationIssue(
                    severity="error",
                    code="invalid_profile_egp_level",
                    message=f"Invalid profile EGP level: {level}",
                    canonical_skill_id=profile.canonical_skill_id,
                    cefr_level=level,
                ),
            )
    for level in [profile.cefr_min_level, profile.cefr_primary_level]:
        if level and level not in VALID_CEFR_LEVELS:
            issues.append(
                AlignmentValidationIssue(
                    severity="error",
                    code="invalid_profile_cefr_level",
                    message=f"Invalid profile CEFR level: {level}",
                    canonical_skill_id=profile.canonical_skill_id,
                    cefr_level=level,
                ),
            )
    return issues


def _duplicate_id_issues(
    ids: Sequence[str],
    code: str,
) -> list[AlignmentValidationIssue]:
    issues: list[AlignmentValidationIssue] = []
    grouped: dict[str, int] = defaultdict(int)
    for item in ids:
        grouped[item] += 1
    for item, count in grouped.items():
        if count > 1:
            issues.append(
                AlignmentValidationIssue(
                    severity="error",
                    code=code,
                    message=f"{item!r} appears {count} times",
                    canonical_skill_id=item,
                ),
            )
    return issues

