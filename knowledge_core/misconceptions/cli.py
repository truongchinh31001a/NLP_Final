from __future__ import annotations

import argparse
import logging
from pathlib import Path

from knowledge_core.misconceptions.paths import (
    DEFAULT_CURATED_DIR,
    DEFAULT_ERROR_NORMALIZATION_REPORT,
    DEFAULT_ERROR_SKILL_MAPPINGS_PATH,
    DEFAULT_INTERIM_DIR,
    DEFAULT_NORMALIZED_ERRORS_PATH,
    DEFAULT_REPORTS_DIR,
    DEFAULT_REVIEW_DIR,
    DEFAULT_SOURCE_RECORD_PATHS,
)
from knowledge_core.misconceptions.processor import run_misconception_mining


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mine pending misconception candidates from normalized corpus errors.",
    )
    parser.add_argument("command", choices=["run"], nargs="?", default="run")
    parser.add_argument("--normalized-errors", default=str(DEFAULT_NORMALIZED_ERRORS_PATH))
    parser.add_argument("--error-skill-mappings", default=str(DEFAULT_ERROR_SKILL_MAPPINGS_PATH))
    parser.add_argument("--error-normalization-report", default=str(DEFAULT_ERROR_NORMALIZATION_REPORT))
    parser.add_argument("--clc-fce-source-records", default=str(DEFAULT_SOURCE_RECORD_PATHS["clc_fce"]))
    parser.add_argument("--efcamdat-source-records", default=str(DEFAULT_SOURCE_RECORD_PATHS["efcamdat"]))
    parser.add_argument("--interim-dir", default=str(DEFAULT_INTERIM_DIR))
    parser.add_argument("--curated-dir", default=str(DEFAULT_CURATED_DIR))
    parser.add_argument("--review-dir", default=str(DEFAULT_REVIEW_DIR))
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORTS_DIR))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level))
    logger = logging.getLogger(__name__)

    result = run_misconception_mining(
        normalized_errors_path=Path(args.normalized_errors),
        error_skill_mappings_path=Path(args.error_skill_mappings),
        error_normalization_report=Path(args.error_normalization_report),
        source_record_paths={
            "clc_fce": Path(args.clc_fce_source_records),
            "efcamdat": Path(args.efcamdat_source_records),
        },
        interim_dir=args.interim_dir,
        curated_dir=args.curated_dir,
        review_dir=args.review_dir,
        reports_dir=args.reports_dir,
        dry_run=args.dry_run,
    )
    report = result.report
    logger.info("Misconception candidates: %s", report["candidate_count"])
    logger.info("Accepted misconceptions: %s", report["accepted_count"])
    logger.info("Source evidence links: %s", report["source_evidence_count"])
    logger.info("Review rows: %s", report["review_queue_count"])
    logger.info("Validation passed: %s", report["validation"]["passed"])
    if result.report_path is not None:
        logger.info("Wrote report: %s", result.report_path)
    for label, path in result.output_paths.items():
        logger.info("Wrote %s: %s", label, path)
    return 0 if report["validation"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
