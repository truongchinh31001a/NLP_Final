from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from pydantic import ValidationError

from knowledge_core.assessment.models import AssessmentCriterion
from knowledge_core.mapping.egp.canonical import (
    CANONICAL_GRAMMAR_V1_SKILLS,
    CANONICAL_GRAMMAR_V1_SKILL_SET,
)
from knowledge_core.misconceptions.models import MisconceptionCandidate
from knowledge_core.misconceptions.review_models import MisconceptionReviewDecision
from knowledge_core.relationships.taxonomy import build_grammar_taxonomy


DEFAULT_CANDIDATES = Path("data/interim/misconceptions/candidate_misconceptions.jsonl")
DEFAULT_APPROVED_MAPPINGS = Path("data/curated/error_mapping/accepted_error_skill_mappings.jsonl")
DEFAULT_CRITERIA = Path("data/curated/assessment/grammar_assessment_criteria.jsonl")
DEFAULT_REVIEW = Path("data/curated/review/misconception_human_review.csv")
DEFAULT_DECISIONS = Path("data/curated/review/misconception_review_decisions.csv")
DEFAULT_CURATED = Path("data/curated/misconceptions")
DEFAULT_LINKS = Path("data/interim/assessment/misconception_assessment_links.jsonl")
DEFAULT_REPORT = Path("data/reports/misconceptions/misconception_human_review_report.json")

REVIEW_FIELDS = [
    "misconception_id", "canonical_skill_id", "skill_name", "misconception_name",
    "description", "normalized_error_category", "normalized_subtype",
    "expected_pattern", "observed_pattern", "diagnostic_rule", "example_correct",
    "example_incorrect", "approved_evidence_count", "source_distribution",
    "corpus_distribution", "proficiency_distribution", "frequency", "frequency_scope",
    "supporting_approved_mapping_ids", "representative_source_native_labels",
    "confidence", "severity", "reason", "provenance", "current_status",
    "current_review_status", "reviewer_decision", "reviewer_note", "reviewed_by",
    "reviewed_at",
]
DECISION_FIELDS = [
    "misconception_id", "reviewer_decision", "reviewer_note", "reviewed_by", "reviewed_at",
]


@dataclass(slots=True)
class MisconceptionReviewResult:
    report: dict[str, Any]
    output_paths: dict[str, Path]


def prepare_misconception_review(
    *, candidates_path: str | Path = DEFAULT_CANDIDATES,
    review_path: str | Path = DEFAULT_REVIEW,
    decisions_path: str | Path = DEFAULT_DECISIONS,
) -> MisconceptionReviewResult:
    candidates = _load_candidates(Path(candidates_path))
    existing = _load_existing_decisions(Path(decisions_path))
    rows = []
    decisions = []
    for candidate in candidates:
        decision = existing.get(candidate.misconception_id) or {
            "misconception_id": candidate.misconception_id,
            "reviewer_decision": "NEEDS_REVIEW",
            "reviewer_note": (
                "No explicit human approval or rejection supplied; retained as unresolved."
            ),
            "reviewed_by": "",
            "reviewed_at": "",
        }
        rows.append(_review_row(candidate, decision))
        decisions.append(decision)
    _write_csv(Path(review_path), REVIEW_FIELDS, rows)
    _write_csv(Path(decisions_path), DECISION_FIELDS, decisions)
    report = {
        "phase": "prepare_review",
        "total_candidates": len(candidates),
        "approved_evidence_count": sum(item.source_evidence_count for item in candidates),
        "privacy": {"learner_pii_emitted": False, "raw_learner_text_emitted": False},
        "taxonomy": _taxonomy_snapshot(),
    }
    return MisconceptionReviewResult(
        report=report,
        output_paths={"review": Path(review_path), "decisions": Path(decisions_path)},
    )


def apply_misconception_review(
    *, candidates_path: str | Path = DEFAULT_CANDIDATES,
    decisions_path: str | Path = DEFAULT_DECISIONS,
    criteria_path: str | Path = DEFAULT_CRITERIA,
    approved_mappings_path: str | Path = DEFAULT_APPROVED_MAPPINGS,
    curated_dir: str | Path = DEFAULT_CURATED,
    links_path: str | Path = DEFAULT_LINKS,
    report_path: str | Path = DEFAULT_REPORT,
) -> MisconceptionReviewResult:
    issues: list[dict[str, str]] = []
    candidates = _load_candidate_payloads(Path(candidates_path), issues)
    decisions = _load_decisions(Path(decisions_path), candidates, issues)
    reviewed = []
    for candidate in candidates:
        candidate_id = str(candidate.get("misconception_id") or "")
        decision = decisions.get(candidate_id)
        if decision is None:
            decision = {
                "misconception_id": candidate_id,
                "reviewer_decision": "NEEDS_REVIEW",
                "reviewer_note": "No reviewer decision supplied; explicitly unresolved.",
                "reviewed_by": "",
                "reviewed_at": "",
            }
        reviewed.append(_apply_decision(candidate, decision))

    accepted = [item for item in reviewed if item.get("status") == "accepted"]
    rejected = [item for item in reviewed if item.get("status") == "rejected"]
    unresolved = [item for item in reviewed if item.get("status") == "candidate"]
    approved_mapping_ids = {
        str(item.get("mapping_id") or "")
        for item in _read_jsonl(Path(approved_mappings_path))
    }
    _validate(
        reviewed,
        accepted,
        rejected,
        unresolved,
        approved_mapping_ids,
        issues,
    )
    criteria = _load_criteria(Path(criteria_path), issues)
    links = _assessment_links(accepted, criteria)
    taxonomy = _taxonomy_snapshot()
    errors = [issue for issue in issues if issue["severity"] == "error"]
    warnings = [issue for issue in issues if issue["severity"] == "warning"]

    root = Path(curated_dir)
    outputs = {
        "accepted": root / "accepted_misconceptions.jsonl",
        "rejected": root / "rejected_misconceptions.jsonl",
        "unresolved": root / "unresolved_misconceptions.jsonl",
        "assessment_links": Path(links_path),
        "report": Path(report_path),
    }
    if not errors:
        _write_jsonl(outputs["accepted"], accepted)
        _write_jsonl(outputs["rejected"], rejected)
        _write_jsonl(outputs["unresolved"], unresolved)
        _write_jsonl(outputs["assessment_links"], links)

    accepted_by_skill = Counter(item["canonical_skill_id"] for item in accepted)
    source_evidence = Counter()
    proficiency = Counter()
    for item in accepted:
        source_evidence.update(item.get("source_distribution", {}))
        proficiency.update(item.get("proficiency_distribution", {}))
    report = {
        "schema_version": "misconception_human_review_v1",
        "total_candidates": len(candidates),
        "approved": len(accepted),
        "rejected": len(rejected),
        "needs_review": len(unresolved),
        "undecided": 0,
        "accepted_misconception_ids": [item["misconception_id"] for item in accepted],
        "accepted_by_skill": dict(sorted(accepted_by_skill.items())),
        "accepted_by_source_evidence": dict(sorted(source_evidence.items())),
        "approved_evidence_count": sum(item["source_evidence_count"] for item in accepted),
        "proficiency_distribution": dict(sorted(proficiency.items())),
        "assessment_links_proposed": len(links),
        "assessment_enrichment_mode": "proposed_only",
        "taxonomy": taxonomy,
        "validation": {
            "passed": not errors,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "issues": issues,
        },
        "outputs": {key: str(path).replace("\\", "/") for key, path in outputs.items()},
    }
    outputs["report"].parent.mkdir(parents=True, exist_ok=True)
    outputs["report"].write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return MisconceptionReviewResult(report=report, output_paths=outputs)


def _review_row(candidate: MisconceptionCandidate, decision: dict[str, str]) -> dict[str, Any]:
    mapping_ids = sorted({link.mapping_id for link in candidate.evidence_links})
    return {
        "misconception_id": candidate.misconception_id,
        "canonical_skill_id": candidate.canonical_skill_id,
        "skill_name": candidate.canonical_skill_id.rsplit(".", 1)[-1].replace("_", " "),
        "misconception_name": candidate.name,
        "description": candidate.description,
        "normalized_error_category": candidate.error_category,
        "normalized_subtype": candidate.error_subtype or "",
        "expected_pattern": candidate.expected_pattern,
        "observed_pattern": candidate.observed_pattern,
        "diagnostic_rule": candidate.diagnostic_rule,
        "example_correct": "not_available_in_source_artifact",
        "example_incorrect": "not_available_in_source_artifact",
        "approved_evidence_count": candidate.source_evidence_count,
        "source_distribution": json.dumps(candidate.source_distribution, sort_keys=True),
        "corpus_distribution": json.dumps(candidate.source_distribution, sort_keys=True),
        "proficiency_distribution": json.dumps(candidate.proficiency_distribution, sort_keys=True),
        "frequency": candidate.frequency,
        "frequency_scope": candidate.frequency_scope,
        "supporting_approved_mapping_ids": ";".join(mapping_ids),
        "representative_source_native_labels": ";".join(candidate.source_labels),
        "confidence": candidate.confidence,
        "severity": candidate.severity,
        "reason": candidate.reason,
        "provenance": json.dumps(candidate.provenance, sort_keys=True),
        "current_status": candidate.status,
        "current_review_status": candidate.review_status,
        **decision,
    }


def _apply_decision(candidate: dict[str, Any], decision: dict[str, str]) -> dict[str, Any]:
    transitions = {
        "APPROVE": ("accepted", "approved"),
        "REJECT": ("rejected", "rejected"),
        "NEEDS_REVIEW": ("candidate", "needs_review"),
    }
    payload = dict(candidate)
    payload["status"], payload["review_status"] = transitions[decision["reviewer_decision"]]
    audit = {
        "reviewer_decision": decision["reviewer_decision"],
        "reviewer_note": decision.get("reviewer_note", ""),
        "reviewed_by": decision.get("reviewed_by", ""),
        "reviewed_at": decision.get("reviewed_at", ""),
    }
    history = list((payload.get("provenance") or {}).get("review_history", []))
    if not history or history[-1] != audit:
        history.append(audit)
    payload["provenance"] = {
        **(payload.get("provenance") or {}),
        "human_review": audit,
        "review_history": history,
        "review_schema_version": "misconception_human_review_v1",
    }
    return payload


def _validate(reviewed, accepted, rejected, unresolved, approved_mapping_ids, issues) -> None:
    if len(reviewed) != len(accepted) + len(rejected) + len(unresolved):
        issues.append(_issue("error", "candidate_accounting_error", "Candidates not partitioned"))
    for item in reviewed:
        if item.get("canonical_skill_id") not in CANONICAL_GRAMMAR_V1_SKILL_SET:
            issues.append(_issue("error", "invalid_skill_reference", item.get("misconception_id", "")))
    for item in accepted:
        review = (item.get("provenance") or {}).get("human_review", {})
        if review.get("reviewer_decision") != "APPROVE":
            issues.append(_issue("error", "accepted_without_approval", item["misconception_id"]))
        if int(item.get("source_evidence_count", 0)) <= 0 or not item.get("evidence_links"):
            issues.append(_issue("error", "accepted_without_approved_evidence", item["misconception_id"]))
        unapproved_ids = sorted({
            str(link.get("mapping_id") or "")
            for link in item.get("evidence_links", [])
        } - approved_mapping_ids)
        if unapproved_ids:
            issues.append(_issue(
                "error",
                "unapproved_mapping_evidence",
                f"{item['misconception_id']}: {','.join(unapproved_ids)}",
            ))
        try:
            MisconceptionCandidate.model_validate(item)
        except ValidationError as exc:
            issues.append(_issue("error", "invalid_accepted_candidate", str(exc)))


def _assessment_links(accepted, criteria: list[AssessmentCriterion]) -> list[dict[str, Any]]:
    links = []
    for misconception in accepted:
        for criterion in criteria:
            if criterion.canonical_skill_id != misconception["canonical_skill_id"]:
                continue
            links.append({
                "misconception_id": misconception["misconception_id"],
                "canonical_skill_id": misconception["canonical_skill_id"],
                "criterion_id": criterion.criterion_id,
                "link_type": "proposed_failure_signal",
                "reason": "Human-approved misconception proposed as empirical diagnostic context.",
                "evidence_count": misconception["source_evidence_count"],
                "provenance": {
                    "source": "misconception_human_review_v1",
                    "assessment_artifact_mutated": False,
                },
                "review_status": "pending",
            })
    return links


def _load_candidates(path: Path) -> list[MisconceptionCandidate]:
    return [MisconceptionCandidate.model_validate(item) for item in _read_jsonl(path)]


def _load_candidate_payloads(path: Path, issues) -> list[dict[str, Any]]:
    records = _read_jsonl(path)
    seen = set()
    for item in records:
        candidate_id = str(item.get("misconception_id") or "")
        if not candidate_id or candidate_id in seen:
            issues.append(_issue("error", "invalid_candidate_id", candidate_id))
        seen.add(candidate_id)
    return records


def _load_criteria(path: Path, issues) -> list[AssessmentCriterion]:
    try:
        return [AssessmentCriterion.model_validate(item) for item in _read_jsonl(path)]
    except (OSError, ValidationError, json.JSONDecodeError) as exc:
        issues.append(_issue("error", "invalid_assessment_criteria", str(exc)))
        return []


def _load_existing_decisions(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            row["misconception_id"]: {field: row.get(field, "") for field in DECISION_FIELDS}
            for row in csv.DictReader(handle)
            if row.get("misconception_id")
        }


def _load_decisions(path: Path, candidates, issues) -> dict[str, dict[str, str]]:
    candidate_ids = {str(item.get("misconception_id") or "") for item in candidates}
    decisions = {}
    if not path.exists():
        issues.append(_issue("error", "missing_decisions", str(path)))
        return decisions
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for line_number, row in enumerate(csv.DictReader(handle), start=2):
            candidate_id = (row.get("misconception_id") or "").strip()
            if candidate_id not in candidate_ids:
                issues.append(_issue("error", "unknown_misconception_id", f"{line_number}:{candidate_id}"))
                continue
            if candidate_id in decisions:
                issues.append(_issue("error", "duplicate_decision", candidate_id))
                continue
            try:
                decision = MisconceptionReviewDecision.model_validate(
                    {field: row.get(field, "") for field in DECISION_FIELDS}
                )
            except ValidationError as exc:
                issues.append(_issue("error", "invalid_reviewer_decision", str(exc)))
                continue
            decisions[candidate_id] = decision.model_dump()
    return decisions


def _taxonomy_snapshot() -> dict[str, Any]:
    taxonomy = build_grammar_taxonomy(CANONICAL_GRAMMAR_V1_SKILLS)
    return {
        "atomic_skill_count": len(CANONICAL_GRAMMAR_V1_SKILLS),
        "taxonomy_hash": taxonomy.taxonomy_hash,
        "taxonomy_unchanged": len(CANONICAL_GRAMMAR_V1_SKILLS) == 43,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _issue(severity: str, code: str, message: str) -> dict[str, str]:
    return {"severity": severity, "code": code, "message": message}
