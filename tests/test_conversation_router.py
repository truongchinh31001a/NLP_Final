import unittest

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


class ConversationRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        config = AppConfig(llm_backend="none")
        parser = IntentParser(config)
        self.router = ConversationRouter(
            config,
            PracticeIntentInterpreter(config, parser),
        )

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
        self.assertFalse(route.needs_clarification)

    def test_review_without_activity_asks_for_clarification(self) -> None:
        route = self.router.route(
            message="Giải thích câu vừa rồi giúp tôi.",
            context=self._context(),
        )

        self.assertEqual(route.intent, ConversationIntent.REVIEW)
        self.assertTrue(route.needs_clarification)
        self.assertEqual(
            route.pending_clarification.pending_intent,
            ConversationIntent.REVIEW,
        )
        self.assertIn("activity_id", route.pending_clarification.missing_fields)

    def test_progress_question_routes_to_progress(self) -> None:
        route = self.router.route(
            message="Tôi đang yếu phần nào?",
            context=self._context(),
        )

        self.assertEqual(route.intent, ConversationIntent.PROGRESS)
        self.assertEqual(route.slots["metric"], "weak_areas")

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

    def test_short_learning_focus_selection_routes_to_general_slot(self) -> None:
        route = self.router.route(
            message="\u0111\u1ecdc tr\u01b0\u1edbc \u0111i",
            context=self._context(active_intent=ConversationIntent.GENERAL),
        )

        self.assertEqual(route.intent, ConversationIntent.GENERAL)
        self.assertEqual(route.slots["learning_focus"], "reading")
        self.assertEqual(route.slots["selection_kind"], "learning_focus")

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

    def _context(
        self,
        *,
        active_intent: ConversationIntent | None = None,
        active_activity: LearningActivity | None = None,
        pending_clarification: PendingClarification | None = None,
    ) -> ConversationTurnContext:
        return ConversationTurnContext(
            conversation_id="conversation_1",
            learner_id="learner",
            profile=LearnerProfile(user_id="learner"),
            active_intent=active_intent,
            active_activity=active_activity,
            pending_clarification=pending_clarification,
        )


if __name__ == "__main__":
    unittest.main()
