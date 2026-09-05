import json
import urllib.error
import urllib.request
import uuid
from collections import Counter
from dataclasses import asdict
from typing import Any

from app.config import AppConfig
from app.conversation.schemas import ConversationRoute
from app.language.translation import BilingualTextNormalizer
from app.persistence.repository import LearningRepository
from app.schemas import AnswerDiagnosis, GeneratedExerciseSet, PracticeReview, SessionResult
from app.schemas import (
    ConversationTurnContext,
    LearningActivity,
    LearningActivityStatus,
    LearningActivityType,
)
from app.tutor.service import TutorCapabilityResult


class PracticeReviewService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.text_normalizer = BilingualTextNormalizer()

    def review(
        self,
        result: SessionResult,
        generated: GeneratedExerciseSet,
        selected_answers: dict[str, str],
        answer_diagnoses: list[AnswerDiagnosis] | None = None,
    ) -> PracticeReview:
        details = self._build_answer_details(
            generated,
            selected_answers,
            answer_diagnoses,
        )
        base_review = self._build_rule_based_review(result, generated, details)
        llm_review = self._try_llm_review(result, generated, details, base_review)
        return llm_review or base_review

    def _build_answer_details(
        self,
        generated: GeneratedExerciseSet,
        selected_answers: dict[str, str],
        answer_diagnoses: list[AnswerDiagnosis] | None,
    ) -> list[dict[str, object]]:
        details: list[dict[str, object]] = []
        diagnosis_by_exercise = {
            diagnosis.exercise_id: diagnosis
            for diagnosis in answer_diagnoses or []
        }
        for exercise in generated.exercises:
            selected = selected_answers.get(exercise.exercise_id, "")
            is_correct = self.text_normalizer.answers_match(
                selected,
                exercise.correct_answer,
            )
            diagnosis = diagnosis_by_exercise.get(exercise.exercise_id)
            details.append(
                {
                    "exercise_id": exercise.exercise_id,
                    "question": exercise.question_text,
                    "selected_answer": selected,
                    "correct_answer": exercise.correct_answer,
                    "is_correct": is_correct,
                    "topic": exercise.topic,
                    "subtopic": exercise.subtopic or "general",
                    "error_tag": (
                        diagnosis.subtype
                        if diagnosis is not None and not diagnosis.is_correct
                        else exercise.error_tag or "general"
                    ),
                    "error_type": (
                        diagnosis.error_type if diagnosis is not None else "unknown"
                    ),
                    "severity": diagnosis.severity if diagnosis is not None else 0.0,
                    "skill_id": diagnosis.skill_id if diagnosis is not None else "",
                    "explanation": exercise.explanation,
                }
            )
        return details

    def _build_rule_based_review(
        self,
        result: SessionResult,
        generated: GeneratedExerciseSet,
        details: list[dict[str, object]],
    ) -> PracticeReview:
        wrong_details = [detail for detail in details if not detail["is_correct"]]
        correct_details = [detail for detail in details if detail["is_correct"]]
        weak_subtopics = self._top_values(wrong_details, "subtopic")
        weak_errors = self._top_values(wrong_details, "error_tag")
        weak_error_types = self._top_values(wrong_details, "error_type")
        strong_subtopics = self._top_values(correct_details, "subtopic")

        if result.score >= 0.8:
            summary = (
                f"Ban lam tot bai {self._label(result.topic)}: "
                f"dung {result.correct_count}/{result.total_questions} cau. "
                "Nen tang do kho hoac luyen bien the gan voi chu de nay."
            )
        elif result.score >= 0.5:
            summary = (
                f"Ban da co nen tang o {self._label(result.topic)}, nhung con "
                f"sai {result.total_questions - result.correct_count} cau. "
                "Nen luyen lai dung nhom loi xuat hien nhieu nhat."
            )
        else:
            summary = (
                f"Bai nay cho thay {self._label(result.topic)} van la diem can "
                "cung co. Nen giam nhip, luyen tung dang loi nho truoc."
            )

        strengths = (
            [
                f"On hon o {self._label(value)}"
                for value in strong_subtopics[:2]
            ]
            if strong_subtopics
            else ["Da hoan thanh bai va co du lieu de ca nhan hoa tiep."]
        )
        weaknesses = (
            [
                f"Hay vuong {self._label(value)}"
                for value in [*weak_subtopics[:2], *weak_error_types[:1], *weak_errors[:1]]
            ]
            if wrong_details
            else ["Chua thay loi noi bat trong bai nay."]
        )
        focus = weak_subtopics[0] if weak_subtopics else result.topic
        next_steps = self._next_steps(result.score, focus, weak_errors)
        next_prompt = self._next_prompt(result, generated, focus, weak_errors)

        return PracticeReview(
            review_code=f"review_{uuid.uuid4().hex}",
            evaluator="rule-based",
            summary=summary,
            strengths=strengths,
            weaknesses=weaknesses,
            next_steps=next_steps,
            next_practice_prompt=next_prompt,
        )

    def _try_llm_review(
        self,
        result: SessionResult,
        generated: GeneratedExerciseSet,
        details: list[dict[str, object]],
        base_review: PracticeReview,
    ) -> PracticeReview | None:
        if self.config.llm_backend.strip().lower() != "ollama":
            return None

        wrong_details = [detail for detail in details if not detail["is_correct"]]
        compact_payload = {
            "learner_summary": generated.plan.learner_summary,
            "topic": result.topic,
            "difficulty": generated.plan.difficulty,
            "score": result.score,
            "correct_count": result.correct_count,
            "total_questions": result.total_questions,
            "wrong_answers": wrong_details[:6],
            "base_review": {
                "summary": base_review.summary,
                "strengths": base_review.strengths,
                "weaknesses": base_review.weaknesses,
                "next_steps": base_review.next_steps,
                "next_practice_prompt": base_review.next_practice_prompt,
            },
        }
        prompt = (
            "You are a serious but encouraging English tutor. "
            "Review this practice session for a Vietnamese learner. "
            "Write every JSON value in Vietnamese only, not English. "
            "Return only valid JSON with keys: summary, strengths, weaknesses, "
            "next_steps, next_practice_prompt. Keep Vietnamese text concise.\n\n"
            f"SESSION_JSON:\n{json.dumps(compact_payload, ensure_ascii=False)}"
        )
        request_payload = {
            "model": self.config.ollama_model,
            "messages": [
                {
                    "role": "system",
                    "content": "Return strict JSON only. No markdown.",
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2},
        }

        url = f"{self.config.ollama_base_url.rstrip('/')}/api/chat"
        request = urllib.request.Request(
            url,
            data=json.dumps(request_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.config.review_llm_timeout_seconds,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
            return None

        raw_content = str(payload.get("message", {}).get("content", "")).strip()
        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError:
            return None

        summary = self._safe_string(parsed.get("summary")) or base_review.summary
        if self._looks_english(summary):
            return None
        return PracticeReview(
            review_code=f"review_{uuid.uuid4().hex}",
            evaluator=f"ollama:{self.config.ollama_model}",
            summary=summary,
            strengths=self._safe_string_list(parsed.get("strengths"))
            or base_review.strengths,
            weaknesses=self._safe_string_list(parsed.get("weaknesses"))
            or base_review.weaknesses,
            next_steps=self._safe_string_list(parsed.get("next_steps"))
            or base_review.next_steps,
            next_practice_prompt=self._safe_string(
                parsed.get("next_practice_prompt")
            )
            or base_review.next_practice_prompt,
            raw_response=raw_content[:4000],
        )

    def _top_values(
        self,
        details: list[dict[str, object]],
        key: str,
    ) -> list[str]:
        counter = Counter(str(detail[key]) for detail in details if detail.get(key))
        return [value for value, _ in counter.most_common()]

    def _next_steps(
        self,
        score: float,
        focus: str,
        weak_errors: list[str],
    ) -> list[str]:
        focus_label = self._label(focus)
        steps = [
            f"Luyen 5-7 cau rieng ve {focus_label}.",
            "Doc lai giai thich cua cac cau sai truoc khi tao bai moi.",
        ]
        if weak_errors:
            steps.append(f"Chu y loi {self._label(weak_errors[0])}.")
        if score >= 0.8:
            steps[0] = f"Tang do kho voi chu de {focus_label}."
        return steps

    def _next_prompt(
        self,
        result: SessionResult,
        generated: GeneratedExerciseSet,
        focus: str,
        weak_errors: list[str],
    ) -> str:
        difficulty = "easy" if result.score < 0.6 else generated.plan.difficulty
        error_part = f", tap trung loi {self._label(weak_errors[0])}" if weak_errors else ""
        return (
            f"Tao {min(max(result.total_questions, 5), 10)} cau trac nghiem "
            f"ve {self._label(focus)} muc {difficulty}{error_part}, "
            "giai thich ngan sau moi cau."
        )

    def _safe_string(self, value: object) -> str:
        return str(value).strip() if isinstance(value, str) else ""

    def _safe_string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _looks_english(self, value: str) -> bool:
        normalized = f" {value.lower()} "
        english_markers = (
            " this ",
            " exercise ",
            " therefore ",
            " practice ",
            " focus ",
            " learner ",
            " should ",
        )
        return any(marker in normalized for marker in english_markers)

    def _label(self, value: str) -> str:
        return value.replace("_", " ").replace(":", " ").title()


class ConversationReviewService:
    """Review capability that answers questions about a prior activity."""

    def __init__(self, repository: LearningRepository) -> None:
        self.repository = repository
        self.text_normalizer = BilingualTextNormalizer()

    def review(
        self,
        *,
        route: ConversationRoute,
        context: ConversationTurnContext,
    ) -> TutorCapabilityResult:
        activity = self._resolve_activity(route, context)
        if activity is None:
            return TutorCapabilityResult(
                assistant_reply=(
                    "Minh can biet ban muon xem lai bai nao. "
                    "Ban gui activity_id hoac noi ro cau so may nhe?"
                ),
                ui_action="clarification.ask",
                metadata={"missing_fields": ["activity_id"]},
            )

        activity_payload = self._activity_payload(activity)
        if activity.type not in {
            LearningActivityType.PRACTICE,
            LearningActivityType.READING,
        }:
            return TutorCapabilityResult(
                assistant_reply=(
                    "Activity nay khong phai bai practice/reading de review "
                    "theo tung cau."
                ),
                ui_action="review.open",
                activity=activity_payload,
                metadata={"activity_id": activity.activity_id},
            )
        if not activity.generation_run_id:
            return TutorCapabilityResult(
                assistant_reply=(
                    "Minh da tim thay activity gan nhat, nhung activity nay "
                    "chua co snapshot bai tap de giai thich chi tiet."
                ),
                ui_action="review.open",
                activity=activity_payload,
                metadata={"activity_id": activity.activity_id},
            )

        generated = self.repository.get_generated_exercise_set(
            context.learner_id,
            activity.generation_run_id,
        )
        if generated is None:
            return TutorCapabilityResult(
                assistant_reply="Minh khong tim thay bo cau hoi cua activity nay.",
                ui_action="review.open",
                activity=activity_payload,
                metadata={"activity_id": activity.activity_id},
            )

        result = (
            self.repository.get_session_result(context.learner_id, activity.session_code)
            if activity.session_code
            else None
        )
        if result is None:
            return TutorCapabilityResult(
                assistant_reply=(
                    "Bai nay da duoc tao nhung chua co ket qua nop bai. "
                    "Ban nop dap an truoc, roi minh se review tung cau."
                ),
                ui_action="review.open",
                activity={
                    **activity_payload,
                    "exercises": [asdict(exercise) for exercise in generated.exercises],
                },
                metadata={"activity_id": activity.activity_id},
            )

        question_index = self._question_index(route, generated)
        exercise = generated.exercises[question_index]
        diagnosis = self._diagnosis_for(result, exercise.exercise_id)
        selected_answer = (
            str(diagnosis.evidence.get("selected_answer") or "")
            if diagnosis is not None
            else ""
        )
        answer_part = (
            f"Ban chon {selected_answer}, dap an dung la {exercise.correct_answer}."
            if selected_answer
            else f"Dap an dung la {exercise.correct_answer}."
        )

        if diagnosis is not None and diagnosis.is_correct:
            reply = (
                f"Cau {question_index + 1} cua ban dung. {answer_part} "
                f"Ly do: {exercise.explanation or diagnosis.explanation}"
            )
        elif diagnosis is not None:
            reply = (
                f"Cau {question_index + 1} sai vi {diagnosis.explanation} "
                f"{answer_part} Goi y: xem lai {self._label(diagnosis.subtype or diagnosis.subtopic or diagnosis.topic)}."
            )
        else:
            reply = (
                f"Cau {question_index + 1}: {answer_part} "
                f"Giai thich: {exercise.explanation}"
            )

        return TutorCapabilityResult(
            assistant_reply=reply,
            ui_action="review.open",
            activity={
                **activity_payload,
                "request": asdict(generated.request),
                "plan": asdict(generated.plan),
                "exercises": [asdict(item) for item in generated.exercises],
                "result": asdict(result),
                "recommendation": result.recommendation,
            },
            metadata={
                "activity_id": activity.activity_id,
                "exercise_id": exercise.exercise_id,
                "question_number": question_index + 1,
                "is_correct": diagnosis.is_correct if diagnosis is not None else None,
            },
        )

    def _resolve_activity(
        self,
        route: ConversationRoute,
        context: ConversationTurnContext,
    ) -> LearningActivity | None:
        activity_id = route.slots.get("activity_id")
        if activity_id:
            activity = self.repository.get_learning_activity(
                context.learner_id,
                str(activity_id),
            )
            if activity is not None:
                return activity
        if self._is_reviewable_activity(context.active_activity):
            return context.active_activity
        latest_reviewable = context.recent_context.get("latest_reviewable_activity")
        if isinstance(latest_reviewable, LearningActivity):
            return latest_reviewable
        latest_activity = context.recent_context.get("latest_activity")
        if isinstance(latest_activity, LearningActivity):
            return latest_activity
        return context.active_activity

    def _is_reviewable_activity(
        self,
        activity: LearningActivity | None,
    ) -> bool:
        if activity is None:
            return False
        return bool(activity.session_code) or activity.status in {
            LearningActivityStatus.SUBMITTED,
            LearningActivityStatus.GRADED,
            LearningActivityStatus.COMPLETED,
        }

    def _question_index(
        self,
        route: ConversationRoute,
        generated: GeneratedExerciseSet,
    ) -> int:
        raw_question_number = route.slots.get("question_number")
        if isinstance(raw_question_number, int):
            return max(0, min(raw_question_number - 1, len(generated.exercises) - 1))
        return max(0, len(generated.exercises) - 1)

    def _diagnosis_for(
        self,
        result: SessionResult,
        exercise_id: str,
    ) -> AnswerDiagnosis | None:
        for diagnosis in result.answer_diagnoses:
            if diagnosis.exercise_id == exercise_id:
                return diagnosis
        return None

    def _activity_payload(self, activity: LearningActivity) -> dict[str, Any]:
        return self._json_safe(asdict(activity))

    def _label(self, value: str) -> str:
        return value.replace("_", " ").replace(":", " ").title()

    def _json_safe(self, value: Any) -> Any:
        if hasattr(value, "value"):
            return value.value
        if isinstance(value, dict):
            return {str(key): self._json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._json_safe(item) for item in value]
        return value
