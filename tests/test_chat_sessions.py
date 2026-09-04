import tempfile
import unittest
from pathlib import Path

from app.config import AppConfig
from app.persistence.repository import InMemoryLearningRepository
from app.persistence.sqlite_repository import SQLiteLearningRepository


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


if __name__ == "__main__":
    unittest.main()
