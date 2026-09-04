import json
import urllib.error
import urllib.request
import uuid
from collections import Counter
from typing import Any

from app.config import AppConfig
from app.language.translation import BilingualTextNormalizer
from app.schemas import AnswerDiagnosis, GeneratedExerciseSet, PracticeReview, SessionResult


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
