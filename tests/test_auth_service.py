import unittest

from app.auth.service import AuthService
from app.config import AppConfig


class AuthServiceTests(unittest.TestCase):
    def test_disabled_auth_allows_user_without_header(self) -> None:
        service = AuthService(AppConfig(auth_mode="disabled"))

        context = service.authorize("learner", None)

        self.assertEqual(context.user_id, "learner")
        self.assertFalse(context.authenticated)

    def test_demo_token_authorizes_matching_user(self) -> None:
        service = AuthService(
            AppConfig(
                auth_mode="demo_token",
                auth_token_secret="test-secret",
                auth_token_ttl_seconds=60,
            )
        )

        token = service.issue_token("learner")
        context = service.authorize("learner", f"Bearer {token}")

        self.assertEqual(context.user_id, "learner")
        self.assertTrue(context.authenticated)

    def test_demo_token_rejects_cross_user_access(self) -> None:
        service = AuthService(
            AppConfig(
                auth_mode="demo_token",
                auth_token_secret="test-secret",
                auth_token_ttl_seconds=60,
            )
        )

        token = service.issue_token("learner")

        with self.assertRaises(PermissionError):
            service.authorize("other-user", f"Bearer {token}")


if __name__ == "__main__":
    unittest.main()
