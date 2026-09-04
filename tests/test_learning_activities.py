import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.config import AppConfig
from app.diagnosis.service import ErrorDiagnosisService
from app.persistence.repository import InMemoryLearningRepository
from app.persistence.sqlite_repository import SQLiteLearningRepository
from app.schemas import (
    ExerciseItem,
    ExerciseOption,
    GeneratedExerciseSet,
    LearningActivity,
    LearningActivityStatus,
    LearningActivityType,
    PracticePlan,
    PracticeRequest,
    SessionResult,
)


class LearningActivityRepositoryTests(unittest.TestCase):
    def test_inmemory_activity_lifecycle_links_generation_and_result(self) -> None:
        repository = InMemoryLearningRepository()
        conversation_id = str(repository.create_chat_session("learner")["session_id"])
        activity = repository.create_learning_activity(
            LearningActivity(
                activity_id="activity_1",
                conversation_id=conversation_id,
                learner_id="learner",
                type=LearningActivityType.PRACTICE,
                target_skills=["grammar.passive_voice.present_simple_passive"],
                difficulty="easy",
            )
        )

        repository.update_learning_activity_status(
            "learner",
            activity.activity_id,
            LearningActivityStatus.READY,
        )
        generated = self._generated_set("learner", activity_id=activity.activity_id)
        generation_run_id = repository.save_generated_exercise_set(
            generated,
            "test-generator",
        )
        diagnoses = ErrorDiagnosisService().diagnose_batch(
            generated.exercises,
            {"q1": "B", "q2": "A"},
        )
        session_code = repository.save_session_result(
            SessionResult(
                user_id="learner",
                topic="passive_voice",
                score=0.5,
                correct_count=1,
                total_questions=2,
                generation_run_id=generation_run_id,
            ),
            generation_run_id=generation_run_id,
            selected_answers={"q1": "B", "q2": "A"},
            answer_diagnoses=diagnoses,
        )

        loaded = repository.get_learning_activity("learner", activity.activity_id)
        latest_completed = repository.get_latest_learning_activity(
            "learner",
            conversation_id,
            statuses=[LearningActivityStatus.COMPLETED],
        )
        loaded_generated = repository.get_generated_exercise_set(
            "learner",
            generation_run_id,
        )

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.generation_run_id, generation_run_id)
        self.assertEqual(loaded.session_code, session_code)
        self.assertEqual(loaded.status, LearningActivityStatus.COMPLETED)
        self.assertEqual(latest_completed.activity_id, activity.activity_id)
        self.assertEqual(loaded_generated.activity_id, activity.activity_id)
        self.assertNotIn(
            conversation_id,
            repository.active_activity_by_chat_session,
        )
        self.assertGreaterEqual(len(repository.activity_events[activity.activity_id]), 3)

    def test_inmemory_activity_enforces_conversation_owner(self) -> None:
        repository = InMemoryLearningRepository()
        conversation_id = str(repository.create_chat_session("learner")["session_id"])
        activity = repository.create_learning_activity(
            LearningActivity(
                activity_id="activity_1",
                conversation_id=conversation_id,
                learner_id="learner",
                type=LearningActivityType.PRACTICE,
            )
        )

        self.assertIsNone(repository.get_learning_activity("other", activity.activity_id))
        with self.assertRaises(LookupError):
            repository.create_learning_activity(
                LearningActivity(
                    activity_id="activity_2",
                    conversation_id=conversation_id,
                    learner_id="other",
                    type=LearningActivityType.PRACTICE,
                )
            )
        with self.assertRaises(LookupError):
            repository.get_latest_learning_activity("other", conversation_id)

    def test_sqlite_activity_lifecycle_links_generation_and_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "app.db"
            repository = SQLiteLearningRepository(
                AppConfig(sqlite_db_path=str(db_path)),
            )
            conversation_id = str(repository.create_chat_session("learner")["session_id"])
            activity = repository.create_learning_activity(
                LearningActivity(
                    activity_id="activity_1",
                    conversation_id=conversation_id,
                    learner_id="learner",
                    type=LearningActivityType.PRACTICE,
                    target_skills=["grammar.passive_voice.present_simple_passive"],
                    difficulty="easy",
                    metadata={"source": "test"},
                )
            )

            repository.update_learning_activity_status(
                "learner",
                activity.activity_id,
                LearningActivityStatus.READY,
            )
            generated = self._generated_set("learner", activity_id=activity.activity_id)
            generation_run_id = repository.save_generated_exercise_set(
                generated,
                "test-generator",
            )
            diagnoses = ErrorDiagnosisService().diagnose_batch(
                generated.exercises,
                {"q1": "B", "q2": "A"},
            )
            session_code = repository.save_session_result(
                SessionResult(
                    user_id="learner",
                    topic="passive_voice",
                    score=0.5,
                    correct_count=1,
                    total_questions=2,
                    generation_run_id=generation_run_id,
                ),
                generation_run_id=generation_run_id,
                selected_answers={"q1": "B", "q2": "A"},
                answer_diagnoses=diagnoses,
            )

            loaded = repository.get_learning_activity("learner", activity.activity_id)
            latest_completed = repository.get_latest_learning_activity(
                "learner",
                conversation_id,
                statuses=[
                    LearningActivityStatus.GRADED,
                    LearningActivityStatus.COMPLETED,
                ],
            )
            loaded_generated = repository.get_generated_exercise_set(
                "learner",
                generation_run_id,
            )

            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.generation_run_id, generation_run_id)
            self.assertEqual(loaded.session_code, session_code)
            self.assertEqual(loaded.status, LearningActivityStatus.COMPLETED)
            self.assertEqual(loaded.metadata, {"source": "test"})
            self.assertEqual(latest_completed.activity_id, activity.activity_id)
            self.assertEqual(loaded_generated.activity_id, activity.activity_id)

            with closing(sqlite3.connect(db_path)) as connection:
                activity_db_id = connection.execute(
                    "SELECT id FROM learning_activities WHERE activity_code = ?",
                    (activity.activity_id,),
                ).fetchone()[0]
                generation_activity_id = connection.execute(
                    """
                    SELECT activity_id
                    FROM generation_runs
                    WHERE generation_run_id = ?
                    """,
                    (generation_run_id,),
                ).fetchone()[0]
                session_activity_id = connection.execute(
                    """
                    SELECT activity_id
                    FROM practice_sessions
                    WHERE session_code = ?
                    """,
                    (session_code,),
                ).fetchone()[0]
                active_activity_id = connection.execute(
                    """
                    SELECT active_activity_id
                    FROM chat_sessions
                    WHERE session_code = ?
                    """,
                    (conversation_id,),
                ).fetchone()[0]
                event_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM learning_activity_events
                    WHERE activity_id = ?
                    """,
                    (activity_db_id,),
                ).fetchone()[0]

            self.assertEqual(generation_activity_id, activity_db_id)
            self.assertEqual(session_activity_id, activity_db_id)
            self.assertIsNone(active_activity_id)
            self.assertGreaterEqual(event_count, 3)

    def test_sqlite_activity_enforces_conversation_owner(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = SQLiteLearningRepository(
                AppConfig(sqlite_db_path=str(Path(temp_dir) / "app.db")),
            )
            conversation_id = str(repository.create_chat_session("learner")["session_id"])
            activity = repository.create_learning_activity(
                LearningActivity(
                    activity_id="activity_1",
                    conversation_id=conversation_id,
                    learner_id="learner",
                    type=LearningActivityType.PRACTICE,
                )
            )

            self.assertIsNone(repository.get_learning_activity("other", activity.activity_id))
            with self.assertRaises(LookupError):
                repository.create_learning_activity(
                    LearningActivity(
                        activity_id="activity_2",
                        conversation_id=conversation_id,
                        learner_id="other",
                        type=LearningActivityType.PRACTICE,
                    )
                )
            with self.assertRaises(LookupError):
                repository.get_latest_learning_activity("other", conversation_id)

    def _generated_set(
        self,
        user_id: str,
        activity_id: str | None,
    ) -> GeneratedExerciseSet:
        return GeneratedExerciseSet(
            request=PracticeRequest(
                user_id=user_id,
                raw_text="practice passive voice",
                topic="passive_voice",
                difficulty="easy",
                exercise_type="grammar_mcq",
                num_questions=2,
            ),
            plan=PracticePlan(
                user_id=user_id,
                topic="passive_voice",
                difficulty="easy",
                exercise_type="grammar_mcq",
                num_questions=2,
                focus_reason="test",
                target_subtopic="present_simple_passive",
                target_skill_id="grammar.passive_voice.present_simple_passive",
            ),
            retrieved_chunks=[],
            exercises=[
                self._exercise("q1", "B"),
                self._exercise("q2", "C"),
            ],
            activity_id=activity_id,
        )

    def _exercise(self, exercise_id: str, correct_answer: str) -> ExerciseItem:
        return ExerciseItem(
            exercise_id=exercise_id,
            exercise_type="grammar_mcq",
            topic="passive_voice",
            difficulty="easy",
            skill="grammar",
            subtopic="present_simple_passive",
            error_tag="missing_be",
            question_text=f"{exercise_id} question",
            options=[
                ExerciseOption("A", "active option", is_correct=correct_answer == "A"),
                ExerciseOption("B", "passive option", is_correct=correct_answer == "B"),
                ExerciseOption("C", "past option", is_correct=correct_answer == "C"),
                ExerciseOption("D", "future option", is_correct=correct_answer == "D"),
            ],
            correct_answer=correct_answer,
            explanation="Use be plus a past participle for passive voice.",
        )


if __name__ == "__main__":
    unittest.main()
