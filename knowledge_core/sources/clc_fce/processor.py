from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from knowledge_core.sources.clc_fce.models import ParsedCLCFCECorpus
from knowledge_core.sources.clc_fce.parser import parse_clc_fce_corpus
from knowledge_core.sources.clc_fce.paths import (
    DEFAULT_INTERIM_DIR,
    DEFAULT_RAW_ROOT,
    DEFAULT_REPORTS_DIR,
    DEFAULT_REVIEW_DIR,
    DEFAULT_SOURCE_INVENTORY_REPORT,
)
from knowledge_core.sources.clc_fce.reporting import (
    build_ingestion_report,
    write_ingestion_outputs,
    write_ingestion_report,
)
from knowledge_core.sources.clc_fce.validator import CLCFCEValidationResult, validate_clc_fce_ingestion


@dataclass(slots=True)
class CLCFCEIngestionResult:
    parsed: ParsedCLCFCECorpus
    validation: CLCFCEValidationResult
    report: dict[str, Any]
    output_paths: dict[str, Path]
    report_path: Path | None


def run_clc_fce_ingestion(
    *,
    raw_root: str | Path = DEFAULT_RAW_ROOT,
    interim_dir: str | Path = DEFAULT_INTERIM_DIR,
    reports_dir: str | Path = DEFAULT_REPORTS_DIR,
    review_dir: str | Path = DEFAULT_REVIEW_DIR,
    source_inventory_report: str | Path = DEFAULT_SOURCE_INVENTORY_REPORT,
    dry_run: bool = False,
) -> CLCFCEIngestionResult:
    parsed = parse_clc_fce_corpus(raw_root)
    inventory = _read_inventory(source_inventory_report)
    validation = validate_clc_fce_ingestion(
        source_records=parsed.source_records,
        error_instances=parsed.error_instances,
        xml_answer_summaries=parsed.xml_answer_summaries,
        json_files=parsed.input_files.json_by_split,
        xml_files=parsed.input_files.xml_by_split,
        expected_answer_records=_inventory_count(inventory, "total_answer_records"),
        expected_annotated_scripts=_inventory_count(inventory, "total_annotated_scripts"),
    )
    input_files = {
        "json": {
            split: str(path).replace("\\", "/")
            for split, path in parsed.input_files.json_by_split.items()
        },
        "xml": {
            split: str(path).replace("\\", "/")
            for split, path in parsed.input_files.xml_by_split.items()
        },
    }
    output_paths: dict[str, Path] = {}
    report_path = None
    if not dry_run:
        output_paths = write_ingestion_outputs(
            source_records=parsed.source_records,
            error_instances=parsed.error_instances,
            interim_dir=interim_dir,
            review_dir=review_dir,
        )
    report = build_ingestion_report(
        source_records=parsed.source_records,
        error_instances=parsed.error_instances,
        xml_answer_summaries=parsed.xml_answer_summaries,
        validation=validation,
        input_files=input_files,
        output_paths=output_paths,
    )
    if not dry_run:
        report_path = write_ingestion_report(report, reports_dir)
    return CLCFCEIngestionResult(
        parsed=parsed,
        validation=validation,
        report=report,
        output_paths=output_paths,
        report_path=report_path,
    )


def _read_inventory(path: str | Path) -> dict[str, Any]:
    report_path = Path(path)
    if not report_path.exists():
        return {}
    return json.loads(report_path.read_text(encoding="utf-8"))


def _inventory_count(report: dict[str, Any], key: str) -> int | None:
    value = report.get(key)
    if isinstance(value, dict) and isinstance(value.get("count"), int):
        return value["count"]
    return None

