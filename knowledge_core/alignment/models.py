from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from knowledge_core.sources.cefr.models import VALID_CEFR_LEVELS


EvidenceType = Literal[
    "egp_direct",
    "cefr_proficiency",
    "cefr_learning_objective",
    "cefr_grammatical_accuracy",
    "curated",
]
AlignmentStatus = Literal[
    "aligned",
    "partial",
    "ambiguous",
    "no_cefr_evidence",
    "curated_only",
]
ReviewStatus = Literal["accepted", "pending", "needs_review"]
ObjectiveRelevance = Literal["direct", "contextual", "ambiguous", "unrelated"]
IssueSeverity = Literal["warning", "error"]


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


class AlignmentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AlignmentInputConfig(AlignmentModel):
    egp_records: str = "data/interim/english_profile/grammar/egp_records.jsonl"
    egp_mappings: str = "data/interim/english_profile/grammar/egp_mappings.jsonl"
    cefr_descriptors: str = "data/interim/cefr/cefr_descriptors.jsonl"
    cefr_objectives: str = "data/interim/cefr/cefr_learning_objective_candidates.jsonl"

    @field_validator("egp_records", "egp_mappings", "cefr_descriptors", "cefr_objectives")
    @classmethod
    def relative_paths(cls, value: str) -> str:
        return _relative_path(value)


class AlignmentOutputConfig(AlignmentModel):
    interim_dir: str = "data/interim/knowledge_alignment"
    review_dir: str = "data/curated/review"
    reports_dir: str = "data/reports/knowledge_alignment"

    @field_validator("interim_dir", "review_dir", "reports_dir")
    @classmethod
    def relative_paths(cls, value: str) -> str:
        return _relative_path(value)


class EGPEvidenceConfig(AlignmentModel):
    establishing_statuses: list[str] = Field(default_factory=lambda: ["exact", "candidate"])
    ambiguous_statuses: list[str] = Field(default_factory=lambda: ["ambiguous"])
    status_weights: dict[str, float] = Field(
        default_factory=lambda: {"exact": 1.0, "candidate": 0.65},
    )

    @field_validator("status_weights")
    @classmethod
    def confidence_values(cls, value: dict[str, float]) -> dict[str, float]:
        for status, weight in value.items():
            if weight < 0.0 or weight > 1.0:
                raise ValueError(f"status weight for {status} must be between 0 and 1")
        return value


class CEFRAlignmentConfig(AlignmentModel):
    grammatical_accuracy_scale: str = "grammatical_accuracy"

    @field_validator("grammatical_accuracy_scale")
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)


class ObjectiveRuleConfig(AlignmentModel):
    canonical_skill_id: str
    direct_terms: list[str] = Field(default_factory=list)
    contextual_terms: list[str] = Field(default_factory=list)

    @field_validator("canonical_skill_id")
    @classmethod
    def required_skill_id(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("direct_terms", "contextual_terms")
    @classmethod
    def clean_terms(cls, values: list[str]) -> list[str]:
        return [clean_required_text(value) for value in values]


class ObjectiveAlignmentConfig(AlignmentModel):
    max_objectives_per_skill_per_mode: int = Field(default=5, ge=1)
    max_level_distance_for_aligned_skills: int = Field(default=1, ge=0)
    direct_confidence: float = Field(default=0.72, ge=0.0, le=1.0)
    contextual_confidence: float = Field(default=0.62, ge=0.0, le=1.0)
    rules: list[ObjectiveRuleConfig] = Field(default_factory=list)


class KnowledgeAlignmentConfig(AlignmentModel):
    inputs: AlignmentInputConfig = Field(default_factory=AlignmentInputConfig)
    outputs: AlignmentOutputConfig = Field(default_factory=AlignmentOutputConfig)
    egp: EGPEvidenceConfig = Field(default_factory=EGPEvidenceConfig)
    cefr: CEFRAlignmentConfig = Field(default_factory=CEFRAlignmentConfig)
    objective_alignment: ObjectiveAlignmentConfig = Field(
        default_factory=ObjectiveAlignmentConfig,
    )

    @model_validator(mode="after")
    def objective_rule_ids_unique(self) -> KnowledgeAlignmentConfig:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for rule in self.objective_alignment.rules:
            if rule.canonical_skill_id in seen:
                duplicates.add(rule.canonical_skill_id)
            seen.add(rule.canonical_skill_id)
        if duplicates:
            joined = ", ".join(sorted(duplicates))
            raise ValueError(f"duplicate objective alignment rules: {joined}")
        return self


class SkillSourceEvidence(AlignmentModel):
    evidence_id: str
    canonical_skill_id: str
    source: str
    source_record_id: str
    evidence_type: EvidenceType
    source_cefr_level: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    status: str
    provenance: dict[str, Any] = Field(default_factory=dict)

    @field_validator("evidence_id", "canonical_skill_id", "source", "source_record_id", "status")
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("source_cefr_level", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return clean_optional_text(value)


class ObjectiveAlignment(AlignmentModel):
    canonical_skill_id: str
    objective_id: str
    source_record_id: str
    cefr_level: str
    relevance: ObjectiveRelevance
    confidence: float = Field(ge=0.0, le=1.0)
    matched_terms: list[str] = Field(default_factory=list)
    reason: str


class SkillCEFRAlignment(AlignmentModel):
    canonical_skill_id: str
    egp_levels: list[str] = Field(default_factory=list)
    inferred_min_level: str | None = None
    inferred_primary_level: str | None = None
    cefr_descriptor_ids: list[str] = Field(default_factory=list)
    objective_ids: list[str] = Field(default_factory=list)
    grammatical_accuracy_descriptor_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    status: AlignmentStatus
    reason: str
    review_status: ReviewStatus

    @field_validator("canonical_skill_id", "reason")
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("egp_levels", "inferred_min_level", "inferred_primary_level")
    @classmethod
    def valid_cefr_levels(cls, value: Any) -> Any:
        if value is None:
            return None
        values = value if isinstance(value, list) else [value]
        invalid = [level for level in values if level not in VALID_CEFR_LEVELS]
        if invalid:
            raise ValueError(f"Invalid CEFR level(s): {invalid}")
        return value


class CanonicalSkillEvidenceProfile(AlignmentModel):
    canonical_skill_id: str
    canonical_parent: str | None = None
    egp_evidence_count: int = Field(ge=0)
    egp_levels: list[str] = Field(default_factory=list)
    egp_source_record_ids: list[str] = Field(default_factory=list)
    cefr_min_level: str | None = None
    cefr_primary_level: str | None = None
    grammatical_accuracy_context: list[str] = Field(default_factory=list)
    direct_objective_ids: list[str] = Field(default_factory=list)
    contextual_objective_ids: list[str] = Field(default_factory=list)
    evidence_status: AlignmentStatus
    alignment_confidence: float = Field(ge=0.0, le=1.0)
    notes: str
    provenance: dict[str, Any] = Field(default_factory=dict)

    @field_validator("canonical_skill_id", "notes")
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("canonical_parent", "cefr_min_level", "cefr_primary_level", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return clean_optional_text(value)


class AlignmentValidationIssue(AlignmentModel):
    severity: IssueSeverity
    code: str
    message: str
    canonical_skill_id: str | None = None
    source_record_id: str | None = None
    objective_id: str | None = None
    cefr_level: str | None = None
    evidence_id: str | None = None


class AlignmentValidationResult(AlignmentModel):
    run_at: datetime = Field(default_factory=now_utc)
    total_canonical_skills: int = 0
    total_profiles: int = 0
    total_alignments: int = 0
    total_source_evidence: int = 0
    issues: list[AlignmentValidationIssue] = Field(default_factory=list)

    @property
    def errors(self) -> list[AlignmentValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[AlignmentValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)


def canonical_parent_from_skill_id(skill_id: str) -> str | None:
    parts = skill_id.split(".")
    if len(parts) < 3:
        return None
    return ".".join(parts[:-1])


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

