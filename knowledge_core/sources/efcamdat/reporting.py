from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from knowledge_core.normalization.error_taxonomy.ids import make_review_row_id
from knowledge_core.normalization.error_taxonomy.models import ErrorInstance
from knowledge_core.sources.efcamdat.models import EFCAMDATCSVSupportSummary, EFCAMDATIngestionCounters
from knowledge_core.sources.efcamdat.paths import DEFAULT_INTERIM_DIR, DEFAULT_REPORTS_DIR, DEFAULT_REVIEW_DIR, SOURCE_KEY
from knowledge_core.sources.efcamdat.validator import EFCAMDATValidationSummary


class EFCAMDATOutputError(RuntimeError):
    """Raised when EFCAMDAT outputs cannot be written."""


def open_jsonl(path: str | Path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination.open("w", encoding="utf-8", newline="\n")


def write_jsonl_record(handle, record: Any) -> None:
    payload = record.model_dump(mode="json") if hasattr(record, "model_dump") else record
    handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    handle.write("\n")


def review_row_for_error(error: ErrorInstance) -> dict[str, Any] | None:
    if not error.parser_notes and error.review_status != "needs_review":
        return None
    label = error.source_native_label.label if error.source_native_label else ""
    return {
        "review_row_id": make_review_row_id(
            review_queue="efcamdat_error_review",
            entity_id=error.error_instance_id,
        ),
        "error_instance_id": error.error_instance_id,
        "source_record_id": error.source_record_id,
        "native_error_id": error.native_error_id,
        "label": label,
        "span_kind": error.span.span_kind,
        "selected_text_length": error.span.selected_text_length,
        "correction_type": error.correction.correction_type if error.correction else None,
        "review_status": error.review_status,
        "reason": ";".join(sorted(set(error.parser_notes))),
    }


def write_review_header(handle) -> csv.DictWriter:
    fieldnames = [
        "review_row_id",
        "error_instance_id",
        "source_record_id",
        "native_error_id",
        "label",
        "span_kind",
        "selected_text_length",
        "correction_type",
        "review_status",
        "reason",
    ]
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    writer.writeheader()
    return writer


def build_ingestion_report(
    *,
    counters: EFCAMDATIngestionCounters,
    labels: Counter[str],
    levels: Counter[str],
    csv_support: EFCAMDATCSVSupportSummary,
    validation: EFCAMDATValidationSummary,
    output_paths: dict[str, Path],
    xml_path: Path,
) -> dict[str, Any]:
    return {
        "source_key": SOURCE_KEY,
        "source_name": "EFCAMDAT",
        "parser": "efcamdat_ingestion_v1",
        "xml_source_file": str(xml_path).replace("\\", "/"),
        "annotation_source_of_truth": "xml_change_markup",
        "source_record_count": counters.source_record_count,
        "changed_writing_count": counters.changed_writing_count,
        "error_instance_count": counters.error_instance_count,
        "parser_fallback_count": counters.parser_fallback_count,
        "malformed_writing_count": counters.malformed_writing_count,
        "review_queue_count": counters.review_queue_count,
        "unique_error_label_count": len(labels),
        "top_error_labels": [
            {"label": label, "count": count}
            for label, count in labels.most_common(30)
        ],
        "level_distribution": dict(sorted(levels.items())),
        "csv_support": {
            "path": str(csv_support.path).replace("\\", "/"),
            "row_count": csv_support.row_count,
            "chunk_count": csv_support.chunk_count,
            "fieldnames": list(csv_support.fieldnames),
            "rows_with_text_change_markup": csv_support.rows_with_text_change_markup,
            "rows_with_support_field_change_markup": (
                csv_support.rows_with_support_field_change_markup
            ),
            "unique_writing_id_count": csv_support.unique_writing_id_count,
            "usage": "derived_support_only",
        },
        "privacy": {
            "raw_learner_text_emitted": False,
            "text_storage_policy": "sha256_fingerprint_and_length_only",
            "correction_storage_policy": "sha256_fingerprint_and_length_only",
        },
        "validation": validation.to_dict(),
        "outputs": {
            key: str(path).replace("\\", "/")
            for key, path in output_paths.items()
        },
        "definition_of_done_satisfied": validation.passed,
    }


def write_report(report: dict[str, Any], reports_dir: str | Path = DEFAULT_REPORTS_DIR) -> Path:
    path = Path(reports_dir) / "ingestion_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def default_output_paths(
    *,
    interim_dir: str | Path = DEFAULT_INTERIM_DIR,
    review_dir: str | Path = DEFAULT_REVIEW_DIR,
) -> dict[str, Path]:
    interim = Path(interim_dir)
    review = Path(review_dir)
    return {
        "source_records_jsonl": interim / "source_records.jsonl",
        "error_instances_jsonl": interim / "error_instances.jsonl",
        "review_csv": review / "efcamdat_error_review.csv",
    }

