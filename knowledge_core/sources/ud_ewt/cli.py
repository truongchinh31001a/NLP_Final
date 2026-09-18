from __future__ import annotations

import argparse
import logging
import sys
from typing import Sequence

from knowledge_core.sources.ud_ewt.parser import UDEWTParseError
from knowledge_core.sources.ud_ewt.paths import (
    DEFAULT_INTERIM_DIR,
    DEFAULT_RELEASE_ROOT,
    DEFAULT_REPORTS_DIR,
    DEFAULT_REVIEW_DIR,
    DEFAULT_SOURCE_INVENTORY_REPORT,
)
from knowledge_core.sources.ud_ewt.processor import run_ud_ewt_ingestion
from knowledge_core.sources.ud_ewt.reporting import UDEWTOutputError


logger = logging.getLogger(__name__)


def _add_common_arguments(parser: argparse.ArgumentParser, *, with_defaults: bool) -> None:
    def default(value: object) -> object:
        return value if with_defaults else argparse.SUPPRESS

    parser.add_argument("--root-dir", default=default(str(DEFAULT_RELEASE_ROOT)))
    parser.add_argument("--interim-dir", default=default(str(DEFAULT_INTERIM_DIR)))
    parser.add_argument("--review-dir", default=default(str(DEFAULT_REVIEW_DIR)))
    parser.add_argument("--reports-dir", default=default(str(DEFAULT_REPORTS_DIR)))
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
        prog="python -m knowledge_core.sources.ud_ewt.cli",
        description="Ingest UD English EWT released CoNLL-U structural data.",
    )
    _add_common_arguments(parser, with_defaults=True)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("parse", parents=[command_options], help="Parse and validate in memory")
    subparsers.add_parser("validate", parents=[command_options], help="Parse and validate in memory")
    subparsers.add_parser("run", parents=[command_options], help="Parse, validate, write artifacts and reports")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        dataset = run_ud_ewt_ingestion(
            root_dir=args.root_dir,
            interim_dir=args.interim_dir,
            review_dir=args.review_dir,
            reports_dir=args.reports_dir,
            source_inventory_report=args.source_inventory_report,
            dry_run=args.dry_run or args.command in {"parse", "validate"},
        )
    except (UDEWTParseError, UDEWTOutputError, KeyError, ValueError) as exc:
        logger.error("%s", exc)
        return 1

    logger.info("UD EWT version: %s", dataset.ud_version)
    logger.info("UD EWT sentences: %s", len(dataset.sentences))
    logger.info(
        "UD EWT syntactic tokens: %s",
        sum(1 for token in dataset.tokens if not token.is_multiword and not token.is_empty_node),
    )
    logger.info(
        "UD EWT multiword tokens: %s",
        sum(1 for token in dataset.tokens if token.is_multiword),
    )
    logger.info(
        "UD EWT empty nodes: %s",
        sum(1 for token in dataset.tokens if token.is_empty_node),
    )
    logger.info("UD EWT structural evidence rows: %s", len(dataset.evidence))
    logger.info(
        "UD EWT validation: %s error(s), %s warning(s)",
        dataset.validation.error_count,
        dataset.validation.warning_count,
    )
    for name, path in dataset.output_paths.items():
        logger.info("Wrote %s: %s", name, path)
    for name, path in dataset.report_paths.items():
        logger.info("Wrote %s: %s", name, path)
    return 1 if dataset.validation.error_count else 0


if __name__ == "__main__":
    sys.exit(main())

