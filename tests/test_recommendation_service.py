import unittest

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


class RecommendationServiceTests(unittest.TestCase):
    def test_repeated_miss_and_due_review_are_recorded_in_evidence(self) -> None:
        service = RecommendationService()
        generated = GeneratedExerciseSet(
            request=PracticeRequest(
                user_id="learner",
                raw_text="practice passive",
            ),
            plan=PracticePlan(
                user_id="learner",
                topic="passive_voice",
                difficulty="medium",
                exercise_type="grammar_mcq",
                num_questions=2,
                focus_reason="test",
                target_subtopic="present_simple_passive",
            ),
            retrieved_chunks=[],
            exercises=[
                self._exercise("q1"),
                self._exercise("q2"),
            ],
        )
        profile = LearnerProfile(
            user_id="learner",
            goals=["improve grammar for passive voice"],
            preferred_difficulty="medium",
            skill_mastery={
                "grammar.passive_voice.present_simple_passive": 0.42,
                "grammar.tenses.present_simple_habits": 0.82,
            },
        )
        snapshot = {
            "skill_mastery": [
                {
                    "code": "grammar.passive_voice.present_simple_passive",
                    "mastery_probability": 0.42,
                    "next_review_at": "2000-01-01T00:00:00+00:00",
                },
            ],
        }

        recommendation = service.build_next_activity_recommendation(
            result=SessionResult(
                user_id="learner",
                topic="passive_voice",
                score=0.0,
                correct_count=0,
                total_questions=2,
            ),
            profile=profile,
            generated=generated,
            selected_answers={"q1": "A", "q2": "A"},
            personalization_snapshot=snapshot,
        )

        selected = recommendation.evidence["selected_candidate"]
        self.assertEqual(
            recommendation.skill,
            "grammar.passive_voice.present_simple_passive",
        )
        self.assertEqual(selected["recent_misses"], 2)
        self.assertIn("recent_miss", selected["signals"])
        self.assertIn("spaced_review", selected["signals"])
        self.assertEqual(selected["forgetting_risk"], 1.0)
        self.assertIn("spaced review", recommendation.reason)
        self.assertEqual(recommendation.difficulty, "easy")

    def _exercise(self, exercise_id: str) -> ExerciseItem:
        return ExerciseItem(
            exercise_id=exercise_id,
            exercise_type="grammar_mcq",
            topic="passive_voice",
            difficulty="medium",
            skill="grammar",
            subtopic="present_simple_passive",
            question_text="The room ____ every day.",
            options=[
                ExerciseOption("A", "clean", is_correct=False),
                ExerciseOption("B", "is cleaned", is_correct=True),
            ],
            correct_answer="B",
            explanation="Use is + past participle.",
        )


if __name__ == "__main__":
    unittest.main()
