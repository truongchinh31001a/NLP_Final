from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from knowledge_core.normalization.error_taxonomy.ids import make_review_row_id
from knowledge_core.normalization.error_taxonomy.models import (
    ErrorInstance,
    LearnerCorpusSourceRecord,
)
from knowledge_core.sources.clc_fce.models import CLCFCEXMLAnswerSummary
from knowledge_core.sources.clc_fce.paths import DEFAULT_INTERIM_DIR, DEFAULT_REPORTS_DIR, DEFAULT_REVIEW_DIR, SOURCE_KEY
from knowledge_core.sources.clc_fce.validator import CLCFCEValidationResult


class CLCFCEOutputError(RuntimeError):
    """Raised when CLC FCE outputs cannot be written."""


def write_ingestion_outputs(
    *,
    source_records: Sequence[LearnerCorpusSourceRecord],
    error_instances: Sequence[ErrorInstance],
    interim_dir: str | Path = DEFAULT_INTERIM_DIR,
    review_dir: str | Path = DEFAULT_REVIEW_DIR,
) -> dict[str, Path]:
    interim = Path(interim_dir)
    review = Path(review_dir)
    return {
        "source_records_jsonl": write_jsonl(
            source_records,
            interim / "source_records.jsonl",
        ),
        "error_instances_jsonl": write_jsonl(
            error_instances,
            interim / "error_instances.jsonl",
        ),
        "review_csv": write_review_csv(
            error_instances,
            review / "clc_fce_error_review.csv",
        ),
    }


def build_ingestion_report(
    *,
    source_records: Sequence[LearnerCorpusSourceRecord],
    error_instances: Sequence[ErrorInstance],
    xml_answer_summaries: dict[str, CLCFCEXMLAnswerSummary],
    validation: CLCFCEValidationResult,
    input_files: dict[str, dict[str, str]],
    output_paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    labels = Counter(
        error.source_native_label.label
        for error in error_instances
        if error.source_native_label is not None
    )
    review_errors = [
        error
        for error in error_instances
        if error.review_status in {"needs_review", "pending"}
        and (
            error.parser_notes
            or (
                error.source_native_label is not None
                and _is_compound_label(error.source_native_label.label)
            )
        )
    ]
    return {
        "source_key": SOURCE_KEY,
        "source_name": "Cambridge Learner Corpus FCE",
        "parser": "clc_fce_ingestion_v1",
        "input_files": input_files,
        "source_record_count": len(source_records),
        "error_instance_count": len(error_instances),
        "source_record_counts_by_split": validation.source_record_counts_by_split,
        "error_counts_by_split": validation.error_counts_by_split,
        "unique_error_label_count": len(labels),
        "top_error_labels": [
            {"label": label, "count": count}
            for label, count in labels.most_common(25)
        ],
        "xml_answer_summary_count": len(xml_answer_summaries),
        "xml_error_node_count": sum(
            summary.error_count for summary in xml_answer_summaries.values()
        ),
        "xml_nested_error_count": validation.xml_nested_error_count,
        "xml_max_error_depth": max(
            (summary.max_error_depth for summary in xml_answer_summaries.values()),
            default=0,
        ),
        "review_queue_count": len(review_errors),
        "validation": validation.model_dump(mode="json"),
        "privacy": {
            "raw_learner_text_emitted": False,
            "text_storage_policy": "sha256_fingerprint_and_length_only",
            "correction_storage_policy": "sha256_fingerprint_and_length_only",
        },
        "outputs": {
            key: str(path).replace("\\", "/")
            for key, path in (output_paths or {}).items()
        },
        "definition_of_done_satisfied": validation.passed,
    }


def write_ingestion_report(
    report: dict[str, Any],
    reports_dir: str | Path = DEFAULT_REPORTS_DIR,
) -> Path:
    return write_json(report, Path(reports_dir) / "ingestion_report.json")


def write_jsonl(records: Sequence[Any], destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            payload = record.model_dump(mode="json") if hasattr(record, "model_dump") else record
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    return path


def write_json(payload: Any, destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def write_review_csv(
    error_instances: Sequence[ErrorInstance],
    destination: str | Path,
) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "review_row_id",
        "error_instance_id",
        "source_record_id",
        "source_key",
        "native_error_id",
        "label",
        "span_kind",
        "start_char",
        "end_char",
        "correction_type",
        "review_status",
        "reason",
    ]
    rows = []
    for error in error_instances:
        label = error.source_native_label.label if error.source_native_label else ""
        reason_parts = list(error.parser_notes)
        if _is_compound_label(label):
            reason_parts.append("compound_source_label")
        if not reason_parts:
            continue
        rows.append(
            {
                "review_row_id": make_review_row_id(
                    review_queue="clc_fce_error_review",
                    entity_id=error.error_instance_id,
                ),
                "error_instance_id": error.error_instance_id,
                "source_record_id": error.source_record_id,
                "source_key": error.source_key,
                "native_error_id": error.native_error_id,
                "label": label,
                "span_kind": error.span.span_kind,
                "start_char": error.span.start_char,
                "end_char": error.span.end_char,
                "correction_type": error.correction.correction_type if error.correction else None,
                "review_status": error.review_status,
                "reason": ";".join(sorted(set(reason_parts))),
            },
        )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _is_compound_label(label: str) -> bool:
    return "(" in label or ")" in label

