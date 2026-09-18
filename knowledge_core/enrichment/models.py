from __future__ import annotations

import hashlib
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from knowledge_core.assessment.models import AssessmentCriterion, SkillAssessmentProfile
from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILL_SET
from knowledge_core.normalization.error_taxonomy.policy import (
    validate_no_forbidden_free_text_keys,
)


KNOWLEDGE_ENRICHMENT_SCHEMA_VERSION = "knowledge_enrichment_v1"

EvidenceStatus = Literal["curated", "accepted_empirical", "pending_review"]
EnrichmentStatus = Literal[
    "curated_only",
    "empirically_enriched",
    "empirical_pending_review",
    "no_accepted_misconceptions",
]


def clean_required_text(value: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError("value must not be empty")
    return text


class EnrichmentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmpiricalFailureSignal(EnrichmentModel):
    signal_id: str
    misconception_id: str
    diagnostic_signal: str
    evidence_status: Literal["accepted_empirical"] = "accepted_empirical"
    source_evidence_count: int = Field(ge=0)
    source_distribution: dict[str, int] = Field(default_factory=dict)
    proficiency_distribution: dict[str, int] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("signal_id", "misconception_id", "diagnostic_signal")
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)


class DiagnosticEvidenceTag(EnrichmentModel):
    evidence_type: Literal[
        "curated_assessment_rule",
        "accepted_misconception",
        "pending_misconception_candidate",
    ]
    evidence_status: EvidenceStatus
    source: str
    source_record_ids: list[str] = Field(default_factory=list)
    note: str

    @field_validator("source", "note")
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)


class SkillMisconceptionLink(EnrichmentModel):
    link_id: str
    misconception_id: str
    canonical_skill_id: str
    evidence_status: Literal["accepted_empirical"] = "accepted_empirical"
    source_evidence_count: int = Field(ge=0)
    source_distribution: dict[str, int] = Field(default_factory=dict)
    proficiency_distribution: dict[str, int] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    review_status: Literal["approved"] = "approved"
    reason: str
    version: str = KNOWLEDGE_ENRICHMENT_SCHEMA_VERSION

    @field_validator("link_id", "misconception_id", "canonical_skill_id", "reason")
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
    def payload_is_clean(self) -> SkillMisconceptionLink:
        validate_no_forbidden_free_text_keys(self.model_dump(mode="json"))
        return self


class EnrichedAssessmentCriterion(EnrichmentModel):
    criterion: AssessmentCriterion
    curated_failure_signals: list[str] = Field(default_factory=list)
    empirical_failure_signals: list[EmpiricalFailureSignal] = Field(default_factory=list)
    diagnostic_evidence_tags: list[DiagnosticEvidenceTag] = Field(default_factory=list)
    enrichment_status: EnrichmentStatus
    version: str = KNOWLEDGE_ENRICHMENT_SCHEMA_VERSION

    @model_validator(mode="after")
    def payload_is_clean(self) -> EnrichedAssessmentCriterion:
        validate_no_forbidden_free_text_keys(self.model_dump(mode="json"))
        return self


class EnrichedSkillProfile(EnrichmentModel):
    profile: SkillAssessmentProfile
    accepted_misconception_ids: list[str] = Field(default_factory=list)
    pending_misconception_candidate_ids: list[str] = Field(default_factory=list)
    empirical_evidence_count: int = Field(ge=0)
    empirical_sources: dict[str, int] = Field(default_factory=dict)
    diagnostic_evidence_status: EnrichmentStatus
    version: str = KNOWLEDGE_ENRICHMENT_SCHEMA_VERSION

    @model_validator(mode="after")
    def payload_is_clean(self) -> EnrichedSkillProfile:
        validate_no_forbidden_free_text_keys(self.model_dump(mode="json"))
        return self


def make_skill_misconception_link_id(
    *,
    canonical_skill_id: str,
    misconception_id: str,
) -> str:
    raw_key = "\x1f".join([canonical_skill_id, misconception_id])
    return "skillmis_" + hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:24]


def make_failure_signal_id(
    *,
    criterion_id: str,
    misconception_id: str,
) -> str:
    raw_key = "\x1f".join([criterion_id, misconception_id])
    return "failsig_" + hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:24]

