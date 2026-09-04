from app.learner.skill_graph import DEFAULT_SKILL_GRAPH, SkillGraph
from app.language.translation import BilingualTextNormalizer
from app.schemas import AnswerDiagnosis, ExerciseItem


ERROR_TYPE_MAP = {
    "active_passive_confusion": "voice",
    "missing_be": "auxiliary",
    "past_perfect_confusion": "verb_tense",
    "present_perfect_confusion": "verb_tense",
    "reported_speech_backshift": "reported_speech",
    "subject_verb_agreement": "agreement",
    "stative_verb_error": "verb_aspect",
    "vocabulary_meaning_confusion": "vocabulary_meaning",
    "wrong_condition_type": "conditionals",
    "wrong_future_form": "verb_tense",
    "wrong_participle": "verb_form",
    "wrong_relative_pronoun": "relative_pronoun",
    "wrong_tense": "verb_tense",
}


class ErrorDiagnosisService:
    def __init__(self, skill_graph: SkillGraph | None = None) -> None:
        self.skill_graph = skill_graph or DEFAULT_SKILL_GRAPH
        self.text_normalizer = BilingualTextNormalizer()

    def diagnose(
        self,
        exercise: ExerciseItem,
        selected_answer: str | None,
    ) -> AnswerDiagnosis:
        is_correct = self.text_normalizer.answers_match(
            selected_answer,
            exercise.correct_answer,
        )
        skill_id = self.skill_graph.skill_id_for(
            topic=exercise.topic,
            skill_type=exercise.skill,
            subtopic=exercise.subtopic,
        )
        selected_label = str(selected_answer or "").strip()
        selected_option_text = self._selected_option_text(exercise, selected_label)

        if is_correct:
            return AnswerDiagnosis(
                exercise_id=exercise.exercise_id,
                is_correct=True,
                error_type="correct",
                skill_id=skill_id,
                topic=exercise.topic,
                subtopic=exercise.subtopic,
                subtype="correct_answer",
                severity=0.0,
                mastery_impact=0.06,
                explanation="The selected answer matches the expected answer.",
                evidence={
                    "selected_answer": selected_label,
                    "correct_answer": exercise.correct_answer,
                    "selected_option_text": selected_option_text,
                },
            )

        subtype = self._subtype(exercise, selected_label)
        error_type = self._error_type(exercise, selected_label)
        severity = self._severity(
            exercise=exercise,
            selected_answer=selected_label,
            selected_option_text=selected_option_text,
            error_type=error_type,
        )
        return AnswerDiagnosis(
            exercise_id=exercise.exercise_id,
            is_correct=False,
            error_type=error_type,
            skill_id=skill_id,
            topic=exercise.topic,
            subtopic=exercise.subtopic,
            subtype=subtype,
            severity=severity,
            mastery_impact=round(-0.16 * severity, 3),
            explanation=self._explanation(exercise, error_type, subtype),
            evidence={
                "selected_answer": selected_label,
                "correct_answer": exercise.correct_answer,
                "selected_option_text": selected_option_text,
                "expected_error_tag": exercise.error_tag or "",
                "difficulty": exercise.difficulty,
            },
        )

    def diagnose_batch(
        self,
        exercises: list[ExerciseItem],
        selected_answers: dict[str, str],
    ) -> list[AnswerDiagnosis]:
        return [
            self.diagnose(
                exercise,
                selected_answers.get(exercise.exercise_id),
            )
            for exercise in exercises
        ]

    def _selected_option_text(
        self,
        exercise: ExerciseItem,
        selected_answer: str,
    ) -> str:
        for option in exercise.options:
            if option.label.strip().lower() == selected_answer.lower():
                return option.text
        return ""

    def _error_type(
        self,
        exercise: ExerciseItem,
        selected_answer: str,
    ) -> str:
        if not selected_answer:
            return "missing_answer"
        if exercise.options and not self._selected_option_text(exercise, selected_answer):
            return "invalid_option"
        error_tag = (exercise.error_tag or "").strip().lower()
        if error_tag in ERROR_TYPE_MAP:
            return ERROR_TYPE_MAP[error_tag]
        if "vocabulary" in exercise.topic or exercise.skill == "vocabulary":
            return "vocabulary_meaning"
        if "tense" in error_tag or "past" in str(exercise.subtopic):
            return "verb_tense"
        return error_tag or "incorrect_answer"

    def _subtype(self, exercise: ExerciseItem, selected_answer: str) -> str:
        if not selected_answer:
            return "blank_submission"
        if exercise.options and not self._selected_option_text(exercise, selected_answer):
            return "option_not_in_exercise"
        return exercise.error_tag or exercise.subtopic or "incorrect_answer"

    def _severity(
        self,
        *,
        exercise: ExerciseItem,
        selected_answer: str,
        selected_option_text: str,
        error_type: str,
    ) -> float:
        if error_type == "missing_answer":
            return 0.7
        if error_type == "invalid_option":
            return 0.8

        difficulty_bonus = {
            "easy": 0.12,
            "medium": 0.0,
            "hard": -0.08,
        }.get(exercise.difficulty, 0.0)
        distractor_bonus = 0.08 if selected_option_text else 0.0
        return round(max(0.35, min(0.95, 0.68 + difficulty_bonus + distractor_bonus)), 2)

    def _explanation(
        self,
        exercise: ExerciseItem,
        error_type: str,
        subtype: str,
    ) -> str:
        if error_type == "missing_answer":
            return "No answer was submitted for this item."
        if error_type == "invalid_option":
            return "The submitted answer does not match any available option."
        if exercise.explanation:
            return exercise.explanation
        return (
            f"The answer suggests a {error_type.replace('_', ' ')} issue "
            f"related to {subtype.replace('_', ' ')}."
        )

