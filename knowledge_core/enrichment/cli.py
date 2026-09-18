from __future__ import annotations

import argparse
import logging
from pathlib import Path

from knowledge_core.enrichment.paths import (
    DEFAULT_ACCEPTED_MISCONCEPTIONS_PATH,
    DEFAULT_ASSESSMENT_CRITERIA_PATH,
    DEFAULT_ASSESSMENT_PROFILES_PATH,
    DEFAULT_CANDIDATE_MISCONCEPTIONS_PATH,
    DEFAULT_CURATED_DIR,
    DEFAULT_REPORTS_DIR,
    DEFAULT_REVIEW_DIR,
)
from knowledge_core.enrichment.processor import run_knowledge_enrichment


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Enrich existing Knowledge Core V1 artifacts with approved diagnostic evidence.",
    )
    parser.add_argument("command", choices=["run"], nargs="?", default="run")
    parser.add_argument("--assessment-criteria", default=str(DEFAULT_ASSESSMENT_CRITERIA_PATH))
    parser.add_argument("--assessment-profiles", default=str(DEFAULT_ASSESSMENT_PROFILES_PATH))
    parser.add_argument("--accepted-misconceptions", default=str(DEFAULT_ACCEPTED_MISCONCEPTIONS_PATH))
    parser.add_argument("--candidate-misconceptions", default=str(DEFAULT_CANDIDATE_MISCONCEPTIONS_PATH))
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

    result = run_knowledge_enrichment(
        assessment_criteria_path=Path(args.assessment_criteria),
        assessment_profiles_path=Path(args.assessment_profiles),
        accepted_misconceptions_path=Path(args.accepted_misconceptions),
        candidate_misconceptions_path=Path(args.candidate_misconceptions),
        curated_dir=Path(args.curated_dir),
        review_dir=Path(args.review_dir),
        reports_dir=Path(args.reports_dir),
        dry_run=args.dry_run,
    )
    report = result.report
    counts = report["counts"]
    logger.info("Enriched assessment criteria: %s", counts["enriched_assessment_criteria"])
    logger.info("Enriched skill profiles: %s", counts["enriched_skill_profiles"])
    logger.info("Accepted misconceptions: %s", counts["accepted_misconceptions"])
    logger.info("Skill-misconception links: %s", counts["skill_misconception_links"])
    logger.info(
        "Criteria with empirical failure signals: %s",
        counts["criteria_with_empirical_failure_signals"],
    )
    logger.info("Validation passed: %s", report["validation"]["passed"])
    if result.report_path is not None:
        logger.info("Wrote report: %s", result.report_path)
    for label, path in result.output_paths.items():
        logger.info("Wrote %s: %s", label, path)
    return 0 if report["validation"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

