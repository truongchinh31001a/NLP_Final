from __future__ import annotations

import argparse
import json
import logging

from knowledge_core.misconceptions.review_processor import (
    apply_misconception_review,
    prepare_misconception_review,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage misconception human review closure.")
    parser.add_argument(
        "command",
        choices=["prepare-review", "apply-review", "run"],
        nargs="?",
        default="run",
    )
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO")
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level))
    logger = logging.getLogger(__name__)
    if args.command in {"prepare-review", "run"}:
        prepared = prepare_misconception_review()
        logger.info("Prepared misconception review rows: %s", prepared.report["total_candidates"])
    if args.command in {"apply-review", "run"}:
        result = apply_misconception_review()
        logger.info(
            "Review result: %s",
            json.dumps({
                "approved": result.report["approved"],
                "rejected": result.report["rejected"],
                "needs_review": result.report["needs_review"],
                "validation": result.report["validation"]["passed"],
            }, sort_keys=True),
        )
        return 0 if result.report["validation"]["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
