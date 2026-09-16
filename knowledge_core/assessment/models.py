from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CriterionType = Literal[
    "form_accuracy",
    "meaning_use",
    "contrast_discrimination",
    "production",
    "recognition",
    "error_correction",
]
TaskType = Literal[
    "multiple_choice",
    "fill_blank",
    "sentence_transformation",
    "sentence_completion",
    "error_correction",
    "short_answer_generation",
    "constrained_generation",
    "free_production",
    "classification",
    "contrast_choice",
    "dialogue_completion",
]
AssessmentEvidenceType = Literal[
    "curated_assessment_rule",
    "egp_evidence",
    "cefr_proficiency_context",
    "cefr_grammatical_accuracy",
    "relationship_context",
]
AssessmentStatus = Literal["candidate", "accepted", "needs_review", "rejected"]
ReviewStatus = Literal["pending", "approved", "needs_review", "rejected"]
AssessmentCoverageStatus = Literal["covered", "missing", "needs_review"]
IssueSeverity = Literal["warning", "error"]

VALID_CRITERION_TYPES = {
    "form_accuracy",
    "meaning_use",
    "contrast_discrimination",
    "production",
    "recognition",
    "error_correction",
}
VALID_TASK_TYPES = {
    "multiple_choice",
    "fill_blank",
    "sentence_transformation",
    "sentence_completion",
    "error_correction",
    "short_answer_generation",
    "constrained_generation",
    "free_production",
    "classification",
    "contrast_choice",
    "dialogue_completion",
}
VALID_ASSESSMENT_EVIDENCE_TYPES = {
    "curated_assessment_rule",
    "egp_evidence",
    "cefr_proficiency_context",
    "cefr_grammatical_accuracy",
    "relationship_context",
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


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


class AssessmentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssessmentEvidence(AssessmentModel):
    evidence_type: AssessmentEvidenceType
    source: str
    source_record_ids: list[str] = Field(default_factory=list)
    note: str | None = None

    @field_validator("source")
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("note", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return clean_optional_text(value)


class AssessmentCriterion(AssessmentModel):
    criterion_id: str
    canonical_skill_id: str
    criterion_type: CriterionType
    name: str
    description: str
    observable_behavior: str
    evidence_requirements: list[str] = Field(default_factory=list)
    acceptable_task_types: list[TaskType] = Field(default_factory=list)
    failure_signals: list[str] = Field(default_factory=list)
    cefr_level: str | None = None
    cefr_context_descriptor_ids: list[str] = Field(default_factory=list)
    recommended_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    recommended_min_items: int | None = Field(default=None, ge=1)
    threshold_source: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    status: AssessmentStatus
    review_status: ReviewStatus
    reason: str
    provenance: list[AssessmentEvidence] = Field(default_factory=list)
    version: str | None = None

    @field_validator(
        "criterion_id",
        "canonical_skill_id",
        "name",
        "description",
        "observable_behavior",
        "reason",
    )
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("cefr_level", "threshold_source", "version", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return clean_optional_text(value)

    @field_validator(
        "evidence_requirements",
        "acceptable_task_types",
        "failure_signals",
    )
    @classmethod
    def non_empty_list(cls, values: list[str]) -> list[str]:
        cleaned = [clean_required_text(value) for value in values]
        if not cleaned:
            raise ValueError("list must not be empty")
        return cleaned

    @model_validator(mode="after")
    def threshold_metadata_is_explicit(self) -> AssessmentCriterion:
        if (
            self.recommended_threshold is not None
            or self.recommended_min_items is not None
        ) and not self.threshold_source:
            raise ValueError("threshold_source is required for recommended thresholds")
        return self


class SkillAssessmentProfile(AssessmentModel):
    canonical_skill_id: str
    cefr_primary_level: str | None = None
    criterion_ids: list[str] = Field(default_factory=list)
    criterion_types: list[CriterionType] = Field(default_factory=list)
    recommended_task_types: list[TaskType] = Field(default_factory=list)
    prerequisite_context: list[str] = Field(default_factory=list)
    assessment_coverage_status: AssessmentCoverageStatus
    review_status: ReviewStatus
    version: str | None = None

    @field_validator("canonical_skill_id")
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("cefr_primary_level", "version", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return clean_optional_text(value)


class AssessmentInputConfig(AssessmentModel):
    skill_evidence_profiles: str = (
        "data/interim/knowledge_alignment/grammar_skill_evidence.jsonl"
    )
    cefr_egp_alignment: str = "data/interim/knowledge_alignment/cefr_egp_alignment.jsonl"
    relationships: str = "data/curated/relationships/grammar_relationships.jsonl"
    cefr_descriptors: str = "data/interim/cefr/cefr_descriptors.jsonl"
    egp_records: str = "data/interim/english_profile/grammar/egp_records.jsonl"

    @field_validator(
        "skill_evidence_profiles",
        "cefr_egp_alignment",
        "relationships",
        "cefr_descriptors",
        "egp_records",
    )
    @classmethod
    def relative_path(cls, value: str) -> str:
        return _relative_path(value)


class AssessmentOutputConfig(AssessmentModel):
    assessment_dir: str = "data/curated/assessment"
    review_dir: str = "data/curated/review"
    reports_dir: str = "data/reports/assessment"

    @field_validator("assessment_dir", "review_dir", "reports_dir")
    @classmethod
    def relative_path(cls, value: str) -> str:
        return _relative_path(value)


class AssessmentMetadataConfig(AssessmentModel):
    created_by: str = "deterministic_assessment_rules_v1"
    version: str | None = "assessment_v1"

    @field_validator("created_by")
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("version", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return clean_optional_text(value)


class AssessmentDefaultsConfig(AssessmentModel):
    status: AssessmentStatus = "candidate"
    review_status: ReviewStatus = "pending"
    threshold_source: str = "curated_v1_default"

    @field_validator("threshold_source")
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)


class AssessmentThresholdConfig(AssessmentModel):
    recommended_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    recommended_min_items: int | None = Field(default=None, ge=1)


class AssessmentThresholdsConfig(AssessmentModel):
    recognition: AssessmentThresholdConfig = Field(
        default_factory=lambda: AssessmentThresholdConfig(
            recommended_threshold=0.80,
            recommended_min_items=5,
        ),
    )
    form_accuracy: AssessmentThresholdConfig = Field(
        default_factory=lambda: AssessmentThresholdConfig(
            recommended_threshold=0.80,
            recommended_min_items=6,
        ),
    )
    meaning_use: AssessmentThresholdConfig = Field(
        default_factory=lambda: AssessmentThresholdConfig(
            recommended_threshold=0.75,
            recommended_min_items=6,
        ),
    )
    contrast_discrimination: AssessmentThresholdConfig = Field(
        default_factory=lambda: AssessmentThresholdConfig(
            recommended_threshold=0.75,
            recommended_min_items=6,
        ),
    )
    production: AssessmentThresholdConfig = Field(
        default_factory=lambda: AssessmentThresholdConfig(
            recommended_threshold=0.70,
            recommended_min_items=4,
        ),
    )
    error_correction: AssessmentThresholdConfig = Field(
        default_factory=lambda: AssessmentThresholdConfig(
            recommended_threshold=0.75,
            recommended_min_items=5,
        ),
    )

    def for_type(self, criterion_type: str) -> AssessmentThresholdConfig:
        if criterion_type not in VALID_CRITERION_TYPES:
            raise ValueError(f"unknown criterion type: {criterion_type}")
        return getattr(self, criterion_type)


class GrammarAssessmentConfig(AssessmentModel):
    inputs: AssessmentInputConfig = Field(default_factory=AssessmentInputConfig)
    outputs: AssessmentOutputConfig = Field(default_factory=AssessmentOutputConfig)
    metadata: AssessmentMetadataConfig = Field(default_factory=AssessmentMetadataConfig)
    defaults: AssessmentDefaultsConfig = Field(default_factory=AssessmentDefaultsConfig)
    thresholds: AssessmentThresholdsConfig = Field(
        default_factory=AssessmentThresholdsConfig,
    )


class AssessmentValidationIssue(AssessmentModel):
    severity: IssueSeverity
    code: str
    message: str
    criterion_id: str | None = None
    canonical_skill_id: str | None = None
    source_record_id: str | None = None
    reference_id: str | None = None


class AssessmentValidationResult(AssessmentModel):
    run_at: datetime = Field(default_factory=now_utc)
    total_canonical_skills: int = 0
    total_criteria: int = 0
    total_profiles: int = 0
    missing_skill_ids: list[str] = Field(default_factory=list)
    invalid_references: list[str] = Field(default_factory=list)
    duplicate_criteria: list[str] = Field(default_factory=list)
    taxonomy_unchanged: bool = True
    issues: list[AssessmentValidationIssue] = Field(default_factory=list)

    @property
    def errors(self) -> list[AssessmentValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[AssessmentValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)


def _relative_path(value: str) -> str:
    text = clean_required_text(value).replace("\\", "/")
    path = PurePosixPath(text)
    if (
        path.is_absolute()
        or ".." in path.parts
        or text.startswith("/")
        or re.match(r"^[a-zA-Z]:", text)
    ):
        raise ValueError("path must be relative inside the workspace")
    return str(path)
