from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from knowledge_core.assessment.models import AssessmentCriterion, SkillAssessmentProfile
from knowledge_core.enrichment.models import (
    KNOWLEDGE_ENRICHMENT_SCHEMA_VERSION,
    DiagnosticEvidenceTag,
    EmpiricalFailureSignal,
    EnrichedAssessmentCriterion,
    EnrichedSkillProfile,
    SkillMisconceptionLink,
    make_failure_signal_id,
    make_skill_misconception_link_id,
)
from knowledge_core.enrichment.paths import (
    ASSESSMENT_CRITERIA_ENRICHED_JSONL,
    DEFAULT_ACCEPTED_MISCONCEPTIONS_PATH,
    DEFAULT_ASSESSMENT_CRITERIA_PATH,
    DEFAULT_ASSESSMENT_PROFILES_PATH,
    DEFAULT_CANDIDATE_MISCONCEPTIONS_PATH,
    DEFAULT_CURATED_DIR,
    DEFAULT_REPORTS_DIR,
    DEFAULT_REVIEW_DIR,
    DEFAULT_REVIEW_STATUS_REPORTS,
    KNOWLEDGE_ENRICHMENT_REPORT_JSON,
    KNOWLEDGE_ENRICHMENT_REVIEW_CSV,
    SKILL_MISCONCEPTION_LINKS_JSONL,
    SKILL_PROFILES_ENRICHED_JSONL,
)
from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILLS
from knowledge_core.misconceptions.models import MisconceptionCandidate
from knowledge_core.normalization.error_taxonomy.ids import make_review_row_id
from knowledge_core.normalization.error_taxonomy.policy import (
    find_forbidden_free_text_keys,
)
from knowledge_core.relationships.taxonomy import build_grammar_taxonomy


@dataclass(slots=True)
class KnowledgeEnrichmentResult:
    enriched_criteria: list[EnrichedAssessmentCriterion]
    enriched_profiles: list[EnrichedSkillProfile]
    skill_misconception_links: list[SkillMisconceptionLink]
    report: dict[str, Any]
    output_paths: dict[str, Path]
    report_path: Path | None


def run_knowledge_enrichment(
    *,
    assessment_criteria_path: str | Path = DEFAULT_ASSESSMENT_CRITERIA_PATH,
    assessment_profiles_path: str | Path = DEFAULT_ASSESSMENT_PROFILES_PATH,
    accepted_misconceptions_path: str | Path = DEFAULT_ACCEPTED_MISCONCEPTIONS_PATH,
    candidate_misconceptions_path: str | Path = DEFAULT_CANDIDATE_MISCONCEPTIONS_PATH,
    review_status_reports: dict[str, str | Path] | None = None,
    curated_dir: str | Path = DEFAULT_CURATED_DIR,
    review_dir: str | Path = DEFAULT_REVIEW_DIR,
    reports_dir: str | Path = DEFAULT_REPORTS_DIR,
    canonical_skill_ids: Sequence[str] = CANONICAL_GRAMMAR_V1_SKILLS,
    dry_run: bool = False,
) -> KnowledgeEnrichmentResult:
    issues: list[dict[str, Any]] = []
    criteria_path = Path(assessment_criteria_path)
    profiles_path = Path(assessment_profiles_path)
    accepted_path = Path(accepted_misconceptions_path)
    candidate_path = Path(candidate_misconceptions_path)
    report_paths = {
        key: Path(path)
        for key, path in (review_status_reports or DEFAULT_REVIEW_STATUS_REPORTS).items()
    }
    output_paths = _default_output_paths(curated_dir=curated_dir, review_dir=review_dir)

    criteria = _load_jsonl_models(criteria_path, AssessmentCriterion, issues)
    profiles = _load_jsonl_models(profiles_path, SkillAssessmentProfile, issues)
    accepted = _load_misconceptions(
        accepted_path,
        issues,
        accepted_file=True,
    )
    candidates = _load_misconceptions(
        candidate_path,
        issues,
        accepted_file=False,
    )

    accepted_by_skill = _by_skill(accepted)
    pending_by_skill = _pending_candidates_by_skill(candidates)
    links = _skill_misconception_links(accepted)
    enriched_criteria = _enrich_criteria(
        criteria=criteria,
        accepted_by_skill=accepted_by_skill,
        pending_by_skill=pending_by_skill,
    )
    enriched_profiles = _enrich_profiles(
        profiles=profiles,
        accepted_by_skill=accepted_by_skill,
        pending_by_skill=pending_by_skill,
    )
    review_consolidation = _review_status_consolidation(report_paths, issues)
    validation = _validate_enrichment(
        criteria=criteria,
        profiles=profiles,
        enriched_criteria=enriched_criteria,
        enriched_profiles=enriched_profiles,
        accepted=accepted,
        candidates=candidates,
        links=links,
        issues=issues,
        canonical_skill_ids=canonical_skill_ids,
    )
    report = _build_report(
        criteria=criteria,
        profiles=profiles,
        enriched_criteria=enriched_criteria,
        enriched_profiles=enriched_profiles,
        accepted=accepted,
        candidates=candidates,
        links=links,
        validation=validation,
        issues=issues,
        review_consolidation=review_consolidation,
        inputs={
            "assessment_criteria": criteria_path,
            "assessment_profiles": profiles_path,
            "accepted_misconceptions": accepted_path,
            "candidate_misconceptions": candidate_path,
            **{f"{key}_report": path for key, path in report_paths.items()},
        },
        output_paths=output_paths if not dry_run else {},
        canonical_skill_ids=canonical_skill_ids,
    )

    report_path = None
    if not dry_run:
        _write_jsonl(enriched_criteria, output_paths["assessment_criteria_enriched_jsonl"])
        _write_jsonl(enriched_profiles, output_paths["skill_profiles_enriched_jsonl"])
        _write_jsonl(links, output_paths["skill_misconception_links_jsonl"])
        _write_review_csv(
            accepted=accepted,
            candidates=candidates,
            destination=output_paths["review_csv"],
        )
        report_path = Path(reports_dir) / KNOWLEDGE_ENRICHMENT_REPORT_JSON
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return KnowledgeEnrichmentResult(
        enriched_criteria=enriched_criteria,
        enriched_profiles=enriched_profiles,
        skill_misconception_links=links,
        report=report,
        output_paths=output_paths if not dry_run else {},
        report_path=report_path,
    )


def _load_jsonl_models(
    path: Path,
    model_type,
    issues: list[dict[str, Any]],
) -> list:
    records = []
    if not path.exists():
        issues.append(
            {
                "severity": "error",
                "code": "missing_input",
                "message": f"Input file not found: {path}",
            },
        )
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(model_type.model_validate(json.loads(line)))
            except Exception as exc:  # noqa: BLE001 - retain validation context.
                issues.append(
                    {
                        "severity": "error",
                        "code": "invalid_jsonl_record",
                        "message": f"{path} line {line_number}: {exc}",
                    },
                )
    return records


def _load_misconceptions(
    path: Path,
    issues: list[dict[str, Any]],
    *,
    accepted_file: bool,
) -> list[MisconceptionCandidate]:
    records = _load_jsonl_models(path, MisconceptionCandidate, issues)
    valid: list[MisconceptionCandidate] = []
    for record in records:
        if accepted_file and (
            record.status != "accepted" or record.review_status != "approved"
        ):
            issues.append(
                {
                    "severity": "error",
                    "code": "unapproved_misconception_in_accepted_file",
                    "message": (
                        "Accepted misconception artifacts may contain only records "
                        "with status='accepted' and review_status='approved'."
                    ),
                    "misconception_id": record.misconception_id,
                },
            )
            continue
        valid.append(record)
    return valid


def _by_skill(
    misconceptions: Sequence[MisconceptionCandidate],
) -> dict[str, list[MisconceptionCandidate]]:
    by_skill: dict[str, list[MisconceptionCandidate]] = defaultdict(list)
    for misconception in misconceptions:
        by_skill[misconception.canonical_skill_id].append(misconception)
    return {
        skill_id: sorted(items, key=lambda item: item.misconception_id)
        for skill_id, items in by_skill.items()
    }


def _pending_candidates_by_skill(
    candidates: Sequence[MisconceptionCandidate],
) -> dict[str, list[MisconceptionCandidate]]:
    pending = [
        candidate
        for candidate in candidates
        if candidate.status == "candidate" and candidate.review_status != "approved"
    ]
    return _by_skill(pending)


def _skill_misconception_links(
    accepted: Sequence[MisconceptionCandidate],
) -> list[SkillMisconceptionLink]:
    links: list[SkillMisconceptionLink] = []
    for misconception in accepted:
        links.append(
            SkillMisconceptionLink(
                link_id=make_skill_misconception_link_id(
                    canonical_skill_id=misconception.canonical_skill_id,
                    misconception_id=misconception.misconception_id,
                ),
                misconception_id=misconception.misconception_id,
                canonical_skill_id=misconception.canonical_skill_id,
                source_evidence_count=misconception.source_evidence_count,
                source_distribution=misconception.source_distribution,
                proficiency_distribution=misconception.proficiency_distribution,
                confidence=misconception.confidence,
                review_status="approved",
                reason=(
                    "Accepted human-reviewed misconception linked to its canonical "
                    "Grammar V1 skill for empirical diagnostic evidence."
                ),
            ),
        )
    return sorted(links, key=lambda link: link.link_id)


def _enrich_criteria(
    *,
    criteria: Sequence[AssessmentCriterion],
    accepted_by_skill: dict[str, list[MisconceptionCandidate]],
    pending_by_skill: dict[str, list[MisconceptionCandidate]],
) -> list[EnrichedAssessmentCriterion]:
    enriched: list[EnrichedAssessmentCriterion] = []
    for criterion in criteria:
        accepted = accepted_by_skill.get(criterion.canonical_skill_id, [])
        pending = pending_by_skill.get(criterion.canonical_skill_id, [])
        empirical_signals = [
            _failure_signal(criterion, misconception)
            for misconception in accepted
        ]
        tags = [
            DiagnosticEvidenceTag(
                evidence_type="curated_assessment_rule",
                evidence_status="curated",
                source="grammar_assessment_criteria",
                source_record_ids=[criterion.criterion_id],
                note=(
                    "Original assessment failure signals are curated diagnostic "
                    "guidance, not corpus-backed evidence."
                ),
            ),
        ]
        tags.extend(
            DiagnosticEvidenceTag(
                evidence_type="accepted_misconception",
                evidence_status="accepted_empirical",
                source="accepted_misconceptions",
                source_record_ids=[misconception.misconception_id],
                note="Human-approved corpus-backed misconception evidence.",
            )
            for misconception in accepted
        )
        tags.extend(
            DiagnosticEvidenceTag(
                evidence_type="pending_misconception_candidate",
                evidence_status="pending_review",
                source="candidate_misconceptions",
                source_record_ids=[misconception.misconception_id],
                note="Candidate evidence is listed for review and is not applied.",
            )
            for misconception in pending
        )
        enriched.append(
            EnrichedAssessmentCriterion(
                criterion=criterion,
                curated_failure_signals=list(criterion.failure_signals),
                empirical_failure_signals=empirical_signals,
                diagnostic_evidence_tags=tags,
                enrichment_status=_criterion_enrichment_status(
                    accepted_count=len(accepted),
                    pending_count=len(pending),
                ),
            ),
        )
    return enriched


def _failure_signal(
    criterion: AssessmentCriterion,
    misconception: MisconceptionCandidate,
) -> EmpiricalFailureSignal:
    source_labels = ", ".join(misconception.source_labels) or "source-native labels"
    return EmpiricalFailureSignal(
        signal_id=make_failure_signal_id(
            criterion_id=criterion.criterion_id,
            misconception_id=misconception.misconception_id,
        ),
        misconception_id=misconception.misconception_id,
        diagnostic_signal=(
            f"{misconception.name} ({misconception.source_evidence_count} "
            f"source errors; source labels: {source_labels})."
        ),
        source_evidence_count=misconception.source_evidence_count,
        source_distribution=misconception.source_distribution,
        proficiency_distribution=misconception.proficiency_distribution,
        confidence=misconception.confidence,
    )


def _criterion_enrichment_status(
    *,
    accepted_count: int,
    pending_count: int,
) -> str:
    if accepted_count:
        return "empirically_enriched"
    if pending_count:
        return "empirical_pending_review"
    return "no_accepted_misconceptions"


def _enrich_profiles(
    *,
    profiles: Sequence[SkillAssessmentProfile],
    accepted_by_skill: dict[str, list[MisconceptionCandidate]],
    pending_by_skill: dict[str, list[MisconceptionCandidate]],
) -> list[EnrichedSkillProfile]:
    enriched: list[EnrichedSkillProfile] = []
    for profile in profiles:
        accepted = accepted_by_skill.get(profile.canonical_skill_id, [])
        pending = pending_by_skill.get(profile.canonical_skill_id, [])
        source_counts = sum(
            (Counter(misconception.source_distribution) for misconception in accepted),
            Counter(),
        )
        enriched.append(
            EnrichedSkillProfile(
                profile=profile,
                accepted_misconception_ids=[
                    misconception.misconception_id for misconception in accepted
                ],
                pending_misconception_candidate_ids=[
                    misconception.misconception_id for misconception in pending
                ],
                empirical_evidence_count=sum(
                    misconception.source_evidence_count for misconception in accepted
                ),
                empirical_sources=dict(sorted(source_counts.items())),
                diagnostic_evidence_status=_profile_enrichment_status(
                    accepted_count=len(accepted),
                    pending_count=len(pending),
                ),
            ),
        )
    return enriched


def _profile_enrichment_status(
    *,
    accepted_count: int,
    pending_count: int,
) -> str:
    if accepted_count:
        return "empirically_enriched"
    if pending_count:
        return "empirical_pending_review"
    return "curated_only"


def _review_status_consolidation(
    report_paths: dict[str, Path],
    issues: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    consolidation: dict[str, dict[str, Any]] = {}
    for key, path in report_paths.items():
        if not path.exists():
            issues.append(
                {
                    "severity": "warning",
                    "code": "missing_review_status_report",
                    "message": f"Review status report unavailable: {path}",
                    "source": key,
                },
            )
            consolidation[key] = {
                "path": str(path).replace("\\", "/"),
                "available": False,
                "validation_passed": None,
                "review_required_count": None,
            }
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append(
                {
                    "severity": "warning",
                    "code": "invalid_review_status_report",
                    "message": f"{path}: {exc}",
                    "source": key,
                },
            )
            consolidation[key] = {
                "path": str(path).replace("\\", "/"),
                "available": False,
                "validation_passed": None,
                "review_required_count": None,
            }
            continue
        consolidation[key] = _compact_review_status(key, path, payload)
    return consolidation


def _compact_review_status(
    key: str,
    path: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    validation_passed = _validation_passed(payload)
    review_required_count = _review_required_count(key, payload)
    status = "ready" if validation_passed and not review_required_count else "review_required"
    if validation_passed is False:
        status = "validation_errors"
    return {
        "path": str(path).replace("\\", "/"),
        "available": True,
        "status": status,
        "validation_passed": validation_passed,
        "review_required_count": review_required_count,
        "summary": _source_specific_summary(key, payload),
    }


def _validation_passed(payload: dict[str, Any]) -> bool | None:
    validation = payload.get("validation")
    if isinstance(validation, dict):
        if isinstance(validation.get("passed"), bool):
            return validation["passed"]
        if isinstance(validation.get("error_count"), int):
            return validation["error_count"] == 0
        if isinstance(validation.get("errors"), int):
            return validation["errors"] == 0
    validation_dicts = [
        value
        for key, value in payload.items()
        if key.endswith("_validation") and isinstance(value, dict)
    ]
    if validation_dicts:
        error_values = [
            value.get("errors")
            for value in validation_dicts
            if isinstance(value.get("errors"), int)
        ]
        if error_values:
            return sum(error_values) == 0
    if isinstance(payload.get("validation_errors"), int):
        return payload["validation_errors"] == 0
    return None


def _review_required_count(key: str, payload: dict[str, Any]) -> int | None:
    candidates = [
        "review_queue_count",
        "relationships_requiring_review_count",
        "criteria_requiring_review_count",
    ]
    for field_name in candidates:
        value = payload.get(field_name)
        if isinstance(value, int):
            return value
    if key == "cefr" and isinstance(payload.get("skills_requiring_review"), list):
        return len(payload["skills_requiring_review"])
    if key == "assessment" and isinstance(payload.get("criteria_requiring_review"), list):
        return len(payload["criteria_requiring_review"])
    if key == "egp":
        review_counts = payload.get("review_counts")
        if isinstance(review_counts, dict):
            return sum(
                int(review_counts.get(status, 0) or 0)
                for status in ("pending", "needs_review")
            )
    return None


def _source_specific_summary(key: str, payload: dict[str, Any]) -> dict[str, Any]:
    if key == "egp":
        source_records = payload.get("source_records")
        return {
            "mapping_status_counts": payload.get("mapping_counts"),
            "source_record_count": source_records.get("total")
            if isinstance(source_records, dict)
            else None,
            "excluded_record_count": source_records.get("excluded")
            if isinstance(source_records, dict)
            else None,
        }
    if key == "cefr":
        return {
            "skills_with_cefr_alignment": payload.get("skills_with_cefr_alignment"),
            "skills_curated_only": payload.get("skills_curated_only"),
            "source_evidence": payload.get("source_evidence"),
        }
    if key == "relationships":
        return {
            "total_relationships": payload.get("total_relationships"),
            "isolated_skills": payload.get("isolated_skills"),
            "cycles_found": payload.get("cycles_found"),
        }
    if key == "assessment":
        return {
            "total_criteria": payload.get("total_criteria"),
            "skills_with_assessment_criteria": payload.get(
                "skills_with_assessment_criteria",
            ),
        }
    if key == "errors":
        return {
            "normalized_error_count": payload.get("normalized_error_count"),
            "skill_mapping_count": payload.get("skill_mapping_count"),
            "skill_mapping_status_counts": payload.get("skill_mapping_status_counts"),
        }
    if key == "misconceptions":
        return {
            "candidate_count": payload.get("candidate_count"),
            "accepted_count": payload.get("accepted_count"),
            "source_evidence_count": payload.get("source_evidence_count"),
        }
    return {}


def _validate_enrichment(
    *,
    criteria: Sequence[AssessmentCriterion],
    profiles: Sequence[SkillAssessmentProfile],
    enriched_criteria: Sequence[EnrichedAssessmentCriterion],
    enriched_profiles: Sequence[EnrichedSkillProfile],
    accepted: Sequence[MisconceptionCandidate],
    candidates: Sequence[MisconceptionCandidate],
    links: Sequence[SkillMisconceptionLink],
    issues: list[dict[str, Any]],
    canonical_skill_ids: Sequence[str],
) -> dict[str, Any]:
    canonical_set = set(canonical_skill_ids)
    profile_skill_ids = {profile.canonical_skill_id for profile in profiles}
    criteria_skill_ids = {criterion.canonical_skill_id for criterion in criteria}
    missing_profiles = sorted(canonical_set - profile_skill_ids)
    missing_criteria = sorted(canonical_set - criteria_skill_ids)
    invalid_skill_refs = sorted(
        {
            *criteria_skill_ids,
            *profile_skill_ids,
            *(misconception.canonical_skill_id for misconception in accepted),
            *(misconception.canonical_skill_id for misconception in candidates),
            *(link.canonical_skill_id for link in links),
        }
        - canonical_set
    )
    duplicate_link_ids = _duplicates(link.link_id for link in links)
    forbidden_key_paths = find_forbidden_free_text_keys(
        {
            "enriched_criteria": [
                item.model_dump(mode="json") for item in enriched_criteria
            ],
            "enriched_profiles": [
                item.model_dump(mode="json") for item in enriched_profiles
            ],
            "links": [link.model_dump(mode="json") for link in links],
        },
    )
    accepted_ids = {misconception.misconception_id for misconception in accepted}
    candidate_ids = {misconception.misconception_id for misconception in candidates}
    linked_ids = {link.misconception_id for link in links}
    candidate_used_as_accepted = sorted((candidate_ids - accepted_ids) & linked_ids)
    validation_issues = list(issues)
    for missing in missing_profiles:
        validation_issues.append(
            {
                "severity": "error",
                "code": "missing_enriched_skill_profile",
                "message": f"Missing enriched profile for skill: {missing}",
                "canonical_skill_id": missing,
            },
        )
    for missing in missing_criteria:
        validation_issues.append(
            {
                "severity": "error",
                "code": "missing_enriched_assessment_criterion",
                "message": f"Missing assessment criterion for skill: {missing}",
                "canonical_skill_id": missing,
            },
        )
    if invalid_skill_refs:
        validation_issues.append(
            {
                "severity": "error",
                "code": "invalid_skill_references",
                "message": "Enrichment input contains skill ids outside Grammar V1.",
                "skill_ids": invalid_skill_refs,
            },
        )
    if duplicate_link_ids:
        validation_issues.append(
            {
                "severity": "error",
                "code": "duplicate_skill_misconception_links",
                "message": "Duplicate skill-misconception link ids found.",
                "link_ids": duplicate_link_ids,
            },
        )
    if forbidden_key_paths:
        validation_issues.append(
            {
                "severity": "error",
                "code": "raw_text_policy_violation",
                "message": "Forbidden learner free-text key found in enrichment output.",
                "paths": forbidden_key_paths,
            },
        )
    if candidate_used_as_accepted:
        validation_issues.append(
            {
                "severity": "error",
                "code": "candidate_used_as_accepted_evidence",
                "message": "Pending candidates must not enrich assessment evidence.",
                "misconception_ids": candidate_used_as_accepted,
            },
        )
    error_count = sum(
        1 for issue in validation_issues if issue.get("severity") == "error"
    )
    warning_count = sum(
        1 for issue in validation_issues if issue.get("severity") == "warning"
    )
    return {
        "passed": error_count == 0,
        "error_count": error_count,
        "warning_count": warning_count,
        "issues": validation_issues,
        "missing_profiles": missing_profiles,
        "missing_criteria": missing_criteria,
        "invalid_skill_reference_count": len(invalid_skill_refs),
        "duplicate_link_count": len(duplicate_link_ids),
        "candidate_used_as_accepted_count": len(candidate_used_as_accepted),
        "raw_text_emitted": bool(forbidden_key_paths),
    }


def _build_report(
    *,
    criteria: Sequence[AssessmentCriterion],
    profiles: Sequence[SkillAssessmentProfile],
    enriched_criteria: Sequence[EnrichedAssessmentCriterion],
    enriched_profiles: Sequence[EnrichedSkillProfile],
    accepted: Sequence[MisconceptionCandidate],
    candidates: Sequence[MisconceptionCandidate],
    links: Sequence[SkillMisconceptionLink],
    validation: dict[str, Any],
    issues: list[dict[str, Any]],
    review_consolidation: dict[str, dict[str, Any]],
    inputs: dict[str, Path],
    output_paths: dict[str, Path],
    canonical_skill_ids: Sequence[str],
) -> dict[str, Any]:
    taxonomy = build_grammar_taxonomy(canonical_skill_ids)
    empirical_criteria = [
        criterion
        for criterion in enriched_criteria
        if criterion.empirical_failure_signals
    ]
    pending_profiles = [
        profile
        for profile in enriched_profiles
        if profile.pending_misconception_candidate_ids
    ]
    accepted_by_skill = Counter(
        misconception.canonical_skill_id for misconception in accepted
    )
    pending_by_skill = Counter(
        misconception.canonical_skill_id
        for misconception in candidates
        if misconception.status == "candidate"
    )
    return {
        "schema_version": KNOWLEDGE_ENRICHMENT_SCHEMA_VERSION,
        "inputs": {
            key: str(path).replace("\\", "/")
            for key, path in inputs.items()
        },
        "outputs": {
            key: str(path).replace("\\", "/")
            for key, path in output_paths.items()
        },
        "counts": {
            "assessment_criteria_read": len(criteria),
            "assessment_profiles_read": len(profiles),
            "enriched_assessment_criteria": len(enriched_criteria),
            "enriched_skill_profiles": len(enriched_profiles),
            "accepted_misconceptions": len(accepted),
            "pending_misconception_candidates": sum(pending_by_skill.values()),
            "skill_misconception_links": len(links),
            "criteria_with_empirical_failure_signals": len(empirical_criteria),
            "profiles_with_accepted_misconceptions": sum(
                1 for profile in enriched_profiles if profile.accepted_misconception_ids
            ),
            "profiles_with_pending_candidates": len(pending_profiles),
            "empirical_failure_signal_count": sum(
                len(criterion.empirical_failure_signals)
                for criterion in enriched_criteria
            ),
        },
        "accepted_misconception_counts_by_skill": dict(sorted(accepted_by_skill.items())),
        "pending_misconception_counts_by_skill": dict(sorted(pending_by_skill.items())),
        "diagnostic_evidence_policy": {
            "curated_failure_signals_field": "curated_failure_signals",
            "empirical_failure_signals_field": "empirical_failure_signals",
            "accepted_only_for_empirical_enrichment": True,
            "pending_candidates_not_applied": True,
        },
        "review_status_consolidation": review_consolidation,
        "taxonomy": {
            "source": "knowledge_core.mapping.egp.canonical.CANONICAL_GRAMMAR_V1_SKILLS",
            "atomic_skill_count": len(canonical_skill_ids),
            "taxonomy_hash": taxonomy.taxonomy_hash,
            "taxonomy_unchanged": tuple(canonical_skill_ids)
            == tuple(CANONICAL_GRAMMAR_V1_SKILLS),
        },
        "validation": validation,
        "known_limitations": _known_limitations(accepted_count=len(accepted)),
        "inspection_issues": issues,
    }


def _known_limitations(*, accepted_count: int) -> list[str]:
    limitations = [
        "Assessment artifacts are enriched as separate derived views; the source assessment artifacts are not mutated.",
        "No raw learner text or correction text is emitted.",
        "Pending misconception candidates are retained for review but are not used as empirical diagnostic evidence.",
    ]
    if accepted_count == 0:
        limitations.append(
            "Accepted misconception set is empty, so no corpus-backed failure signals were attached.",
        )
    return limitations


def _default_output_paths(
    *,
    curated_dir: str | Path,
    review_dir: str | Path,
) -> dict[str, Path]:
    curated = Path(curated_dir)
    review = Path(review_dir)
    return {
        "assessment_criteria_enriched_jsonl": curated
        / ASSESSMENT_CRITERIA_ENRICHED_JSONL,
        "skill_profiles_enriched_jsonl": curated / SKILL_PROFILES_ENRICHED_JSONL,
        "skill_misconception_links_jsonl": curated / SKILL_MISCONCEPTION_LINKS_JSONL,
        "review_csv": review / KNOWLEDGE_ENRICHMENT_REVIEW_CSV,
    }


def _write_jsonl(records: Sequence[Any], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(
                json.dumps(
                    record.model_dump(mode="json"),
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )
            handle.write("\n")


def _write_review_csv(
    *,
    accepted: Sequence[MisconceptionCandidate],
    candidates: Sequence[MisconceptionCandidate],
    destination: Path,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "review_row_id",
        "entity_type",
        "entity_id",
        "canonical_skill_id",
        "status",
        "review_status",
        "source_evidence_count",
        "evidence_status",
        "recommended_action",
        "reason",
    ]
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for misconception in accepted:
            writer.writerow(
                _review_row(
                    misconception=misconception,
                    evidence_status="accepted_empirical",
                    recommended_action="linked_to_skill",
                ),
            )
        for misconception in candidates:
            if misconception.status != "candidate":
                continue
            writer.writerow(
                _review_row(
                    misconception=misconception,
                    evidence_status="pending_review",
                    recommended_action="approve_or_reject_before_enrichment",
                ),
            )


def _review_row(
    *,
    misconception: MisconceptionCandidate,
    evidence_status: str,
    recommended_action: str,
) -> dict[str, Any]:
    return {
        "review_row_id": make_review_row_id(
            review_queue="knowledge_enrichment_review",
            entity_id=misconception.misconception_id,
        ),
        "entity_type": "misconception",
        "entity_id": misconception.misconception_id,
        "canonical_skill_id": misconception.canonical_skill_id,
        "status": misconception.status,
        "review_status": misconception.review_status,
        "source_evidence_count": misconception.source_evidence_count,
        "evidence_status": evidence_status,
        "recommended_action": recommended_action,
        "reason": misconception.reason,
    }


def _duplicates(values) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)
