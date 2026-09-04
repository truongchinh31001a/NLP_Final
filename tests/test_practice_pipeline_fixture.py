import unittest

from app.schemas import SubmittedAnswer
from practice_fixtures import build_offline_practice_pipeline


class OfflinePracticePipelineFixtureTests(unittest.TestCase):
    def test_generates_and_scores_practice_without_llm(self) -> None:
        pipeline = build_offline_practice_pipeline()

        generated = pipeline.create_exercise_set(
            user_id="learner",
            raw_text="Cho toi 2 cau passive voice",
        )
        answers = [
            SubmittedAnswer(
                exercise_id=exercise.exercise_id,
                selected_answer=exercise.correct_answer,
            )
            for exercise in generated.exercises
        ]
        result = pipeline.score_submission(
            user_id="learner",
            generation_run_id=generated.generation_run_id,
            answers=answers,
        )

        self.assertEqual(len(generated.exercises), 2)
        self.assertTrue(generated.generation_run_id)
        self.assertEqual(result.correct_count, 2)
        self.assertEqual(result.total_questions, 2)
        self.assertEqual(result.score, 1.0)
        self.assertTrue(result.session_code)
        self.assertIsNotNone(result.practice_review)


if __name__ == "__main__":
    unittest.main()
