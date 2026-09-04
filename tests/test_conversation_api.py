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
        second = self._send_message(
            conversation["conversation_id"],
            "5 câu passive voice.",
        )

        self.assertEqual(first["intent"], "PRACTICE")
        self.assertEqual(first["ui_action"], "clarification.ask")
        self.assertEqual(first["pending_clarification"]["pending_intent"], "PRACTICE")
        self.assertEqual(second["intent"], "PRACTICE")
        self.assertEqual(second["ui_action"], "practice.start")
        self.assertEqual(second["activity"]["status"], "READY")
        self.assertEqual(second["route"]["slots"]["topic"], "passive_voice")
        self.assertEqual(second["route"]["slots"]["num_questions"], 5)

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


if __name__ == "__main__":
    unittest.main()
