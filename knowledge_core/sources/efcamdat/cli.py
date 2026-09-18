from __future__ import annotations

import argparse
import logging
import sys
from typing import Sequence

from knowledge_core.sources.efcamdat.parser import EFCAMDATParseError
from knowledge_core.sources.efcamdat.paths import (
    DEFAULT_CSV_PATH,
    DEFAULT_INTERIM_DIR,
    DEFAULT_REPORTS_DIR,
    DEFAULT_REVIEW_DIR,
    DEFAULT_XML_PATH,
)
from knowledge_core.sources.efcamdat.processor import run_efcamdat_ingestion
from knowledge_core.sources.efcamdat.reporting import EFCAMDATOutputError


logger = logging.getLogger(__name__)


def _add_common_arguments(parser: argparse.ArgumentParser, *, with_defaults: bool) -> None:
    def default(value: object) -> object:
        return value if with_defaults else argparse.SUPPRESS

    parser.add_argument("--xml", default=default(str(DEFAULT_XML_PATH)))
    parser.add_argument("--csv", default=default(str(DEFAULT_CSV_PATH)))
    parser.add_argument("--interim-dir", default=default(str(DEFAULT_INTERIM_DIR)))
    parser.add_argument("--review-dir", default=default(str(DEFAULT_REVIEW_DIR)))
    parser.add_argument("--reports-dir", default=default(str(DEFAULT_REPORTS_DIR)))
    parser.add_argument("--limit-writings", type=int, default=default(None))
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
        prog="python -m knowledge_core.sources.efcamdat.cli",
        description="Ingest EFCAMDAT XML change markup into source-native error artifacts.",
    )
    _add_common_arguments(parser, with_defaults=True)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("parse", parents=[command_options], help="Parse in memory and summarize")
    subparsers.add_parser("validate", parents=[command_options], help="Parse and validate")
    subparsers.add_parser("run", parents=[command_options], help="Parse, validate, and write artifacts")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        result = run_efcamdat_ingestion(
            xml_path=args.xml,
            csv_path=args.csv,
            interim_dir=args.interim_dir,
            review_dir=args.review_dir,
            reports_dir=args.reports_dir,
            dry_run=args.dry_run or args.command in {"parse", "validate"},
            limit_writings=args.limit_writings,
        )
    except (EFCAMDATParseError, EFCAMDATOutputError, ValueError, KeyError) as exc:
        logger.error("%s", exc)
        return 1

    report = result.report
    validation = report["validation"]
    logger.info("EFCAMDAT source records: %s", report["source_record_count"])
    logger.info("EFCAMDAT changed writings: %s", report["changed_writing_count"])
    logger.info("EFCAMDAT error instances: %s", report["error_instance_count"])
    logger.info("EFCAMDAT unique labels: %s", report["unique_error_label_count"])
    logger.info("EFCAMDAT parser fallbacks: %s", report["parser_fallback_count"])
    logger.info(
        "EFCAMDAT validation: %s error(s), %s warning(s)",
        validation["error_count"],
        validation["warning_count"],
    )
    for name, path in result.output_paths.items():
        logger.info("Wrote %s: %s", name, path)
    if result.report_path:
        logger.info("Wrote ingestion_report: %s", result.report_path)
    return 1 if validation["error_count"] else 0


if __name__ == "__main__":
    sys.exit(main())

