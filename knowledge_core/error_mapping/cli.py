from __future__ import annotations

import argparse
import json
import logging

from knowledge_core.error_mapping.processor import (
    apply_review_decisions,
    prepare_review_package,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage error-to-skill human review.")
    parser.add_argument(
        "command",
        choices=["prepare-review", "apply-review", "run"],
        nargs="?",
        default="run",
    )
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
    prepared = None
    if args.command in {"prepare-review", "run"}:
        prepared = prepare_review_package()
        logger.info("Prepared mapping review rows: %s", prepared.report["mapping_review_queue"])
        logger.info("Preserved legacy review rows: %s", prepared.report["legacy_normalization_review_rows"])
    if args.command in {"apply-review", "run"}:
        result = apply_review_decisions()
        logger.info(
            "Review result: %s",
            json.dumps(
                {
                    "approved": result.report["approved_mappings"],
                    "rejected": result.report["rejected_mappings"],
                    "needs_review": result.report["needs_review_mappings"],
                    "validation": result.report["validation"]["passed"],
                },
                sort_keys=True,
            ),
        )
        return 0 if result.report["validation"]["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
