import unittest

from app.schemas import SubmittedAnswer
from app.tutor.service import GeneralTutorService, TutorExplainService
from practice_fixtures import build_offline_practice_pipeline


class FakeTutorLLM:
    backend_name = "fake:tutor"

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[list[dict[str, str]]] = []

    def generate(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        return self.reply


class ConversationCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pipeline = build_offline_practice_pipeline()

    def test_explain_service_uses_retrieval_context_and_persists_reply(self) -> None:
        conversation = self.pipeline.create_conversation("learner")

        result = self.pipeline.handle_conversation_message(
            user_id="learner",
            conversation_id=conversation["conversation_id"],
            message="Past Perfect dung khi nao?",
        )

        self.assertEqual(result.ui_action, "explain.respond")
        self.assertIn("Past Perfect", result.assistant_reply)
        self.assertIn("Tai lieu lien quan", result.assistant_reply)
        self.assertIsNotNone(result.assistant_message)
        metadata = result.assistant_message["metadata"]
        self.assertEqual(metadata["capability"]["topic"], "tenses")
        self.assertEqual(
            metadata["capability"]["sources"][0]["chunk_id"],
            "fixture-passive-voice",
        )
        self.assertEqual(metadata["capability"]["response_source"], "rule-fallback")

    def test_explain_service_uses_llm_response_when_available(self) -> None:
        fake_llm = FakeTutorLLM(
            "LLM explain: Past Perfect dien ta hanh dong xay ra truoc mot moc qua khu.",
        )
        self.pipeline.conversation_service.explain_service = TutorExplainService(
            config=self.pipeline.config,
            retrieval=self.pipeline.retrieval,
            response_llm=fake_llm,
        )
        conversation = self.pipeline.create_conversation("learner")

        result = self.pipeline.handle_conversation_message(
            user_id="learner",
            conversation_id=conversation["conversation_id"],
            message="Past Perfect dung khi nao?",
        )

        self.assertEqual(result.ui_action, "explain.respond")
        self.assertIn("LLM explain", result.assistant_reply)
        self.assertTrue(fake_llm.calls)
        self.assertIn("EXPLAIN_PAYLOAD", fake_llm.calls[0][-1]["content"])
        capability = result.assistant_message["metadata"]["capability"]
        self.assertEqual(capability["response_source"], "llm")
        self.assertEqual(capability["llm_backend"], "fake:tutor")
        self.assertEqual(
            capability["sources"][0]["chunk_id"],
            "fixture-passive-voice",
        )

    def test_progress_service_reads_personalization_snapshot(self) -> None:
        conversation = self.pipeline.create_conversation("learner")
        profile = self.pipeline.repository.get_profile("learner")
        profile.topic_accuracy["passive_voice"] = 0.2
        profile.weak_topics["passive_voice"] = 0.8
        self.pipeline.repository.save_profile(profile)

        result = self.pipeline.handle_conversation_message(
            user_id="learner",
            conversation_id=conversation["conversation_id"],
            message="Toi dang yeu phan nao?",
        )

        self.assertEqual(result.ui_action, "progress.open")
        self.assertIn("Passive Voice", result.assistant_reply)
        self.assertEqual(
            result.assistant_message["metadata"]["capability"]["metric"],
            "weak_areas",
        )
        self.assertTrue(
            result.assistant_message["metadata"]["capability"]["weak_areas"],
        )

    def test_profile_update_service_updates_preferences_goals_and_weak_topics(self) -> None:
        conversation = self.pipeline.create_conversation("learner")

        result = self.pipeline.handle_conversation_message(
            user_id="learner",
            conversation_id=conversation["conversation_id"],
            message=(
                "Tu gio toi muon hoc giao tiep, toi yeu passive voice, "
                "5 cau moi lan."
            ),
        )
        profile = self.pipeline.repository.get_profile("learner")

        self.assertEqual(result.ui_action, "profile.update")
        self.assertEqual(profile.preferred_num_questions, 5)
        self.assertIn("communication", profile.goals)
        self.assertEqual(profile.weak_topics["passive_voice"], 0.75)

    def test_review_service_explains_submitted_activity_question(self) -> None:
        conversation = self.pipeline.create_conversation("learner")
        created = self.pipeline.create_practice_activity(
            user_id="learner",
            raw_text="Cho toi 2 cau passive voice.",
            conversation_id=conversation["conversation_id"],
        )
        first = created.generated.exercises[0]
        wrong_answer = next(
            option.label
            for option in first.options
            if option.label != first.correct_answer
        )
        answers = [
            SubmittedAnswer(
                exercise_id=first.exercise_id,
                selected_answer=wrong_answer,
            ),
            *[
                SubmittedAnswer(
                    exercise_id=exercise.exercise_id,
                    selected_answer=exercise.correct_answer,
                )
                for exercise in created.generated.exercises[1:]
            ],
        ]
        submitted = self.pipeline.submit_practice_activity(
            user_id="learner",
            activity_id=created.activity.activity_id,
            answers=answers,
        )

        result = self.pipeline.handle_conversation_message(
            user_id="learner",
            conversation_id=conversation["conversation_id"],
            message="Tai sao cau 1 sai?",
        )

        self.assertEqual(result.ui_action, "review.open")
        self.assertIn("Cau 1 sai", result.assistant_reply)
        self.assertIn(first.correct_answer, result.assistant_reply)
        self.assertEqual(result.activity["activity_id"], created.activity.activity_id)
        self.assertEqual(
            result.activity["result"]["session_code"],
            submitted.result.session_code,
        )

    def test_general_tutor_service_persists_bounded_reply(self) -> None:
        conversation = self.pipeline.create_conversation("learner")

        result = self.pipeline.handle_conversation_message(
            user_id="learner",
            conversation_id=conversation["conversation_id"],
            message="Chao ban, hom nay minh hoc gi?",
        )

        self.assertEqual(result.ui_action, "conversation.reply")
        self.assertIn("ngu phap", result.assistant_reply)
        self.assertEqual(
            result.assistant_message["metadata"]["capability"]["scope"],
            "english_tutor_general",
        )
        self.assertEqual(
            result.assistant_message["metadata"]["capability"]["response_source"],
            "context-fallback",
        )
        self.assertNotEqual(
            result.assistant_reply,
            "Minh day, ban. Ban co the hoi ngu phap, gui cau can sua, "
            "xem tien do, hoac noi chu de muon luyen tiep.",
        )

    def test_general_tutor_service_uses_llm_response_when_available(self) -> None:
        fake_llm = FakeTutorLLM(
            "LLM general: hom nay minh goi y luyen passive voice vi do la diem yeu.",
        )
        self.pipeline.conversation_service.general_tutor_service = GeneralTutorService(
            config=self.pipeline.config,
            response_llm=fake_llm,
        )
        profile = self.pipeline.repository.get_profile("learner")
        profile.weak_topics["passive_voice"] = 0.9
        self.pipeline.repository.save_profile(profile)
        conversation = self.pipeline.create_conversation("learner")

        result = self.pipeline.handle_conversation_message(
            user_id="learner",
            conversation_id=conversation["conversation_id"],
            message="Chao ban, hom nay minh hoc gi?",
        )

        self.assertEqual(result.ui_action, "conversation.reply")
        self.assertIn("LLM general", result.assistant_reply)
        self.assertTrue(fake_llm.calls)
        payload = fake_llm.calls[0][-1]["content"]
        self.assertIn("GENERAL_CHAT_PAYLOAD", payload)
        self.assertIn("hom nay minh hoc gi", payload)
        self.assertIn("passive_voice", payload)
        capability = result.assistant_message["metadata"]["capability"]
        self.assertEqual(capability["response_source"], "llm")
        self.assertEqual(capability["llm_backend"], "fake:tutor")

    def test_general_tutor_fallback_varies_by_message_context(self) -> None:
        conversation = self.pipeline.create_conversation("learner")

        greeting = self.pipeline.handle_conversation_message(
            user_id="learner",
            conversation_id=conversation["conversation_id"],
            message="Chao ban",
        )
        thanks = self.pipeline.handle_conversation_message(
            user_id="learner",
            conversation_id=conversation["conversation_id"],
            message="Cam on ban",
        )

        self.assertEqual(greeting.ui_action, "conversation.reply")
        self.assertEqual(thanks.ui_action, "conversation.reply")
        self.assertNotEqual(greeting.assistant_reply, thanks.assistant_reply)
        self.assertEqual(
            greeting.assistant_message["metadata"]["capability"]["matched_template"],
            "greeting",
        )
        self.assertEqual(
            thanks.assistant_message["metadata"]["capability"]["matched_template"],
            "thanks",
        )

    def test_general_tutor_accepts_learning_focus_selection(self) -> None:
        fake_llm = FakeTutorLLM("Bad menu repeat.")
        self.pipeline.conversation_service.general_tutor_service = GeneralTutorService(
            config=self.pipeline.config,
            response_llm=fake_llm,
        )
        conversation = self.pipeline.create_conversation("learner")

        result = self.pipeline.handle_conversation_message(
            user_id="learner",
            conversation_id=conversation["conversation_id"],
            message="\u0111\u1ecdc tr\u01b0\u1edbc \u0111i",
        )

        self.assertEqual(result.ui_action, "conversation.reply")
        self.assertIn("reading", result.assistant_reply)
        self.assertIn("doan tieng Anh", result.assistant_reply)
        self.assertNotIn("noi, nghe, doc hay viet", result.assistant_reply.lower())
        self.assertFalse(fake_llm.calls)
        capability = result.assistant_message["metadata"]["capability"]
        self.assertEqual(capability["response_source"], "guided-choice")
        self.assertEqual(capability["learning_focus"], "reading")
        self.assertEqual(capability["matched_template"], "learning_focus_reading")


if __name__ == "__main__":
    unittest.main()
