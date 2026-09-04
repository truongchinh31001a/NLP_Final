import unittest

from app.activities.practice_service import PracticeActivityService
from app.config import AppConfig
from app.persistence.repository import InMemoryLearningRepository
from app.schemas import LearningActivityStatus, SubmittedAnswer
from practice_fixtures import build_offline_practice_pipeline


class PracticeActivityServiceTests(unittest.TestCase):
    def test_create_and_submit_practice_activity_lifecycle(self) -> None:
        pipeline = build_offline_practice_pipeline()
        conversation = pipeline.create_conversation("learner")

        created = pipeline.create_practice_activity(
            user_id="learner",
            raw_text="Cho toi 2 cau passive voice.",
            conversation_id=conversation["conversation_id"],
        )

        self.assertTrue(created.activity.activity_id)
        self.assertEqual(created.activity.status, LearningActivityStatus.READY)
        self.assertEqual(created.generated.activity_id, created.activity.activity_id)
        self.assertTrue(created.generated.generation_run_id)

        first_exercise = created.generated.exercises[0]
        answers = [
            SubmittedAnswer(
                exercise_id=first_exercise.exercise_id,
                selected_answer=self._wrong_answer(first_exercise),
            ),
            *[
                SubmittedAnswer(
                    exercise_id=exercise.exercise_id,
                    selected_answer=exercise.correct_answer,
                )
                for exercise in created.generated.exercises[1:]
            ],
        ]
        submitted = pipeline.submit_practice_activity(
            user_id="learner",
            activity_id=created.activity.activity_id,
            answers=answers,
        )

        self.assertEqual(submitted.activity.status, LearningActivityStatus.COMPLETED)
        self.assertEqual(submitted.result.activity_id, created.activity.activity_id)
        self.assertEqual(submitted.result.generation_run_id, created.generated.generation_run_id)
        self.assertTrue(submitted.result.session_code)
        self.assertIsNotNone(submitted.result.practice_review)
        self.assertEqual(len(submitted.result.answer_diagnoses), 2)
        self.assertIsNotNone(submitted.next_activity_suggestion)
        self.assertEqual(
            submitted.next_activity_suggestion["topic"],
            created.generated.plan.topic,
        )
        event_statuses = [
            event["status"]
            for event in pipeline.repository.activity_events[created.activity.activity_id]
        ]
        self.assertIn("SUBMITTED", event_statuses)
        self.assertIn("GRADED", event_statuses)
        self.assertEqual(event_statuses[-1], "COMPLETED")
        self.assertLess(event_statuses.index("SUBMITTED"), event_statuses.index("GRADED"))
        loaded_result = pipeline.repository.get_session_result(
            "learner",
            submitted.result.session_code,
        )
        self.assertIsNotNone(loaded_result)
        self.assertEqual(loaded_result.activity_id, created.activity.activity_id)

    def test_generation_failure_marks_activity_failed(self) -> None:
        repository = InMemoryLearningRepository()
        conversation = repository.create_chat_session("learner")
        service = PracticeActivityService(
            AppConfig(llm_backend="none"),
            repository,
            FailingAgent(),
        )

        with self.assertRaises(RuntimeError):
            service.create_practice_activity(
                user_id="learner",
                raw_text="Cho toi 2 cau passive voice.",
                conversation_id=str(conversation["session_id"]),
            )

        failed = repository.get_latest_learning_activity(
            "learner",
            str(conversation["session_id"]),
            statuses=[LearningActivityStatus.FAILED],
        )
        self.assertIsNotNone(failed)
        self.assertEqual(failed.status, LearningActivityStatus.FAILED)

    def _wrong_answer(self, exercise) -> str:
        for option in exercise.options:
            if option.label != exercise.correct_answer:
                return option.label
        return ""


class FailingAgent:
    def create_exercise_set(self, **kwargs):
        _ = kwargs
        raise RuntimeError("generation failed")


if __name__ == "__main__":
    unittest.main()
