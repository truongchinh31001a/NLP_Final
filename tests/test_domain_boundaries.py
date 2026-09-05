import json
import unittest
from dataclasses import asdict

from app.api.schemas import (
    ConversationTurnContextResponseModel,
    LearningActivityResponseModel,
    PendingClarificationResponseModel,
)
from app.schemas import (
    ConversationIntent,
    ConversationTurnContext,
    GeneratedExerciseSet,
    LearnerProfile,
    LearningActivity,
    LearningActivityStatus,
    LearningActivityType,
    PendingClarification,
    PracticePlan,
    PracticeRequest,
)


class DomainBoundaryModelTests(unittest.TestCase):
    def test_conversation_intent_values_are_stable(self) -> None:
        self.assertEqual(
            [intent.value for intent in ConversationIntent],
            [
                "PRACTICE",
                "READING",
                "WRITING",
                "EXPLAIN",
                "REVIEW",
                "PROGRESS",
                "PROFILE_UPDATE",
                "GENERAL",
            ],
        )

    def test_pending_clarification_defaults_are_serializable(self) -> None:
        clarification = PendingClarification(
            pending_intent=ConversationIntent.PRACTICE,
            missing_fields=["num_questions"],
            collected_slots={"topic": "passive_voice"},
            question="How many questions do you want?",
        )
        other = PendingClarification(pending_intent=ConversationIntent.REVIEW)
        payload = json.loads(json.dumps(asdict(clarification)))

        self.assertEqual(payload["pending_intent"], "PRACTICE")
        self.assertEqual(payload["missing_fields"], ["num_questions"])
        self.assertEqual(payload["collected_slots"]["topic"], "passive_voice")
        self.assertEqual(other.missing_fields, [])
        self.assertEqual(other.collected_slots, {})

    def test_learning_activity_defaults_are_serializable_and_isolated(self) -> None:
        activity = LearningActivity(
            activity_id="activity_1",
            conversation_id="conversation_1",
            learner_id="learner",
            type=LearningActivityType.PRACTICE,
            target_skills=["grammar.passive.present_simple_passive"],
            difficulty="easy",
        )
        other = LearningActivity(
            activity_id="activity_2",
            conversation_id="conversation_2",
            learner_id="learner",
            type=LearningActivityType.REVIEW,
        )
        payload = json.loads(json.dumps(asdict(activity)))

        self.assertEqual(activity.status, LearningActivityStatus.CREATED)
        self.assertEqual(payload["type"], "PRACTICE")
        self.assertEqual(payload["status"], "CREATED")
        self.assertIsNone(payload["created_at"])
        self.assertEqual(other.target_skills, [])

    def test_conversation_context_separates_profile_and_activity_state(self) -> None:
        profile = LearnerProfile(
            user_id="learner",
            skill_mastery={"grammar.tenses.present_simple_habits": 0.72},
        )
        activity = LearningActivity(
            activity_id="activity_1",
            conversation_id="conversation_1",
            learner_id="learner",
            type=LearningActivityType.PRACTICE,
        )
        first_context = ConversationTurnContext(
            conversation_id="conversation_1",
            learner_id="learner",
            profile=profile,
            active_intent=ConversationIntent.PRACTICE,
            active_activity=activity,
        )
        second_context = ConversationTurnContext(
            conversation_id="conversation_2",
            learner_id="learner",
            profile=profile,
        )

        first_context.recent_messages.append(
            {"role": "user", "content": "practice passive voice"}
        )

        self.assertIs(first_context.profile, second_context.profile)
        self.assertEqual(
            second_context.profile.skill_mastery,
            {"grammar.tenses.present_simple_habits": 0.72},
        )
        self.assertEqual(second_context.recent_messages, [])
        self.assertEqual(first_context.active_activity.activity_id, "activity_1")

    def test_generated_set_keeps_generation_run_and_activity_ids(self) -> None:
        generated = GeneratedExerciseSet(
            request=PracticeRequest(
                user_id="learner",
                raw_text="practice passive voice",
                topic="passive_voice",
            ),
            plan=PracticePlan(
                user_id="learner",
                topic="passive_voice",
                difficulty="easy",
                exercise_type="grammar_mcq",
                num_questions=2,
                focus_reason="test",
            ),
            retrieved_chunks=[],
            exercises=[],
            activity_id="activity_1",
            generation_run_id="gen_1",
        )
        payload = json.loads(json.dumps(asdict(generated)))

        self.assertEqual(payload["activity_id"], "activity_1")
        self.assertEqual(payload["generation_run_id"], "gen_1")

    def test_api_domain_models_dump_json_values(self) -> None:
        activity = LearningActivityResponseModel(
            activity_id="activity_1",
            conversation_id="conversation_1",
            learner_id="learner",
            type=LearningActivityType.PRACTICE,
        )
        clarification = PendingClarificationResponseModel(
            pending_intent=ConversationIntent.PRACTICE,
            missing_fields=["num_questions"],
            question="How many questions do you want?",
        )
        context = ConversationTurnContextResponseModel(
            conversation_id="conversation_1",
            learner_id="learner",
            active_intent=ConversationIntent.PRACTICE,
            active_activity=activity,
            pending_clarification=clarification,
        )
        payload = context.model_dump(mode="json")

        self.assertEqual(payload["active_intent"], "PRACTICE")
        self.assertEqual(payload["active_activity"]["status"], "CREATED")
        self.assertEqual(
            payload["pending_clarification"]["pending_intent"],
            "PRACTICE",
        )


if __name__ == "__main__":
    unittest.main()
