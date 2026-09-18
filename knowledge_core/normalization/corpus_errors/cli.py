from __future__ import annotations

import argparse
import logging
from pathlib import Path

from knowledge_core.normalization.corpus_errors.paths import (
    DEFAULT_INPUT_PATHS,
    DEFAULT_INTERIM_DIR,
    DEFAULT_REPORTS_DIR,
    DEFAULT_REVIEW_DIR,
)
from knowledge_core.normalization.corpus_errors.processor import (
    run_corpus_error_normalization,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalize learner-corpus error labels and map conservative skill candidates.",
    )
    parser.add_argument("command", choices=["run"], nargs="?", default="run")
    parser.add_argument("--clc-fce-errors", default=str(DEFAULT_INPUT_PATHS["clc_fce"]))
    parser.add_argument("--efcamdat-errors", default=str(DEFAULT_INPUT_PATHS["efcamdat"]))
    parser.add_argument("--interim-dir", default=str(DEFAULT_INTERIM_DIR))
    parser.add_argument("--review-dir", default=str(DEFAULT_REVIEW_DIR))
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORTS_DIR))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit-per-source", type=int)
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

    result = run_corpus_error_normalization(
        input_paths={
            "clc_fce": Path(args.clc_fce_errors),
            "efcamdat": Path(args.efcamdat_errors),
        },
        interim_dir=args.interim_dir,
        review_dir=args.review_dir,
        reports_dir=args.reports_dir,
        dry_run=args.dry_run,
        limit_per_source=args.limit_per_source,
    )
    report = result.report
    logger.info("Corpus source errors: %s", report["source_error_counts"])
    logger.info("Normalized errors: %s", report["normalized_error_count"])
    logger.info("Normalization statuses: %s", report["normalization_status_counts"])
    logger.info("Skill mappings: %s", report["skill_mapping_count"])
    logger.info("Review labels: %s", report["review_queue_count"])
    logger.info("Validation passed: %s", report["validation"]["passed"])
    if result.report_path is not None:
        logger.info("Wrote report: %s", result.report_path)
    for label, path in result.output_paths.items():
        logger.info("Wrote %s: %s", label, path)
    return 0 if report["validation"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
