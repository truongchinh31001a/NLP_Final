import argparse
import json
import sys
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail CI when offline AI eval metrics fall below thresholds.",
    )
    parser.add_argument(
        "--report-path",
        default="./evals/reports/summary_report.json",
        help="Path to the summary report produced by scripts/run_evals.py.",
    )
    parser.add_argument(
        "--thresholds-path",
        default="./evals/thresholds.json",
        help="JSON object mapping eval group names to minimum scores.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = load_json(args.report_path)
    thresholds = load_json(args.thresholds_path)
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise SystemExit("Eval report is missing a summary object.")
    if not isinstance(thresholds, dict):
        raise SystemExit("Thresholds file must be a JSON object.")

    failures = []
    for metric_name, threshold_value in thresholds.items():
        expected = float(threshold_value)
        actual_value = summary.get(metric_name)
        if actual_value == "skipped":
            continue
        if not isinstance(actual_value, (int, float)):
            failures.append(f"{metric_name}: missing numeric score")
            continue
        actual = float(actual_value)
        if actual < expected:
            failures.append(f"{metric_name}: {actual:.4f} < {expected:.4f}")

    if failures:
        joined = "\n".join(f"- {failure}" for failure in failures)
        raise SystemExit(f"AI eval thresholds failed:\n{joined}")

    print("AI eval thresholds passed.")


def load_json(path: str) -> Any:
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as exc:
        print(f"Missing eval artifact: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
