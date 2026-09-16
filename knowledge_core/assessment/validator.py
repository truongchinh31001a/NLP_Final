from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Sequence

from knowledge_core.assessment.builder import AssessmentInputArtifacts
from knowledge_core.assessment.models import (
    VALID_ASSESSMENT_EVIDENCE_TYPES,
    VALID_CRITERION_TYPES,
    VALID_TASK_TYPES,
    AssessmentCriterion,
    AssessmentValidationIssue,
    AssessmentValidationResult,
    SkillAssessmentProfile,
)
from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILLS


def validate_assessment_dataset(
    *,
    criteria: Sequence[AssessmentCriterion],
    profiles: Sequence[SkillAssessmentProfile],
    artifacts: AssessmentInputArtifacts,
    canonical_skill_ids: Sequence[str] = CANONICAL_GRAMMAR_V1_SKILLS,
) -> AssessmentValidationResult:
    issues: list[AssessmentValidationIssue] = []
    canonical_set = set(canonical_skill_ids)
    criteria_by_skill: dict[str, list[AssessmentCriterion]] = defaultdict(list)
    criterion_ids = [criterion.criterion_id for criterion in criteria]
    criterion_id_counts = Counter(criterion_ids)
    duplicate_criteria: set[str] = set()
    invalid_references: set[str] = set()

    taxonomy_unchanged = tuple(canonical_skill_ids) == tuple(
        CANONICAL_GRAMMAR_V1_SKILLS,
    )
    if not taxonomy_unchanged:
        issues.append(
            AssessmentValidationIssue(
                severity="error",
                code="taxonomy_changed",
                message="Assessment canonical skill list differs from Grammar V1 taxonomy.",
            ),
        )

    for criterion_id, count in criterion_id_counts.items():
        if count < 2:
            continue
        duplicate_criteria.add(criterion_id)
        issues.append(
            AssessmentValidationIssue(
                severity="error",
                code="duplicate_criterion_id",
                message=f"criterion_id {criterion_id!r} appears {count} times.",
                criterion_id=criterion_id,
            ),
        )

    known_cefr_ids = {
        descriptor.source_record_id
        for descriptor in artifacts.cefr_descriptors
    }
    grammatical_accuracy_by_id = {
        descriptor.source_record_id: descriptor
        for descriptor in artifacts.cefr_descriptors
        if descriptor.scale_name == "grammatical_accuracy"
    }
    known_egp_ids = {
        record.source_record_id
        for record in artifacts.egp_records
        if record.source_record_id
    }
    known_relationship_ids = {
        relationship.relationship_id
        for relationship in artifacts.relationships
    }
    skills_with_cefr_alignment = {
        profile.canonical_skill_id
        for profile in artifacts.skill_profiles
        if profile.cefr_primary_level
    } | {
        alignment.canonical_skill_id
        for alignment in artifacts.skill_alignments
        if alignment.inferred_primary_level
    }

    semantic_keys: dict[tuple[str, str, str], list[AssessmentCriterion]] = defaultdict(list)
    for criterion in criteria:
        criteria_by_skill[criterion.canonical_skill_id].append(criterion)
        if criterion.canonical_skill_id not in canonical_set:
            invalid_references.add(criterion.canonical_skill_id)
            issues.append(
                _criterion_issue(
                    criterion,
                    code="unknown_skill_id",
                    message=(
                        "Assessment criterion references an unknown canonical "
                        f"skill: {criterion.canonical_skill_id}"
                    ),
                    reference_id=criterion.canonical_skill_id,
                ),
            )
        if criterion.criterion_type not in VALID_CRITERION_TYPES:
            issues.append(
                _criterion_issue(
                    criterion,
                    code="invalid_criterion_type",
                    message=f"Invalid criterion type: {criterion.criterion_type}",
                ),
            )
        for task_type in criterion.acceptable_task_types:
            if task_type not in VALID_TASK_TYPES:
                issues.append(
                    _criterion_issue(
                        criterion,
                        code="invalid_task_type",
                        message=f"Invalid task type: {task_type}",
                    ),
                )
        if criterion.confidence < 0.0 or criterion.confidence > 1.0:
            issues.append(
                _criterion_issue(
                    criterion,
                    code="invalid_confidence",
                    message=f"Confidence must be in [0,1]: {criterion.confidence}",
                ),
            )
        if (
            criterion.recommended_threshold is not None
            and (
                criterion.recommended_threshold < 0.0
                or criterion.recommended_threshold > 1.0
            )
        ):
            issues.append(
                _criterion_issue(
                    criterion,
                    code="invalid_recommended_threshold",
                    message=(
                        "recommended_threshold must be in [0,1]: "
                        f"{criterion.recommended_threshold}"
                    ),
                ),
            )
        if (
            criterion.recommended_min_items is not None
            and criterion.recommended_min_items <= 0
        ):
            issues.append(
                _criterion_issue(
                    criterion,
                    code="invalid_recommended_min_items",
                    message=(
                        "recommended_min_items must be greater than 0: "
                        f"{criterion.recommended_min_items}"
                    ),
                ),
            )
        if (
            criterion.recommended_threshold is not None
            and criterion.threshold_source != "curated_v1_default"
        ):
            issues.append(
                _criterion_issue(
                    criterion,
                    code="invalid_threshold_source",
                    message=(
                        "recommended thresholds must be marked as "
                        "curated_v1_default in V1."
                    ),
                ),
            )
        if not criterion.provenance:
            issues.append(
                _criterion_issue(
                    criterion,
                    code="missing_provenance",
                    message="Every assessment criterion must include provenance.",
                ),
            )
        if not criterion.evidence_requirements:
            issues.append(
                _criterion_issue(
                    criterion,
                    code="missing_evidence_requirements",
                    message="Every criterion must include evidence requirements.",
                ),
            )
        if not criterion.acceptable_task_types:
            issues.append(
                _criterion_issue(
                    criterion,
                    code="missing_task_types",
                    message="Every criterion must include acceptable task types.",
                ),
            )
        if not criterion.failure_signals:
            issues.append(
                _criterion_issue(
                    criterion,
                    code="missing_failure_signals",
                    message="Every criterion must include failure signals.",
                ),
            )

        for descriptor_id in criterion.cefr_context_descriptor_ids:
            if descriptor_id not in known_cefr_ids:
                invalid_references.add(descriptor_id)
                issues.append(
                    _criterion_issue(
                        criterion,
                        code="unknown_cefr_descriptor_id",
                        message=(
                            "Criterion references an unknown CEFR descriptor: "
                            f"{descriptor_id}"
                        ),
                        reference_id=descriptor_id,
                    ),
                )
                continue
            descriptor = grammatical_accuracy_by_id.get(descriptor_id)
            if descriptor is None:
                issues.append(
                    _criterion_issue(
                        criterion,
                        code="non_grammatical_accuracy_cefr_context",
                        message=(
                            "CEFR context descriptor must come from the "
                            f"grammatical_accuracy scale: {descriptor_id}"
                        ),
                        reference_id=descriptor_id,
                    ),
                )
            elif criterion.cefr_level and descriptor.cefr_level != criterion.cefr_level:
                issues.append(
                    _criterion_issue(
                        criterion,
                        code="cefr_context_level_mismatch",
                        message=(
                            f"CEFR context descriptor {descriptor_id} is "
                            f"{descriptor.cefr_level}, expected "
                            f"{criterion.cefr_level}."
                        ),
                        reference_id=descriptor_id,
                    ),
                )

        if (
            criterion.canonical_skill_id in skills_with_cefr_alignment
            and criterion.cefr_level
            and not criterion.cefr_context_descriptor_ids
        ):
            issues.append(
                _criterion_issue(
                    criterion,
                    severity="warning",
                    code="missing_cefr_grammatical_accuracy_context",
                    message=(
                        "Skill has CEFR alignment but no grammatical accuracy "
                        "descriptor context was attached."
                    ),
                ),
            )

        for evidence in criterion.provenance:
            if evidence.evidence_type not in VALID_ASSESSMENT_EVIDENCE_TYPES:
                issues.append(
                    _criterion_issue(
                        criterion,
                        code="invalid_provenance_type",
                        message=f"Invalid provenance type: {evidence.evidence_type}",
                    ),
                )
            if _claims_empirical_misconception_evidence(evidence.evidence_type, evidence.source):
                issues.append(
                    _criterion_issue(
                        criterion,
                        code="unsupported_empirical_misconception_claim",
                        message=(
                            "Assessment Criteria V1 must not claim empirical "
                            "misconception evidence."
                        ),
                    ),
                )
            if evidence.evidence_type == "egp_evidence":
                for source_record_id in evidence.source_record_ids:
                    if source_record_id not in known_egp_ids:
                        invalid_references.add(source_record_id)
                        issues.append(
                            _criterion_issue(
                                criterion,
                                code="unknown_egp_source_record_id",
                                message=(
                                    "Criterion references an unknown EGP source "
                                    f"record: {source_record_id}"
                                ),
                                reference_id=source_record_id,
                            ),
                        )
            if evidence.evidence_type == "relationship_context":
                for relationship_id in evidence.source_record_ids:
                    if relationship_id not in known_relationship_ids:
                        invalid_references.add(relationship_id)
                        issues.append(
                            _criterion_issue(
                                criterion,
                                code="unknown_relationship_id",
                                message=(
                                    "Criterion references an unknown relationship: "
                                    f"{relationship_id}"
                                ),
                                reference_id=relationship_id,
                            ),
                        )

        semantic_key = (
            criterion.canonical_skill_id,
            str(criterion.criterion_type),
            _normalize_semantics(criterion.observable_behavior),
        )
        semantic_keys[semantic_key].append(criterion)

    for semantic_key, grouped in semantic_keys.items():
        if len(grouped) < 2:
            continue
        duplicate_key = "|".join(semantic_key)
        duplicate_criteria.add(duplicate_key)
        for criterion in grouped:
            issues.append(
                _criterion_issue(
                    criterion,
                    code="duplicate_criterion_semantics",
                    message="Duplicate criterion semantics for the same skill.",
                ),
            )

    missing_skill_ids = sorted(
        skill_id
        for skill_id in canonical_skill_ids
        if skill_id not in criteria_by_skill
    )
    for skill_id in missing_skill_ids:
        issues.append(
            AssessmentValidationIssue(
                severity="error",
                code="missing_skill_criteria",
                message=f"Canonical skill has no assessment criteria: {skill_id}",
                canonical_skill_id=skill_id,
            ),
        )

    profile_by_skill = {profile.canonical_skill_id: profile for profile in profiles}
    for skill_id in canonical_skill_ids:
        profile = profile_by_skill.get(skill_id)
        if profile is None:
            issues.append(
                AssessmentValidationIssue(
                    severity="error",
                    code="missing_assessment_profile",
                    message=f"Canonical skill has no assessment profile: {skill_id}",
                    canonical_skill_id=skill_id,
                ),
            )
            continue
        for criterion_id in profile.criterion_ids:
            if criterion_id not in criterion_id_counts:
                invalid_references.add(criterion_id)
                issues.append(
                    AssessmentValidationIssue(
                        severity="error",
                        code="profile_unknown_criterion_id",
                        message=(
                            "Assessment profile references an unknown criterion: "
                            f"{criterion_id}"
                        ),
                        canonical_skill_id=skill_id,
                        reference_id=criterion_id,
                    ),
                )
        for task_type in profile.recommended_task_types:
            if task_type not in VALID_TASK_TYPES:
                issues.append(
                    AssessmentValidationIssue(
                        severity="error",
                        code="profile_invalid_task_type",
                        message=f"Invalid profile task type: {task_type}",
                        canonical_skill_id=skill_id,
                    ),
                )

    extra_profiles = sorted(set(profile_by_skill) - canonical_set)
    for skill_id in extra_profiles:
        invalid_references.add(skill_id)
        issues.append(
            AssessmentValidationIssue(
                severity="error",
                code="profile_unknown_skill_id",
                message=f"Assessment profile references unknown skill: {skill_id}",
                canonical_skill_id=skill_id,
                reference_id=skill_id,
            ),
        )

    return AssessmentValidationResult(
        total_canonical_skills=len(canonical_skill_ids),
        total_criteria=len(criteria),
        total_profiles=len(profiles),
        missing_skill_ids=missing_skill_ids,
        invalid_references=sorted(invalid_references),
        duplicate_criteria=sorted(duplicate_criteria),
        taxonomy_unchanged=taxonomy_unchanged,
        issues=issues,
    )


def _criterion_issue(
    criterion: AssessmentCriterion,
    *,
    code: str,
    message: str,
    severity: str = "error",
    reference_id: str | None = None,
) -> AssessmentValidationIssue:
    return AssessmentValidationIssue(
        severity=severity,  # type: ignore[arg-type]
        code=code,
        message=message,
        criterion_id=criterion.criterion_id,
        canonical_skill_id=criterion.canonical_skill_id,
        reference_id=reference_id,
    )


def _claims_empirical_misconception_evidence(
    evidence_type: str,
    source: str,
) -> bool:
    haystack = f"{evidence_type} {source}".casefold()
    return any(
        token in haystack
        for token in [
            "empirical_misconception",
            "misconception_corpus",
            "error_frequency",
            "efcamdat",
            "clc_fce",
        ]
    )


def _normalize_semantics(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
