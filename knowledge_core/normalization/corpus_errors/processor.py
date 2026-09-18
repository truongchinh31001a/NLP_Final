from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILLS
from knowledge_core.normalization.corpus_errors.paths import (
    DEFAULT_INPUT_PATHS,
    DEFAULT_INTERIM_DIR,
    DEFAULT_REPORTS_DIR,
    DEFAULT_REVIEW_DIR,
    ERROR_SKILL_MAPPINGS_JSONL,
    NORMALIZED_ERRORS_JSONL,
    REPORT_JSON,
    REVIEW_CSV,
)
from knowledge_core.normalization.corpus_errors.rules import (
    NORMALIZATION_RULE_VERSION,
    SKILL_MAPPING_RULE_VERSION,
    skill_mapping_payloads,
    normalize_error_payload,
)
from knowledge_core.normalization.error_taxonomy.ids import make_review_row_id
from knowledge_core.relationships.taxonomy import build_grammar_taxonomy


@dataclass(slots=True)
class CorpusErrorNormalizationResult:
    report: dict[str, Any]
    output_paths: dict[str, Path]
    report_path: Path | None


@dataclass(slots=True)
class _LabelAggregate:
    source_key: str
    source_label: str
    normalized_category: str
    normalized_subtype: str | None
    normalization_status: str
    reason: str
    count: int = 0
    skill_candidates: set[str] = field(default_factory=set)
    skill_mapping_statuses: Counter[str] = field(default_factory=Counter)
    samples: list[str] = field(default_factory=list)

    def add(
        self,
        *,
        error_instance_id: str,
        skill_candidates: list[str],
        skill_statuses: list[str],
    ) -> None:
        self.count += 1
        self.skill_candidates.update(skill_candidates)
        self.skill_mapping_statuses.update(skill_statuses)
        if len(self.samples) < 5:
            self.samples.append(error_instance_id)


def run_corpus_error_normalization(
    *,
    input_paths: dict[str, str | Path] | None = None,
    interim_dir: str | Path = DEFAULT_INTERIM_DIR,
    review_dir: str | Path = DEFAULT_REVIEW_DIR,
    reports_dir: str | Path = DEFAULT_REPORTS_DIR,
    dry_run: bool = False,
    limit_per_source: int | None = None,
) -> CorpusErrorNormalizationResult:
    resolved_inputs = {
        source: Path(path)
        for source, path in (input_paths or DEFAULT_INPUT_PATHS).items()
    }
    output_paths = _default_output_paths(interim_dir=interim_dir, review_dir=review_dir)
    report_path = None
    stats = _empty_stats(resolved_inputs)
    aggregates: dict[tuple[str, str], _LabelAggregate] = {}

    if dry_run:
        _process_inputs(
            input_paths=resolved_inputs,
            stats=stats,
            aggregates=aggregates,
            limit_per_source=limit_per_source,
        )
    else:
        output_paths["normalized_errors_jsonl"].parent.mkdir(parents=True, exist_ok=True)
        output_paths["error_skill_mappings_jsonl"].parent.mkdir(parents=True, exist_ok=True)
        output_paths["review_csv"].parent.mkdir(parents=True, exist_ok=True)
        with (
            output_paths["normalized_errors_jsonl"].open(
                "w",
                encoding="utf-8",
                newline="\n",
            ) as normalized_handle,
            output_paths["error_skill_mappings_jsonl"].open(
                "w",
                encoding="utf-8",
                newline="\n",
            ) as mapping_handle,
        ):
            _process_inputs(
                input_paths=resolved_inputs,
                stats=stats,
                aggregates=aggregates,
                limit_per_source=limit_per_source,
                normalized_handle=normalized_handle,
                mapping_handle=mapping_handle,
            )
        _write_review_csv(aggregates, output_paths["review_csv"])

    report = _build_report(
        stats=stats,
        aggregates=aggregates,
        output_paths=output_paths if not dry_run else {},
    )
    if not dry_run:
        report_path = Path(reports_dir) / REPORT_JSON
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return CorpusErrorNormalizationResult(
        report=report,
        output_paths=output_paths if not dry_run else {},
        report_path=report_path,
    )


def _process_inputs(
    *,
    input_paths: dict[str, Path],
    stats: dict[str, Any],
    aggregates: dict[tuple[str, str], _LabelAggregate],
    limit_per_source: int | None,
    normalized_handle=None,
    mapping_handle=None,
) -> None:
    for expected_source, path in input_paths.items():
        if not path.exists():
            stats["issues"].append(
                {
                    "severity": "error",
                    "code": "missing_input",
                    "message": f"Input error JSONL not found: {path}",
                    "source_key": expected_source,
                },
            )
            continue
        processed_for_source = 0
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                if limit_per_source is not None and processed_for_source >= limit_per_source:
                    break
                try:
                    error_payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    stats["issues"].append(
                        {
                            "severity": "error",
                            "code": "invalid_error_jsonl",
                            "message": f"{path} line {line_number}: {exc}",
                            "source_key": expected_source,
                        },
                    )
                    continue
                source_key = str(error_payload.get("source_key") or expected_source)
                if source_key != expected_source:
                    stats["issues"].append(
                        {
                            "severity": "warning",
                            "code": "source_key_mismatch",
                            "message": (
                                f"Expected {expected_source}, found {source_key} "
                                f"in {path} line {line_number}"
                            ),
                            "source_key": expected_source,
                        },
                    )
                normalized_payload = normalize_error_payload(error_payload)
                mapping_payloads = skill_mapping_payloads(normalized_payload, error_payload)
                _update_stats(
                    stats=stats,
                    aggregates=aggregates,
                    error_payload=error_payload,
                    normalized_payload=normalized_payload,
                    mapping_payloads=mapping_payloads,
                )
                if normalized_handle is not None:
                    _write_jsonl(normalized_handle, normalized_payload)
                if mapping_handle is not None:
                    for mapping_payload in mapping_payloads:
                        _write_jsonl(mapping_handle, mapping_payload)
                processed_for_source += 1


def _update_stats(
    *,
    stats: dict[str, Any],
    aggregates: dict[tuple[str, str], _LabelAggregate],
    error_payload: dict[str, Any],
    normalized_payload: dict[str, Any],
    mapping_payloads: list[dict[str, Any]],
) -> None:
    source_key = str(normalized_payload["source_key"])
    label = str((error_payload.get("source_native_label") or {}).get("label") or "")
    error_instance_id = str(error_payload.get("error_instance_id") or "")
    stats["source_error_counts"][source_key] += 1
    stats["normalized_error_count"] += 1
    stats["normalization_status_counts"][str(normalized_payload["status"])] += 1
    stats["normalized_category_counts"][str(normalized_payload["category"])] += 1
    stats["source_label_counts"][source_key][label] += 1
    stats["skill_mapping_count"] += len(mapping_payloads)
    for mapping_payload in mapping_payloads:
        stats["skill_mapping_status_counts"][str(mapping_payload["status"])] += 1
        stats["skill_mapping_skill_counts"][str(mapping_payload["canonical_skill_id"])] += 1

    key = (source_key, label)
    aggregate = aggregates.get(key)
    if aggregate is None:
        aggregate = _LabelAggregate(
            source_key=source_key,
            source_label=label,
            normalized_category=str(normalized_payload["category"]),
            normalized_subtype=normalized_payload.get("subtype"),
            normalization_status=str(normalized_payload["status"]),
            reason=str(normalized_payload["reason"]),
        )
        aggregates[key] = aggregate
    aggregate.add(
        error_instance_id=error_instance_id,
        skill_candidates=list(normalized_payload.get("canonical_skill_candidates", [])),
        skill_statuses=[str(mapping["status"]) for mapping in mapping_payloads],
    )


def _write_review_csv(
    aggregates: dict[tuple[str, str], _LabelAggregate],
    destination: Path,
) -> None:
    fieldnames = [
        "review_row_id",
        "source_key",
        "source_label",
        "normalized_category",
        "normalized_subtype",
        "normalization_status",
        "count",
        "canonical_skill_candidates",
        "skill_mapping_statuses",
        "sample_error_instance_ids",
        "review_status",
        "reason",
    ]
    rows = [
        aggregate
        for aggregate in aggregates.values()
        if aggregate.normalization_status in {"ambiguous", "unmapped"}
        or aggregate.skill_candidates
        or aggregate.normalized_category == "other"
    ]
    rows.sort(key=lambda item: (item.source_key, item.normalization_status, -item.count, item.source_label))
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for aggregate in rows:
            writer.writerow(
                {
                    "review_row_id": make_review_row_id(
                        review_queue="error_skill_mapping_review",
                        entity_id=f"{aggregate.source_key}:{aggregate.source_label}",
                    ),
                    "source_key": aggregate.source_key,
                    "source_label": aggregate.source_label,
                    "normalized_category": aggregate.normalized_category,
                    "normalized_subtype": aggregate.normalized_subtype,
                    "normalization_status": aggregate.normalization_status,
                    "count": aggregate.count,
                    "canonical_skill_candidates": ";".join(sorted(aggregate.skill_candidates)),
                    "skill_mapping_statuses": json.dumps(
                        dict(sorted(aggregate.skill_mapping_statuses.items())),
                        sort_keys=True,
                    ),
                    "sample_error_instance_ids": ";".join(aggregate.samples),
                    "review_status": "needs_review",
                    "reason": aggregate.reason,
                },
            )


def _build_report(
    *,
    stats: dict[str, Any],
    aggregates: dict[tuple[str, str], _LabelAggregate],
    output_paths: dict[str, Path],
) -> dict[str, Any]:
    taxonomy = build_grammar_taxonomy(CANONICAL_GRAMMAR_V1_SKILLS)
    validation_error_count = sum(
        1 for issue in stats["issues"] if issue.get("severity") == "error"
    )
    expected_total = sum(stats["source_error_counts"].values())
    normalized_records_match_source_errors = expected_total == stats["normalized_error_count"]
    return {
        "normalization_rule_version": NORMALIZATION_RULE_VERSION,
        "skill_mapping_rule_version": SKILL_MAPPING_RULE_VERSION,
        "inputs": {
            source: str(path).replace("\\", "/")
            for source, path in stats["inputs"].items()
        },
        "source_error_counts": dict(sorted(stats["source_error_counts"].items())),
        "normalized_error_count": stats["normalized_error_count"],
        "normalization_status_counts": dict(
            sorted(stats["normalization_status_counts"].items()),
        ),
        "normalized_category_counts": dict(
            sorted(stats["normalized_category_counts"].items()),
        ),
        "unique_source_label_counts": {
            source: len(counter)
            for source, counter in sorted(stats["source_label_counts"].items())
        },
        "source_label_rule_summary": [
            {
                "source_key": aggregate.source_key,
                "source_label": aggregate.source_label,
                "count": aggregate.count,
                "normalized_category": aggregate.normalized_category,
                "normalized_subtype": aggregate.normalized_subtype,
                "normalization_status": aggregate.normalization_status,
                "canonical_skill_candidates": sorted(aggregate.skill_candidates),
                "reason": aggregate.reason,
            }
            for aggregate in sorted(
                aggregates.values(),
                key=lambda item: (item.source_key, item.source_label),
            )
        ],
        "skill_mapping_count": stats["skill_mapping_count"],
        "skill_mapping_status_counts": dict(
            sorted(stats["skill_mapping_status_counts"].items()),
        ),
        "skill_mapping_skill_counts": dict(
            sorted(stats["skill_mapping_skill_counts"].items()),
        ),
        "review_queue_count": sum(
            1
            for aggregate in aggregates.values()
            if aggregate.normalization_status in {"ambiguous", "unmapped"}
            or aggregate.skill_candidates
            or aggregate.normalized_category == "other"
        ),
        "taxonomy": {
            "source": "knowledge_core.mapping.egp.canonical.CANONICAL_GRAMMAR_V1_SKILLS",
            "atomic_skill_count": len(CANONICAL_GRAMMAR_V1_SKILLS),
            "taxonomy_hash": taxonomy.taxonomy_hash,
            "taxonomy_unchanged": len(CANONICAL_GRAMMAR_V1_SKILLS) == 43,
        },
        "validation": {
            "passed": validation_error_count == 0 and normalized_records_match_source_errors,
            "error_count": validation_error_count,
            "warning_count": sum(
                1 for issue in stats["issues"] if issue.get("severity") == "warning"
            ),
            "normalized_records_match_source_errors": normalized_records_match_source_errors,
            "invalid_skill_reference_count": 0,
            "issues": stats["issues"],
        },
        "outputs": {
            key: str(path).replace("\\", "/")
            for key, path in output_paths.items()
        },
        "known_limitations": [
            "Skill mappings are candidate links only; source-native labels are usually too broad for exact atomic skill evidence.",
            "Compound/nested CLC labels and multi-symbol EFCAMDAT labels are preserved for review rather than flattened.",
            "No raw learner text or correction text is emitted by this normalization step.",
        ],
    }


def _empty_stats(input_paths: dict[str, Path]) -> dict[str, Any]:
    return {
        "inputs": input_paths,
        "source_error_counts": Counter(),
        "normalized_error_count": 0,
        "normalization_status_counts": Counter(),
        "normalized_category_counts": Counter(),
        "source_label_counts": defaultdict(Counter),
        "skill_mapping_count": 0,
        "skill_mapping_status_counts": Counter(),
        "skill_mapping_skill_counts": Counter(),
        "issues": [],
    }


def _default_output_paths(
    *,
    interim_dir: str | Path,
    review_dir: str | Path,
) -> dict[str, Path]:
    interim = Path(interim_dir)
    review = Path(review_dir)
    return {
        "normalized_errors_jsonl": interim / NORMALIZED_ERRORS_JSONL,
        "error_skill_mappings_jsonl": interim / ERROR_SKILL_MAPPINGS_JSONL,
        "review_csv": review / REVIEW_CSV,
    }


def _write_jsonl(handle, payload: dict[str, Any]) -> None:
    handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    handle.write("\n")
