import unittest

from app.activities.practice_service import PracticeActivityGeneration
from app.config import AppConfig
from app.conversation.router import ConversationRouter
from app.conversation.schemas import ConversationRoute
from app.conversation.service import ConversationService
from app.intent.interpreter import PracticeIntentInterpreter
from app.intent.parser import IntentParser
from app.persistence.repository import InMemoryLearningRepository
from app.schemas import (
    ConversationIntent,
    GeneratedExerciseSet,
    LearningActivity,
    LearningActivityStatus,
    LearningActivityType,
    PendingClarification,
    PracticePlan,
    PracticeRequest,
)
from app.tutor.service import TutorCapabilityResult


class _StaticRouter:
    def __init__(self, routes: list[ConversationRoute]) -> None:
        self.routes = list(routes)
        self.contexts = []

    def route(self, *, message: str, context):
        self.contexts.append(context)
        if not self.routes:
            raise AssertionError("No route configured for test.")
        return self.routes.pop(0)


class _FakePracticeActivityService:
    def __init__(self) -> None:
        self.calls = []

    def create_practice_activity(
        self,
        *,
        user_id: str,
        raw_text: str,
        conversation_id: str | None = None,
        request_overrides: PracticeRequest | None = None,
        **_kwargs,
    ) -> PracticeActivityGeneration:
        self.calls.append(
            {
                "user_id": user_id,
                "raw_text": raw_text,
                "conversation_id": conversation_id,
                "request_overrides": request_overrides,
            },
        )
        activity = LearningActivity(
            activity_id="activity_service_test",
            conversation_id=conversation_id or "conversation_service_test",
            learner_id=user_id,
            type=LearningActivityType.PRACTICE,
            status=LearningActivityStatus.READY,
            generation_run_id="generation_service_test",
        )
        request = request_overrides or PracticeRequest(
            user_id=user_id,
            raw_text=raw_text,
            topic="passive_voice",
            num_questions=2,
        )
        generated = GeneratedExerciseSet(
            request=request,
            plan=PracticePlan(
                user_id=user_id,
                topic=request.topic or "passive_voice",
                difficulty=request.difficulty or "easy",
                exercise_type=request.exercise_type or "grammar_mcq",
                num_questions=request.num_questions or 2,
                focus_reason="conversation service test",
            ),
            retrieved_chunks=[],
            exercises=[],
            activity_id=activity.activity_id,
            generation_run_id=activity.generation_run_id or "",
        )
        return PracticeActivityGeneration(
            activity=activity,
            generated=generated,
            recommendation="Review this next.",
        )


class _FakeExplainService:
    def explain(self, *, route, context) -> TutorCapabilityResult:
        return TutorCapabilityResult(
            assistant_reply="Explain response",
            ui_action="explain.respond",
            metadata={"conversation_id": context.conversation_id},
        )


class _FakeReviewService:
    def review(self, *, route, context) -> TutorCapabilityResult:
        return TutorCapabilityResult(
            assistant_reply="Review response",
            ui_action="review.open",
            metadata={"activity_id": route.target_activity_id},
        )


class _FakeProgressService:
    def summarize(self, *, user_id: str, route, context) -> TutorCapabilityResult:
        return TutorCapabilityResult(
            assistant_reply=f"Progress response for {user_id}",
            ui_action="progress.open",
            metadata={"metric": route.slots.get("metric")},
        )


class _FakeProfileUpdateService:
    def apply(self, *, user_id: str, route, message: str) -> TutorCapabilityResult:
        return TutorCapabilityResult(
            assistant_reply=f"Profile response for {user_id}",
            ui_action="profile.update",
            metadata={"message": message, "slots": route.slots},
        )


class _FakeGeneralTutorService:
    def respond(self, *, route, context) -> TutorCapabilityResult:
        return TutorCapabilityResult(
            assistant_reply="General response",
            ui_action="conversation.reply",
            metadata={"response_source": "fake"},
        )


class ConversationServiceTests(unittest.TestCase):
    def test_handle_message_persists_user_and_assistant_messages(self) -> None:
        repository = InMemoryLearningRepository()
        conversation_id = str(repository.create_chat_session("learner")["session_id"])
        router = _StaticRouter(
            [
                ConversationRoute(
                    intent=ConversationIntent.GENERAL,
                    confidence=0.61,
                    source="test",
                    reason="test route",
                )
            ],
        )
        service = ConversationService(AppConfig(llm_backend="none"), repository, router)

        result = service.handle_message(
            user_id="learner",
            conversation_id=conversation_id,
            message="hello",
            metadata={"client": "unit"},
        )
        resume = repository.get_chat_resume("learner", session_id=conversation_id)

        self.assertEqual(result.message["role"], "user")
        self.assertEqual(result.assistant_message["role"], "assistant")
        self.assertEqual(result.intent, ConversationIntent.GENERAL)
        self.assertEqual(len(resume["messages"]), 2)
        self.assertEqual(resume["messages"][0]["content"], "hello")
        self.assertEqual(
            result.assistant_message["metadata"]["route"]["next_action"],
            "conversation.reply",
        )

    def test_handle_message_loads_context_state_before_routing(self) -> None:
        repository = InMemoryLearningRepository()
        conversation_id = str(repository.create_chat_session("learner")["session_id"])
        pending = PendingClarification(
            pending_intent=ConversationIntent.REVIEW,
            missing_fields=["activity_id"],
            collected_slots={"question_number": 2},
            active_activity_id="activity_old",
            question="Which activity?",
        )
        repository.save_pending_clarification("learner", conversation_id, pending)
        repository.save_chat_message(
            user_id="learner",
            role="assistant",
            content="Previous answer",
            session_id=conversation_id,
            metadata={"intent": "EXPLAIN"},
            update_memory=False,
        )
        repository.create_learning_activity(
            LearningActivity(
                activity_id="activity_latest",
                conversation_id=conversation_id,
                learner_id="learner",
                type=LearningActivityType.PRACTICE,
                status=LearningActivityStatus.READY,
            ),
        )
        router = _StaticRouter(
            [
                ConversationRoute(
                    intent=ConversationIntent.GENERAL,
                    confidence=0.61,
                    source="test",
                    reason="test route",
                )
            ],
        )
        service = ConversationService(AppConfig(llm_backend="none"), repository, router)

        service.handle_message(
            user_id="learner",
            conversation_id=conversation_id,
            message="continue",
        )
        context = router.contexts[0]

        self.assertEqual(context.conversation_id, conversation_id)
        self.assertEqual(context.active_intent, ConversationIntent.EXPLAIN)
        self.assertEqual(context.pending_clarification.pending_intent, ConversationIntent.REVIEW)
        self.assertEqual(context.pending_clarification.active_activity_id, "activity_old")
        self.assertEqual(context.active_activity.activity_id, "activity_latest")
        self.assertEqual(context.recent_context["active_activity_id"], "activity_latest")
        self.assertTrue(
            any(
                message["role"] == "user" and message["content"] == "continue"
                for message in context.recent_messages
            )
        )

    def test_pending_practice_follow_up_merges_slots_and_clears_state(self) -> None:
        config = AppConfig(llm_backend="none")
        parser = IntentParser(config)
        repository = InMemoryLearningRepository()
        conversation_id = str(repository.create_chat_session("learner")["session_id"])
        service = ConversationService(
            config,
            repository,
            ConversationRouter(config, PracticeIntentInterpreter(config, parser)),
        )

        first = service.handle_message(
            user_id="learner",
            conversation_id=conversation_id,
            message="Minh muon luyen bai.",
        )
        second = service.handle_message(
            user_id="learner",
            conversation_id=conversation_id,
            message="5 cau passive voice.",
        )

        self.assertTrue(first.pending_clarification)
        self.assertEqual(first.ui_action, "clarification.ask")
        self.assertEqual(second.intent, ConversationIntent.PRACTICE)
        self.assertEqual(second.route.slots["topic"], "passive_voice")
        self.assertEqual(second.route.slots["num_questions"], 5)
        self.assertFalse(second.route.needs_clarification)
        self.assertIsNone(
            repository.get_pending_clarification("learner", conversation_id),
        )

    def test_dispatches_practice_capability(self) -> None:
        request = PracticeRequest(
            user_id="learner",
            raw_text="practice",
            topic="passive_voice",
            num_questions=2,
        )
        router = _StaticRouter(
            [
                ConversationRoute(
                    intent=ConversationIntent.PRACTICE,
                    confidence=0.95,
                    source="test",
                    reason="practice",
                    slots={"topic": "passive_voice", "num_questions": 2},
                    practice_request=request,
                )
            ],
        )
        repository = InMemoryLearningRepository()
        conversation_id = str(repository.create_chat_session("learner")["session_id"])
        service = ConversationService(AppConfig(llm_backend="none"), repository, router)
        practice_service = _FakePracticeActivityService()
        service.practice_activity_service = practice_service

        result = service.handle_message(
            user_id="learner",
            conversation_id=conversation_id,
            message="practice passive",
        )

        self.assertEqual(result.ui_action, "practice.start")
        self.assertEqual(result.activity["activity_id"], "activity_service_test")
        self.assertEqual(practice_service.calls[0]["request_overrides"], request)

    def test_dispatches_non_practice_capabilities(self) -> None:
        cases = [
            (
                ConversationRoute(
                    intent=ConversationIntent.EXPLAIN,
                    confidence=0.9,
                    source="test",
                    reason="explain",
                    slots={"concept": "past_perfect"},
                ),
                "Explain response",
                "explain.respond",
            ),
            (
                ConversationRoute(
                    intent=ConversationIntent.REVIEW,
                    confidence=0.9,
                    source="test",
                    reason="review",
                    slots={"activity_id": "activity_1"},
                ),
                "Review response",
                "review.open",
            ),
            (
                ConversationRoute(
                    intent=ConversationIntent.PROGRESS,
                    confidence=0.9,
                    source="test",
                    reason="progress",
                    slots={"metric": "weak_areas"},
                ),
                "Progress response for learner",
                "progress.open",
            ),
            (
                ConversationRoute(
                    intent=ConversationIntent.PROFILE_UPDATE,
                    confidence=0.9,
                    source="test",
                    reason="profile",
                    slots={"preferred_num_questions": 5},
                ),
                "Profile response for learner",
                "profile.update",
            ),
            (
                ConversationRoute(
                    intent=ConversationIntent.GENERAL,
                    confidence=0.7,
                    source="test",
                    reason="general",
                ),
                "General response",
                "conversation.reply",
            ),
        ]

        for route, expected_reply, expected_action in cases:
            with self.subTest(intent=route.intent.value):
                repository = InMemoryLearningRepository()
                conversation_id = str(
                    repository.create_chat_session("learner")["session_id"],
                )
                service = ConversationService(
                    AppConfig(llm_backend="none"),
                    repository,
                    _StaticRouter([route]),
                )
                service.explain_service = _FakeExplainService()
                service.review_service = _FakeReviewService()
                service.progress_service = _FakeProgressService()
                service.profile_update_service = _FakeProfileUpdateService()
                service.general_tutor_service = _FakeGeneralTutorService()

                result = service.handle_message(
                    user_id="learner",
                    conversation_id=conversation_id,
                    message="message",
                )

                self.assertEqual(result.assistant_reply, expected_reply)
                self.assertEqual(result.ui_action, expected_action)
                self.assertEqual(result.assistant_message["content"], expected_reply)


if __name__ == "__main__":
    unittest.main()
