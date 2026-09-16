import unittest

from app.activities.practice_service import PracticeActivityService
from app.config import AppConfig
from app.persistence.repository import InMemoryLearningRepository
from app.schemas import (
    ExerciseItem,
    ExerciseOption,
    GeneratedExerciseSet,
    LearningActivityStatus,
    PracticePlan,
    PracticeRequest,
    SubmittedAnswer,
)
from practice_fixtures import build_offline_practice_pipeline


class PracticeActivityServiceTests(unittest.TestCase):
    def test_activity_exists_before_generation_runs(self) -> None:
        repository = InMemoryLearningRepository()
        conversation = repository.create_chat_session("learner")
        agent = InspectingGenerationAgent(repository)
        service = PracticeActivityService(
            AppConfig(llm_backend="none"),
            repository,
            agent,
        )

        created = service.create_practice_activity(
            user_id="learner",
            raw_text="Cho toi 1 cau passive voice.",
            conversation_id=str(conversation["session_id"]),
        )

        self.assertEqual(agent.seen_activity_id, created.activity.activity_id)
        self.assertEqual(agent.seen_activity_status, LearningActivityStatus.GENERATING)
        self.assertEqual(created.activity.status, LearningActivityStatus.READY)
        self.assertEqual(created.generated.activity_id, created.activity.activity_id)
        self.assertEqual(
            created.activity.generation_run_id,
            created.generated.generation_run_id,
        )

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


class InspectingGenerationAgent:
    def __init__(self, repository: InMemoryLearningRepository) -> None:
        self.repository = repository
        self.seen_activity_id: str | None = None
        self.seen_activity_status: LearningActivityStatus | None = None

    def create_exercise_set(self, **kwargs):
        user_id = kwargs["user_id"]
        activity_id = kwargs["activity_id"]
        activity = self.repository.get_learning_activity(user_id, activity_id)
        self.seen_activity_id = activity_id
        self.seen_activity_status = activity.status if activity is not None else None

        generated = GeneratedExerciseSet(
            request=PracticeRequest(
                user_id=user_id,
                raw_text=kwargs["raw_text"],
                topic="grammar",
                difficulty="easy",
                exercise_type="multiple_choice",
                num_questions=1,
            ),
            plan=PracticePlan(
                user_id=user_id,
                topic="grammar",
                difficulty="easy",
                exercise_type="multiple_choice",
                num_questions=1,
                focus_reason="unit test",
            ),
            retrieved_chunks=[],
            exercises=[
                ExerciseItem(
                    exercise_id="q1",
                    exercise_type="multiple_choice",
                    topic="grammar",
                    difficulty="easy",
                    skill="grammar",
                    subtopic="passive_voice",
                    error_tag="word_order",
                    question_text="Choose the passive sentence.",
                    options=[
                        ExerciseOption("A", "The cake is made by Minh.", True),
                        ExerciseOption("B", "Minh makes the cake."),
                        ExerciseOption("C", "Minh is cake made."),
                        ExerciseOption("D", "The cake Minh made."),
                    ],
                    correct_answer="A",
                    explanation="'Is made' is passive voice.",
                )
            ],
            activity_id=activity_id,
        )
        self.repository.save_generated_exercise_set(generated, "test-inspecting-agent")
        return generated


if __name__ == "__main__":
    unittest.main()
