import tempfile
import unittest
from pathlib import Path

from app.config import AppConfig
from app.onboarding.service import OnboardingInterpreter
from app.persistence.sqlite_repository import SQLiteLearningRepository
from practice_fixtures import build_offline_practice_pipeline


class ProgressiveProfileTests(unittest.TestCase):
    def test_onboarding_interpreter_extracts_multiple_progressive_facts(self) -> None:
        facts = OnboardingInterpreter(
            AppConfig(llm_backend="none"),
        ).extract_progressive_profile_facts(
            "Goi minh la Linh, minh beginner, hoc TOEIC, yeu passive voice, "
            "tu gio 5 cau moi lan theo chu de anime.",
        )

        self.assertEqual(facts["display_name"], "Linh")
        self.assertEqual(facts["level"], "beginner")
        self.assertIn("exam_preparation", facts["goals"])
        self.assertEqual(facts["weak_topics"], ["passive_voice"])
        self.assertEqual(facts["recent_topics"], ["passive_voice"])
        self.assertEqual(facts["last_topic_requested"], "passive_voice")
        self.assertEqual(facts["preferred_num_questions"], 5)
        self.assertEqual(facts["preferred_content_theme"], "anime")

    def test_conversation_turn_enriches_profile_without_onboarding_gate(self) -> None:
        pipeline = build_offline_practice_pipeline()
        conversation = pipeline.create_conversation("learner")

        result = pipeline.handle_conversation_message(
            user_id="learner",
            conversation_id=conversation["conversation_id"],
            message=(
                "Goi minh la Linh, minh beginner, hoc TOEIC, yeu passive voice, "
                "tu gio 5 cau moi lan. Tao 5 cau passive voice."
            ),
        )
        profile = pipeline.repository.get_profile("learner")
        resume = pipeline.repository.get_chat_resume(
            "learner",
            session_id=conversation["conversation_id"],
        )

        self.assertEqual(result.intent.value, "PRACTICE")
        self.assertEqual(result.ui_action, "practice.start")
        self.assertEqual(len(result.activity["exercises"]), 5)
        self.assertEqual(profile.display_name, "Linh")
        self.assertEqual(profile.level, "beginner")
        self.assertIn("exam_preparation", profile.goals)
        self.assertEqual(profile.weak_topics["passive_voice"], 0.75)
        self.assertEqual(profile.preferred_num_questions, 5)
        self.assertFalse(profile.onboarding_completed)
        self.assertEqual(resume["extracted_facts"]["display_name"], "Linh")
        self.assertEqual(
            resume["extracted_facts"]["last_topic_requested"],
            "passive_voice",
        )

    def test_sqlite_memory_merge_keeps_onboarding_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = SQLiteLearningRepository(
                AppConfig(sqlite_db_path=str(Path(temp_dir) / "app.db")),
            )
            conversation = repository.create_chat_session("learner")

            repository.merge_chat_memory_facts(
                "learner",
                {
                    "display_name": "Linh",
                    "level": "beginner",
                    "goals": ["exam_preparation"],
                    "weak_topics": ["passive_voice"],
                    "preferred_difficulty": "easy",
                    "preferred_num_questions": 5,
                    "last_topic_requested": "passive_voice",
                    "recent_topics": ["passive_voice"],
                },
                session_id=str(conversation["session_id"]),
            )
            profile = repository.get_profile("learner")
            resume = repository.get_chat_resume(
                "learner",
                session_id=str(conversation["session_id"]),
            )

            self.assertEqual(profile.display_name, "Linh")
            self.assertEqual(profile.preferred_num_questions, 5)
            self.assertEqual(profile.weak_topics["passive_voice"], 0.75)
            self.assertFalse(profile.onboarding_completed)
            self.assertEqual(
                resume["extracted_facts"]["recent_topics"],
                ["passive_voice"],
            )


if __name__ == "__main__":
    unittest.main()
