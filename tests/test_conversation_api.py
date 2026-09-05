import unittest

from fastapi.testclient import TestClient

from app.api import main as api_main
from app.auth.service import AuthService
from app.schemas import (
    LearningActivity,
    LearningActivityStatus,
    LearningActivityType,
)
from tests.practice_fixtures import build_offline_practice_pipeline


class ConversationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_pipeline = api_main.pipeline
        self.original_auth_service = api_main.auth_service
        api_main.pipeline = build_offline_practice_pipeline()
        api_main.auth_service = AuthService(api_main.pipeline.config)
        self.client = TestClient(api_main.app)

    def tearDown(self) -> None:
        api_main.pipeline = self.original_pipeline
        api_main.auth_service = self.original_auth_service

    def test_create_list_and_get_conversation(self) -> None:
        created = self._create_conversation("learner")

        listed_response = self.client.get(
            "/api/conversations",
            params={"user_id": "learner"},
        )
        detail_response = self.client.get(
            f"/api/conversations/{created['conversation_id']}",
            params={"user_id": "learner"},
        )

        self.assertEqual(listed_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(
            listed_response.json()["conversations"][0]["conversation_id"],
            created["conversation_id"],
        )
        self.assertEqual(
            detail_response.json()["conversation_id"],
            created["conversation_id"],
        )

    def test_message_endpoint_routes_practice_turn(self) -> None:
        conversation = self._create_conversation("learner")
        payload = self._send_message(
            conversation["conversation_id"],
            "Cho tôi 10 câu passive voice.",
        )

        self.assertEqual(payload["intent"], "PRACTICE")
        self.assertEqual(payload["ui_action"], "practice.start")
        self.assertEqual(payload["message"]["role"], "user")
        self.assertEqual(payload["assistant_message"]["role"], "assistant")
        self.assertTrue(payload["activity"]["activity_id"])
        self.assertEqual(payload["activity"]["status"], "READY")
        self.assertTrue(payload["activity"]["generation_run_id"])
        self.assertEqual(len(payload["activity"]["exercises"]), 10)
        self.assertEqual(payload["route"]["slots"]["topic"], "passive_voice")
        self.assertEqual(payload["route"]["slots"]["num_questions"], 10)

    def test_message_endpoint_routes_explain_turn(self) -> None:
        conversation = self._create_conversation("learner")
        payload = self._send_message(
            conversation["conversation_id"],
            "Past Perfect dùng khi nào?",
        )

        self.assertEqual(payload["intent"], "EXPLAIN")
        self.assertEqual(payload["ui_action"], "explain.respond")
        self.assertEqual(payload["route"]["slots"]["concept"], "past_perfect")

    def test_message_endpoint_routes_review_with_latest_activity(self) -> None:
        conversation = self._create_conversation("learner")
        api_main.pipeline.repository.create_learning_activity(
            LearningActivity(
                activity_id="activity_api_1",
                conversation_id=conversation["conversation_id"],
                learner_id="learner",
                type=LearningActivityType.PRACTICE,
                status=LearningActivityStatus.COMPLETED,
                session_code="session_api_1",
            ),
        )

        payload = self._send_message(
            conversation["conversation_id"],
            "Tại sao câu 2 sai?",
        )

        self.assertEqual(payload["intent"], "REVIEW")
        self.assertEqual(payload["ui_action"], "review.open")
        self.assertEqual(payload["activity"]["activity_id"], "activity_api_1")
        self.assertEqual(payload["route"]["slots"]["question_number"], 2)

    def test_message_endpoint_routes_progress_turn(self) -> None:
        conversation = self._create_conversation("learner")
        payload = self._send_message(
            conversation["conversation_id"],
            "Tôi đang yếu phần nào?",
        )

        self.assertEqual(payload["intent"], "PROGRESS")
        self.assertEqual(payload["ui_action"], "progress.open")
        self.assertEqual(payload["route"]["slots"]["metric"], "weak_areas")

    def test_message_endpoint_routes_profile_update_and_updates_preferences(self) -> None:
        conversation = self._create_conversation("learner")
        payload = self._send_message(
            conversation["conversation_id"],
            "Từ giờ cho tôi bài khó hơn và 10 câu mỗi lần.",
        )
        profile = api_main.pipeline.repository.get_profile("learner")

        self.assertEqual(payload["intent"], "PROFILE_UPDATE")
        self.assertEqual(payload["ui_action"], "profile.update")
        self.assertEqual(profile.preferred_difficulty, "hard")
        self.assertEqual(profile.preferred_num_questions, 10)

    def test_message_endpoint_routes_general_turn(self) -> None:
        conversation = self._create_conversation("learner")
        payload = self._send_message(
            conversation["conversation_id"],
            "Chào bạn, hôm nay mình học gì?",
        )

        self.assertEqual(payload["intent"], "GENERAL")
        self.assertEqual(payload["ui_action"], "conversation.reply")
        self.assertNotEqual(
            payload["assistant_reply"],
            "Minh day, ban. Ban co the hoi ngu phap, gui cau can sua, "
            "xem tien do, hoac noi chu de muon luyen tiep.",
        )
        self.assertEqual(
            payload["assistant_message"]["metadata"]["capability"]["response_source"],
            "context-fallback",
        )

    def test_pending_clarification_survives_to_next_turn(self) -> None:
        conversation = self._create_conversation("learner")
        first = self._send_message(
            conversation["conversation_id"],
            "Mình muốn luyện bài.",
        )
        stored_pending = api_main.pipeline.repository.get_pending_clarification(
            "learner",
            conversation["conversation_id"],
        )
        resumed_response = self.client.get(
            f"/api/conversations/{conversation['conversation_id']}",
            params={"user_id": "learner"},
        )
        second = self._send_message(
            conversation["conversation_id"],
            "5 câu passive voice.",
        )

        cleared_pending = api_main.pipeline.repository.get_pending_clarification(
            "learner",
            conversation["conversation_id"],
        )

        self.assertEqual(first["intent"], "PRACTICE")
        self.assertEqual(first["ui_action"], "clarification.ask")
        self.assertEqual(first["pending_clarification"]["pending_intent"], "PRACTICE")
        self.assertTrue(first["route"]["missing_slots"])
        self.assertIsNone(first["route"]["referenced_activity_id"])
        self.assertEqual(resumed_response.status_code, 200)
        self.assertEqual(
            resumed_response.json()["pending_clarification"]["pending_intent"],
            "PRACTICE",
        )
        self.assertIsNotNone(stored_pending)
        self.assertEqual(stored_pending.pending_intent.value, "PRACTICE")
        self.assertEqual(second["intent"], "PRACTICE")
        self.assertEqual(second["ui_action"], "practice.start")
        self.assertEqual(second["activity"]["status"], "READY")
        self.assertEqual(second["route"]["slots"]["topic"], "passive_voice")
        self.assertEqual(second["route"]["slots"]["num_questions"], 5)
        self.assertIsNone(cleared_pending)

    def test_review_turn_prefers_completed_activity_over_new_unsubmitted_activity(
        self,
    ) -> None:
        conversation = self._create_conversation("learner")
        first_generated_response = self.client.post(
            "/api/practice/generate",
            json={
                "user_id": "learner",
                "conversation_id": conversation["conversation_id"],
                "message": "Create 2 passive voice questions.",
                "topic": "passive_voice",
                "num_questions": 2,
            },
        )
        self.assertEqual(first_generated_response.status_code, 200)
        first_generated = first_generated_response.json()
        first_activity_id = first_generated["activity_id"]
        submit_response = self.client.post(
            f"/api/activities/{first_activity_id}/submit",
            json={
                "user_id": "learner",
                "answers": self._first_wrong_answers(first_generated),
            },
        )
        self.assertEqual(submit_response.status_code, 200)

        second_generated_response = self.client.post(
            "/api/practice/generate",
            json={
                "user_id": "learner",
                "conversation_id": conversation["conversation_id"],
                "message": "Create 1 vocabulary question.",
                "topic": "vocabulary",
                "num_questions": 1,
            },
        )
        self.assertEqual(second_generated_response.status_code, 200)
        second_activity_id = second_generated_response.json()["activity_id"]

        payload = self._send_message(
            conversation["conversation_id"],
            "Tai sao cau 1 sai?",
        )

        self.assertNotEqual(first_activity_id, second_activity_id)
        self.assertEqual(payload["intent"], "REVIEW")
        self.assertEqual(payload["ui_action"], "review.open")
        self.assertEqual(payload["activity"]["activity_id"], first_activity_id)
        self.assertEqual(payload["route"]["slots"]["activity_id"], first_activity_id)
        self.assertEqual(payload["route"]["referenced_activity_id"], first_activity_id)
        self.assertEqual(payload["route"]["slots"]["question_number"], 1)

    def test_generate_and_submit_activity_endpoint(self) -> None:
        conversation = self._create_conversation("learner")
        generated_response = self.client.post(
            "/api/practice/generate",
            json={
                "user_id": "learner",
                "conversation_id": conversation["conversation_id"],
                "message": "Cho toi 2 cau passive voice.",
                "topic": "passive_voice",
                "num_questions": 2,
            },
        )
        self.assertEqual(generated_response.status_code, 200)
        generated = generated_response.json()
        answers = [
            {
                "exercise_id": exercise["exercise_id"],
                "selected_answer": exercise["correct_answer"],
            }
            for exercise in generated["exercises"]
        ]

        submit_response = self.client.post(
            f"/api/activities/{generated['activity_id']}/submit",
            json={"user_id": "learner", "answers": answers},
        )

        self.assertEqual(submit_response.status_code, 200)
        submitted = submit_response.json()
        self.assertEqual(submitted["ui_action"], "practice.result")
        self.assertEqual(submitted["activity"]["activity_id"], generated["activity_id"])
        self.assertEqual(submitted["activity"]["status"], "COMPLETED")
        self.assertEqual(submitted["result"]["activity_id"], generated["activity_id"])
        self.assertEqual(submitted["result"]["score"], 1.0)
        self.assertTrue(submitted["result"]["session_code"])
        self.assertTrue(submitted["result"]["practice_review"])
        self.assertEqual(len(submitted["answers"]), 2)
        self.assertEqual(
            submitted["next_activity_suggestion"]["topic"],
            "passive_voice",
        )
        self.assertTrue(submitted["next_activity_suggestion"]["recommendation_id"])

        recommendations_response = self.client.get(
            "/api/recommendations",
            params={"user_id": "learner"},
        )

        self.assertEqual(recommendations_response.status_code, 200)
        recommendations = recommendations_response.json()["recommendations"]
        self.assertEqual(
            recommendations[0]["recommendation_id"],
            submitted["next_activity_suggestion"]["recommendation_id"],
        )

    def test_canonical_activity_read_and_review_endpoints(self) -> None:
        conversation = self._create_conversation("learner")
        generated_response = self.client.post(
            "/api/practice/generate",
            json={
                "user_id": "learner",
                "conversation_id": conversation["conversation_id"],
                "message": "Create 2 passive voice questions.",
                "topic": "passive_voice",
                "num_questions": 2,
            },
        )
        self.assertEqual(generated_response.status_code, 200)
        generated = generated_response.json()
        submit_response = self.client.post(
            f"/api/activities/{generated['activity_id']}/submit",
            json={
                "user_id": "learner",
                "answers": self._first_wrong_answers(generated),
            },
        )
        self.assertEqual(submit_response.status_code, 200)

        activity_response = self.client.get(
            f"/api/activities/{generated['activity_id']}",
            params={"user_id": "learner"},
        )
        review_response = self.client.get(
            f"/api/activities/{generated['activity_id']}/review",
            params={"user_id": "learner", "question_number": 1},
        )

        self.assertEqual(activity_response.status_code, 200)
        activity = activity_response.json()
        self.assertEqual(activity["activity_id"], generated["activity_id"])
        self.assertEqual(activity["learner_id"], "learner")
        self.assertEqual(activity["conversation_id"], conversation["conversation_id"])
        self.assertEqual(activity["ui_action"], "practice.open")
        self.assertEqual(activity["status"], "COMPLETED")
        self.assertEqual(len(activity["exercises"]), 2)
        self.assertEqual(activity["result"]["activity_id"], generated["activity_id"])
        self.assertTrue(activity["next_activity_suggestion"]["recommendation_id"])

        self.assertEqual(review_response.status_code, 200)
        review = review_response.json()
        self.assertEqual(review["learner_id"], "learner")
        self.assertEqual(review["activity_id"], generated["activity_id"])
        self.assertEqual(review["conversation_id"], conversation["conversation_id"])
        self.assertEqual(review["ui_action"], "review.open")
        self.assertEqual(review["metadata"]["question_number"], 1)
        self.assertEqual(review["activity"]["activity_id"], generated["activity_id"])
        self.assertTrue(review["assistant_reply"])

    def test_canonical_activity_read_rejects_other_user(self) -> None:
        conversation = self._create_conversation("learner")
        generated_response = self.client.post(
            "/api/practice/generate",
            json={
                "user_id": "learner",
                "conversation_id": conversation["conversation_id"],
                "message": "Create 1 passive voice question.",
                "topic": "passive_voice",
                "num_questions": 1,
            },
        )
        self.assertEqual(generated_response.status_code, 200)

        response = self.client.get(
            f"/api/activities/{generated_response.json()['activity_id']}",
            params={"user_id": "other"},
        )

        self.assertEqual(response.status_code, 404)

    def test_canonical_learner_profile_mastery_progress_and_recommendations(self) -> None:
        profile_response = self.client.patch(
            "/api/learners/learner/profile",
            json={
                "display_name": "Linh",
                "level": "intermediate",
                "goals": ["ielts"],
                "preferred_difficulty": "medium",
                "preferred_num_questions": 2,
                "weak_topics": ["passive voice"],
                "onboarding_completed": True,
            },
        )
        self.assertEqual(profile_response.status_code, 200)
        self.assertEqual(profile_response.json()["display_name"], "Linh")

        get_profile_response = self.client.get("/api/learners/learner/profile")
        legacy_profile_response = self.client.get("/api/users/learner/profile")
        self.assertEqual(get_profile_response.status_code, 200)
        self.assertEqual(legacy_profile_response.status_code, 200)
        self.assertEqual(get_profile_response.json()["level"], "intermediate")
        self.assertEqual(legacy_profile_response.json()["display_name"], "Linh")

        conversation = self._create_conversation("learner")
        generated_response = self.client.post(
            "/api/practice/generate",
            json={
                "user_id": "learner",
                "conversation_id": conversation["conversation_id"],
                "message": "Create 2 passive voice questions.",
                "topic": "passive_voice",
                "num_questions": 2,
            },
        )
        self.assertEqual(generated_response.status_code, 200)
        generated = generated_response.json()
        submit_response = self.client.post(
            f"/api/activities/{generated['activity_id']}/submit",
            json={
                "user_id": "learner",
                "answers": self._correct_answers(generated),
            },
        )
        self.assertEqual(submit_response.status_code, 200)
        recommendation_id = submit_response.json()["next_activity_suggestion"][
            "recommendation_id"
        ]

        mastery_response = self.client.get("/api/learners/learner/mastery")
        progress_response = self.client.get(
            "/api/learners/learner/progress",
            params={"conversation_id": conversation["conversation_id"]},
        )
        recommendations_response = self.client.get(
            "/api/learners/learner/recommendations",
        )

        self.assertEqual(mastery_response.status_code, 200)
        mastery = mastery_response.json()
        self.assertEqual(mastery["learner_id"], "learner")
        self.assertEqual(mastery["ui_action"], "mastery.open")
        self.assertTrue(mastery["skill_mastery"])
        self.assertTrue(mastery["weak_skills"])
        self.assertIn("next_review_at", mastery["skill_mastery"][0])

        self.assertEqual(progress_response.status_code, 200)
        progress = progress_response.json()
        self.assertEqual(progress["learner_id"], "learner")
        self.assertEqual(progress["conversation_id"], conversation["conversation_id"])
        self.assertEqual(progress["ui_action"], "progress.open")
        self.assertTrue(progress["summary"])
        self.assertEqual(progress["snapshot"]["user_id"], "learner")

        self.assertEqual(recommendations_response.status_code, 200)
        recommendations = recommendations_response.json()["recommendations"]
        self.assertEqual(recommendations[0]["recommendation_id"], recommendation_id)

    def test_accept_recommendation_creates_activity_without_parsing_prompt(self) -> None:
        conversation = self._create_conversation("learner")
        generated_response = self.client.post(
            "/api/practice/generate",
            json={
                "user_id": "learner",
                "conversation_id": conversation["conversation_id"],
                "message": "Create 2 passive voice questions.",
                "topic": "passive_voice",
                "num_questions": 2,
            },
        )
        self.assertEqual(generated_response.status_code, 200)
        generated = generated_response.json()
        submit_response = self.client.post(
            f"/api/activities/{generated['activity_id']}/submit",
            json={
                "user_id": "learner",
                "answers": self._correct_answers(generated),
            },
        )
        self.assertEqual(submit_response.status_code, 200)
        recommendation_id = submit_response.json()["next_activity_suggestion"][
            "recommendation_id"
        ]

        original_parse = api_main.pipeline.agent.parser.parse

        def fail_parse(*_args, **_kwargs):
            raise AssertionError("parser should not run for accepted recommendations")

        api_main.pipeline.agent.parser.parse = fail_parse
        try:
            accept_response = self.client.post(
                f"/api/recommendations/{recommendation_id}/accept",
                json={
                    "user_id": "learner",
                    "conversation_id": conversation["conversation_id"],
                },
            )
        finally:
            api_main.pipeline.agent.parser.parse = original_parse

        self.assertEqual(accept_response.status_code, 200)
        accepted = accept_response.json()
        self.assertEqual(accepted["ui_action"], "practice.start")
        self.assertEqual(
            accepted["recommendation"]["recommendation_id"],
            recommendation_id,
        )
        self.assertTrue(accepted["activity"]["activity_id"])
        self.assertEqual(accepted["activity"]["status"], "READY")
        self.assertTrue(accepted["activity"]["exercises"])
        self.assertEqual(
            accepted["activity"]["plan"]["topic"],
            accepted["recommendation"]["topic"],
        )
        self.assertTrue(accepted["recommendation"]["evidence"]["candidate_scores"])
        accepted_metadata = accepted["activity"]["metadata"]["accepted_recommendation"]
        self.assertEqual(accepted_metadata["recommendation_id"], recommendation_id)
        self.assertTrue(accepted_metadata["evidence"]["candidate_scores"])

    def test_legacy_practice_score_wraps_activity_submission(self) -> None:
        conversation = self._create_conversation("learner")
        generated_response = self.client.post(
            "/api/practice/generate",
            json={
                "user_id": "learner",
                "conversation_id": conversation["conversation_id"],
                "message": "Create 2 passive voice questions.",
                "topic": "passive_voice",
                "num_questions": 2,
            },
        )
        self.assertEqual(generated_response.status_code, 200)
        self.assertEqual(generated_response.headers["deprecation"], "true")
        generated = generated_response.json()

        score_response = self.client.post(
            "/api/practice/score",
            json={
                "user_id": "learner",
                "generation_run_id": generated["generation_run_id"],
                "answers": self._correct_answers(generated),
            },
        )

        self.assertEqual(score_response.status_code, 200)
        self.assertEqual(score_response.headers["deprecation"], "true")
        scored = score_response.json()
        self.assertEqual(scored["activity_id"], generated["activity_id"])
        activity = api_main.pipeline.repository.get_learning_activity(
            "learner",
            generated["activity_id"],
        )
        self.assertIsNotNone(activity)
        self.assertEqual(activity.status, LearningActivityStatus.COMPLETED)

    def test_reading_activity_lifecycle_via_conversation_api(self) -> None:
        conversation = self._create_conversation("learner")
        created = self._send_message(
            conversation["conversation_id"],
            "doc truoc di",
        )

        self.assertEqual(created["intent"], "READING")
        self.assertEqual(created["ui_action"], "reading.start")
        self.assertEqual(created["activity"]["type"], "READING")
        self.assertTrue(created["activity"]["metadata"]["passage"])
        answers = self._correct_answers(created["activity"])

        submit_response = self.client.post(
            f"/api/activities/{created['activity']['activity_id']}/submit",
            json={"user_id": "learner", "answers": answers},
        )

        self.assertEqual(submit_response.status_code, 200)
        submitted = submit_response.json()
        self.assertEqual(submitted["ui_action"], "reading.result")
        self.assertEqual(submitted["activity"]["status"], "COMPLETED")
        self.assertEqual(submitted["result"]["score"], 1.0)

    def test_writing_activity_lifecycle_via_conversation_api(self) -> None:
        conversation = self._create_conversation("learner")
        created = self._send_message(
            conversation["conversation_id"],
            "viet truoc nhe",
        )

        self.assertEqual(created["intent"], "WRITING")
        self.assertEqual(created["ui_action"], "writing.start")
        self.assertEqual(created["activity"]["type"], "WRITING")
        self.assertTrue(created["activity"]["metadata"]["writing_prompt"])

        submit_response = self.client.post(
            f"/api/activities/{created['activity']['activity_id']}/submit",
            json={
                "user_id": "learner",
                "writing_text": (
                    "I study English every evening. I read a short story and "
                    "write five new words because I want to improve."
                ),
            },
        )

        self.assertEqual(submit_response.status_code, 200)
        submitted = submit_response.json()
        self.assertEqual(submitted["ui_action"], "writing.result")
        self.assertEqual(submitted["activity"]["status"], "COMPLETED")
        self.assertTrue(submitted["activity"]["metadata"]["corrected_version"])
        self.assertEqual(submitted["result"]["topic"], "writing")
        self.assertTrue(submitted["result"]["practice_review"])

    def test_debug_endpoint_gate_keeps_ops_observability_available(self) -> None:
        original_debug_enabled = api_main.pipeline.config.debug_endpoints_enabled
        api_main.pipeline.config.debug_endpoints_enabled = False
        try:
            debug_response = self.client.get("/api/debug/metrics")
            ops_response = self.client.get("/api/ops/observability")
        finally:
            api_main.pipeline.config.debug_endpoints_enabled = original_debug_enabled

        self.assertEqual(debug_response.status_code, 404)
        self.assertEqual(ops_response.status_code, 200)
        self.assertEqual(ops_response.json()["status"], "ok")

    def test_missing_conversation_returns_404(self) -> None:
        response = self.client.post(
            "/api/conversations/missing/messages",
            json={"user_id": "learner", "message": "Hello"},
        )

        self.assertEqual(response.status_code, 404)

    def _create_conversation(self, user_id: str) -> dict:
        response = self.client.post(
            "/api/conversations",
            json={"user_id": user_id},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _send_message(self, conversation_id: str, message: str) -> dict:
        response = self.client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"user_id": "learner", "message": message},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _correct_answers(self, generated: dict) -> list[dict]:
        return [
            {
                "exercise_id": exercise["exercise_id"],
                "selected_answer": exercise["correct_answer"],
            }
            for exercise in generated["exercises"]
        ]

    def _first_wrong_answers(self, generated: dict) -> list[dict]:
        answers = self._correct_answers(generated)
        first_exercise = generated["exercises"][0]
        wrong_option = next(
            option
            for option in first_exercise["options"]
            if option["text"] != first_exercise["correct_answer"]
        )
        answers[0]["selected_answer"] = wrong_option["text"]
        return answers


if __name__ == "__main__":
    unittest.main()
