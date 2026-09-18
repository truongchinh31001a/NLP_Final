from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILL_SET
from knowledge_core.normalization.error_taxonomy.policy import (
    validate_no_forbidden_free_text_keys,
)


MISCONCEPTION_SCHEMA_VERSION = "misconceptions_v1"

MisconceptionStatus = Literal["candidate", "accepted", "rejected"]
ReviewStatus = Literal["pending", "approved", "needs_review", "rejected"]
Severity = Literal["low", "medium", "high"]


def clean_required_text(value: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError("value must not be empty")
    return text


def clean_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class MisconceptionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MisconceptionEvidenceLink(MisconceptionModel):
    normalized_error_id: str
    error_instance_id: str
    source_record_id: str
    source_key: str
    source_label: str | None = None
    proficiency_label: str | None = None
    task_id: str | None = None
    split: str | None = None
    mapping_id: str
    mapping_confidence: float = Field(ge=0.0, le=1.0)

    @field_validator(
        "normalized_error_id",
        "error_instance_id",
        "source_record_id",
        "source_key",
        "mapping_id",
    )
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("source_label", "proficiency_label", "task_id", "split", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return clean_optional_text(value)

    @model_validator(mode="after")
    def payload_is_clean(self) -> MisconceptionEvidenceLink:
        validate_no_forbidden_free_text_keys(self.model_dump(mode="json"))
        return self


class MisconceptionCandidate(MisconceptionModel):
    misconception_id: str
    canonical_skill_id: str
    name: str
    description: str
    error_category: str
    error_subtype: str | None = None
    source_labels: list[str] = Field(default_factory=list)
    expected_pattern: str
    observed_pattern: str
    diagnostic_rule: str
    source_evidence_count: int = Field(ge=0)
    source_distribution: dict[str, int] = Field(default_factory=dict)
    frequency: float = Field(ge=0.0, le=1.0)
    frequency_scope: str
    source_frequencies: dict[str, float] = Field(default_factory=dict)
    proficiency_distribution: dict[str, int] = Field(default_factory=dict)
    evidence_links: list[MisconceptionEvidenceLink] = Field(default_factory=list)
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    status: MisconceptionStatus = "candidate"
    review_status: ReviewStatus = "pending"
    reason: str
    provenance: dict[str, Any] = Field(default_factory=dict)
    version: str = MISCONCEPTION_SCHEMA_VERSION

    @field_validator(
        "misconception_id",
        "canonical_skill_id",
        "name",
        "description",
        "error_category",
        "expected_pattern",
        "observed_pattern",
        "diagnostic_rule",
        "frequency_scope",
        "reason",
    )
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("error_subtype", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return clean_optional_text(value)

    @field_validator("canonical_skill_id")
    @classmethod
    def canonical_skill_exists(cls, value: str) -> str:
        if value not in CANONICAL_GRAMMAR_V1_SKILL_SET:
            raise ValueError(f"Unknown canonical skill id: {value}")
        return value

    @field_validator("source_labels")
    @classmethod
    def clean_source_labels(cls, values: list[str]) -> list[str]:
        return [clean_required_text(value) for value in values]

    @model_validator(mode="after")
    def candidate_is_consistent(self) -> MisconceptionCandidate:
        validate_no_forbidden_free_text_keys(self.model_dump(mode="json"))
        if self.status == "accepted" and self.review_status != "approved":
            raise ValueError("accepted misconceptions must have review_status='approved'")
        if self.source_evidence_count != len(self.evidence_links):
            raise ValueError("source_evidence_count must match evidence_links length")
        return self
