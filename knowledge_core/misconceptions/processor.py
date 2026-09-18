from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILLS
from knowledge_core.misconceptions.models import (
    MISCONCEPTION_SCHEMA_VERSION,
    MisconceptionCandidate,
    MisconceptionEvidenceLink,
)
from knowledge_core.misconceptions.paths import (
    ACCEPTED_MISCONCEPTIONS_JSONL,
    CANDIDATE_MISCONCEPTIONS_JSONL,
    DEFAULT_CURATED_DIR,
    DEFAULT_ERROR_NORMALIZATION_REPORT,
    DEFAULT_ERROR_SKILL_MAPPINGS_PATH,
    DEFAULT_INTERIM_DIR,
    DEFAULT_NORMALIZED_ERRORS_PATH,
    DEFAULT_REPORTS_DIR,
    DEFAULT_REVIEW_DIR,
    DEFAULT_SOURCE_RECORD_PATHS,
    MISCONCEPTION_REPORT_JSON,
    MISCONCEPTION_REVIEW_CSV,
)
from knowledge_core.misconceptions.rules import (
    MISCONCEPTION_MINING_RULE_VERSION,
    confidence_for,
    make_misconception_id,
    pattern_rule_for,
    severity_for,
)
from knowledge_core.normalization.corpus_errors.models import ErrorSkillMapping
from knowledge_core.normalization.error_taxonomy.ids import make_review_row_id
from knowledge_core.normalization.error_taxonomy.models import (
    LearnerCorpusSourceRecord,
    NormalizedErrorInstance,
)
from knowledge_core.relationships.taxonomy import build_grammar_taxonomy


@dataclass(slots=True)
class MisconceptionMiningResult:
    candidates: list[MisconceptionCandidate]
    accepted: list[MisconceptionCandidate]
    report: dict[str, Any]
    output_paths: dict[str, Path]
    report_path: Path | None


@dataclass(slots=True)
class _PendingEvidence:
    mapping: ErrorSkillMapping
    normalized: NormalizedErrorInstance


@dataclass(slots=True)
class _CandidateAggregate:
    canonical_skill_id: str
    error_category: str
    error_subtype: str | None
    evidence: list[_PendingEvidence] = field(default_factory=list)
    source_labels: set[str] = field(default_factory=set)
    source_distribution: Counter[str] = field(default_factory=Counter)
    mapping_confidences: list[float] = field(default_factory=list)

    def add(self, mapping: ErrorSkillMapping, normalized: NormalizedErrorInstance) -> None:
        self.evidence.append(_PendingEvidence(mapping=mapping, normalized=normalized))
        label = normalized.metadata.get("source_label")
        if isinstance(label, str) and label:
            self.source_labels.add(label)
        self.source_distribution[normalized.source_key] += 1
        self.mapping_confidences.append(mapping.confidence)


def run_misconception_mining(
    *,
    normalized_errors_path: str | Path = DEFAULT_NORMALIZED_ERRORS_PATH,
    error_skill_mappings_path: str | Path = DEFAULT_ERROR_SKILL_MAPPINGS_PATH,
    error_normalization_report: str | Path = DEFAULT_ERROR_NORMALIZATION_REPORT,
    source_record_paths: dict[str, str | Path] | None = None,
    interim_dir: str | Path = DEFAULT_INTERIM_DIR,
    curated_dir: str | Path = DEFAULT_CURATED_DIR,
    review_dir: str | Path = DEFAULT_REVIEW_DIR,
    reports_dir: str | Path = DEFAULT_REPORTS_DIR,
    dry_run: bool = False,
) -> MisconceptionMiningResult:
    mapping_path = Path(error_skill_mappings_path)
    normalized_path = Path(normalized_errors_path)
    report_input_path = Path(error_normalization_report)
    source_paths = {
        source: Path(path)
        for source, path in (source_record_paths or DEFAULT_SOURCE_RECORD_PATHS).items()
    }
    output_paths = _default_output_paths(
        interim_dir=interim_dir,
        curated_dir=curated_dir,
        review_dir=review_dir,
    )
    issues: list[dict[str, Any]] = []
    mappings_by_normalized = _load_skill_mappings(mapping_path, issues)
    aggregates = _aggregate_candidates(
        normalized_path=normalized_path,
        mappings_by_normalized=mappings_by_normalized,
        issues=issues,
    )
    source_denominators = _load_source_error_counts(report_input_path, issues)
    source_records = _load_needed_source_records(
        source_paths=source_paths,
        source_record_ids_by_source=_needed_source_record_ids(aggregates),
        issues=issues,
    )
    candidates = _build_candidates(
        aggregates=aggregates,
        source_records=source_records,
        source_denominators=source_denominators,
    )
    accepted = [candidate for candidate in candidates if candidate.review_status == "approved"]
    report = _build_report(
        candidates=candidates,
        accepted=accepted,
        mappings_by_normalized=mappings_by_normalized,
        source_denominators=source_denominators,
        issues=issues,
        inputs={
            "normalized_errors": normalized_path,
            "error_skill_mappings": mapping_path,
            "error_normalization_report": report_input_path,
            **{f"{source}_source_records": path for source, path in source_paths.items()},
        },
        output_paths=output_paths if not dry_run else {},
    )
    report_path = None
    if not dry_run:
        _write_jsonl(candidates, output_paths["candidate_misconceptions_jsonl"])
        _write_jsonl(accepted, output_paths["accepted_misconceptions_jsonl"])
        _write_review_csv(candidates, output_paths["review_csv"])
        report_path = Path(reports_dir) / MISCONCEPTION_REPORT_JSON
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return MisconceptionMiningResult(
        candidates=candidates,
        accepted=accepted,
        report=report,
        output_paths=output_paths if not dry_run else {},
        report_path=report_path,
    )


def _load_skill_mappings(
    path: Path,
    issues: list[dict[str, Any]],
) -> dict[str, list[ErrorSkillMapping]]:
    mappings: dict[str, list[ErrorSkillMapping]] = defaultdict(list)
    if not path.exists():
        issues.append(
            {
                "severity": "error",
                "code": "missing_error_skill_mappings",
                "message": f"Input file not found: {path}",
            },
        )
        return mappings
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                mapping = ErrorSkillMapping.model_validate(json.loads(line))
            except Exception as exc:  # noqa: BLE001 - include validation context in report.
                issues.append(
                    {
                        "severity": "error",
                        "code": "invalid_error_skill_mapping",
                        "message": f"{path} line {line_number}: {exc}",
                    },
                )
                continue
            mappings[mapping.normalized_error_id].append(mapping)
    return mappings


def _aggregate_candidates(
    *,
    normalized_path: Path,
    mappings_by_normalized: dict[str, list[ErrorSkillMapping]],
    issues: list[dict[str, Any]],
) -> dict[tuple[str, str, str | None], _CandidateAggregate]:
    aggregates: dict[tuple[str, str, str | None], _CandidateAggregate] = {}
    if not normalized_path.exists():
        issues.append(
            {
                "severity": "error",
                "code": "missing_normalized_errors",
                "message": f"Input file not found: {normalized_path}",
            },
        )
        return aggregates
    needed_ids = set(mappings_by_normalized)
    seen_needed: set[str] = set()
    with normalized_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                issues.append(
                    {
                        "severity": "error",
                        "code": "invalid_normalized_error_json",
                        "message": f"{normalized_path} line {line_number}: {exc}",
                    },
                )
                continue
            normalized_id = str(payload.get("normalized_error_id") or "")
            if normalized_id not in needed_ids:
                continue
            try:
                normalized = NormalizedErrorInstance.model_validate(payload)
            except Exception as exc:  # noqa: BLE001
                issues.append(
                    {
                        "severity": "error",
                        "code": "invalid_normalized_error",
                        "message": f"{normalized_path} line {line_number}: {exc}",
                    },
                )
                continue
            seen_needed.add(normalized_id)
            for mapping in mappings_by_normalized[normalized_id]:
                key = (mapping.canonical_skill_id, normalized.category, normalized.subtype)
                aggregate = aggregates.get(key)
                if aggregate is None:
                    aggregate = _CandidateAggregate(
                        canonical_skill_id=mapping.canonical_skill_id,
                        error_category=normalized.category,
                        error_subtype=normalized.subtype,
                    )
                    aggregates[key] = aggregate
                aggregate.add(mapping, normalized)
    missing = needed_ids - seen_needed
    if missing:
        issues.append(
            {
                "severity": "error",
                "code": "missing_normalized_mapping_references",
                "message": f"{len(missing)} mapped normalized error ids were not found.",
                "sample_ids": sorted(missing)[:10],
            },
        )
    return aggregates


def _load_source_error_counts(path: Path, issues: list[dict[str, Any]]) -> dict[str, int]:
    if not path.exists():
        issues.append(
            {
                "severity": "warning",
                "code": "missing_error_normalization_report",
                "message": f"Frequency denominators unavailable: {path}",
            },
        )
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(
            {
                "severity": "warning",
                "code": "invalid_error_normalization_report",
                "message": f"{path}: {exc}",
            },
        )
        return {}
    counts = payload.get("source_error_counts", {})
    return {
        str(source): int(count)
        for source, count in counts.items()
        if isinstance(count, int)
    }


def _needed_source_record_ids(
    aggregates: dict[tuple[str, str, str | None], _CandidateAggregate],
) -> dict[str, set[str]]:
    needed: dict[str, set[str]] = defaultdict(set)
    for aggregate in aggregates.values():
        for item in aggregate.evidence:
            needed[item.normalized.source_key].add(item.normalized.source_record_id)
    return needed


def _load_needed_source_records(
    *,
    source_paths: dict[str, Path],
    source_record_ids_by_source: dict[str, set[str]],
    issues: list[dict[str, Any]],
) -> dict[str, LearnerCorpusSourceRecord]:
    records: dict[str, LearnerCorpusSourceRecord] = {}
    for source, needed_ids in source_record_ids_by_source.items():
        if not needed_ids:
            continue
        path = source_paths.get(source)
        if path is None or not path.exists():
            issues.append(
                {
                    "severity": "warning",
                    "code": "missing_source_records",
                    "message": f"Source records unavailable for {source}: {path}",
                },
            )
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    issues.append(
                        {
                            "severity": "warning",
                            "code": "invalid_source_record_json",
                            "message": f"{path} line {line_number}: {exc}",
                        },
                    )
                    continue
                source_record_id = str(payload.get("source_record_id") or "")
                if source_record_id not in needed_ids:
                    continue
                try:
                    records[source_record_id] = LearnerCorpusSourceRecord.model_validate(payload)
                except Exception as exc:  # noqa: BLE001
                    issues.append(
                        {
                            "severity": "warning",
                            "code": "invalid_source_record",
                            "message": f"{path} line {line_number}: {exc}",
                            "source_record_id": source_record_id,
                        },
                    )
                if len(needed_ids & set(records)) == len(needed_ids):
                    break
    return records


def _build_candidates(
    *,
    aggregates: dict[tuple[str, str, str | None], _CandidateAggregate],
    source_records: dict[str, LearnerCorpusSourceRecord],
    source_denominators: dict[str, int],
) -> list[MisconceptionCandidate]:
    candidates: list[MisconceptionCandidate] = []
    total_denominator = sum(source_denominators.values()) or sum(
        len(aggregate.evidence) for aggregate in aggregates.values()
    )
    for aggregate in aggregates.values():
        source_labels = sorted(aggregate.source_labels)
        rule = pattern_rule_for(
            canonical_skill_id=aggregate.canonical_skill_id,
            error_category=aggregate.error_category,
            error_subtype=aggregate.error_subtype,
            source_labels=source_labels,
        )
        evidence_links = [
            _evidence_link(item, source_records.get(item.normalized.source_record_id))
            for item in aggregate.evidence
        ]
        proficiency_distribution = Counter(
            link.proficiency_label or "unknown"
            for link in evidence_links
        )
        source_distribution = dict(sorted(aggregate.source_distribution.items()))
        source_frequencies = {
            source: round(count / source_denominators[source], 8)
            for source, count in source_distribution.items()
            if source_denominators.get(source)
        }
        max_source_frequency = max(source_frequencies.values(), default=0.0)
        evidence_count = len(evidence_links)
        average_mapping_confidence = (
            sum(aggregate.mapping_confidences) / len(aggregate.mapping_confidences)
            if aggregate.mapping_confidences
            else 0.0
        )
        misconception_id = make_misconception_id(
            canonical_skill_id=aggregate.canonical_skill_id,
            pattern_key=rule.pattern_key,
            error_category=aggregate.error_category,
            error_subtype=aggregate.error_subtype,
            source_labels=source_labels,
        )
        candidates.append(
            MisconceptionCandidate(
                misconception_id=misconception_id,
                canonical_skill_id=aggregate.canonical_skill_id,
                name=rule.name,
                description=rule.description,
                error_category=aggregate.error_category,
                error_subtype=aggregate.error_subtype,
                source_labels=source_labels,
                expected_pattern=rule.expected_pattern,
                observed_pattern=rule.observed_pattern,
                diagnostic_rule=rule.diagnostic_rule,
                source_evidence_count=evidence_count,
                source_distribution=source_distribution,
                frequency=round(evidence_count / total_denominator, 8)
                if total_denominator
                else 0.0,
                frequency_scope=(
                    "all normalized CLC FCE and EFCAMDAT error instances from "
                    "corpus_error_normalization_rules_v1"
                ),
                source_frequencies=source_frequencies,
                proficiency_distribution=dict(sorted(proficiency_distribution.items())),
                evidence_links=evidence_links,
                severity=severity_for(
                    evidence_count=evidence_count,
                    max_source_frequency=max_source_frequency,
                ),
                confidence=confidence_for(
                    average_mapping_confidence=average_mapping_confidence,
                    evidence_count=evidence_count,
                    source_count=len(source_distribution),
                ),
                status="candidate",
                review_status="pending",
                reason=rule.reason,
                provenance={
                    "created_by": MISCONCEPTION_MINING_RULE_VERSION,
                    "pattern_key": rule.pattern_key,
                    "source_mapping_count": evidence_count,
                    "human_review_required_before_acceptance": True,
                },
            ),
        )
    return sorted(
        candidates,
        key=lambda candidate: (
            candidate.canonical_skill_id,
            candidate.error_category,
            candidate.error_subtype or "",
            candidate.misconception_id,
        ),
    )


def _evidence_link(
    item: _PendingEvidence,
    source_record: LearnerCorpusSourceRecord | None,
) -> MisconceptionEvidenceLink:
    normalized = item.normalized
    label = normalized.metadata.get("source_label")
    return MisconceptionEvidenceLink(
        normalized_error_id=normalized.normalized_error_id,
        error_instance_id=normalized.error_instance_id,
        source_record_id=normalized.source_record_id,
        source_key=normalized.source_key,
        source_label=label if isinstance(label, str) else None,
        proficiency_label=source_record.proficiency_label if source_record else None,
        task_id=source_record.task_id if source_record else None,
        split=source_record.split if source_record else None,
        mapping_id=item.mapping.mapping_id,
        mapping_confidence=item.mapping.confidence,
    )


def _build_report(
    *,
    candidates: list[MisconceptionCandidate],
    accepted: list[MisconceptionCandidate],
    mappings_by_normalized: dict[str, list[ErrorSkillMapping]],
    source_denominators: dict[str, int],
    issues: list[dict[str, Any]],
    inputs: dict[str, Path],
    output_paths: dict[str, Path],
) -> dict[str, Any]:
    taxonomy = build_grammar_taxonomy(CANONICAL_GRAMMAR_V1_SKILLS)
    error_count = sum(1 for issue in issues if issue.get("severity") == "error")
    warning_count = sum(1 for issue in issues if issue.get("severity") == "warning")
    evidence_count = sum(candidate.source_evidence_count for candidate in candidates)
    return {
        "schema_version": MISCONCEPTION_SCHEMA_VERSION,
        "mining_rule_version": MISCONCEPTION_MINING_RULE_VERSION,
        "inputs": {
            key: str(path).replace("\\", "/")
            for key, path in inputs.items()
        },
        "candidate_count": len(candidates),
        "accepted_count": len(accepted),
        "review_queue_count": len(candidates),
        "source_evidence_count": evidence_count,
        "mapped_error_count": sum(len(values) for values in mappings_by_normalized.values()),
        "candidate_counts_by_skill": dict(
            sorted(Counter(candidate.canonical_skill_id for candidate in candidates).items()),
        ),
        "evidence_counts_by_skill": dict(
            sorted(
                Counter(
                    {
                        candidate.canonical_skill_id: candidate.source_evidence_count
                        for candidate in candidates
                    },
                ).items(),
            ),
        ),
        "evidence_counts_by_source": dict(
            sorted(
                sum(
                    (Counter(candidate.source_distribution) for candidate in candidates),
                    Counter(),
                ).items(),
            ),
        ),
        "proficiency_distribution": dict(
            sorted(
                sum(
                    (
                        Counter(candidate.proficiency_distribution)
                        for candidate in candidates
                    ),
                    Counter(),
                ).items(),
            ),
        ),
        "frequency_denominators": source_denominators,
        "taxonomy": {
            "source": "knowledge_core.mapping.egp.canonical.CANONICAL_GRAMMAR_V1_SKILLS",
            "atomic_skill_count": len(CANONICAL_GRAMMAR_V1_SKILLS),
            "taxonomy_hash": taxonomy.taxonomy_hash,
            "taxonomy_unchanged": len(CANONICAL_GRAMMAR_V1_SKILLS) == 43,
        },
        "validation": {
            "passed": error_count == 0,
            "error_count": error_count,
            "warning_count": warning_count,
            "issues": issues,
            "accepted_requires_human_review": all(
                candidate.review_status == "approved"
                for candidate in accepted
            ),
            "raw_text_emitted": False,
        },
        "outputs": {
            key: str(path).replace("\\", "/")
            for key, path in output_paths.items()
        },
        "known_limitations": [
            "Only normalized errors with existing error-skill mappings are mined into misconception candidates.",
            "Candidates are not canonical misconceptions until human review approves them.",
            "No raw learner text or corrected text is emitted.",
        ],
    }


def _default_output_paths(
    *,
    interim_dir: str | Path,
    curated_dir: str | Path,
    review_dir: str | Path,
) -> dict[str, Path]:
    interim = Path(interim_dir)
    curated = Path(curated_dir)
    review = Path(review_dir)
    return {
        "candidate_misconceptions_jsonl": interim / CANDIDATE_MISCONCEPTIONS_JSONL,
        "accepted_misconceptions_jsonl": curated / ACCEPTED_MISCONCEPTIONS_JSONL,
        "review_csv": review / MISCONCEPTION_REVIEW_CSV,
    }


def _write_jsonl(records: list[MisconceptionCandidate], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def _write_review_csv(candidates: list[MisconceptionCandidate], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "review_row_id",
        "misconception_id",
        "canonical_skill_id",
        "name",
        "error_category",
        "error_subtype",
        "source_labels",
        "source_evidence_count",
        "source_distribution",
        "frequency",
        "source_frequencies",
        "proficiency_distribution",
        "severity",
        "confidence",
        "status",
        "review_status",
        "reason",
    ]
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for candidate in candidates:
            writer.writerow(
                {
                    "review_row_id": make_review_row_id(
                        review_queue="misconception_review",
                        entity_id=candidate.misconception_id,
                    ),
                    "misconception_id": candidate.misconception_id,
                    "canonical_skill_id": candidate.canonical_skill_id,
                    "name": candidate.name,
                    "error_category": candidate.error_category,
                    "error_subtype": candidate.error_subtype,
                    "source_labels": ";".join(candidate.source_labels),
                    "source_evidence_count": candidate.source_evidence_count,
                    "source_distribution": json.dumps(
                        candidate.source_distribution,
                        sort_keys=True,
                    ),
                    "frequency": candidate.frequency,
                    "source_frequencies": json.dumps(
                        candidate.source_frequencies,
                        sort_keys=True,
                    ),
                    "proficiency_distribution": json.dumps(
                        candidate.proficiency_distribution,
                        sort_keys=True,
                    ),
                    "severity": candidate.severity,
                    "confidence": candidate.confidence,
                    "status": candidate.status,
                    "review_status": candidate.review_status,
                    "reason": candidate.reason,
                },
            )
