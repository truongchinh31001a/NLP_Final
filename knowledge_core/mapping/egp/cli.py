from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Sequence

from knowledge_core.mapping.egp.mapper import create_mappings
from knowledge_core.mapping.egp.reporting import (
    MAPPINGS_JSONL_OUTPUT_NAME,
    build_mapping_report,
    load_mappings_jsonl,
    load_records_jsonl,
    write_mapping_outputs,
    write_mapping_report,
    write_review_queue,
)
from knowledge_core.mapping.egp.validator import validate_mappings
from knowledge_core.sources.egp.config import DEFAULT_CONFIG_PATH, EGPConfigError, load_egp_config
from knowledge_core.sources.egp.filtering import (
    SOURCE_EXCLUSION_REPORT_NAME,
    build_source_exclusion_report,
    partition_v1_category_records,
    write_source_exclusion_report,
)
from knowledge_core.sources.egp.inspection import (
    SOURCE_INSPECTION_REPORT_NAME,
    inspect_configured_sources,
    write_source_inspection_report,
)
from knowledge_core.sources.egp.parser import EGPParseError, parse_configured_workbooks
from knowledge_core.sources.egp.models import SourceRecordExclusion
from knowledge_core.sources.egp.paths import (
    DEFAULT_EGP_REPORTS_DIR,
    DEFAULT_EGP_REVIEW_DIR,
    DEFAULT_INTERIM_GRAMMAR_DIR,
    DEFAULT_RAW_GRAMMAR_DIR,
)
from knowledge_core.sources.egp.reporting import (
    JSONL_OUTPUT_NAME,
    build_validation_report,
    write_normalized_outputs,
    write_validation_report,
)
from knowledge_core.sources.egp.validator import validate_records


logger = logging.getLogger(__name__)


def _add_common_arguments(parser: argparse.ArgumentParser, *, with_defaults: bool) -> None:
    def default(value: object) -> object:
        return value if with_defaults else argparse.SUPPRESS

    parser.add_argument("--config", default=default(str(DEFAULT_CONFIG_PATH)))
    parser.add_argument("--raw-dir", default=default(str(DEFAULT_RAW_GRAMMAR_DIR)))
    parser.add_argument("--interim-dir", default=default(str(DEFAULT_INTERIM_GRAMMAR_DIR)))
    parser.add_argument("--reports-dir", default=default(str(DEFAULT_EGP_REPORTS_DIR)))
    parser.add_argument("--review-dir", default=default(str(DEFAULT_EGP_REVIEW_DIR)))
    parser.add_argument("--category", default=default(None))
    parser.add_argument("--dry-run", action="store_true", default=default(False))
    parser.add_argument(
        "--log-level",
        default=default("INFO"),
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )


def build_parser() -> argparse.ArgumentParser:
    command_options = argparse.ArgumentParser(add_help=False)
    _add_common_arguments(command_options, with_defaults=False)

    parser = argparse.ArgumentParser(
        prog="python -m knowledge_core.mapping.egp.cli",
        description="Map normalized EGP records to canonical Grammar V1 skills.",
    )
    _add_common_arguments(parser, with_defaults=True)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "map",
        parents=[command_options],
        help="Create mapping outputs from normalized JSONL",
    )
    subparsers.add_parser(
        "validate",
        parents=[command_options],
        help="Validate source records and mappings",
    )
    subparsers.add_parser(
        "report",
        parents=[command_options],
        help="Write the EGP mapping report",
    )
    subparsers.add_parser(
        "run",
        parents=[command_options],
        help="Inspect, parse, map, validate, review, report",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        config = load_egp_config(args.config)
        if args.command == "map":
            return _map(args)
        if args.command == "validate":
            return _validate(config, args)
        if args.command == "report":
            return _report(args)
        if args.command == "run":
            return _run(config, args)
    except (EGPConfigError, EGPParseError, FileNotFoundError, KeyError) as exc:
        logger.error("%s", exc)
        return 1

    parser.error(f"unsupported command: {args.command}")
    return 2


def _map(args: argparse.Namespace) -> int:
    records = _load_records(args)
    mappings = create_mappings(records)
    if not args.dry_run:
        outputs = write_mapping_outputs(mappings, args.interim_dir)
        review_path = write_review_queue(records, mappings, args.review_dir)
        logger.info("Wrote EGP mappings JSONL: %s", outputs["jsonl"])
        logger.info("Wrote EGP mappings Parquet: %s", outputs["parquet"])
        logger.info("Wrote EGP mapping review queue: %s", review_path)
    _print_mapping_counts(mappings)
    return 0


def _validate(config: object, args: argparse.Namespace) -> int:
    records = _load_records(args)
    mappings = _load_mappings(args)
    source_validation = validate_records(records, config)  # type: ignore[arg-type]
    mapping_validation = validate_mappings(records, mappings)
    logger.info(
        "EGP source validation: records=%s warnings=%s errors=%s",
        source_validation.total_records,
        source_validation.warning_count,
        source_validation.error_count,
    )
    logger.info(
        "EGP mapping validation: mappings=%s warnings=%s errors=%s",
        mapping_validation.total_mappings,
        mapping_validation.warning_count,
        mapping_validation.error_count,
    )
    return 1 if source_validation.error_count or mapping_validation.error_count else 0


def _report(args: argparse.Namespace) -> int:
    records = _load_records(args)
    mappings = _load_mappings(args)
    source_exclusion_report = _load_source_exclusion_report(args)
    source_exclusions = _exclusions_from_report(source_exclusion_report)
    raw_record_count = source_exclusion_report.get("raw_records")
    report = build_mapping_report(
        records,
        mappings,
        raw_record_count=raw_record_count if isinstance(raw_record_count, int) else None,
        source_exclusions=source_exclusions,
        source_inspection_report=_load_source_inspection_report(args),
    )
    if not args.dry_run:
        report_path = write_mapping_report(report, args.reports_dir)
        logger.info("Wrote EGP mapping report: %s", report_path)
    _print_report_summary(report)
    return 0


def _run(config: object, args: argparse.Namespace) -> int:
    source_inspection = inspect_configured_sources(
        config,  # type: ignore[arg-type]
        args.raw_dir,
        category_id=args.category,
    )
    parsed = parse_configured_workbooks(
        config,  # type: ignore[arg-type]
        args.raw_dir,
        category_id=args.category,
    )
    partition = partition_v1_category_records(
        parsed.records,
        config,  # type: ignore[arg-type]
    )
    source_validation = validate_records(
        partition.included_records,
        config,  # type: ignore[arg-type]
    )
    mappings = create_mappings(partition.included_records)
    mapping_validation = validate_mappings(partition.included_records, mappings)
    source_report = build_validation_report(
        config,  # type: ignore[arg-type]
        source_validation,
        records=partition.included_records,
        empty_files=parsed.empty_files,
        source_exclusions=partition.excluded_records,
    )
    source_exclusion_report = build_source_exclusion_report(
        partition.excluded_records,
        raw_record_count=len(parsed.records),
        included_record_count=len(partition.included_records),
    )
    mapping_report = build_mapping_report(
        partition.included_records,
        mappings,
        raw_record_count=len(parsed.records),
        source_exclusions=partition.excluded_records,
        source_validation=source_validation,
        mapping_validation=mapping_validation,
        source_inspection_report=source_inspection,
    )

    if not args.dry_run:
        source_inspection_path = write_source_inspection_report(
            source_inspection,
            args.reports_dir,
        )
        normalized_outputs = write_normalized_outputs(
            partition.included_records,
            args.interim_dir,
        )
        source_validation_path = write_validation_report(source_report, args.reports_dir)
        source_exclusion_path = write_source_exclusion_report(
            source_exclusion_report,
            args.reports_dir,
        )
        mapping_outputs = write_mapping_outputs(mappings, args.interim_dir)
        review_path = write_review_queue(
            partition.included_records,
            mappings,
            args.review_dir,
        )
        mapping_report_path = write_mapping_report(mapping_report, args.reports_dir)
        logger.info("Wrote EGP source inspection report: %s", source_inspection_path)
        logger.info("Wrote EGP records JSONL: %s", normalized_outputs["jsonl"])
        logger.info("Wrote EGP records Parquet: %s", normalized_outputs["parquet"])
        logger.info("Wrote EGP source validation report: %s", source_validation_path)
        logger.info("Wrote EGP source exclusion report: %s", source_exclusion_path)
        logger.info("Wrote EGP mappings JSONL: %s", mapping_outputs["jsonl"])
        logger.info("Wrote EGP mappings Parquet: %s", mapping_outputs["parquet"])
        logger.info("Wrote EGP mapping review queue: %s", review_path)
        logger.info("Wrote EGP mapping report: %s", mapping_report_path)

    _print_mapping_counts(mappings)
    _print_report_summary(mapping_report)
    return 1 if source_validation.error_count or mapping_validation.error_count else 0


def _load_records(args: argparse.Namespace):
    return load_records_jsonl(Path(args.interim_dir) / JSONL_OUTPUT_NAME)


def _load_mappings(args: argparse.Namespace):
    return load_mappings_jsonl(Path(args.interim_dir) / MAPPINGS_JSONL_OUTPUT_NAME)


def _load_source_inspection_report(args: argparse.Namespace) -> dict[str, object] | None:
    path = Path(args.reports_dir) / SOURCE_INSPECTION_REPORT_NAME
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_source_exclusion_report(args: argparse.Namespace) -> dict[str, object]:
    path = Path(args.reports_dir) / SOURCE_EXCLUSION_REPORT_NAME
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _exclusions_from_report(
    report: dict[str, object],
) -> list[SourceRecordExclusion]:
    records = report.get("records")
    if not isinstance(records, list):
        return []
    return [SourceRecordExclusion.model_validate(record) for record in records]


def _print_mapping_counts(mappings) -> None:
    counts: dict[str, int] = {}
    for mapping in mappings:
        counts[mapping.status] = counts.get(mapping.status, 0) + 1
    logger.info("EGP mapping counts: %s", counts)


def _print_report_summary(report: dict[str, object]) -> None:
    logger.info("EGP mapping report records: %s", report["source_records"])
    logger.info("EGP mapping counts: %s", report["mapping_counts"])
    logger.info("EGP canonical coverage: %s", report["canonical_coverage"]["coverage_ratio"])


if __name__ == "__main__":
    sys.exit(main())
