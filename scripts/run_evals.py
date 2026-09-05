import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.diagnosis.service import ErrorDiagnosisService
from app.config import AppConfig
from app.conversation.schemas import ConversationRoute
from app.conversation.router import ConversationRouter
from app.generation.validator import ExerciseValidator
from app.intent.interpreter import PracticeIntentInterpreter
from app.intent.parser import IntentParser
from app.llm.factory import LangChainModelFactory
from app.recommendation.service import RecommendationService
from app.schemas import (
    ConversationIntent,
    ConversationTurnContext,
    ExerciseItem,
    ExerciseOption,
    GeneratedExerciseSet,
    KnowledgeChunk,
    LearnerProfile,
    PracticePlan,
    PracticeRequest,
    SessionResult,
)
from app.tutor.service import (
    GeneralTutorService,
    TutorCapabilityResult,
    TutorExplainService,
    TutorResponseLLM,
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
    parser.add_argument(
        "--tutor-live-backends",
        default="",
        help=(
            "Optional comma-separated tutor response backends to compare, "
            "for example 'ollama,openai'. Default runs offline checks only."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = {
        "generation": evaluate_generation_schema(),
        "diagnosis": evaluate_diagnosis(),
        "recommendation": evaluate_recommendation(),
        "tutor_response": evaluate_tutor_response_quality(),
        "explanation_grounding": evaluate_explanation_grounding(),
        "audio_activity_contract": evaluate_audio_activity_contract(),
        "retrieval": (
            {
                "status": "skipped",
                "reason": "retrieval eval was disabled by --skip-retrieval",
            }
            if args.skip_retrieval
            else evaluate_retrieval_subprocess()
        ),
    }
    live_tutor_backends = parse_backend_list(args.tutor_live_backends)
    if live_tutor_backends:
        report["tutor_response_live"] = {
            backend: evaluate_live_tutor_backend(backend)
            for backend in live_tutor_backends
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
    if "score" in group_report:
        return float(group_report.get("score", 0.0))
    nested_scores = [
        float(item["score"])
        for item in group_report.values()
        if isinstance(item, dict)
        and isinstance(item.get("score"), (int, float))
        and item.get("status") != "skipped"
    ]
    if nested_scores:
        return sum(nested_scores) / len(nested_scores)
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
        recommendation = service.build_next_activity_recommendation(
            result=result,
            profile=profile,
            generated=generated,
            selected_answers=case.get("selected_answers", {}),
            personalization_snapshot=case.get("personalization_snapshot"),
        )
        reason = recommendation.reason
        evidence = recommendation.evidence
        evidence_checks = recommendation_evidence_checks(
            evidence,
            case.get("expected_evidence", {}),
        )
        is_pass = all(expected in reason for expected in case["expected_contains"])
        is_pass = is_pass and all(check["passed"] for check in evidence_checks)
        passed += int(is_pass)
        rows.append(
            {
                "case_id": case["case_id"],
                "recommendation": reason,
                "skill": recommendation.skill,
                "evidence": evidence,
                "expected_contains": case["expected_contains"],
                "evidence_checks": evidence_checks,
                "passed": is_pass,
            }
        )
    return metric_report("recommendation_policy_match", passed, len(cases), rows)


def recommendation_evidence_checks(
    evidence: dict[str, Any],
    expected: dict[str, Any],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if not expected:
        return checks
    selected = evidence.get("selected_candidate")
    selected = selected if isinstance(selected, dict) else {}
    if expected.get("selected_skill"):
        checks.append(
            check_result(
                "selected_skill",
                selected.get("skill_id") == expected["selected_skill"],
                {
                    "expected": expected["selected_skill"],
                    "actual": selected.get("skill_id"),
                },
            ),
        )
    for signal in expected.get("signals", []):
        checks.append(
            check_result(
                f"signal:{signal}",
                signal in selected.get("signals", []),
                {"actual": selected.get("signals", [])},
            ),
        )
    if "min_recent_misses" in expected:
        checks.append(
            check_result(
                "min_recent_misses",
                int(selected.get("recent_misses") or 0)
                >= int(expected["min_recent_misses"]),
                {"actual": selected.get("recent_misses")},
            ),
        )
    if expected.get("requires_evidence"):
        checks.append(
            check_result(
                "candidate_scores",
                bool(evidence.get("candidate_scores")),
            ),
        )
    return checks


def evaluate_tutor_response_quality(
    response_llm: TutorResponseLLM | None = None,
    *,
    label: str = "offline",
    require_expected_source: bool = True,
) -> dict[str, Any]:
    cases = load_json("./evals/datasets/tutor_response_cases.json")
    config = AppConfig(llm_backend="none", tutor_response_llm_enabled=False)
    parser = IntentParser(config)
    router = ConversationRouter(config, PracticeIntentInterpreter(config, parser))
    general_service = GeneralTutorService(config=config, response_llm=response_llm)
    explain_service = TutorExplainService(config=config, response_llm=response_llm)

    passed = 0
    rows = []
    response_sources: dict[str, int] = {}
    for case in cases:
        context = tutor_context_from_case(case)
        route = router.route(message=str(case["message"]), context=context)
        if route.intent == ConversationIntent.EXPLAIN:
            result = explain_service.explain(route=route, context=context)
        elif route.intent in {ConversationIntent.READING, ConversationIntent.WRITING}:
            result = TutorCapabilityResult(
                assistant_reply=route.assistant_reply,
                ui_action=f"{route.intent.value.lower()}.start",
                metadata={
                    "response_source": "activity-route",
                    "learning_focus": route.slots.get("learning_focus"),
                },
            )
        elif route.intent == ConversationIntent.GENERAL:
            result = general_service.respond(route=route, context=context)
        else:
            result = None

        assistant_reply = result.assistant_reply if result is not None else ""
        metadata = result.metadata if result is not None else {}
        response_source = str(metadata.get("response_source") or "unsupported")
        response_sources[response_source] = response_sources.get(response_source, 0) + 1
        case_checks = tutor_case_checks(
            case=case,
            route_intent=route.intent.value,
            assistant_reply=assistant_reply,
            metadata=metadata,
            require_expected_source=require_expected_source,
        )
        is_pass = all(check["passed"] for check in case_checks)
        passed += int(is_pass)
        rows.append(
            {
                "case_id": case["case_id"],
                "label": label,
                "intent": route.intent.value,
                "response_source": response_source,
                "learning_focus": metadata.get("learning_focus"),
                "assistant_reply": assistant_reply[:700],
                "checks": case_checks,
                "passed": is_pass,
            }
        )

    report = metric_report("tutor_response_quality", passed, len(cases), rows)
    report["label"] = label
    report["response_sources"] = response_sources
    return report


def evaluate_explanation_grounding() -> dict[str, Any]:
    cases = load_json("./evals/datasets/explanation_grounding_cases.json")
    config = AppConfig(llm_backend="none", tutor_response_llm_enabled=False)
    passed = 0
    rows = []
    for case in cases:
        retrieval = StaticExplanationRetrieval([KnowledgeChunk(**case["chunk"])])
        service = TutorExplainService(config=config, retrieval=retrieval)
        route = ConversationRoute(
            intent=ConversationIntent.EXPLAIN,
            confidence=1.0,
            source="eval",
            reason="grounding eval",
            slots={"concept": case["concept"]},
        )
        context = ConversationTurnContext(
            conversation_id="eval_conversation",
            learner_id="eval_learner",
            profile=LearnerProfile(user_id="eval_learner", level="beginner"),
            recent_messages=[{"role": "user", "content": case["message"]}],
        )
        result = service.explain(route=route, context=context)
        expected = case["expected"]
        normalized_reply = normalize_eval_text(result.assistant_reply)
        sources = result.metadata.get("sources", [])
        source_ids = [
            str(source.get("chunk_id"))
            for source in sources
            if isinstance(source, dict)
        ]
        source_names = [
            str(source.get("source"))
            for source in sources
            if isinstance(source, dict)
        ]
        checks = [
            check_result(
                "response_source",
                result.metadata.get("response_source") == expected["response_source"],
            ),
            check_result("source_chunk", expected["chunk_id"] in source_ids),
            check_result("source_name", expected["source"] in source_names),
            check_result(
                "grounded_reply",
                any(
                    normalize_eval_text(term) in normalized_reply
                    for term in expected.get("must_contain_any", [])
                ),
                {"expected_any": expected.get("must_contain_any", [])},
            ),
        ]
        is_pass = all(check["passed"] for check in checks)
        passed += int(is_pass)
        rows.append(
            {
                "case_id": case["case_id"],
                "assistant_reply": result.assistant_reply[:700],
                "sources": sources,
                "checks": checks,
                "passed": is_pass,
            }
        )
    return metric_report("explanation_source_grounding", passed, len(cases), rows)


def evaluate_audio_activity_contract() -> dict[str, Any]:
    cases = load_json("./evals/datasets/audio_activity_cases.json")
    passed = 0
    rows = []
    for case in cases:
        activity_type = str(case.get("activity_type", ""))
        metadata = case.get("metadata") if isinstance(case.get("metadata"), dict) else {}
        submission = (
            case.get("submission") if isinstance(case.get("submission"), dict) else {}
        )
        expected = case.get("expected") if isinstance(case.get("expected"), dict) else {}
        privacy = metadata.get("privacy")
        privacy = privacy if isinstance(privacy, dict) else {}
        checks = [
            check_result("case_id", bool(str(case.get("case_id", "")).strip())),
            check_result("activity_type", activity_type in {"LISTENING", "SPEAKING"}),
            check_result("metadata", bool(metadata)),
            check_result("submission", bool(submission)),
            check_result("expected", bool(expected)),
            check_result(
                "default_no_raw_audio",
                privacy.get("store_raw_audio_by_default") is False
                and "audio" not in submission
                and "audio_blob" not in submission
                and "audio_base64" not in submission,
            ),
        ]
        if activity_type == "LISTENING":
            checks.extend(audio_listening_checks(metadata, submission, expected))
        elif activity_type == "SPEAKING":
            checks.extend(audio_speaking_checks(metadata, submission, expected))

        is_pass = all(check["passed"] for check in checks)
        passed += int(is_pass)
        rows.append(
            {
                "case_id": case.get("case_id"),
                "activity_type": activity_type,
                "checks": checks,
                "passed": is_pass,
            }
        )
    return metric_report("audio_activity_contract", passed, len(cases), rows)


def audio_listening_checks(
    metadata: dict[str, Any],
    submission: dict[str, Any],
    expected: dict[str, Any],
) -> list[dict[str, Any]]:
    audio_source = metadata.get("audio_source")
    audio_source = audio_source if isinstance(audio_source, dict) else {}
    prompts = metadata.get("comprehension_prompts")
    prompts = prompts if isinstance(prompts, list) else []
    replay_policy = metadata.get("replay_policy")
    replay_policy = replay_policy if isinstance(replay_policy, dict) else {}
    answers = submission.get("answers")
    answers = answers if isinstance(answers, dict) else {}
    return [
        check_result("mode", metadata.get("mode") == "listening"),
        check_result("audio_source_kind", audio_source.get("kind") == "browser_tts"),
        check_result("transcript", bool(str(metadata.get("transcript", "")).strip())),
        check_result("target_skills", bool(metadata.get("target_skills"))),
        check_result("comprehension_prompts", bool(prompts)),
        check_result(
            "prompt_answers",
            all(
                isinstance(prompt, dict) and prompt.get("correct_answer")
                for prompt in prompts
            ),
        ),
        check_result(
            "replay_policy",
            isinstance(replay_policy.get("max_replays"), int)
            and replay_policy.get("max_replays", 0) >= 0,
        ),
        check_result("submission_answers", bool(answers)),
        check_result("ui_action", expected.get("ui_action") == "listening.result"),
    ]


def audio_speaking_checks(
    metadata: dict[str, Any],
    submission: dict[str, Any],
    expected: dict[str, Any],
) -> list[dict[str, Any]]:
    rubric = metadata.get("rubric")
    rubric = rubric if isinstance(rubric, dict) else {}
    retry_policy = metadata.get("retry_policy")
    retry_policy = retry_policy if isinstance(retry_policy, dict) else {}
    stt = metadata.get("stt")
    stt = stt if isinstance(stt, dict) else {}
    return [
        check_result("mode", metadata.get("mode") == "speaking"),
        check_result("prompt", bool(str(metadata.get("prompt", "")).strip())),
        check_result("expected_patterns", bool(metadata.get("expected_patterns"))),
        check_result(
            "rubric",
            {"pronunciation", "fluency", "grammar", "task_completion"}.issubset(
                set(rubric)
            ),
        ),
        check_result(
            "retry_policy",
            isinstance(retry_policy.get("max_attempts"), int)
            and retry_policy.get("max_attempts", 0) > 0,
        ),
        check_result("browser_stt", stt.get("preferred") == "browser_web_speech"),
        check_result("manual_transcript", stt.get("allow_manual_transcript") is True),
        check_result(
            "submission_transcript",
            bool(str(submission.get("transcript", "")).strip()),
        ),
        check_result("ui_action", expected.get("ui_action") == "speaking.result"),
    ]


class StaticExplanationRetrieval:
    def __init__(self, chunks: list[KnowledgeChunk]) -> None:
        self.chunks = chunks

    def retrieve(self, plan: PracticePlan, learner_level: str) -> list[KnowledgeChunk]:
        _ = plan, learner_level
        return self.chunks


def evaluate_live_tutor_backend(backend: str) -> dict[str, Any]:
    backend = backend.strip().lower()
    if backend not in {"ollama", "openai"}:
        return {
            "status": "skipped",
            "score": 0.0,
            "reason": f"unsupported tutor backend: {backend}",
        }
    if backend == "openai" and not os.getenv("OPENAI_API_KEY"):
        return {
            "status": "skipped",
            "score": "skipped",
            "reason": "OPENAI_API_KEY is not configured.",
        }

    config = AppConfig(llm_backend=backend, tutor_response_llm_enabled=True)
    try:
        factory = LangChainModelFactory(config)
        runnable = factory.build_tutor_response_runnable()
    except RuntimeError as exc:
        return {"status": "skipped", "score": "skipped", "reason": str(exc)}

    llm = TutorResponseLLM(
        config=config,
        runnable=runnable,
        backend_name=factory.get_tutor_response_backend_name(),
    )
    report = evaluate_tutor_response_quality(
        llm,
        label=backend,
        require_expected_source=False,
    )
    report["status"] = "ok"
    return report


def tutor_case_checks(
    *,
    case: dict[str, Any],
    route_intent: str,
    assistant_reply: str,
    metadata: dict[str, Any],
    require_expected_source: bool,
) -> list[dict[str, Any]]:
    expected = case.get("expected", {})
    normalized_reply = normalize_eval_text(assistant_reply)
    checks = [
        check_result(
            "intent",
            route_intent == expected.get("intent"),
            {"expected": expected.get("intent"), "actual": route_intent},
        ),
        check_result("non_empty", bool(assistant_reply.strip())),
        check_result(
            "max_chars",
            len(assistant_reply) <= int(expected.get("max_chars", 1600)),
            {
                "actual": len(assistant_reply),
                "limit": int(expected.get("max_chars", 1600)),
            },
        ),
        check_result(
            "no_repeated_menu",
            not has_repeated_menu(normalized_reply),
        ),
    ]

    if require_expected_source and expected.get("response_source"):
        checks.append(
            check_result(
                "response_source",
                metadata.get("response_source") == expected["response_source"],
                {
                    "expected": expected["response_source"],
                    "actual": metadata.get("response_source"),
                },
            ),
        )

    if expected.get("learning_focus"):
        checks.append(
            check_result(
                "learning_focus",
                metadata.get("learning_focus") == expected["learning_focus"],
                {
                    "expected": expected["learning_focus"],
                    "actual": metadata.get("learning_focus"),
                },
            ),
        )

    if expected.get("forbid_learning_focus"):
        checks.append(
            check_result(
                "forbid_learning_focus",
                "learning_focus" not in metadata,
                {"actual": metadata.get("learning_focus")},
            ),
        )

    must_contain_any = expected.get("must_contain_any") or []
    if must_contain_any:
        checks.append(
            check_result(
                "must_contain_any",
                any(normalize_eval_text(term) in normalized_reply for term in must_contain_any),
                {"expected_any": must_contain_any},
            ),
        )

    must_not_contain = expected.get("must_not_contain") or []
    for term in must_not_contain:
        normalized_term = normalize_eval_text(term)
        checks.append(
            check_result(
                f"must_not_contain:{term}",
                normalized_term not in normalized_reply,
            ),
        )

    if expected.get("require_vietnamese_tutor_text"):
        checks.append(
            check_result(
                "vietnamese_tutor_text",
                looks_like_vietnamese_tutor_text(normalized_reply),
            ),
        )

    return checks


def tutor_context_from_case(case: dict[str, Any]) -> ConversationTurnContext:
    context = case.get("context") or {}
    profile_payload = context.get("profile") or {}
    active_intent = parse_conversation_intent(context.get("active_intent"))
    return ConversationTurnContext(
        conversation_id="eval_conversation",
        learner_id="eval_learner",
        profile=LearnerProfile(
            user_id="eval_learner",
            display_name=str(profile_payload.get("display_name") or ""),
            level=str(profile_payload.get("level") or "beginner"),
            preferred_difficulty=profile_payload.get("preferred_difficulty"),
            preferred_num_questions=profile_payload.get("preferred_num_questions"),
            weak_topics=dict(profile_payload.get("weak_topics") or {}),
            skill_mastery=dict(profile_payload.get("skill_mastery") or {}),
        ),
        recent_messages=[
            {"role": "user", "content": str(case.get("message") or "")},
        ],
        memory_summary=str(context.get("memory_summary") or ""),
        active_intent=active_intent,
    )


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
    score_keys = [
        "recall_at_k",
        "metadata_recall_at_k",
        "expected_chunk_recall_at_k",
        "top_1_metadata_match",
    ]
    score = sum(float(metrics.get(key, 0.0)) for key in score_keys) / len(score_keys)
    return {
        "status": "ok",
        "score": score,
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


def parse_backend_list(value: str) -> list[str]:
    return [item.strip().lower() for item in value.split(",") if item.strip()]


def parse_conversation_intent(value: object) -> ConversationIntent | None:
    if not value:
        return None
    try:
        return ConversationIntent(str(value))
    except ValueError:
        return None


def normalize_eval_text(value: str) -> str:
    normalized = value.lower()
    normalized = normalized.replace("+", " ")
    normalized = normalized.replace("/", " ")
    normalized = "".join(
        character if character.isalnum() else " "
        for character in normalized
    )
    return " ".join(normalized.split())


def has_repeated_menu(normalized_reply: str) -> bool:
    menu_patterns = (
        "ban muon tap noi nghe doc hay viet",
        "ban muon hoc gi dau tien",
        "noi nghe doc hay viet",
        "tap noi nghe doc hay viet",
        "speaking listening reading writing",
    )
    return any(pattern in normalized_reply for pattern in menu_patterns)


def looks_like_vietnamese_tutor_text(normalized_reply: str) -> bool:
    markers = (
        "ban",
        "minh",
        "hoc",
        "tieng anh",
        "ngu phap",
        "cau",
        "giai thich",
        "khong",
        "doc",
        "nghe",
        "viet",
        "noi",
    )
    return any(marker in normalized_reply for marker in markers)


def check_result(
    name: str,
    passed: bool,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "passed": bool(passed),
        "details": details or {},
    }


if __name__ == "__main__":
    main()
