from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from knowledge_core.sources.egp.models import (
    CEFR_LEVELS,
    DownloadResult,
    EGPConfig,
    RawEGPRecord,
    SourceRecordExclusion,
    ValidationResult,
    now_utc,
)
from knowledge_core.sources.egp.paths import DEFAULT_EGP_REPORTS_DIR, DEFAULT_INTERIM_GRAMMAR_DIR


JSONL_OUTPUT_NAME = "egp_records.jsonl"
PARQUET_OUTPUT_NAME = "egp_records.parquet"
VALIDATION_REPORT_NAME = "validation_report.json"


class EGPOutputError(RuntimeError):
    """Raised when normalized EGP output cannot be written."""


def write_records_jsonl(
    records: Sequence[RawEGPRecord],
    destination: str | Path,
) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(
                json.dumps(
                    record.model_dump(mode="json"),
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )
            handle.write("\n")
    return path


def write_records_parquet(
    records: Sequence[RawEGPRecord],
    destination: str | Path,
) -> Path:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise EGPOutputError(
            "pyarrow is required to write EGP Parquet output",
        ) from exc

    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = pa.schema(
        [
            ("source", pa.string()),
            ("source_record_id", pa.string()),
            ("category_id", pa.string()),
            ("super_category", pa.string()),
            ("sub_category", pa.string()),
            ("cefr_level", pa.string()),
            ("feature_type", pa.string()),
            ("feature_name", pa.string()),
            ("can_do_statement", pa.string()),
            ("example", pa.string()),
            ("details", pa.string()),
            ("source_row_number", pa.int64()),
            ("source_file", pa.string()),
            ("source_url", pa.string()),
            ("retrieved_at", pa.string()),
            ("canonical_parent_hint", pa.string()),
            ("raw_payload", pa.string()),
        ],
    )
    rows = [_parquet_row(record) for record in records]
    table = pa.Table.from_pylist(rows, schema=schema)
    pq.write_table(table, path)
    return path


def write_normalized_outputs(
    records: Sequence[RawEGPRecord],
    interim_dir: str | Path = DEFAULT_INTERIM_GRAMMAR_DIR,
) -> dict[str, Path]:
    output_dir = Path(interim_dir)
    return {
        "jsonl": write_records_jsonl(records, output_dir / JSONL_OUTPUT_NAME),
        "parquet": write_records_parquet(records, output_dir / PARQUET_OUTPUT_NAME),
    }


def write_validation_report(
    report: dict[str, Any],
    reports_dir: str | Path = DEFAULT_EGP_REPORTS_DIR,
) -> Path:
    path = Path(reports_dir) / VALIDATION_REPORT_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return path


def build_validation_report(
    config: EGPConfig,
    validation: ValidationResult,
    *,
    records: Sequence[RawEGPRecord] = (),
    download_results: Sequence[DownloadResult] | None = None,
    empty_files: Sequence[str | Path] = (),
    source_exclusions: Sequence[SourceRecordExclusion] = (),
) -> dict[str, Any]:
    download_results = list(download_results or [])
    issue_payloads = [issue.model_dump(mode="json") for issue in validation.issues]
    return {
        "source": config.source.name,
        "run_at": now_utc().isoformat(),
        "categories": {
            "configured": len(config.categories),
            "downloaded": _count_download_status(download_results, "downloaded"),
            "failed": _count_download_status(download_results, "failed"),
            "skipped": _count_download_status(download_results, "skipped"),
            "dry_run": _count_download_status(download_results, "dry_run"),
        },
        "records": {
            "total": validation.total_records,
            "valid": validation.valid_records,
            "warnings": validation.warning_count,
            "errors": validation.error_count,
        },
        "cefr_distribution": cefr_distribution(records),
        "files": {
            "empty": [str(path) for path in empty_files],
        },
        "source_exclusions": {
            "excluded_records": len(source_exclusions),
            "records": [
                exclusion.model_dump(mode="json")
                for exclusion in source_exclusions
            ],
        },
        "issues": issue_payloads,
        "downloads": [result.model_dump(mode="json") for result in download_results],
    }


def _parquet_row(record: RawEGPRecord) -> dict[str, Any]:
    payload = record.model_dump(mode="json")
    raw_payload = payload.get("raw_payload")
    payload["raw_payload"] = (
        json.dumps(raw_payload, ensure_ascii=False, sort_keys=True)
        if raw_payload is not None
        else None
    )
    return payload


def _count_download_status(
    results: Sequence[DownloadResult],
    status: str,
) -> int:
    return sum(1 for result in results if result.status == status)


def cefr_distribution(records: Sequence[RawEGPRecord]) -> dict[str, int]:
    counts = {level: 0 for level in sorted(CEFR_LEVELS)}
    for record in records:
        if record.cefr_level in counts:
            counts[record.cefr_level] += 1
    return counts
