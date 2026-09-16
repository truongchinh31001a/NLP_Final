from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from knowledge_core.sources.cefr.models import (
    CEFRConfig,
    CEFRDescriptorRecord,
    CEFRLearningObjectiveCandidate,
    CEFRValidationResult,
    now_utc,
)
from knowledge_core.sources.cefr.parser import ParsedCEFRDataset
from knowledge_core.sources.cefr.paths import (
    DEFAULT_CEFR_INTERIM_DIR,
    DEFAULT_CEFR_REPORTS_DIR,
)


DESCRIPTOR_JSONL_OUTPUT_NAME = "cefr_descriptors.jsonl"
DESCRIPTOR_PARQUET_OUTPUT_NAME = "cefr_descriptors.parquet"
OBJECTIVE_JSONL_OUTPUT_NAME = "cefr_learning_objective_candidates.jsonl"
OBJECTIVE_PARQUET_OUTPUT_NAME = "cefr_learning_objective_candidates.parquet"
SOURCE_INSPECTION_REPORT_NAME = "source_inspection_report.json"
EXTRACTION_REPORT_NAME = "extraction_report.json"


class CEFROutputError(RuntimeError):
    """Raised when CEFR output cannot be written."""


def write_descriptor_outputs(
    records: Sequence[CEFRDescriptorRecord],
    interim_dir: str | Path = DEFAULT_CEFR_INTERIM_DIR,
) -> dict[str, Path]:
    output_dir = Path(interim_dir)
    return {
        "jsonl": write_jsonl(records, output_dir / DESCRIPTOR_JSONL_OUTPUT_NAME),
        "parquet": write_descriptors_parquet(
            records,
            output_dir / DESCRIPTOR_PARQUET_OUTPUT_NAME,
        ),
    }


def write_objective_outputs(
    candidates: Sequence[CEFRLearningObjectiveCandidate],
    interim_dir: str | Path = DEFAULT_CEFR_INTERIM_DIR,
) -> dict[str, Path]:
    output_dir = Path(interim_dir)
    return {
        "jsonl": write_jsonl(candidates, output_dir / OBJECTIVE_JSONL_OUTPUT_NAME),
        "parquet": write_objectives_parquet(
            candidates,
            output_dir / OBJECTIVE_PARQUET_OUTPUT_NAME,
        ),
    }


def write_jsonl(records: Sequence[Any], destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            payload = (
                record.model_dump(mode="json")
                if hasattr(record, "model_dump")
                else record
            )
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    return path


def write_descriptors_parquet(
    records: Sequence[CEFRDescriptorRecord],
    destination: str | Path,
) -> Path:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise CEFROutputError(
            "pyarrow is required to write CEFR Parquet output",
        ) from exc

    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = pa.schema(
        [
            ("source", pa.string()),
            ("source_document", pa.string()),
            ("source_year", pa.int64()),
            ("source_record_id", pa.string()),
            ("chapter", pa.string()),
            ("section", pa.string()),
            ("domain", pa.string()),
            ("subdomain", pa.string()),
            ("scale_name", pa.string()),
            ("descriptor_type", pa.string()),
            ("cefr_level", pa.string()),
            ("descriptor_text", pa.string()),
            ("descriptor_available", pa.bool_()),
            ("reference_level", pa.string()),
            ("page_number", pa.int64()),
            ("source_table", pa.string()),
            ("is_pre_a1", pa.bool_()),
            ("source_file", pa.string()),
            ("raw_payload", pa.string()),
        ],
    )
    rows = [_descriptor_parquet_row(record) for record in records]
    table = pa.Table.from_pylist(rows, schema=schema)
    pq.write_table(table, path)
    return path


def write_objectives_parquet(
    candidates: Sequence[CEFRLearningObjectiveCandidate],
    destination: str | Path,
) -> Path:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise CEFROutputError(
            "pyarrow is required to write CEFR objective Parquet output",
        ) from exc

    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = pa.schema(
        [
            ("objective_id", pa.string()),
            ("source_record_id", pa.string()),
            ("cefr_level", pa.string()),
            ("domain", pa.string()),
            ("scale_name", pa.string()),
            ("objective_text", pa.string()),
            ("source_descriptor_text", pa.string()),
            ("status", pa.string()),
            ("confidence", pa.float64()),
            ("canonical_skill_hint", pa.string()),
        ],
    )
    rows = [candidate.model_dump(mode="json") for candidate in candidates]
    table = pa.Table.from_pylist(rows, schema=schema)
    pq.write_table(table, path)
    return path


def write_source_inspection_report(
    report: dict[str, Any],
    reports_dir: str | Path = DEFAULT_CEFR_REPORTS_DIR,
) -> Path:
    return _write_report(report, Path(reports_dir) / SOURCE_INSPECTION_REPORT_NAME)


def write_extraction_report(
    report: dict[str, Any],
    reports_dir: str | Path = DEFAULT_CEFR_REPORTS_DIR,
) -> Path:
    return _write_report(report, Path(reports_dir) / EXTRACTION_REPORT_NAME)


def build_extraction_report(
    config: CEFRConfig,
    parsed: ParsedCEFRDataset,
    validation: CEFRValidationResult,
    candidates: Sequence[CEFRLearningObjectiveCandidate],
) -> dict[str, Any]:
    records = parsed.records
    no_descriptor_rows = [record for record in records if not record.descriptor_available]
    malformed_issues = [issue for issue in parsed.issues if issue.severity == "error"]
    return {
        "source": config.source.name,
        "source_document": config.source.document,
        "source_year": config.source.year,
        "run_at": now_utc().isoformat(),
        "source_file": config.source.source_file,
        "pdf": {
            "total_pages": parsed.page_count,
            "pages_scanned": parsed.pages_scanned,
            "tables_seen": parsed.tables_seen,
            "tables_matched": parsed.tables_matched,
        },
        "sections_processed": _sections_processed(config),
        "descriptor_scales_found": parsed.scale_hits,
        "totals": {
            "descriptor_records": len(records),
            "descriptor_available_records": sum(
                1 for record in records if record.descriptor_available
            ),
            "no_descriptor_rows": len(no_descriptor_rows),
            "objective_candidates": len(candidates),
            "malformed_records": len(malformed_issues),
            "extraction_warnings": parsed.warning_count,
            "extraction_errors": parsed.error_count,
            "validation_warnings": validation.warning_count,
            "validation_errors": validation.error_count,
        },
        "records_by_cefr_level": count_records_by(records, "cefr_level"),
        "records_by_domain": count_records_by(records, "domain"),
        "records_by_scale": count_records_by(records, "scale_name"),
        "objective_candidates_by_level": count_records_by(candidates, "cefr_level"),
        "objective_candidates_by_domain": count_records_by(candidates, "domain"),
        "grammatical_accuracy_record_count": sum(
            1 for record in records if record.scale_name == "grammatical_accuracy"
        ),
        "no_descriptor_rows": [
            _compact_record(record) for record in no_descriptor_rows
        ],
        "malformed_records": [issue.model_dump(mode="json") for issue in malformed_issues],
        "duplicate_candidates": [
            issue.model_dump(mode="json")
            for issue in validation.issues
            if issue.code in {"duplicate_objective_id", "duplicate_descriptor_row"}
        ],
        "pages_skipped": _pages_skipped(parsed),
        "skipped_tables": parsed.skipped_tables[:200],
        "appendices": [
            appendix.model_dump(mode="json") for appendix in config.appendices
        ],
        "extraction_issues": [
            issue.model_dump(mode="json") for issue in parsed.issues
        ],
        "validation_issues": [
            issue.model_dump(mode="json") for issue in validation.issues
        ],
    }


def count_records_by(records: Sequence[Any], field_name: str) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for record in records:
        value = getattr(record, field_name)
        counter[str(value)] += 1
    return dict(sorted(counter.items()))


def _descriptor_parquet_row(record: CEFRDescriptorRecord) -> dict[str, Any]:
    payload = record.model_dump(mode="json")
    raw_payload = payload.get("raw_payload")
    payload["raw_payload"] = (
        json.dumps(raw_payload, ensure_ascii=False, sort_keys=True)
        if raw_payload is not None
        else None
    )
    return payload


def _sections_processed(config: CEFRConfig) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for domain, section in config.sections.items():
        if not section.enabled:
            continue
        sections.append(
            {
                "domain": domain,
                "chapter": section.chapter,
                "section": section.section,
                "page_start": section.page_start,
                "page_end": section.page_end,
                "scales": [scale.id for scale in section.scales if scale.enabled],
            },
        )
    return sections


def _pages_skipped(parsed: ParsedCEFRDataset) -> list[int]:
    scanned = set(parsed.pages_scanned)
    if not scanned:
        return []
    return [
        page_number
        for page_number in range(min(scanned), max(scanned) + 1)
        if page_number not in scanned
    ]


def _compact_record(record: CEFRDescriptorRecord) -> dict[str, Any]:
    return {
        "source_record_id": record.source_record_id,
        "cefr_level": record.cefr_level,
        "reference_level": record.reference_level,
        "domain": record.domain,
        "scale_name": record.scale_name,
        "descriptor_text": record.descriptor_text,
        "page_number": record.page_number,
        "source_table": record.source_table,
    }


def _write_report(report: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return path

