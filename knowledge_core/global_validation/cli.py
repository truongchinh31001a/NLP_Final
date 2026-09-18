from __future__ import annotations

import argparse
import logging
from pathlib import Path

from knowledge_core.global_validation.paths import KNOWLEDGE_CORE_V1_REPORT
from knowledge_core.global_validation.report import run_global_validation
from knowledge_core.storage.config import DEFAULT_VERSION_NAME


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Knowledge Core V1 global validation and persistence checks.",
    )
    parser.add_argument("command", choices=["run"], nargs="?", default="run")
    parser.add_argument("--db-path", default=None)
    parser.add_argument("--version-name", default=DEFAULT_VERSION_NAME)
    parser.add_argument("--report-path", default=str(KNOWLEDGE_CORE_V1_REPORT))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--postgres", action="store_true", help="Attempt live PostgreSQL validation.")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level))
    logger = logging.getLogger(__name__)
    result = run_global_validation(
        db_path=Path(args.db_path) if args.db_path else None,
        version_name=args.version_name,
        report_path=Path(args.report_path),
        dry_run=args.dry_run,
        run_postgres_validation=args.postgres,
    )
    report = result.report
    logger.info("Validation result: %s", report["validation_result"])
    logger.info("Taxonomy nodes: %s", report["taxonomy"]["node_count"])
    logger.info("Atomic skills: %s", report["taxonomy"]["atomic_skill_count"])
    logger.info("Storage validation: %s", report["storage"]["validation"]["validation_result"])
    logger.info("Idempotency: %s", report["storage"]["idempotency"]["passed"])
    logger.info("PostgreSQL validation: %s", report["postgres_validation"]["status"])
    if result.report_path is not None:
        logger.info("Wrote report: %s", result.report_path)
    return 0 if report["validation_result"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

