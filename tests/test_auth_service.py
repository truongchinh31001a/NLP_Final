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

    def test_production_like_deployment_rejects_disabled_auth(self) -> None:
        with self.assertRaises(RuntimeError):
            AuthService(
                AppConfig(
                    deployment_environment="production",
                    auth_mode="disabled",
                )
            )

    def test_production_like_deployment_requires_strong_secret(self) -> None:
        with self.assertRaises(RuntimeError):
            AuthService(
                AppConfig(
                    deployment_environment="production",
                    auth_mode="demo_token",
                    auth_token_secret="short-secret",
                )
            )

    def test_production_like_deployment_accepts_strong_token_auth(self) -> None:
        service = AuthService(
            AppConfig(
                deployment_environment="production",
                auth_mode="demo_token",
                auth_token_secret="a-very-long-test-secret-for-production",
            )
        )

        self.assertTrue(service.requires_authentication)


if __name__ == "__main__":
    unittest.main()
