from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


RelationType = Literal[
    "parent_of",
    "prerequisite_of",
    "recommended_before",
    "related_to",
    "contrast_with",
    "commonly_confused_with",
    "supports",
]
DependencyStrength = Literal["hard", "soft", "none"]
RelationshipStatus = Literal[
    "accepted",
    "candidate",
    "ambiguous",
    "rejected",
    "needs_review",
]
ReviewStatus = Literal["pending", "approved", "rejected", "needs_review"]
EvidenceType = Literal[
    "taxonomy_structure",
    "curated_pedagogy",
    "egp_progression",
    "cefr_alignment",
    "linguistic_structure",
]
IssueSeverity = Literal["warning", "error"]

VALID_RELATION_TYPES = {
    "parent_of",
    "prerequisite_of",
    "recommended_before",
    "related_to",
    "contrast_with",
    "commonly_confused_with",
    "supports",
}
VALID_DEPENDENCY_STRENGTHS = {"hard", "soft", "none"}
BIDIRECTIONAL_RELATION_TYPES = {
    "related_to",
    "contrast_with",
    "commonly_confused_with",
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


class RelationshipModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RelationshipEvidence(RelationshipModel):
    evidence_type: EvidenceType
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


class SkillRelationship(RelationshipModel):
    relationship_id: str
    source_skill_id: str
    target_skill_id: str
    relation_type: RelationType
    dependency_strength: DependencyStrength
    confidence: float = Field(ge=0.0, le=1.0)
    status: RelationshipStatus
    reason: str
    evidence: list[RelationshipEvidence] = Field(default_factory=list)
    bidirectional: bool = False
    review_status: ReviewStatus
    created_by: str
    version: str | None = None

    @field_validator(
        "relationship_id",
        "source_skill_id",
        "target_skill_id",
        "reason",
        "created_by",
    )
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("version", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return clean_optional_text(value)

    @model_validator(mode="after")
    def bidirectional_matches_relation_type(self) -> SkillRelationship:
        if self.bidirectional and self.relation_type not in BIDIRECTIONAL_RELATION_TYPES:
            raise ValueError("Only semantic relation types may be bidirectional")
        return self


class RelationshipRule(RelationshipModel):
    source: str
    target: str
    relation_type: RelationType
    reason: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    status: RelationshipStatus | None = None
    review_status: ReviewStatus | None = None

    @field_validator("source", "target", "reason")
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)


class RelationshipInputConfig(RelationshipModel):
    skill_evidence_profiles: str = (
        "data/interim/knowledge_alignment/grammar_skill_evidence.jsonl"
    )
    cefr_egp_alignment: str = "data/interim/knowledge_alignment/cefr_egp_alignment.jsonl"

    @field_validator("skill_evidence_profiles", "cefr_egp_alignment")
    @classmethod
    def relative_path(cls, value: str) -> str:
        return _relative_path(value)


class RelationshipOutputConfig(RelationshipModel):
    relationships_dir: str = "data/curated/relationships"
    review_dir: str = "data/curated/review"
    reports_dir: str = "data/reports/relationships"

    @field_validator("relationships_dir", "review_dir", "reports_dir")
    @classmethod
    def relative_path(cls, value: str) -> str:
        return _relative_path(value)


class RelationshipMetadataConfig(RelationshipModel):
    created_by: str = "deterministic_relationship_rules_v1"
    version: str | None = "relationships_v1"

    @field_validator("created_by")
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("version", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return clean_optional_text(value)


class RelationshipDefaultsConfig(RelationshipModel):
    structural_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    prerequisite_confidence: float = Field(default=0.95, ge=0.0, le=1.0)
    recommended_confidence: float = Field(default=0.88, ge=0.0, le=1.0)
    supports_confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    semantic_confidence: float = Field(default=0.78, ge=0.0, le=1.0)
    non_structural_status: RelationshipStatus = "candidate"
    non_structural_review_status: ReviewStatus = "pending"


class GrammarRelationshipConfig(RelationshipModel):
    inputs: RelationshipInputConfig = Field(default_factory=RelationshipInputConfig)
    outputs: RelationshipOutputConfig = Field(default_factory=RelationshipOutputConfig)
    metadata: RelationshipMetadataConfig = Field(
        default_factory=RelationshipMetadataConfig,
    )
    defaults: RelationshipDefaultsConfig = Field(
        default_factory=RelationshipDefaultsConfig,
    )
    curated_relationships: list[RelationshipRule] = Field(default_factory=list)


class SkillGraphNodeSummary(RelationshipModel):
    skill_id: str
    in_degree: int = Field(ge=0)
    out_degree: int = Field(ge=0)
    prerequisite_depth: int = Field(ge=0)
    direct_prerequisites: list[str] = Field(default_factory=list)
    transitive_prerequisites: list[str] = Field(default_factory=list)
    direct_unlocks: list[str] = Field(default_factory=list)
    related_skills: list[str] = Field(default_factory=list)
    contrast_skills: list[str] = Field(default_factory=list)


class RelationshipGraphAnalysis(RelationshipModel):
    total_nodes: int = Field(ge=0)
    total_atomic_skills: int = Field(ge=0)
    root_prerequisite_skills: list[str] = Field(default_factory=list)
    terminal_skills: list[str] = Field(default_factory=list)
    isolated_skills: list[str] = Field(default_factory=list)
    connected_components: list[list[str]] = Field(default_factory=list)
    max_prerequisite_depth: int = Field(ge=0)
    longest_prerequisite_path: list[str] = Field(default_factory=list)
    node_summaries: dict[str, SkillGraphNodeSummary] = Field(default_factory=dict)


class RelationshipValidationIssue(RelationshipModel):
    severity: IssueSeverity
    code: str
    message: str
    relationship_id: str | None = None
    source_skill_id: str | None = None
    target_skill_id: str | None = None
    relation_type: str | None = None


class RelationshipValidationResult(RelationshipModel):
    run_at: datetime = Field(default_factory=now_utc)
    total_relationships: int = 0
    total_atomic_skills: int = 0
    issues: list[RelationshipValidationIssue] = Field(default_factory=list)
    prerequisite_dag_valid: bool = True
    cycles_found: list[list[str]] = Field(default_factory=list)
    duplicate_edges: list[str] = Field(default_factory=list)
    invalid_references: list[str] = Field(default_factory=list)

    @property
    def errors(self) -> list[RelationshipValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[RelationshipValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)


def dependency_strength_for_relation(relation_type: str) -> str:
    if relation_type == "prerequisite_of":
        return "hard"
    if relation_type == "recommended_before":
        return "soft"
    return "none"


def is_bidirectional_relation(relation_type: str) -> bool:
    return relation_type in BIDIRECTIONAL_RELATION_TYPES


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

