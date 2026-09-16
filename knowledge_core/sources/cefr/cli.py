from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Sequence

from knowledge_core.sources.cefr.config import CEFRConfigError, load_cefr_config
from knowledge_core.sources.cefr.inspection import (
    CEFRInspectionError,
    inspect_source_pdf,
)
from knowledge_core.sources.cefr.objective_extractor import (
    extract_learning_objective_candidates,
)
from knowledge_core.sources.cefr.parser import CEFRParseError, ParsedCEFRDataset, parse_configured_pdf
from knowledge_core.sources.cefr.paths import (
    DEFAULT_CEFR_INTERIM_DIR,
    DEFAULT_CEFR_PDF_PATH,
    DEFAULT_CEFR_REPORTS_DIR,
    DEFAULT_CONFIG_PATH,
)
from knowledge_core.sources.cefr.reporting import (
    build_extraction_report,
    write_descriptor_outputs,
    write_extraction_report,
    write_objective_outputs,
    write_source_inspection_report,
)
from knowledge_core.sources.cefr.validator import validate_records


logger = logging.getLogger(__name__)


def _add_common_arguments(parser: argparse.ArgumentParser, *, with_defaults: bool) -> None:
    def default(value: object) -> object:
        return value if with_defaults else argparse.SUPPRESS

    parser.add_argument("--config", default=default(str(DEFAULT_CONFIG_PATH)))
    parser.add_argument("--pdf", default=default(str(DEFAULT_CEFR_PDF_PATH)))
    parser.add_argument("--interim-dir", default=default(str(DEFAULT_CEFR_INTERIM_DIR)))
    parser.add_argument("--reports-dir", default=default(str(DEFAULT_CEFR_REPORTS_DIR)))
    parser.add_argument("--section", default=default(None))
    parser.add_argument("--domain", default=default(None))
    parser.add_argument("--level", default=default(None))
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
        prog="python -m knowledge_core.sources.cefr.cli",
        description="Ingest CEFR Companion Volume 2020 descriptor tables.",
    )
    _add_common_arguments(parser, with_defaults=True)

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "inspect",
        parents=[command_options],
        help="Inspect configured CEFR source PDF tables",
    )
    subparsers.add_parser(
        "extract",
        parents=[command_options],
        help="Extract normalized CEFR descriptor records",
    )
    subparsers.add_parser(
        "normalize",
        parents=[command_options],
        help="Extract descriptors and derived learning objective candidates",
    )
    subparsers.add_parser(
        "validate",
        parents=[command_options],
        help="Validate CEFR descriptor and objective candidate outputs",
    )
    subparsers.add_parser(
        "report",
        parents=[command_options],
        help="Build CEFR extraction report",
    )
    subparsers.add_parser(
        "run",
        parents=[command_options],
        help="Inspect, extract, normalize, validate, and report",
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
        config = load_cefr_config(args.config)
        if args.command == "inspect":
            return _inspect(config, args)
        if args.command == "extract":
            parsed = _parse(config, args)
            if not args.dry_run:
                outputs = write_descriptor_outputs(parsed.records, args.interim_dir)
                logger.info("Wrote CEFR descriptor JSONL: %s", outputs["jsonl"])
                logger.info("Wrote CEFR descriptor Parquet: %s", outputs["parquet"])
            _print_parse_summary(parsed)
            return 1 if parsed.error_count else 0
        if args.command == "normalize":
            parsed = _parse(config, args)
            candidates = extract_learning_objective_candidates(parsed.records)
            if not args.dry_run:
                descriptor_outputs = write_descriptor_outputs(
                    parsed.records,
                    args.interim_dir,
                )
                objective_outputs = write_objective_outputs(
                    candidates,
                    args.interim_dir,
                )
                logger.info(
                    "Wrote CEFR descriptor JSONL: %s",
                    descriptor_outputs["jsonl"],
                )
                logger.info(
                    "Wrote CEFR descriptor Parquet: %s",
                    descriptor_outputs["parquet"],
                )
                logger.info(
                    "Wrote CEFR objective JSONL: %s",
                    objective_outputs["jsonl"],
                )
                logger.info(
                    "Wrote CEFR objective Parquet: %s",
                    objective_outputs["parquet"],
                )
            _print_parse_summary(parsed, candidates=len(candidates))
            return 1 if parsed.error_count else 0
        if args.command == "validate":
            return _validate(config, args)
        if args.command == "report":
            return _report(config, args)
        if args.command == "run":
            return _run(config, args)
    except (CEFRConfigError, CEFRInspectionError, CEFRParseError, KeyError) as exc:
        logger.error("%s", exc)
        return 1

    parser.error(f"unsupported command: {args.command}")
    return 2


def _inspect(config: object, args: argparse.Namespace) -> int:
    report = inspect_source_pdf(config, args.pdf)
    if not args.dry_run:
        report_path = write_source_inspection_report(report, args.reports_dir)
        logger.info("Wrote CEFR source inspection report: %s", report_path)
    logger.info("CEFR PDF pages: %s", report["pdf"]["total_pages"])
    logger.info("Configured CEFR scales: %s", len(report["configured_scales"]))
    logger.info("Missing configured scales: %s", len(report["missing_scales"]))
    return 1 if report["missing_scales"] else 0


def _parse(config: object, args: argparse.Namespace) -> ParsedCEFRDataset:
    return parse_configured_pdf(
        config,
        args.pdf,
        section=args.section,
        domain=args.domain,
        level=args.level,
    )


def _validate(config: object, args: argparse.Namespace) -> int:
    parsed = _parse(config, args)
    candidates = extract_learning_objective_candidates(parsed.records)
    validation = validate_records(parsed.records, config, candidates=candidates)
    report = build_extraction_report(config, parsed, validation, candidates)
    if not args.dry_run:
        report_path = write_extraction_report(report, args.reports_dir)
        logger.info("Wrote CEFR extraction report: %s", report_path)
    _print_parse_summary(parsed, candidates=len(candidates))
    _print_validation_summary(validation)
    return 1 if parsed.error_count or validation.error_count else 0


def _report(config: object, args: argparse.Namespace) -> int:
    parsed = _parse(config, args)
    candidates = extract_learning_objective_candidates(parsed.records)
    validation = validate_records(parsed.records, config, candidates=candidates)
    report = build_extraction_report(config, parsed, validation, candidates)
    if not args.dry_run:
        report_path = write_extraction_report(report, args.reports_dir)
        logger.info("Wrote CEFR extraction report: %s", report_path)
    _print_parse_summary(parsed, candidates=len(candidates))
    _print_validation_summary(validation)
    return 1 if parsed.error_count or validation.error_count else 0


def _run(config: object, args: argparse.Namespace) -> int:
    inspection_report = inspect_source_pdf(config, args.pdf)
    parsed = _parse(config, args)
    candidates = extract_learning_objective_candidates(parsed.records)
    validation = validate_records(parsed.records, config, candidates=candidates)
    extraction_report = build_extraction_report(config, parsed, validation, candidates)

    if not args.dry_run:
        inspection_path = write_source_inspection_report(
            inspection_report,
            args.reports_dir,
        )
        descriptor_outputs = write_descriptor_outputs(parsed.records, args.interim_dir)
        objective_outputs = write_objective_outputs(candidates, args.interim_dir)
        extraction_path = write_extraction_report(
            extraction_report,
            args.reports_dir,
        )
        logger.info("Wrote CEFR source inspection report: %s", inspection_path)
        logger.info("Wrote CEFR descriptor JSONL: %s", descriptor_outputs["jsonl"])
        logger.info("Wrote CEFR descriptor Parquet: %s", descriptor_outputs["parquet"])
        logger.info("Wrote CEFR objective JSONL: %s", objective_outputs["jsonl"])
        logger.info("Wrote CEFR objective Parquet: %s", objective_outputs["parquet"])
        logger.info("Wrote CEFR extraction report: %s", extraction_path)

    _print_parse_summary(parsed, candidates=len(candidates))
    _print_validation_summary(validation)
    return 1 if parsed.error_count or validation.error_count else 0


def _print_parse_summary(
    parsed: ParsedCEFRDataset,
    *,
    candidates: int | None = None,
) -> None:
    logger.info("CEFR descriptor records: %s", len(parsed.records))
    logger.info("CEFR no-descriptor rows: %s", len(parsed.no_descriptor_rows))
    logger.info("CEFR extraction issues: %s error(s), %s warning(s)", parsed.error_count, parsed.warning_count)
    if candidates is not None:
        logger.info("CEFR objective candidates: %s", candidates)


def _print_validation_summary(validation: object) -> None:
    logger.info(
        "CEFR validation: %s error(s), %s warning(s)",
        validation.error_count,
        validation.warning_count,
    )


if __name__ == "__main__":
    sys.exit(main())

