from __future__ import annotations

import argparse
import logging
import sys
from typing import Sequence

from knowledge_core.sources.clc_fce.parser import CLCFCEParseError
from knowledge_core.sources.clc_fce.paths import (
    DEFAULT_INTERIM_DIR,
    DEFAULT_RAW_ROOT,
    DEFAULT_REPORTS_DIR,
    DEFAULT_REVIEW_DIR,
    DEFAULT_SOURCE_INVENTORY_REPORT,
)
from knowledge_core.sources.clc_fce.processor import run_clc_fce_ingestion
from knowledge_core.sources.clc_fce.reporting import CLCFCEOutputError


logger = logging.getLogger(__name__)


def _add_common_arguments(parser: argparse.ArgumentParser, *, with_defaults: bool) -> None:
    def default(value: object) -> object:
        return value if with_defaults else argparse.SUPPRESS

    parser.add_argument("--raw-root", default=default(str(DEFAULT_RAW_ROOT)))
    parser.add_argument("--interim-dir", default=default(str(DEFAULT_INTERIM_DIR)))
    parser.add_argument("--reports-dir", default=default(str(DEFAULT_REPORTS_DIR)))
    parser.add_argument("--review-dir", default=default(str(DEFAULT_REVIEW_DIR)))
    parser.add_argument(
        "--source-inventory-report",
        default=default(str(DEFAULT_SOURCE_INVENTORY_REPORT)),
    )
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
        prog="python -m knowledge_core.sources.clc_fce.cli",
        description="Ingest CLC FCE learner-error source records.",
    )
    _add_common_arguments(parser, with_defaults=True)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("parse", parents=[command_options], help="Parse in memory")
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
        result = run_clc_fce_ingestion(
            raw_root=args.raw_root,
            interim_dir=args.interim_dir,
            reports_dir=args.reports_dir,
            review_dir=args.review_dir,
            source_inventory_report=args.source_inventory_report,
            dry_run=args.dry_run or args.command in {"parse", "validate"},
        )
    except (CLCFCEParseError, CLCFCEOutputError, ValueError, KeyError) as exc:
        logger.error("%s", exc)
        return 1

    logger.info("CLC FCE source records: %s", len(result.parsed.source_records))
    logger.info("CLC FCE error instances: %s", len(result.parsed.error_instances))
    logger.info("CLC FCE XML answer summaries: %s", len(result.parsed.xml_answer_summaries))
    logger.info(
        "CLC FCE validation: %s error(s), %s warning(s)",
        result.validation.error_count,
        result.validation.warning_count,
    )
    for name, path in result.output_paths.items():
        logger.info("Wrote %s: %s", name, path)
    if result.report_path:
        logger.info("Wrote ingestion_report: %s", result.report_path)
    return 1 if result.validation.error_count else 0


if __name__ == "__main__":
    sys.exit(main())

