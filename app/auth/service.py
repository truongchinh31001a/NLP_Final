import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any

from app.config import AppConfig


@dataclass(slots=True)
class AuthContext:
    user_id: str
    authenticated: bool
    expires_at: int | None = None


class AuthService:
    """Small signed-token auth layer for P2 multi-user isolation.

    `AUTH_MODE=disabled` keeps local demos frictionless. `AUTH_MODE=demo_token`
    requires `Authorization: Bearer <token>` and verifies that the token subject
    matches the path/payload user id.
    """

    def __init__(self, config: AppConfig) -> None:
        self.mode = config.auth_mode.strip().lower()
        self.secret = config.auth_token_secret
        self.ttl_seconds = config.auth_token_ttl_seconds
        self.deployment_environment = config.deployment_environment.strip().lower()
        self._validate_runtime_security()

    @property
    def requires_authentication(self) -> bool:
        return self.mode not in {"", "disabled", "off", "none"}

    def issue_token(self, user_id: str) -> str:
        expires_at = int(time.time()) + self.ttl_seconds
        payload = {
            "user_id": user_id,
            "exp": expires_at,
            "iat": int(time.time()),
        }
        payload_segment = self._b64encode_json(payload)
        signature_segment = self._signature(payload_segment)
        return f"{payload_segment}.{signature_segment}"

    def authorize(
        self,
        user_id: str,
        authorization_header: str | None,
    ) -> AuthContext:
        if not self.requires_authentication:
            return AuthContext(user_id=user_id, authenticated=False)

        token = self._bearer_token(authorization_header)
        payload = self.verify_token(token)
        token_user_id = str(payload.get("user_id") or "")
        if token_user_id != user_id:
            raise PermissionError("Token subject does not match requested user.")
        return AuthContext(
            user_id=token_user_id,
            authenticated=True,
            expires_at=int(payload.get("exp") or 0),
        )

    def verify_token(self, token: str) -> dict[str, Any]:
        try:
            payload_segment, signature_segment = token.split(".", maxsplit=1)
        except ValueError as exc:
            raise PermissionError("Invalid auth token format.") from exc

        expected_signature = self._signature(payload_segment)
        if not hmac.compare_digest(signature_segment, expected_signature):
            raise PermissionError("Invalid auth token signature.")

        payload = self._b64decode_json(payload_segment)
        expires_at = int(payload.get("exp") or 0)
        if expires_at < int(time.time()):
            raise PermissionError("Auth token has expired.")
        if not payload.get("user_id"):
            raise PermissionError("Auth token is missing user_id.")
        return payload

    def _bearer_token(self, authorization_header: str | None) -> str:
        if not authorization_header:
            raise PermissionError("Missing Authorization bearer token.")
        scheme, _, token = authorization_header.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise PermissionError("Authorization header must use Bearer token.")
        return token.strip()

    def _signature(self, payload_segment: str) -> str:
        digest = hmac.new(
            self.secret.encode("utf-8"),
            payload_segment.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return self._b64encode_bytes(digest)

    def _b64encode_json(self, payload: dict[str, Any]) -> str:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return self._b64encode_bytes(encoded)

    def _b64decode_json(self, segment: str) -> dict[str, Any]:
        padded = segment + "=" * (-len(segment) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise PermissionError("Invalid auth token payload.")
        return payload

    def _b64encode_bytes(self, value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    def _validate_runtime_security(self) -> None:
        production_like = self.deployment_environment in {"prod", "production"}
        strict_mode = self.mode in {"prod", "production", "strict"}
        if not production_like and not strict_mode:
            return
        if not self.requires_authentication:
            raise RuntimeError(
                "AUTH_MODE must require bearer tokens in production-like deployments.",
            )
        if self.secret in {"", "dev-secret-change-me", "change-me-before-enabling-auth"}:
            raise RuntimeError(
                "AUTH_TOKEN_SECRET must be replaced before production-like deployments.",
            )
        if len(self.secret) < 32:
            raise RuntimeError(
                "AUTH_TOKEN_SECRET must be at least 32 characters for production-like deployments.",
            )
