import json
import unittest
from unittest.mock import patch

from app.config import AppConfig
from app.conversation.router import ConversationRouter
from app.intent.interpreter import PracticeIntentInterpreter
from app.intent.parser import IntentParser
from app.schemas import (
    ConversationIntent,
    ConversationTurnContext,
    LearnerProfile,
    LearningActivity,
    LearningActivityStatus,
    LearningActivityType,
    PendingClarification,
)


class _FakeHTTPResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class ConversationRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        config = AppConfig(llm_backend="none")
        parser = IntentParser(config)
        self.router = ConversationRouter(
            config,
            PracticeIntentInterpreter(config, parser),
        )

    def test_canonical_practice_request_routes_to_practice(self) -> None:
        route = self.router.route(
            message="Cho t\u00f4i 5 c\u00e2u Past Simple.",
            context=self._context(),
        )

        self.assertEqual(route.intent, ConversationIntent.PRACTICE)
        self.assertEqual(route.practice_request.topic, "tenses")
        self.assertEqual(
            route.practice_request.target_subtopic,
            "past_simple_finished_time",
        )
        self.assertEqual(route.practice_request.num_questions, 5)
        self.assertTrue(route.requires_context)
        self.assertIsNone(route.target_activity_id)
        self.assertEqual(route.missing_slots, [])
        self.assertEqual(route.next_action, "practice.interpret")

    def test_practice_request_routes_to_practice_interpreter(self) -> None:
        route = self.router.route(
            message="Cho tôi 10 câu passive voice.",
            context=self._context(),
        )

        self.assertEqual(route.intent, ConversationIntent.PRACTICE)
        self.assertEqual(route.practice_request.topic, "passive_voice")
        self.assertEqual(route.practice_request.num_questions, 10)
        self.assertEqual(route.slots["topic"], "passive_voice")
        self.assertFalse(route.needs_clarification)

    def test_canonical_explain_request_routes_to_explain(self) -> None:
        route = self.router.route(
            message="Present Perfect d\u00f9ng khi n\u00e0o?",
            context=self._context(),
        )

        self.assertEqual(route.intent, ConversationIntent.EXPLAIN)
        self.assertEqual(route.slots["concept"], "present_perfect")
        self.assertTrue(route.requires_context)
        self.assertEqual(route.next_action, "explain.respond")
        self.assertFalse(route.needs_clarification)

    def test_explain_concept_is_not_forced_into_practice(self) -> None:
        route = self.router.route(
            message="Past Perfect dùng khi nào?",
            context=self._context(),
        )

        self.assertEqual(route.intent, ConversationIntent.EXPLAIN)
        self.assertEqual(route.slots["concept"], "past_perfect")
        self.assertFalse(route.needs_clarification)

    def test_review_uses_active_activity_context(self) -> None:
        activity = LearningActivity(
            activity_id="activity_1",
            conversation_id="conversation_1",
            learner_id="learner",
            type=LearningActivityType.PRACTICE,
            status=LearningActivityStatus.COMPLETED,
            generation_run_id="gen_1",
            session_code="session_1",
        )

        route = self.router.route(
            message="Tại sao câu 3 của tôi sai?",
            context=self._context(active_activity=activity),
        )

        self.assertEqual(route.intent, ConversationIntent.REVIEW)
        self.assertEqual(route.slots["question_number"], 3)
        self.assertEqual(route.slots["activity_id"], "activity_1")
        self.assertEqual(route.target_activity_id, "activity_1")
        self.assertEqual(route.next_action, "review.open")
        self.assertFalse(route.needs_clarification)

    def test_review_prefers_latest_reviewable_activity_over_ready_activity(self) -> None:
        ready_activity = LearningActivity(
            activity_id="activity_ready",
            conversation_id="conversation_1",
            learner_id="learner",
            type=LearningActivityType.PRACTICE,
            status=LearningActivityStatus.READY,
            generation_run_id="gen_ready",
        )
        completed_activity = LearningActivity(
            activity_id="activity_completed",
            conversation_id="conversation_1",
            learner_id="learner",
            type=LearningActivityType.PRACTICE,
            status=LearningActivityStatus.COMPLETED,
            generation_run_id="gen_completed",
            session_code="session_completed",
        )

        route = self.router.route(
            message="Tai sao cau 1 sai?",
            context=self._context(
                active_activity=ready_activity,
                recent_context={"latest_reviewable_activity": completed_activity},
            ),
        )

        self.assertEqual(route.intent, ConversationIntent.REVIEW)
        self.assertEqual(route.slots["activity_id"], "activity_completed")
        self.assertEqual(route.slots["question_number"], 1)

    def test_review_without_activity_asks_for_clarification(self) -> None:
        route = self.router.route(
            message="Giải thích câu vừa rồi giúp tôi.",
            context=self._context(),
        )

        self.assertEqual(route.intent, ConversationIntent.REVIEW)
        self.assertTrue(route.needs_clarification)
        self.assertTrue(route.requires_context)
        self.assertIsNone(route.target_activity_id)
        self.assertEqual(route.missing_slots, ["activity_id"])
        self.assertEqual(route.next_action, "clarification.ask")
        self.assertEqual(
            route.pending_clarification.pending_intent,
            ConversationIntent.REVIEW,
        )
        self.assertIn("activity_id", route.pending_clarification.missing_fields)

    def test_pending_review_clarification_accepts_activity_id_and_question(self) -> None:
        route = self.router.route(
            message="activity_id=activity_api_1 cau 2",
            context=self._context(
                pending_clarification=PendingClarification(
                    pending_intent=ConversationIntent.REVIEW,
                    missing_fields=["activity_id"],
                    collected_slots={"review_focus": "mistake"},
                    question="Ban muon xem lai activity nao?",
                ),
            ),
        )

        self.assertEqual(route.intent, ConversationIntent.REVIEW)
        self.assertEqual(route.slots["activity_id"], "activity_api_1")
        self.assertEqual(route.slots["question_number"], 2)
        self.assertFalse(route.needs_clarification)

    def test_progress_question_routes_to_progress(self) -> None:
        route = self.router.route(
            message="Tôi đang yếu phần nào?",
            context=self._context(),
        )

        self.assertEqual(route.intent, ConversationIntent.PROGRESS)
        self.assertEqual(route.slots["metric"], "weak_areas")
        self.assertTrue(route.requires_context)
        self.assertEqual(route.next_action, "progress.open")

    def test_lowest_skill_question_routes_to_progress(self) -> None:
        route = self.router.route(
            message="Kỹ năng nào thấp nhất?",
            context=self._context(),
        )

        self.assertEqual(route.intent, ConversationIntent.PROGRESS)
        self.assertEqual(route.slots["metric"], "lowest_skill")

    def test_difficulty_feedback_routes_to_profile_update(self) -> None:
        route = self.router.route(
            message="Bài vừa rồi khó quá.",
            context=self._context(),
        )

        self.assertEqual(route.intent, ConversationIntent.PROFILE_UPDATE)
        self.assertEqual(route.slots["difficulty_feedback"], "too_hard")
        self.assertEqual(route.slots["difficulty_delta"], "easier")

    def test_future_preference_routes_to_profile_update(self) -> None:
        route = self.router.route(
            message="Từ giờ cho tôi bài khó hơn và 10 câu mỗi lần.",
            context=self._context(),
        )

        self.assertEqual(route.intent, ConversationIntent.PROFILE_UPDATE)
        self.assertEqual(route.slots["preferred_difficulty"], "hard")
        self.assertEqual(route.slots["preferred_num_questions"], 10)
        self.assertEqual(route.next_action, "profile.update")

    def test_canonical_future_count_preference_routes_to_profile_update(self) -> None:
        route = self.router.route(
            message="T\u1eeb gi\u1edd m\u1ed7i b\u00e0i 5 c\u00e2u th\u00f4i.",
            context=self._context(),
        )

        self.assertEqual(route.intent, ConversationIntent.PROFILE_UPDATE)
        self.assertEqual(route.slots["preferred_num_questions"], 5)
        self.assertTrue(route.requires_context)
        self.assertEqual(route.next_action, "profile.update")

    def test_continue_weakest_area_routes_to_practice(self) -> None:
        route = self.router.route(
            message="Cho tôi luyện tiếp phần tôi yếu nhất.",
            context=self._context(),
        )

        self.assertEqual(route.intent, ConversationIntent.PRACTICE)
        self.assertFalse(route.needs_clarification)

    def test_explain_continuation_uses_recent_intent_context(self) -> None:
        route = self.router.route(
            message="Giải thích tiếp giúp tôi.",
            context=self._context(active_intent=ConversationIntent.EXPLAIN),
        )

        self.assertEqual(route.intent, ConversationIntent.EXPLAIN)

    def test_general_chat_falls_back_to_general(self) -> None:
        route = self.router.route(
            message="Chào bạn, hôm nay mình học gì?",
            context=self._context(),
        )

        self.assertEqual(route.intent, ConversationIntent.GENERAL)
        self.assertFalse(route.requires_context)
        self.assertEqual(route.next_action, "conversation.reply")

    def test_short_reading_focus_selection_routes_to_reading_activity(self) -> None:
        route = self.router.route(
            message="\u0111\u1ecdc tr\u01b0\u1edbc \u0111i",
            context=self._context(active_intent=ConversationIntent.GENERAL),
        )

        self.assertEqual(route.intent, ConversationIntent.READING)
        self.assertEqual(route.slots["learning_focus"], "reading")
        self.assertEqual(route.slots["selection_kind"], "learning_focus")

    def test_short_writing_focus_selection_routes_to_writing_activity(self) -> None:
        route = self.router.route(
            message="viet truoc nhe",
            context=self._context(active_intent=ConversationIntent.GENERAL),
        )

        self.assertEqual(route.intent, ConversationIntent.WRITING)
        self.assertEqual(route.slots["learning_focus"], "writing")
        self.assertEqual(route.slots["selection_kind"], "learning_focus")

    def test_audio_focus_selection_stays_planned_until_audio_stack_exists(self) -> None:
        route = self.router.route(
            message="noi truoc di",
            context=self._context(active_intent=ConversationIntent.GENERAL),
        )

        self.assertEqual(route.intent, ConversationIntent.GENERAL)
        self.assertEqual(route.slots["planned_activity"], "speaking")

    def test_learning_focus_selection_does_not_overmatch_complaint(self) -> None:
        route = self.router.route(
            message="nghe ki phet",
            context=self._context(active_intent=ConversationIntent.GENERAL),
        )

        self.assertEqual(route.intent, ConversationIntent.GENERAL)
        self.assertNotIn("learning_focus", route.slots)

    def test_pending_practice_clarification_preserves_collected_slots(self) -> None:
        route = self.router.route(
            message="5 câu thôi.",
            context=self._context(
                pending_clarification=PendingClarification(
                    pending_intent=ConversationIntent.PRACTICE,
                    missing_fields=["num_questions"],
                    collected_slots={"topic": "passive_voice"},
                    question="Bạn muốn bao nhiêu câu?",
                ),
            ),
        )

        self.assertEqual(route.intent, ConversationIntent.PRACTICE)
        self.assertEqual(route.slots["topic"], "passive_voice")
        self.assertEqual(route.slots["num_questions"], 5)
        self.assertEqual(route.practice_request.topic, "passive_voice")
        self.assertFalse(route.needs_clarification)

    def test_ambiguous_request_uses_llm_fallback_when_enabled(self) -> None:
        router = self._llm_router()
        llm_content = json.dumps(
            {
                "intent": "EXPLAIN",
                "confidence": 0.73,
                "reason": "The learner asks an underspecified English question.",
                "slots": {"concept": "conditionals"},
                "needs_clarification": False,
                "missing_slots": [],
            },
        )

        with patch(
            "app.conversation.router.urllib.request.urlopen",
            return_value=_FakeHTTPResponse({"message": {"content": llm_content}}),
        ):
            route = router.route(
                message="Can you help me understand this bit?",
                context=self._context(),
            )

        self.assertEqual(route.intent, ConversationIntent.EXPLAIN)
        self.assertEqual(route.confidence, 0.73)
        self.assertEqual(route.source, "llm-ollama")
        self.assertTrue(route.requires_context)
        self.assertEqual(route.next_action, "explain.respond")

    def test_low_confidence_llm_route_falls_back_to_general(self) -> None:
        router = self._llm_router()
        llm_content = json.dumps(
            {
                "intent": "REVIEW",
                "confidence": 0.42,
                "reason": "Too uncertain.",
                "slots": {},
                "needs_clarification": False,
                "missing_slots": [],
            },
        )

        with patch(
            "app.conversation.router.urllib.request.urlopen",
            return_value=_FakeHTTPResponse({"message": {"content": llm_content}}),
        ):
            route = router.route(
                message="Maybe that thing from earlier?",
                context=self._context(),
            )

        self.assertEqual(route.intent, ConversationIntent.GENERAL)
        self.assertEqual(route.source, "fallback")
        self.assertEqual(route.confidence, 0.55)
        self.assertFalse(route.requires_context)

    def test_llm_clarification_populates_missing_slots_contract(self) -> None:
        router = self._llm_router()
        llm_content = json.dumps(
            {
                "intent": "REVIEW",
                "confidence": 0.7,
                "reason": "The learner refers to a previous answer without a target.",
                "slots": {"review_focus": "mistake"},
                "needs_clarification": True,
                "missing_slots": ["activity_id"],
                "clarification_question": "Ban muon xem lai bai nao?",
            },
        )

        with patch(
            "app.conversation.router.urllib.request.urlopen",
            return_value=_FakeHTTPResponse({"message": {"content": llm_content}}),
        ):
            route = router.route(
                message="Can we look at the earlier one?",
                context=self._context(),
            )

        self.assertEqual(route.intent, ConversationIntent.REVIEW)
        self.assertTrue(route.needs_clarification)
        self.assertEqual(route.missing_slots, ["activity_id"])
        self.assertEqual(route.next_action, "clarification.ask")
        self.assertEqual(
            route.pending_clarification.pending_intent,
            ConversationIntent.REVIEW,
        )

    def _context(
        self,
        *,
        active_intent: ConversationIntent | None = None,
        active_activity: LearningActivity | None = None,
        pending_clarification: PendingClarification | None = None,
        recent_context: dict | None = None,
    ) -> ConversationTurnContext:
        return ConversationTurnContext(
            conversation_id="conversation_1",
            learner_id="learner",
            profile=LearnerProfile(user_id="learner"),
            active_intent=active_intent,
            active_activity=active_activity,
            pending_clarification=pending_clarification,
            recent_context=recent_context or {},
        )

    def _llm_router(self) -> ConversationRouter:
        config = AppConfig(
            llm_backend="ollama",
            conversation_router_llm_enabled=True,
        )
        parser = IntentParser(config)
        return ConversationRouter(
            config,
            PracticeIntentInterpreter(config, parser),
        )


if __name__ == "__main__":
    unittest.main()
