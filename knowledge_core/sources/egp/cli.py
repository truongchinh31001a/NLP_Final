from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Sequence

from knowledge_core.sources.egp.browser_downloader import BrowserEGPDownloader
from knowledge_core.sources.egp.config import DEFAULT_CONFIG_PATH, EGPConfigError, load_egp_config
from knowledge_core.sources.egp.downloader import download_categories
from knowledge_core.sources.egp.filtering import (
    build_source_exclusion_report,
    partition_v1_category_records,
    write_source_exclusion_report,
)
from knowledge_core.sources.egp.http_downloader import HttpEGPDownloader
from knowledge_core.sources.egp.inspection import (
    inspect_configured_sources,
    write_source_inspection_report,
)
from knowledge_core.sources.egp.models import DEFAULT_EGP_ONLINE_URL, DownloadResult, EGPConfig
from knowledge_core.sources.egp.paths import DEFAULT_INTERIM_GRAMMAR_DIR, DEFAULT_RAW_GRAMMAR_DIR
from knowledge_core.sources.egp.parser import EGPParseError, ParsedEGPDataset, parse_configured_workbooks
from knowledge_core.sources.egp.reporting import (
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
    parser.add_argument("--reports-dir", default=default("data/reports/egp"))
    parser.add_argument("--category", default=default(None), help="Run one configured category id")
    parser.add_argument("--dry-run", action="store_true", default=default(False))
    parser.add_argument("--force", action="store_true", default=default(False))
    parser.add_argument(
        "--headless",
        action="store_true",
        dest="headless",
        default=default(True),
    )
    parser.add_argument(
        "--headed",
        action="store_false",
        dest="headless",
        default=default(True),
    )
    parser.add_argument(
        "--method",
        choices=("auto", "http", "browser"),
        default=default("auto"),
        help="Downloader strategy for download/run.",
    )
    parser.add_argument(
        "--http-export-url-template",
        default=default(None),
        help=(
            "Stable XLSX export URL template. Supports {query}, {query_raw}, "
            "{category_id}, {level}, {expected_super_category}, and "
            "{expected_sub_category}."
        ),
    )
    parser.add_argument("--base-url", default=default(DEFAULT_EGP_ONLINE_URL))
    parser.add_argument("--delay-seconds", type=float, default=default(0.0))
    parser.add_argument("--timeout-ms", type=int, default=default(120_000))
    parser.add_argument("--slow-mo-ms", type=int, default=default(0))
    parser.add_argument(
        "--log-level",
        default=default("INFO"),
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )


def build_parser() -> argparse.ArgumentParser:
    command_options = argparse.ArgumentParser(add_help=False)
    _add_common_arguments(command_options, with_defaults=False)

    parser = argparse.ArgumentParser(
        prog="python -m knowledge_core.sources.egp.cli",
        description="Ingest English Grammar Profile source XLSX exports.",
    )
    _add_common_arguments(parser, with_defaults=True)

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "download",
        parents=[command_options],
        help="Download configured raw EGP XLSX files",
    )
    subparsers.add_parser(
        "inspect",
        parents=[command_options],
        help="Inspect raw EGP XLSX files and write a source report",
    )
    subparsers.add_parser(
        "parse",
        parents=[command_options],
        help="Parse raw XLSX files into JSONL and Parquet",
    )
    subparsers.add_parser(
        "validate",
        parents=[command_options],
        help="Validate raw XLSX files and write a report",
    )
    subparsers.add_parser(
        "run",
        parents=[command_options],
        help="Download, parse, validate, and report",
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
        if args.command == "download":
            results = _download(config, args)
            _print_download_summary(results)
            return 1 if any(result.status == "failed" for result in results) else 0
        if args.command == "inspect":
            return _inspect(config, args)
        if args.command == "parse":
            parsed = _parse(config, args)
            return 0 if parsed is not None else 1
        if args.command == "validate":
            return _validate(config, args)
        if args.command == "run":
            return _run(config, args)
    except (EGPConfigError, EGPParseError, KeyError) as exc:
        logger.error("%s", exc)
        return 1

    parser.error(f"unsupported command: {args.command}")
    return 2


def _download(config: EGPConfig, args: argparse.Namespace) -> list[DownloadResult]:
    categories = config.select_categories(args.category)
    downloader = _select_downloader(args)
    return download_categories(
        downloader,
        categories,
        args.raw_dir,
        force=args.force,
        dry_run=args.dry_run,
        delay_seconds=args.delay_seconds,
    )


def _inspect(config: EGPConfig, args: argparse.Namespace) -> int:
    report = inspect_configured_sources(
        config,
        args.raw_dir,
        category_id=args.category,
    )
    if not args.dry_run:
        report_path = write_source_inspection_report(report, args.reports_dir)
        logger.info("Wrote EGP source inspection report: %s", report_path)
    logger.info("EGP source files found: %s", report["totals"]["files_found"])
    logger.info("EGP source data rows: %s", report["totals"]["data_rows"])
    return 1 if report["totals"]["files_with_errors"] else 0


def _parse(config: EGPConfig, args: argparse.Namespace) -> ParsedEGPDataset | None:
    parsed = parse_configured_workbooks(
        config,
        args.raw_dir,
        category_id=args.category,
    )
    partition = partition_v1_category_records(parsed.records, config)
    if args.dry_run:
        logger.info(
            "Dry run: parsed %s raw records, %s included V1 records, %s excluded",
            len(parsed.records),
            len(partition.included_records),
            len(partition.excluded_records),
        )
        return parsed
    outputs = write_normalized_outputs(partition.included_records, args.interim_dir)
    exclusion_report = build_source_exclusion_report(
        partition.excluded_records,
        raw_record_count=len(parsed.records),
        included_record_count=len(partition.included_records),
    )
    exclusion_path = write_source_exclusion_report(exclusion_report, args.reports_dir)
    logger.info("Wrote EGP JSONL output: %s", outputs["jsonl"])
    logger.info("Wrote EGP Parquet output: %s", outputs["parquet"])
    logger.info("Wrote EGP source exclusion report: %s", exclusion_path)
    if parsed.empty_files:
        logger.warning(
            "Parsed %s empty EGP workbook(s): %s",
            len(parsed.empty_files),
            ", ".join(str(path) for path in parsed.empty_files),
        )
    return parsed


def _validate(config: EGPConfig, args: argparse.Namespace) -> int:
    parsed = parse_configured_workbooks(
        config,
        args.raw_dir,
        category_id=args.category,
    )
    partition = partition_v1_category_records(parsed.records, config)
    validation = validate_records(partition.included_records, config)
    report = build_validation_report(
        config,
        validation,
        records=partition.included_records,
        empty_files=parsed.empty_files,
        source_exclusions=partition.excluded_records,
    )
    if not args.dry_run:
        exclusion_report = build_source_exclusion_report(
            partition.excluded_records,
            raw_record_count=len(parsed.records),
            included_record_count=len(partition.included_records),
        )
        exclusion_path = write_source_exclusion_report(
            exclusion_report,
            args.reports_dir,
        )
        report_path = write_validation_report(report, args.reports_dir)
        logger.info("Wrote EGP source exclusion report: %s", exclusion_path)
        logger.info("Wrote EGP validation report: %s", report_path)
    _print_validation_summary(report)
    return 1 if validation.error_count else 0


def _run(config: EGPConfig, args: argparse.Namespace) -> int:
    download_results = _download(config, args)
    failed_downloads = [result for result in download_results if result.status == "failed"]
    if failed_downloads:
        _print_download_summary(download_results)
        return 1

    parsed = parse_configured_workbooks(
        config,
        args.raw_dir,
        category_id=args.category,
    )
    partition = partition_v1_category_records(parsed.records, config)
    if not args.dry_run:
        outputs = write_normalized_outputs(partition.included_records, args.interim_dir)
        exclusion_report = build_source_exclusion_report(
            partition.excluded_records,
            raw_record_count=len(parsed.records),
            included_record_count=len(partition.included_records),
        )
        exclusion_path = write_source_exclusion_report(
            exclusion_report,
            args.reports_dir,
        )
        logger.info("Wrote EGP JSONL output: %s", outputs["jsonl"])
        logger.info("Wrote EGP Parquet output: %s", outputs["parquet"])
        logger.info("Wrote EGP source exclusion report: %s", exclusion_path)

    validation = validate_records(partition.included_records, config)
    report = build_validation_report(
        config,
        validation,
        records=partition.included_records,
        download_results=download_results,
        empty_files=parsed.empty_files,
        source_exclusions=partition.excluded_records,
    )
    if not args.dry_run:
        report_path = write_validation_report(report, args.reports_dir)
        logger.info("Wrote EGP validation report: %s", report_path)

    _print_download_summary(download_results)
    _print_validation_summary(report)
    return 1 if validation.error_count else 0


def _select_downloader(args: argparse.Namespace) -> object:
    template = args.http_export_url_template or os.getenv("EGP_EXPORT_URL_TEMPLATE")
    if args.method == "http" or (args.method == "auto" and template):
        return HttpEGPDownloader(export_url_template=template)
    return BrowserEGPDownloader(
        base_url=args.base_url,
        headless=args.headless,
        timeout_ms=args.timeout_ms,
        slow_mo_ms=args.slow_mo_ms,
    )


def _print_download_summary(results: Sequence[DownloadResult]) -> None:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    logger.info("EGP download summary: %s", counts)
    skipped = [result for result in results if result.status == "skipped"]
    if skipped:
        logger.info(
            "Skipped existing files: %s",
            ", ".join(str(result.destination) for result in skipped),
        )
    for result in results:
        if result.status == "failed":
            logger.error("%s failed: %s", result.category_id, result.error)


def _print_validation_summary(report: dict[str, object]) -> None:
    logger.info("EGP validation records: %s", report["records"])
    logger.info("EGP CEFR distribution: %s", report["cefr_distribution"])


if __name__ == "__main__":
    sys.exit(main())
