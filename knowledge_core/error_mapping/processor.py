from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from pydantic import ValidationError

from knowledge_core.error_mapping.models import GroupDecision, ReviewDecision
from knowledge_core.error_mapping.paths import (
    ACCEPTED_FILE,
    DECISIONS_FILE,
    DEFAULT_CURATED_DIR,
    DEFAULT_ERROR_INSTANCE_PATHS,
    DEFAULT_ERROR_REPORT_PATH,
    DEFAULT_MAPPINGS_PATH,
    DEFAULT_MISCONCEPTION_REPORT_PATH,
    DEFAULT_MISCONCEPTION_REVIEW_PATH,
    DEFAULT_MISCONCEPTIONS_PATH,
    DEFAULT_NORMALIZED_ERRORS_PATH,
    DEFAULT_REPORT_PATH,
    DEFAULT_REVIEW_DIR,
    GROUP_DECISIONS_FILE,
    GROUPS_FILE,
    LEGACY_REVIEW_FILE,
    MISCONCEPTION_EVIDENCE_BASELINE_FILE,
    REJECTED_FILE,
    REVIEW_FILE,
    UNRESOLVED_FILE,
)
from knowledge_core.mapping.egp.canonical import (
    CANONICAL_GRAMMAR_V1_SKILLS,
    CANONICAL_GRAMMAR_V1_SKILL_SET,
)
from knowledge_core.misconceptions.models import MisconceptionCandidate
from knowledge_core.normalization.corpus_errors.models import ErrorSkillMapping
from knowledge_core.relationships.taxonomy import build_grammar_taxonomy


REVIEW_SCHEMA_VERSION = "error_mapping_human_review_v1"
REVIEW_FIELDS = [
    "mapping_id",
    "review_group_id",
    "group_can_share_decision",
    "source_key",
    "source_error_label",
    "normalized_error_category",
    "normalized_error_subtype",
    "error_pattern",
    "corrected_pattern",
    "candidate_skill_id",
    "candidate_skill_name",
    "mapping_rule",
    "mapping_reason",
    "confidence",
    "evidence_count",
    "source_distribution",
    "proficiency_distribution",
    "ambiguity_reason",
    "current_status",
    "current_review_status",
    "reviewer_decision",
    "reviewer_note",
    "reviewed_by",
    "reviewed_at",
]
DECISION_FIELDS = [
    "mapping_id",
    "reviewer_decision",
    "reviewer_note",
    "reviewed_by",
    "reviewed_at",
]


@dataclass(slots=True)
class ReviewResult:
    report: dict[str, Any]
    output_paths: dict[str, Path]


def prepare_review_package(
    *,
    mappings_path: str | Path = DEFAULT_MAPPINGS_PATH,
    normalized_errors_path: str | Path = DEFAULT_NORMALIZED_ERRORS_PATH,
    error_instance_paths: dict[str, str | Path] | None = None,
    misconceptions_path: str | Path = DEFAULT_MISCONCEPTIONS_PATH,
    review_dir: str | Path = DEFAULT_REVIEW_DIR,
) -> ReviewResult:
    mappings = _load_mappings(Path(mappings_path))
    mapping_ids = {item.mapping_id for item in mappings}
    normalized = _load_selected_jsonl(
        Path(normalized_errors_path),
        "normalized_error_id",
        {item.normalized_error_id for item in mappings},
    )
    errors = _load_error_instances(
        mappings,
        error_instance_paths or DEFAULT_ERROR_INSTANCE_PATHS,
    )
    evidence_metadata = _misconception_evidence_metadata(
        Path(misconceptions_path),
        mapping_ids,
    )
    rows = _build_review_rows(mappings, normalized, errors, evidence_metadata)
    groups = _build_groups(rows)
    group_by_mapping = {
        mapping_id: group
        for group in groups
        for mapping_id in group["member_mapping_ids"]
    }
    for row in rows:
        group = group_by_mapping[row["mapping_id"]]
        row["review_group_id"] = group["review_group_id"]
        row["group_can_share_decision"] = str(group["group_can_share_decision"]).lower()
        row["evidence_count"] = group["member_count"]
        row["source_distribution"] = json.dumps(group["source_distribution"], sort_keys=True)
        row["proficiency_distribution"] = json.dumps(
            group["proficiency_distribution"],
            sort_keys=True,
        )

    review_root = Path(review_dir)
    review_root.mkdir(parents=True, exist_ok=True)
    review_path = review_root / REVIEW_FILE
    legacy_path = review_root / LEGACY_REVIEW_FILE
    legacy_rows = _preserve_legacy_review(review_path, legacy_path)
    existing_decisions = _existing_decisions(review_root / DECISIONS_FILE)
    for row in rows:
        decision = existing_decisions.get(row["mapping_id"])
        if decision:
            row.update(decision)
    _write_csv(review_path, REVIEW_FIELDS, rows)
    _write_csv(review_root / GROUPS_FILE, _group_fields(), _group_csv_rows(groups))

    decision_rows = []
    for row in rows:
        existing = existing_decisions.get(row["mapping_id"])
        decision_rows.append(
            existing
            or {
                "mapping_id": row["mapping_id"],
                "reviewer_decision": "NEEDS_REVIEW",
                "reviewer_note": (
                    "No explicit human approval or rejection supplied; retained "
                    "as unresolved candidate."
                ),
                "reviewed_by": "",
                "reviewed_at": "",
            }
        )
    _write_csv(review_root / DECISIONS_FILE, DECISION_FIELDS, decision_rows)
    group_decision_path = review_root / GROUP_DECISIONS_FILE
    if not group_decision_path.exists():
        _write_csv(
            group_decision_path,
            [
                "review_group_id",
                "reviewer_decision",
                "reviewer_note",
                "reviewed_by",
                "reviewed_at",
            ],
            [],
        )

    report = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "phase": "prepare_review",
        "total_mappings": len(mappings),
        "mapping_review_queue": len(rows),
        "legacy_normalization_review_rows": legacy_rows,
        "review_groups": len(groups),
        "safe_shared_decision_groups": sum(
            1 for group in groups if group["group_can_share_decision"]
        ),
        "taxonomy": _taxonomy_snapshot(),
        "privacy": {
            "raw_learner_text_emitted": False,
            "patterns_use_offsets_lengths_and_fingerprints_only": True,
        },
    }
    return ReviewResult(
        report=report,
        output_paths={
            "review": review_path,
            "legacy_review": legacy_path,
            "groups": review_root / GROUPS_FILE,
            "decisions": review_root / DECISIONS_FILE,
            "group_decisions": group_decision_path,
        },
    )


def apply_review_decisions(
    *,
    mappings_path: str | Path = DEFAULT_MAPPINGS_PATH,
    decisions_path: str | Path | None = None,
    groups_path: str | Path | None = None,
    group_decisions_path: str | Path | None = None,
    misconceptions_path: str | Path = DEFAULT_MISCONCEPTIONS_PATH,
    misconception_report_path: str | Path = DEFAULT_MISCONCEPTION_REPORT_PATH,
    misconception_review_path: str | Path = DEFAULT_MISCONCEPTION_REVIEW_PATH,
    error_report_path: str | Path = DEFAULT_ERROR_REPORT_PATH,
    review_dir: str | Path = DEFAULT_REVIEW_DIR,
    curated_dir: str | Path = DEFAULT_CURATED_DIR,
    report_path: str | Path = DEFAULT_REPORT_PATH,
) -> ReviewResult:
    review_root = Path(review_dir)
    mappings = _load_mappings(Path(mappings_path))
    mapping_by_id = {item.mapping_id: item for item in mappings}
    issues: list[dict[str, Any]] = []
    row_decisions = _load_row_decisions(
        Path(decisions_path or review_root / DECISIONS_FILE),
        mapping_by_id,
        issues,
    )
    groups = _load_groups(Path(groups_path or review_root / GROUPS_FILE), issues)
    group_decisions = _load_group_decisions(
        Path(group_decisions_path or review_root / GROUP_DECISIONS_FILE),
        groups,
        issues,
    )
    propagated = _propagate_group_decisions(groups, group_decisions, row_decisions, issues)

    taxonomy_before = _taxonomy_snapshot()
    reviewed: list[dict[str, Any]] = []
    decision_sources: Counter[str] = Counter()
    for mapping in mappings:
        decision_payload = row_decisions.get(mapping.mapping_id)
        decision_source = "row"
        if decision_payload is None:
            decision_payload = propagated.get(mapping.mapping_id)
            decision_source = "group"
        if decision_payload is None:
            decision_payload = {
                "mapping_id": mapping.mapping_id,
                "reviewer_decision": "NEEDS_REVIEW",
                "reviewer_note": "No reviewer decision supplied; explicitly unresolved.",
                "reviewed_by": "",
                "reviewed_at": "",
            }
            decision_source = "default_unresolved"
        reviewed.append(_apply_decision(mapping, decision_payload, decision_source))
        decision_sources[decision_source] += 1

    accepted = [item for item in reviewed if item["status"] == "accepted"]
    rejected = [item for item in reviewed if item["status"] == "rejected"]
    unresolved = [item for item in reviewed if item["status"] == "candidate"]
    _validate_outputs(reviewed, accepted, rejected, unresolved, issues)
    taxonomy_after = _taxonomy_snapshot()
    if taxonomy_before != taxonomy_after:
        issues.append(
            {
                "severity": "error",
                "code": "taxonomy_changed",
                "message": "Canonical taxonomy changed while applying review decisions.",
            }
        )

    curated_root = Path(curated_dir)
    output_paths = {
        "accepted": curated_root / ACCEPTED_FILE,
        "rejected": curated_root / REJECTED_FILE,
        "unresolved": curated_root / UNRESOLVED_FILE,
    }
    if not any(issue["severity"] == "error" for issue in issues):
        _write_jsonl(output_paths["accepted"], accepted)
        _write_jsonl(output_paths["rejected"], rejected)
        _write_jsonl(output_paths["unresolved"], unresolved)

    evidence_before, evidence_after = _recompute_misconception_evidence(
        Path(misconceptions_path),
        {item["mapping_id"] for item in accepted},
        Path(error_report_path),
        Path(misconception_report_path),
        Path(misconception_review_path),
        output_paths["accepted"],
        curated_root / MISCONCEPTION_EVIDENCE_BASELINE_FILE,
        write=not any(issue["severity"] == "error" for issue in issues),
    )
    error_count = sum(issue["severity"] == "error" for issue in issues)
    warning_count = sum(issue["severity"] == "warning" for issue in issues)
    accepted_skills = sorted({item["canonical_skill_id"] for item in accepted})
    unresolved_skills = sorted(
        {item["canonical_skill_id"] for item in unresolved} - set(accepted_skills)
    )
    report = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "total_mappings": len(mappings),
        "total_review_queue": len(mappings),
        "approved_mappings": len(accepted),
        "rejected_mappings": len(rejected),
        "needs_review_mappings": len(unresolved),
        "undecided_mappings": 0,
        "review_groups": len(groups),
        "group_approved_rows": sum(
            1
            for item in accepted
            if item["provenance"]["human_review"]["decision_source"] == "group"
        ),
        "row_level_approved_rows": sum(
            1
            for item in accepted
            if item["provenance"]["human_review"]["decision_source"] == "row"
        ),
        "decision_source_counts": dict(sorted(decision_sources.items())),
        "canonical_skills_with_accepted_empirical_mappings": accepted_skills,
        "canonical_skills_with_only_unresolved_mappings": unresolved_skills,
        "source_distribution": dict(
            sorted(Counter(item["source_key"] for item in reviewed).items())
        ),
        "confidence_distribution": _confidence_distribution(reviewed),
        "invalid_reviewer_decisions": sum(
            issue["code"] == "invalid_reviewer_decision" for issue in issues
        ),
        "invalid_skill_references": sum(
            issue["code"] == "invalid_skill_reference" for issue in issues
        ),
        "misconception_evidence_before": evidence_before,
        "misconception_evidence_after": evidence_after,
        "taxonomy": taxonomy_after,
        "validation": {
            "passed": error_count == 0,
            "error_count": error_count,
            "warning_count": warning_count,
            "issues": issues,
        },
        "outputs": {key: str(path).replace("\\", "/") for key, path in output_paths.items()},
    }
    destination = Path(report_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return ReviewResult(report=report, output_paths={**output_paths, "report": destination})


def _load_mappings(path: Path) -> list[ErrorSkillMapping]:
    records: list[ErrorSkillMapping] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            mapping = ErrorSkillMapping.model_validate_json(line)
            if mapping.mapping_id in seen:
                raise ValueError(f"Duplicate mapping_id at {path}:{line_number}: {mapping.mapping_id}")
            seen.add(mapping.mapping_id)
            records.append(mapping)
    return records


def _load_selected_jsonl(path: Path, id_field: str, needed: set[str]) -> dict[str, dict]:
    if not needed:
        return {}
    found: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            record_id = str(payload.get(id_field) or "")
            if record_id in needed:
                found[record_id] = payload
                if len(found) == len(needed):
                    break
    missing = needed - set(found)
    if missing:
        raise ValueError(f"Missing {len(missing)} references in {path}")
    return found


def _load_error_instances(
    mappings: list[ErrorSkillMapping],
    paths: dict[str, str | Path],
) -> dict[str, dict]:
    by_source: dict[str, set[str]] = defaultdict(set)
    for mapping in mappings:
        by_source[mapping.source_key].add(mapping.error_instance_id)
    found: dict[str, dict] = {}
    for source, needed in by_source.items():
        path = Path(paths[source])
        found.update(_load_selected_jsonl(path, "error_instance_id", needed))
    return found


def _misconception_evidence_metadata(path: Path, mapping_ids: set[str]) -> dict[str, dict]:
    metadata: dict[str, dict] = {}
    if not path.exists():
        return metadata
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            for link in payload.get("evidence_links", []):
                mapping_id = str(link.get("mapping_id") or "")
                if mapping_id in mapping_ids:
                    metadata[mapping_id] = link
    return metadata


def _build_review_rows(
    mappings: list[ErrorSkillMapping],
    normalized: dict[str, dict],
    errors: dict[str, dict],
    evidence_metadata: dict[str, dict],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for mapping in mappings:
        norm = normalized[mapping.normalized_error_id]
        error = errors[mapping.error_instance_id]
        evidence = evidence_metadata.get(mapping.mapping_id, {})
        span = error.get("span") or {}
        correction = error.get("correction") or {}
        rows.append(
            {
                "mapping_id": mapping.mapping_id,
                "review_group_id": "",
                "group_can_share_decision": "false",
                "source_key": mapping.source_key,
                "source_error_label": mapping.provenance.get("source_label") or "",
                "normalized_error_category": norm.get("category") or "",
                "normalized_error_subtype": norm.get("subtype") or "",
                "error_pattern": json.dumps(
                    {
                        key: span.get(key)
                        for key in (
                            "span_kind",
                            "start_char",
                            "end_char",
                            "selected_text_length",
                            "selection_fingerprint",
                        )
                        if span.get(key) is not None
                    },
                    sort_keys=True,
                ),
                "corrected_pattern": json.dumps(
                    {
                        key: correction.get(key)
                        for key in (
                            "correction_type",
                            "correction_length",
                            "correction_fingerprint",
                        )
                        if correction.get(key) is not None
                    },
                    sort_keys=True,
                ),
                "candidate_skill_id": mapping.canonical_skill_id,
                "candidate_skill_name": _skill_name(mapping.canonical_skill_id),
                "mapping_rule": mapping.provenance.get("skill_mapping_rule_version") or "",
                "mapping_reason": mapping.reason,
                "confidence": mapping.confidence,
                "evidence_count": 1,
                "source_distribution": json.dumps({mapping.source_key: 1}),
                "proficiency_distribution": json.dumps(
                    {str(evidence.get("proficiency_label") or "unknown"): 1},
                    sort_keys=True,
                ),
                "ambiguity_reason": (
                    "The source label indicates agreement error but does not prove "
                    "the exact tense/use required by the atomic canonical skill."
                ),
                "current_status": mapping.status,
                "current_review_status": mapping.review_status,
                "reviewer_decision": "NEEDS_REVIEW",
                "reviewer_note": "",
                "reviewed_by": "",
                "reviewed_at": "",
                "_proficiency": str(evidence.get("proficiency_label") or "unknown"),
            }
        )
    return sorted(rows, key=lambda row: row["mapping_id"])


def _build_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        reason_signature = hashlib.sha256(row["mapping_reason"].encode("utf-8")).hexdigest()[:16]
        key = (
            row["source_error_label"],
            row["normalized_error_category"],
            row["normalized_error_subtype"],
            row["candidate_skill_id"],
            row["mapping_rule"],
            reason_signature,
        )
        grouped[key].append(row)
    groups = []
    for key, members in sorted(grouped.items()):
        digest = hashlib.sha256(json.dumps(key).encode("utf-8")).hexdigest()[:16]
        # Source labels broader than an atomic skill need row context; never bulk-approve.
        can_share = False
        groups.append(
            {
                "review_group_id": f"errmap_group__{digest}",
                "member_count": len(members),
                "member_mapping_ids": [row["mapping_id"] for row in members],
                "representative_mapping_ids": [row["mapping_id"] for row in members[:5]],
                "source_distribution": dict(
                    sorted(Counter(row["source_key"] for row in members).items())
                ),
                "proficiency_distribution": dict(
                    sorted(Counter(row["_proficiency"] for row in members).items())
                ),
                "candidate_skill_id": key[3],
                "normalized_error_category": key[1],
                "normalized_error_subtype": key[2],
                "confidence_min": min(float(row["confidence"]) for row in members),
                "confidence_max": max(float(row["confidence"]) for row in members),
                "reason": members[0]["mapping_reason"],
                "group_can_share_decision": can_share,
                "group_decision_note": (
                    "Grouping is for review navigation only. Each learner-error context "
                    "must be reviewed separately because the source label is broader than "
                    "the atomic skill."
                ),
            }
        )
    return groups


def _preserve_legacy_review(review_path: Path, legacy_path: Path) -> int:
    if not review_path.exists():
        return _csv_row_count(legacy_path)
    with review_path.open("r", encoding="utf-8-sig", newline="") as handle:
        fieldnames = (csv.DictReader(handle).fieldnames or [])
    if "mapping_id" not in fieldnames:
        if not legacy_path.exists():
            shutil.copyfile(review_path, legacy_path)
        return _csv_row_count(legacy_path)
    return _csv_row_count(legacy_path)


def _existing_decisions(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    decisions = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            mapping_id = (row.get("mapping_id") or "").strip()
            decision = (row.get("reviewer_decision") or "").strip()
            if mapping_id and decision:
                decisions[mapping_id] = {field: row.get(field, "") for field in DECISION_FIELDS}
    return decisions


def _load_row_decisions(
    path: Path,
    mapping_by_id: dict[str, ErrorSkillMapping],
    issues: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    decisions: dict[str, dict[str, str]] = {}
    if not path.exists():
        issues.append(_issue("error", "missing_decisions", f"Decision file not found: {path}"))
        return decisions
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for line_number, row in enumerate(csv.DictReader(handle), start=2):
            mapping_id = (row.get("mapping_id") or "").strip()
            if mapping_id not in mapping_by_id:
                issues.append(
                    _issue("error", "unknown_mapping_id", f"{path}:{line_number}: {mapping_id}")
                )
                continue
            if mapping_id in decisions:
                issues.append(
                    _issue("error", "duplicate_decision", f"Duplicate decision: {mapping_id}")
                )
                continue
            try:
                decision = ReviewDecision.model_validate(
                    {field: row.get(field, "") for field in DECISION_FIELDS}
                )
            except ValidationError as exc:
                issues.append(
                    _issue(
                        "error",
                        "invalid_reviewer_decision",
                        f"{path}:{line_number}: {exc}",
                    )
                )
                continue
            decisions[mapping_id] = decision.model_dump()
    return decisions


def _load_groups(path: Path, issues: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    if not path.exists():
        issues.append(_issue("error", "missing_review_groups", f"Group file not found: {path}"))
        return groups
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            group_id = row["review_group_id"]
            groups[group_id] = {
                **row,
                "group_can_share_decision": row["group_can_share_decision"].lower() == "true",
                "member_mapping_ids": [
                    item for item in row["member_mapping_ids"].split(";") if item
                ],
            }
    return groups


def _load_group_decisions(
    path: Path,
    groups: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    decisions: dict[str, dict[str, str]] = {}
    if not path.exists():
        return decisions
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for line_number, row in enumerate(csv.DictReader(handle), start=2):
            if not any(str(value).strip() for value in row.values()):
                continue
            group_id = (row.get("review_group_id") or "").strip()
            if group_id not in groups:
                issues.append(
                    _issue("error", "unknown_review_group", f"{path}:{line_number}: {group_id}")
                )
                continue
            try:
                decision = GroupDecision.model_validate(row)
            except ValidationError as exc:
                issues.append(
                    _issue("error", "invalid_reviewer_decision", f"{path}:{line_number}: {exc}")
                )
                continue
            decisions[group_id] = decision.model_dump()
    return decisions


def _propagate_group_decisions(
    groups: dict[str, dict[str, Any]],
    group_decisions: dict[str, dict[str, str]],
    row_decisions: dict[str, dict[str, str]],
    issues: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    propagated = {}
    for group_id, decision in group_decisions.items():
        group = groups[group_id]
        if not group["group_can_share_decision"]:
            issues.append(
                _issue(
                    "error",
                    "unsafe_group_propagation",
                    f"Group does not permit shared decision: {group_id}",
                )
            )
            continue
        for mapping_id in group["member_mapping_ids"]:
            if mapping_id not in row_decisions:
                propagated[mapping_id] = {
                    "mapping_id": mapping_id,
                    **{key: value for key, value in decision.items() if key != "review_group_id"},
                }
    return propagated


def _apply_decision(
    mapping: ErrorSkillMapping,
    decision: dict[str, str],
    decision_source: str,
) -> dict[str, Any]:
    transitions = {
        "APPROVE": ("accepted", "approved"),
        "REJECT": ("rejected", "rejected"),
        "NEEDS_REVIEW": ("candidate", "needs_review"),
    }
    status, review_status = transitions[decision["reviewer_decision"]]
    payload = mapping.model_dump(mode="json")
    history = list(payload["provenance"].get("review_history", []))
    audit = {
        "reviewer_decision": decision["reviewer_decision"],
        "reviewer_note": decision.get("reviewer_note", ""),
        "reviewed_by": decision.get("reviewed_by", ""),
        "reviewed_at": decision.get("reviewed_at", ""),
        "decision_source": decision_source,
    }
    if not history or history[-1] != audit:
        history.append(audit)
    payload["status"] = status
    payload["review_status"] = review_status
    payload["provenance"] = {
        **payload["provenance"],
        "human_review": audit,
        "review_history": history,
        "review_schema_version": REVIEW_SCHEMA_VERSION,
    }
    return payload


def _validate_outputs(
    reviewed: list[dict[str, Any]],
    accepted: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    unresolved: list[dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    for item in reviewed:
        if item["canonical_skill_id"] not in CANONICAL_GRAMMAR_V1_SKILL_SET:
            issues.append(
                _issue("error", "invalid_skill_reference", item["canonical_skill_id"])
            )
    for item in accepted:
        review = item["provenance"].get("human_review", {})
        if review.get("reviewer_decision") != "APPROVE" or item["review_status"] != "approved":
            issues.append(_issue("error", "accepted_without_approval", item["mapping_id"]))
    accepted_keys = [
        (item["normalized_error_id"], item["canonical_skill_id"]) for item in accepted
    ]
    if len(accepted_keys) != len(set(accepted_keys)):
        issues.append(_issue("error", "duplicate_accepted_mapping", "Duplicate logical mapping"))
    if len(reviewed) != len(accepted) + len(rejected) + len(unresolved):
        issues.append(_issue("error", "mapping_accounting_error", "Mappings not fully partitioned"))


def _recompute_misconception_evidence(
    path: Path,
    accepted_mapping_ids: set[str],
    error_report_path: Path,
    misconception_report_path: Path,
    misconception_review_path: Path,
    accepted_mappings_path: Path,
    evidence_baseline_path: Path,
    *,
    write: bool,
) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    denominators = {}
    if error_report_path.exists():
        denominators = json.loads(error_report_path.read_text(encoding="utf-8")).get(
            "source_error_counts",
            {},
        )
    source_path = evidence_baseline_path if evidence_baseline_path.exists() else path
    candidates: list[dict[str, Any]] = []
    baseline_candidates: list[dict[str, Any]] = []
    before = 0
    after = 0
    with source_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            candidate = json.loads(line)
            baseline_candidates.append(json.loads(line))
            links = candidate.get("evidence_links", [])
            before += len(links)
            kept = [link for link in links if link.get("mapping_id") in accepted_mapping_ids]
            after += len(kept)
            source_distribution = Counter(link["source_key"] for link in kept)
            proficiency_distribution = Counter(
                link.get("proficiency_label") or "unknown" for link in kept
            )
            candidate["evidence_links"] = kept
            candidate["source_evidence_count"] = len(kept)
            candidate["source_distribution"] = dict(sorted(source_distribution.items()))
            candidate["proficiency_distribution"] = dict(
                sorted(proficiency_distribution.items())
            )
            total = sum(int(value) for value in denominators.values())
            candidate["frequency"] = round(len(kept) / total, 8) if total else 0.0
            candidate["source_frequencies"] = {
                source: round(count / int(denominators[source]), 8)
                for source, count in source_distribution.items()
                if int(denominators.get(source, 0))
            }
            candidate["provenance"] = {
                **candidate.get("provenance", {}),
                "approved_mapping_evidence_only": True,
                "source_mapping_count": len(kept),
            }
            MisconceptionCandidate.model_validate(candidate)
            candidates.append(candidate)
    if write:
        if not evidence_baseline_path.exists():
            _write_jsonl(evidence_baseline_path, baseline_candidates)
        _write_jsonl(path, candidates)
        _update_misconception_report(
            misconception_report_path,
            candidates,
            accepted_mappings_path,
        )
        _update_misconception_review(misconception_review_path, candidates)
    return before, after


def _update_misconception_report(
    path: Path,
    candidates: list[dict[str, Any]],
    accepted_mappings_path: Path,
) -> None:
    if not path.exists():
        return
    report = json.loads(path.read_text(encoding="utf-8"))
    source_counts: Counter[str] = Counter()
    proficiency_counts: Counter[str] = Counter()
    skill_counts: Counter[str] = Counter()
    evidence_count = 0
    for candidate in candidates:
        count = int(candidate["source_evidence_count"])
        evidence_count += count
        skill_counts[candidate["canonical_skill_id"]] += count
        source_counts.update(candidate.get("source_distribution", {}))
        proficiency_counts.update(candidate.get("proficiency_distribution", {}))
    report["source_evidence_count"] = evidence_count
    report["mapped_error_count"] = len(accepted_mapping_ids := {
        link["mapping_id"]
        for candidate in candidates
        for link in candidate.get("evidence_links", [])
    })
    report["evidence_counts_by_skill"] = dict(sorted(skill_counts.items()))
    report["evidence_counts_by_source"] = dict(sorted(source_counts.items()))
    report["proficiency_distribution"] = dict(sorted(proficiency_counts.items()))
    report.setdefault("inputs", {})["error_skill_mappings"] = str(
        accepted_mappings_path,
    ).replace("\\", "/")
    report.setdefault("validation", {})["approved_mapping_evidence_only"] = True
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _update_misconception_review(
    path: Path,
    candidates: list[dict[str, Any]],
) -> None:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        rows = list(reader)
    by_id = {candidate["misconception_id"]: candidate for candidate in candidates}
    for row in rows:
        candidate = by_id.get(row.get("misconception_id", ""))
        if not candidate:
            continue
        for field in (
            "source_evidence_count",
            "source_distribution",
            "frequency",
            "source_frequencies",
            "proficiency_distribution",
        ):
            value = candidate[field]
            row[field] = (
                json.dumps(value, sort_keys=True)
                if isinstance(value, dict)
                else str(value)
            )
    _write_csv(path, fields, rows)


def _taxonomy_snapshot() -> dict[str, Any]:
    taxonomy = build_grammar_taxonomy(CANONICAL_GRAMMAR_V1_SKILLS)
    return {
        "atomic_skill_count": len(CANONICAL_GRAMMAR_V1_SKILLS),
        "taxonomy_hash": taxonomy.taxonomy_hash,
        "taxonomy_unchanged": len(CANONICAL_GRAMMAR_V1_SKILLS) == 43,
    }


def _confidence_distribution(records: list[dict[str, Any]]) -> dict[str, int]:
    buckets = Counter()
    for item in records:
        confidence = float(item["confidence"])
        bucket = "0.8-1.0" if confidence >= 0.8 else "0.6-0.79" if confidence >= 0.6 else "0-0.59"
        buckets[bucket] += 1
    return dict(sorted(buckets.items()))


def _skill_name(skill_id: str) -> str:
    return skill_id.rsplit(".", 1)[-1].replace("_", " ").replace(" s", " -s").title()


def _group_fields() -> list[str]:
    return [
        "review_group_id",
        "member_count",
        "member_mapping_ids",
        "representative_mapping_ids",
        "source_distribution",
        "proficiency_distribution",
        "candidate_skill_id",
        "normalized_error_category",
        "normalized_error_subtype",
        "confidence_min",
        "confidence_max",
        "reason",
        "group_can_share_decision",
        "group_decision_note",
    ]


def _group_csv_rows(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            **group,
            "member_mapping_ids": ";".join(group["member_mapping_ids"]),
            "representative_mapping_ids": ";".join(group["representative_mapping_ids"]),
            "source_distribution": json.dumps(group["source_distribution"], sort_keys=True),
            "proficiency_distribution": json.dumps(
                group["proficiency_distribution"],
                sort_keys=True,
            ),
            "group_can_share_decision": str(group["group_can_share_decision"]).lower(),
        }
        for group in groups
    ]


def _write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _csv_row_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _issue(severity: str, code: str, message: str) -> dict[str, str]:
    return {"severity": severity, "code": code, "message": message}
