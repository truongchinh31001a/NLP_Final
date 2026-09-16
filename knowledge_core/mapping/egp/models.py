from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


MappingStatus = Literal["exact", "candidate", "ambiguous", "unmapped"]
ReviewStatus = Literal["pending", "approved", "rejected", "needs_review"]


class MappingModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EGPCanonicalMapping(MappingModel):
    mapping_id: str
    source_record_id: str
    canonical_skill: str | None = None
    secondary_candidates: list[str] = Field(default_factory=list)
    status: MappingStatus
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    matched_terms: list[str] = Field(default_factory=list)
    review_status: ReviewStatus
    reviewer_note: str | None = None

    @field_validator("mapping_id", "source_record_id", "reason")
    @classmethod
    def required_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("value must not be empty")
        return text

    @field_validator("canonical_skill", "reviewer_note", mode="before")
    @classmethod
    def optional_text(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class MappingValidationIssue(MappingModel):
    severity: Literal["warning", "error"]
    code: str
    message: str
    mapping_id: str | None = None
    source_record_id: str | None = None
    canonical_skill: str | None = None


class MappingValidationResult(MappingModel):
    total_records: int = 0
    total_mappings: int = 0
    issues: list[MappingValidationIssue] = Field(default_factory=list)

    @property
    def errors(self) -> list[MappingValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[MappingValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)
