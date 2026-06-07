import unittest

from app.config import AppConfig
from app.intent.interpreter import PracticeIntentInterpreter
from app.intent.parser import IntentParser


class PracticeIntentInterpreterTests(unittest.TestCase):
    def setUp(self) -> None:
        config = AppConfig(llm_backend="none")
        self.interpreter = PracticeIntentInterpreter(config, IntentParser(config))

    def test_continue_request_reuses_last_travel_vocabulary_topic(self) -> None:
        result = self.interpreter.interpret(
            user_id="learner",
            message="Luyện tiếp, mình xin 5 câu",
            profile_context={
                "weak_topics": ["passive_voice"],
                "chat_extracted_facts": {
                    "last_topic_requested": "travel_vocabulary",
                    "recent_topics": ["travel_vocabulary", "passive_voice"],
                },
            },
        )

        self.assertEqual(result.request.topic, "travel_vocabulary")
        self.assertEqual(result.request.exercise_type, "vocabulary_mcq")
        self.assertEqual(result.request.num_questions, 5)
        self.assertFalse(result.needs_clarification)

    def test_explicit_new_topic_wins_over_continuation_memory(self) -> None:
        result = self.interpreter.interpret(
            user_id="learner",
            message="Luyen tiep 5 cau passive voice",
            profile_context={
                "chat_extracted_facts": {
                    "last_topic_requested": "travel_vocabulary",
                },
            },
        )

        self.assertEqual(result.request.topic, "passive_voice")
        self.assertEqual(result.request.exercise_type, "grammar_mcq")
        self.assertEqual(result.request.num_questions, 5)


if __name__ == "__main__":
    unittest.main()
