import tempfile
import unittest
from pathlib import Path

from app.config import AppConfig
from app.persistence.repository import InMemoryLearningRepository
from app.persistence.sqlite_repository import SQLiteLearningRepository
from app.schemas import ConversationIntent, PendingClarification


class ChatSessionRepositoryTests(unittest.TestCase):
    def test_inmemory_repository_lists_and_resumes_chat_sessions(self) -> None:
        repository = InMemoryLearningRepository()

        first_session = repository.create_chat_session("learner")["session_id"]
        repository.save_chat_message(
            "learner",
            "user",
            "practice passive voice",
            session_id=str(first_session),
        )
        second_session = repository.create_chat_session("learner")["session_id"]
        repository.save_chat_message(
            "learner",
            "user",
            "practice travel vocabulary",
            session_id=str(second_session),
        )

        sessions = repository.list_chat_sessions("learner")["sessions"]
        resumed = repository.get_chat_resume(
            "learner",
            session_id=str(first_session),
        )

        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0]["session_id"], second_session)
        self.assertEqual(sessions[0]["message_count"], 1)
        self.assertEqual(resumed["session_id"], first_session)
        self.assertEqual(resumed["messages"][0]["content"], "practice passive voice")

    def test_sqlite_repository_lists_and_resumes_chat_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "app.db"
            repository = SQLiteLearningRepository(
                AppConfig(sqlite_db_path=str(db_path)),
            )

            first_session = repository.create_chat_session("learner")["session_id"]
            repository.save_chat_message(
                "learner",
                "user",
                "practice passive voice",
                session_id=str(first_session),
            )
            second_session = repository.create_chat_session("learner")["session_id"]
            repository.save_chat_message(
                "learner",
                "user",
                "practice travel vocabulary",
                session_id=str(second_session),
            )

            sessions = repository.list_chat_sessions("learner")["sessions"]
            resumed = repository.get_chat_resume(
                "learner",
                session_id=str(first_session),
            )

            self.assertEqual(len(sessions), 2)
            self.assertEqual(sessions[0]["session_id"], second_session)
            self.assertEqual(sessions[0]["message_count"], 1)
            self.assertEqual(resumed["session_id"], first_session)
            self.assertEqual(
                resumed["messages"][0]["content"],
                "practice passive voice",
            )

            with self.assertRaises(LookupError):
                repository.get_chat_resume("learner", session_id="missing")

    def test_inmemory_repository_persists_pending_clarification(self) -> None:
        repository = InMemoryLearningRepository()
        session_id = str(repository.create_chat_session("learner")["session_id"])
        pending = PendingClarification(
            pending_intent=ConversationIntent.PRACTICE,
            missing_fields=["topic"],
            collected_slots={"num_questions": 5},
            question="Ban muon luyen chu de nao?",
        )

        repository.save_pending_clarification("learner", session_id, pending)
        stored = repository.get_pending_clarification("learner", session_id)
        resumed = repository.get_chat_resume("learner", session_id=session_id)
        repository.save_pending_clarification("learner", session_id, None)

        self.assertIsNotNone(stored)
        self.assertEqual(stored.pending_intent, ConversationIntent.PRACTICE)
        self.assertEqual(stored.collected_slots["num_questions"], 5)
        self.assertEqual(
            resumed["pending_clarification"]["pending_intent"],
            "PRACTICE",
        )
        self.assertIsNone(repository.get_pending_clarification("learner", session_id))

    def test_sqlite_repository_persists_pending_clarification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "app.db"
            repository = SQLiteLearningRepository(
                AppConfig(sqlite_db_path=str(db_path)),
            )
            session_id = str(repository.create_chat_session("learner")["session_id"])
            pending = PendingClarification(
                pending_intent=ConversationIntent.REVIEW,
                missing_fields=["activity_id"],
                collected_slots={"question_number": 2},
                question="Ban muon xem lai activity nao?",
            )

            repository.save_pending_clarification("learner", session_id, pending)
            stored = repository.get_pending_clarification("learner", session_id)
            resumed = repository.get_chat_resume("learner", session_id=session_id)
            repository.save_pending_clarification("learner", session_id, None)

            self.assertIsNotNone(stored)
            self.assertEqual(stored.pending_intent, ConversationIntent.REVIEW)
            self.assertEqual(stored.collected_slots["question_number"], 2)
            self.assertEqual(
                resumed["pending_clarification"]["pending_intent"],
                "REVIEW",
            )
            self.assertIsNone(repository.get_pending_clarification("learner", session_id))


if __name__ == "__main__":
    unittest.main()
