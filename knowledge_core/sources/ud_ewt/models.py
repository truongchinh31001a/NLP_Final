from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from knowledge_core.sources.ud_ewt.paths import SOURCE_KEY


EvidenceStatus = Literal["accepted", "candidate", "ambiguous"]
ReviewStatus = Literal["pending", "approved", "needs_review", "rejected"]
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


class UDEWTModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UDTokenRecord(UDEWTModel):
    token_ref: str
    sentence_id: str
    source_key: str = SOURCE_KEY
    split: str
    token_id: str
    form: str
    lemma: str | None = None
    upos: str | None = None
    xpos: str | None = None
    feats: dict[str, list[str]] = Field(default_factory=dict)
    feats_text: str | None = None
    head: str | None = None
    deprel: str | None = None
    deps: list[dict[str, str]] = Field(default_factory=list)
    deps_text: str | None = None
    misc: dict[str, list[str]] = Field(default_factory=dict)
    misc_text: str | None = None
    is_multiword: bool = False
    is_empty_node: bool = False
    source_line_number: int | None = None

    @field_validator("token_ref", "sentence_id", "split", "token_id", "form")
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator(
        "lemma",
        "upos",
        "xpos",
        "feats_text",
        "head",
        "deprel",
        "deps_text",
        "misc_text",
        mode="before",
    )
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return clean_optional_text(value)


class UDSentenceRecord(UDEWTModel):
    sentence_id: str
    source_key: str = SOURCE_KEY
    split: str
    text: str | None = None
    newdoc_id: str | None = None
    newpar_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tokens: list[UDTokenRecord] = Field(default_factory=list)
    source_file: str
    source_sentence_number: int

    @field_validator("sentence_id", "split", "source_file")
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("text", "newdoc_id", "newpar_id", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return clean_optional_text(value)


class UDMorphFeature(UDEWTModel):
    token_ref: str
    sentence_id: str
    split: str
    token_id: str
    feature_name: str
    feature_value: str

    @field_validator(
        "token_ref",
        "sentence_id",
        "split",
        "token_id",
        "feature_name",
        "feature_value",
    )
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)


class UDDependencyEdge(UDEWTModel):
    sentence_id: str
    split: str
    head_token_id: str
    dependent_token_id: str
    relation: str
    enhanced: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "sentence_id",
        "split",
        "head_token_id",
        "dependent_token_id",
        "relation",
    )
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)


class SkillStructuralEvidence(UDEWTModel):
    evidence_id: str
    canonical_skill_id: str
    pattern_type: str
    description: str
    ud_features: list[str] = Field(default_factory=list)
    dependency_relations: list[str] = Field(default_factory=list)
    lexical_constraints: list[str] = Field(default_factory=list)
    source_sentence_ids: list[str] = Field(default_factory=list)
    occurrence_count: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    status: EvidenceStatus
    review_status: ReviewStatus
    reason: str
    provenance: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "evidence_id",
        "canonical_skill_id",
        "pattern_type",
        "description",
        "reason",
    )
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)


class UDValidationIssue(UDEWTModel):
    severity: IssueSeverity
    code: str
    message: str
    split: str | None = None
    sentence_id: str | None = None
    token_id: str | None = None

    @field_validator("code", "message")
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("split", "sentence_id", "token_id", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return clean_optional_text(value)


class UDValidationResult(UDEWTModel):
    run_at: datetime = Field(default_factory=now_utc)
    issues: list[UDValidationIssue] = Field(default_factory=list)
    parsed_splits: list[str] = Field(default_factory=list)
    sentence_counts: dict[str, int] = Field(default_factory=dict)
    token_counts: dict[str, int] = Field(default_factory=dict)
    expected_sentence_counts: dict[str, int] = Field(default_factory=dict)
    expected_token_counts: dict[str, int] = Field(default_factory=dict)
    taxonomy_unchanged: bool = True
    no_new_canonical_skills: bool = True
    no_cefr_inference_introduced: bool = True

    @property
    def errors(self) -> list[UDValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[UDValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

