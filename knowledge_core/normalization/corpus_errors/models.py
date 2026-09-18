from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILL_SET
from knowledge_core.normalization.error_taxonomy.models import (
    LearnerErrorSourceKey,
    ReviewStatus,
    clean_required_text,
)
from knowledge_core.normalization.error_taxonomy.policy import (
    validate_no_forbidden_free_text_keys,
)


class ErrorSkillMapping(BaseModel):
    """Pending-review link from a normalized learner error to a canonical skill."""

    model_config = ConfigDict(extra="forbid")

    mapping_id: str
    normalized_error_id: str
    error_instance_id: str
    source_record_id: str
    source_key: LearnerErrorSourceKey
    canonical_skill_id: str
    status: Literal["candidate", "accepted", "rejected"]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    review_status: ReviewStatus = "pending"
    provenance: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "mapping_id",
        "normalized_error_id",
        "error_instance_id",
        "source_record_id",
        "canonical_skill_id",
        "reason",
    )
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("canonical_skill_id")
    @classmethod
    def canonical_skill_exists(cls, value: str) -> str:
        if value not in CANONICAL_GRAMMAR_V1_SKILL_SET:
            raise ValueError(f"Unknown canonical skill id: {value}")
        return value

    @model_validator(mode="after")
    def payload_is_clean(self) -> ErrorSkillMapping:
        validate_no_forbidden_free_text_keys(self.model_dump(mode="json"))
        return self
