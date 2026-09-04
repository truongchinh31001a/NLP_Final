import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.config import AppConfig
from app.diagnosis.service import ErrorDiagnosisService
from app.learner.knowledge_tracing import BayesianKnowledgeTracer
from app.learner.skill_graph import DEFAULT_SKILL_GRAPH
from app.persistence.sqlite_repository import SQLiteLearningRepository
from app.schemas import (
    ExerciseItem,
    ExerciseOption,
    GeneratedExerciseSet,
    PracticePlan,
    PracticeRequest,
    SessionResult,
)


class LearnerModelTests(unittest.TestCase):
    def test_bkt_updates_mastery_in_expected_directions(self) -> None:
        tracer = BayesianKnowledgeTracer()

        self.assertGreater(tracer.update(0.35, True), 0.35)
        self.assertLess(tracer.update(0.35, False), 0.35)

    def test_skill_graph_resolves_prerequisite_readiness(self) -> None:
        readiness = DEFAULT_SKILL_GRAPH.prerequisite_readiness(
            "grammar.tenses.past_simple_finished_time",
            {"grammar.tenses.present_simple_habits": 0.7},
        )

        self.assertEqual(readiness, 1.0)

    def test_sqlite_repository_persists_skill_mastery_from_answers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "app.db"
            repository = SQLiteLearningRepository(
                AppConfig(sqlite_db_path=str(db_path)),
            )
            generated = GeneratedExerciseSet(
                request=PracticeRequest(
                    user_id="learner",
                    raw_text="practice past simple",
                    topic="tenses",
                    difficulty="easy",
                    exercise_type="grammar_mcq",
                    num_questions=2,
                ),
                plan=PracticePlan(
                    user_id="learner",
                    topic="tenses",
                    difficulty="easy",
                    exercise_type="grammar_mcq",
                    num_questions=2,
                    focus_reason="test",
                    target_subtopic="past_simple_finished_time",
                    target_skill_id="grammar.tenses.past_simple_finished_time",
                ),
                retrieved_chunks=[],
                exercises=[
                    self._exercise("q1", correct_answer="A"),
                    self._exercise("q2", correct_answer="B"),
                ],
            )

            generation_run_id = repository.save_generated_exercise_set(
                generated,
                "test-generator",
            )
            diagnoses = ErrorDiagnosisService().diagnose_batch(
                generated.exercises,
                {"q1": "A", "q2": "A"},
            )
            repository.save_session_result(
                SessionResult(
                    user_id="learner",
                    topic="tenses",
                    score=0.5,
                    correct_count=1,
                    total_questions=2,
                    recommendation="test recommendation",
                    generation_run_id=generation_run_id,
                ),
                generation_run_id=generation_run_id,
                selected_answers={"q1": "A", "q2": "A"},
                answer_diagnoses=diagnoses,
            )

            profile = repository.get_profile("learner")
            skill_id = "grammar.tenses.past_simple_finished_time"
            snapshot = repository.get_personalization_snapshot("learner")
            skill_rows = {
                row["code"]: row for row in snapshot["skill_mastery"]
            }

            self.assertIn(skill_id, profile.skill_mastery)
            self.assertEqual(profile.skill_attempts[skill_id], 2)
            self.assertEqual(skill_rows[skill_id]["attempts_count"], 2)
            self.assertEqual(skill_rows[skill_id]["correct_count"], 1)
            self.assertEqual(skill_rows[skill_id]["incorrect_count"], 1)
            self.assertEqual(skill_rows[skill_id]["status"], "weak")

            with closing(sqlite3.connect(db_path)) as connection:
                diagnosis_count = connection.execute(
                    "SELECT COUNT(*) FROM answer_diagnoses"
                ).fetchone()[0]
                wrong_tense_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM answer_diagnoses
                    WHERE error_type = 'verb_tense'
                    """
                ).fetchone()[0]

            self.assertEqual(diagnosis_count, 2)
            self.assertEqual(wrong_tense_count, 1)

    def _exercise(self, exercise_id: str, correct_answer: str) -> ExerciseItem:
        return ExerciseItem(
            exercise_id=exercise_id,
            exercise_type="grammar_mcq",
            topic="tenses",
            difficulty="easy",
            skill="grammar",
            subtopic="past_simple_finished_time",
            error_tag="wrong_tense",
            question_text=f"{exercise_id} question",
            options=[
                ExerciseOption("A", "A option", is_correct=correct_answer == "A"),
                ExerciseOption("B", "B option", is_correct=correct_answer == "B"),
                ExerciseOption("C", "C option"),
                ExerciseOption("D", "D option"),
            ],
            correct_answer=correct_answer,
            explanation="test explanation",
        )


if __name__ == "__main__":
    unittest.main()
