from __future__ import annotations

import hashlib
from typing import Any


FREE_TEXT_POLICY_VERSION = "learner_free_text_policy_v1"

FORBIDDEN_FREE_TEXT_KEYS = frozenset(
    {
        "answer_text",
        "correct_text",
        "corrected_text",
        "correction_text",
        "free_text",
        "learner_text",
        "original_text",
        "prompt_text",
        "raw_text",
        "response_text",
        "selected_text",
        "sentence_text",
        "source_text",
        "text",
    },
)

ALLOWED_TEXTUAL_METADATA_KEYS = frozenset(
    {
        "description",
        "reason",
        "source_path",
        "source_file",
        "label",
        "label_system",
        "label_path",
    },
)


class FreeTextPolicyError(ValueError):
    """Raised when learner free-text fields appear in schema payloads."""


def fingerprint_text(value: str) -> tuple[str, int]:
    encoded = value.encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}", len(value)


def validate_no_forbidden_free_text_keys(payload: Any, *, path: str = "$") -> None:
    for violation in find_forbidden_free_text_keys(payload, path=path):
        raise FreeTextPolicyError(f"Forbidden learner free-text field: {violation}")


def find_forbidden_free_text_keys(payload: Any, *, path: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized = str(key).strip().casefold()
            child_path = f"{path}.{key}"
            if (
                normalized in FORBIDDEN_FREE_TEXT_KEYS
                and normalized not in ALLOWED_TEXTUAL_METADATA_KEYS
            ):
                violations.append(child_path)
            violations.extend(find_forbidden_free_text_keys(value, path=child_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            violations.extend(find_forbidden_free_text_keys(value, path=f"{path}[{index}]"))
    return violations

