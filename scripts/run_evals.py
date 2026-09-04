import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.diagnosis.service import ErrorDiagnosisService
from app.generation.validator import ExerciseValidator
from app.recommendation.service import RecommendationService
from app.schemas import (
    ExerciseItem,
    ExerciseOption,
    GeneratedExerciseSet,
    LearnerProfile,
    PracticePlan,
    PracticeRequest,
    SessionResult,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run offline AI evaluation suite.")
    parser.add_argument(
        "--skip-retrieval",
        action="store_true",
        help="Skip retrieval eval when LangChain dependencies are unavailable.",
    )
    parser.add_argument(
        "--report-path",
        default="./evals/reports/summary_report.json",
        help="Where to write the summary report.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = {
        "generation": evaluate_generation_schema(),
        "diagnosis": evaluate_diagnosis(),
        "recommendation": evaluate_recommendation(),
        "retrieval": (
            {
                "status": "skipped",
                "reason": "retrieval eval was disabled by --skip-retrieval",
            }
            if args.skip_retrieval
            else evaluate_retrieval_subprocess()
        ),
    }
    report["summary"] = {
        group: summary_value(group_report)
        for group, group_report in report.items()
        if isinstance(group_report, dict) and group != "summary"
    }
    write_json(report, args.report_path)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


def evaluate_generation_schema() -> dict[str, Any]:
    cases = load_json("./evals/datasets/generation_schema_cases.json")
    validator = ExerciseValidator()
    passed = 0
    rows = []
    for case in cases:
        exercises = [exercise_from_record(record) for record in case["exercises"]]
        actual_valid = True
        error = ""
        try:
            validator.validate(exercises, expected_count=int(case["expected_count"]))
        except ValueError as exc:
            actual_valid = False
            error = str(exc)
        is_pass = actual_valid is bool(case["is_valid"])
        passed += int(is_pass)
        rows.append(
            {
                "case_id": case["case_id"],
                "expected_valid": case["is_valid"],
                "actual_valid": actual_valid,
                "passed": is_pass,
                "error": error,
            }
        )
    return metric_report("generation_schema_validity", passed, len(cases), rows)


def summary_value(group_report: dict[str, Any]) -> float | str:
    if group_report.get("status") == "skipped":
        return "skipped"
    return float(group_report.get("score", 0.0))


def evaluate_diagnosis() -> dict[str, Any]:
    cases = load_json("./evals/datasets/diagnosis_cases.json")
    service = ErrorDiagnosisService()
    passed = 0
    rows = []
    for case in cases:
        diagnosis = service.diagnose(
            exercise_from_record(case["exercise"]),
            case["selected_answer"],
        )
        is_pass = (
            diagnosis.error_type == case["expected_error_type"]
            and diagnosis.skill_id == case["expected_skill_id"]
        )
        passed += int(is_pass)
        rows.append(
            {
                "case_id": case["case_id"],
                "expected_error_type": case["expected_error_type"],
                "actual_error_type": diagnosis.error_type,
                "expected_skill_id": case["expected_skill_id"],
                "actual_skill_id": diagnosis.skill_id,
                "severity": diagnosis.severity,
                "passed": is_pass,
            }
        )
    return metric_report("diagnosis_accuracy", passed, len(cases), rows)


def evaluate_recommendation() -> dict[str, Any]:
    cases = load_json("./evals/datasets/recommendation_cases.json")
    service = RecommendationService()
    passed = 0
    rows = []
    for case in cases:
        result = SessionResult(**case["result"])
        profile = LearnerProfile(
            user_id=case["result"]["user_id"],
            skill_mastery=case["profile"].get("skill_mastery", {}),
        )
        generated = generated_set_from_records(
            user_id=case["result"]["user_id"],
            topic=case["result"]["topic"],
            exercises=case.get("exercises", []),
        )
        recommendation = service.recommend(
            result,
            profile=profile,
            generated=generated,
            selected_answers=case.get("selected_answers", {}),
        )
        is_pass = all(
            expected in recommendation for expected in case["expected_contains"]
        )
        passed += int(is_pass)
        rows.append(
            {
                "case_id": case["case_id"],
                "recommendation": recommendation,
                "expected_contains": case["expected_contains"],
                "passed": is_pass,
            }
        )
    return metric_report("recommendation_policy_match", passed, len(cases), rows)


def evaluate_retrieval_subprocess() -> dict[str, Any]:
    report_path = Path("./evals/reports/retrieval_report.json")
    command = [
        sys.executable,
        "scripts/evaluate_retrieval.py",
        "--report-path",
        str(report_path),
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return {
            "status": "error",
            "score": 0.0,
            "stdout": completed.stdout[-2000:],
            "stderr": completed.stderr[-2000:],
        }
    if not report_path.exists():
        return {"status": "error", "score": 0.0, "stderr": "missing report"}
    report = load_json(report_path)
    metrics = report.get("metrics", {})
    return {
        "status": "ok",
        "score": float(metrics.get("recall_at_k", 0.0)),
        "metrics": metrics,
        "report_path": str(report_path),
    }


def generated_set_from_records(
    *,
    user_id: str,
    topic: str,
    exercises: list[dict[str, Any]],
) -> GeneratedExerciseSet:
    return GeneratedExerciseSet(
        request=PracticeRequest(user_id=user_id, raw_text="eval"),
        plan=PracticePlan(
            user_id=user_id,
            topic=topic,
            difficulty="medium",
            exercise_type="grammar_mcq",
            num_questions=max(len(exercises), 1),
            focus_reason="eval",
        ),
        retrieved_chunks=[],
        exercises=[exercise_from_record(record) for record in exercises],
    )


def exercise_from_record(record: dict[str, Any]) -> ExerciseItem:
    return ExerciseItem(
        exercise_id=str(record["exercise_id"]),
        exercise_type=str(record["exercise_type"]),
        topic=str(record["topic"]),
        difficulty=str(record["difficulty"]),
        skill=str(record.get("skill", "")),
        subtopic=record.get("subtopic"),
        error_tag=record.get("error_tag"),
        question_text=str(record["question_text"]),
        options=[
            ExerciseOption(
                label=str(option["label"]),
                text=str(option["text"]),
                is_correct=bool(option["is_correct"]),
            )
            for option in record.get("options", [])
        ],
        correct_answer=str(record["correct_answer"]),
        explanation=str(record["explanation"]),
    )


def metric_report(
    name: str,
    passed: int,
    total: int,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": "ok",
        "metric": name,
        "passed": passed,
        "total": total,
        "score": passed / max(total, 1),
        "rows": rows,
    }


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(payload: dict[str, Any], path: str | Path) -> None:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
