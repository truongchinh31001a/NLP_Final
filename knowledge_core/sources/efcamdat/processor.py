from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from knowledge_core.sources.efcamdat.models import EFCAMDATIngestionCounters
from knowledge_core.sources.efcamdat.parser import inspect_csv_support, iter_writing_blocks
from knowledge_core.sources.efcamdat.paths import (
    DEFAULT_CSV_PATH,
    DEFAULT_INTERIM_DIR,
    DEFAULT_REPORTS_DIR,
    DEFAULT_REVIEW_DIR,
    DEFAULT_XML_PATH,
)
from knowledge_core.sources.efcamdat.reporting import (
    build_ingestion_report,
    default_output_paths,
    open_jsonl,
    review_row_for_error,
    write_jsonl_record,
    write_report,
    write_review_header,
)
from knowledge_core.sources.efcamdat.validator import build_validation_summary


@dataclass(slots=True)
class EFCAMDATIngestionResult:
    report: dict[str, object]
    report_path: Path | None
    output_paths: dict[str, Path]


def run_efcamdat_ingestion(
    *,
    xml_path: str | Path = DEFAULT_XML_PATH,
    csv_path: str | Path = DEFAULT_CSV_PATH,
    interim_dir: str | Path = DEFAULT_INTERIM_DIR,
    review_dir: str | Path = DEFAULT_REVIEW_DIR,
    reports_dir: str | Path = DEFAULT_REPORTS_DIR,
    dry_run: bool = False,
    limit_writings: int | None = None,
) -> EFCAMDATIngestionResult:
    resolved_xml = Path(xml_path)
    output_paths = default_output_paths(interim_dir=interim_dir, review_dir=review_dir)
    counters = EFCAMDATIngestionCounters()
    labels: Counter[str] = Counter()
    levels: Counter[str] = Counter()

    if dry_run:
        _consume_stream(
            xml_path=resolved_xml,
            counters=counters,
            labels=labels,
            levels=levels,
            limit_writings=limit_writings,
        )
    else:
        output_paths["source_records_jsonl"].parent.mkdir(parents=True, exist_ok=True)
        output_paths["error_instances_jsonl"].parent.mkdir(parents=True, exist_ok=True)
        output_paths["review_csv"].parent.mkdir(parents=True, exist_ok=True)
        with (
            open_jsonl(output_paths["source_records_jsonl"]) as source_handle,
            open_jsonl(output_paths["error_instances_jsonl"]) as error_handle,
            output_paths["review_csv"].open("w", encoding="utf-8", newline="") as review_handle,
        ):
            review_writer = write_review_header(review_handle)
            _consume_stream(
                xml_path=resolved_xml,
                counters=counters,
                labels=labels,
                levels=levels,
                limit_writings=limit_writings,
                source_handle=source_handle,
                error_handle=error_handle,
                review_writer=review_writer,
            )

    csv_support = inspect_csv_support(csv_path)
    validation = build_validation_summary(
        source_record_count=counters.source_record_count,
        error_instance_count=counters.error_instance_count,
        parser_fallback_count=counters.parser_fallback_count,
        malformed_writing_count=counters.malformed_writing_count,
    )
    report = build_ingestion_report(
        counters=counters,
        labels=labels,
        levels=levels,
        csv_support=csv_support,
        validation=validation,
        output_paths=output_paths if not dry_run else {},
        xml_path=resolved_xml,
    )
    report_path = None if dry_run else write_report(report, reports_dir)
    return EFCAMDATIngestionResult(
        report=report,
        report_path=report_path,
        output_paths=output_paths if not dry_run else {},
    )


def _consume_stream(
    *,
    xml_path: Path,
    counters: EFCAMDATIngestionCounters,
    labels: Counter[str],
    levels: Counter[str],
    limit_writings: int | None,
    source_handle=None,
    error_handle=None,
    review_writer=None,
) -> None:
    for block in iter_writing_blocks(xml_path):
        counters.source_record_count += 1
        level = block.source_record.metadata.get("level")
        if isinstance(level, str) and level:
            levels[level] += 1
        if block.parser_status == "regex_fallback":
            counters.parser_fallback_count += 1
            counters.malformed_writing_count += 1
        if block.error_instances:
            counters.changed_writing_count += 1
        if source_handle is not None:
            write_jsonl_record(source_handle, block.source_record)
        for error in block.error_instances:
            counters.error_instance_count += 1
            if error.source_native_label is not None:
                labels[error.source_native_label.label] += 1
            if error_handle is not None:
                write_jsonl_record(error_handle, error)
            if review_writer is not None:
                row = review_row_for_error(error)
                if row is not None:
                    counters.review_queue_count += 1
                    review_writer.writerow(row)
            elif error.parser_notes or error.review_status == "needs_review":
                counters.review_queue_count += 1
        if limit_writings is not None and counters.source_record_count >= limit_writings:
            break

