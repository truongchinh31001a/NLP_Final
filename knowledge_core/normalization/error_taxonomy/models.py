from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from knowledge_core.normalization.error_taxonomy.policy import (
    validate_no_forbidden_free_text_keys,
)
from knowledge_core.normalization.error_taxonomy.vocabulary import (
    ERROR_TAXONOMY_VERSION,
    NormalizedErrorCategory,
)


LearnerErrorSourceKey = Literal["clc_fce", "efcamdat", "write_improve"]
RecordUnit = Literal["script", "answer", "writing", "essay_version", "sentence", "unknown"]
SpanKind = Literal[
    "json_char_offsets",
    "xml_inline_selection",
    "m2_token_offsets",
    "efcamdat_selection_text",
    "token_range",
    "whole_record",
    "unknown",
]
CorrectionType = Literal["replacement", "deletion", "insertion", "noop", "unknown"]
MappingStatus = Literal["exact", "candidate", "ambiguous", "unmapped"]
ReviewStatus = Literal["pending", "approved", "needs_review", "rejected"]
ErrorInstanceStatus = Literal["source_native", "parsed", "known_invalid_source_record"]
IssueSeverity = Literal["warning", "error"]

_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_SHA256_RE = re.compile(r"^sha256:[a-f0-9]{64}$")


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


class ErrorTaxonomyModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LearnerCorpusSourceRecord(ErrorTaxonomyModel):
    source_record_id: str
    source_key: LearnerErrorSourceKey
    native_record_id: str
    record_unit: RecordUnit
    split: str | None = None
    learner_id_pseudonym: str | None = None
    document_id_pseudonym: str | None = None
    task_id: str | None = None
    proficiency_label: str | None = None
    source_path: str | None = None
    text_fingerprint: str | None = None
    text_length: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_record_id", "native_record_id")
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator(
        "split",
        "learner_id_pseudonym",
        "document_id_pseudonym",
        "task_id",
        "proficiency_label",
        "source_path",
        "text_fingerprint",
        mode="before",
    )
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return clean_optional_text(value)

    @field_validator("text_fingerprint")
    @classmethod
    def valid_fingerprint(cls, value: str | None) -> str | None:
        if value is not None and not _SHA256_RE.match(value):
            raise ValueError("text_fingerprint must use sha256:<64 hex chars>")
        return value

    @model_validator(mode="after")
    def privacy_payload_is_clean(self) -> LearnerCorpusSourceRecord:
        validate_no_forbidden_free_text_keys(self.model_dump(mode="json"))
        return self


class TextSpan(ErrorTaxonomyModel):
    span_kind: SpanKind
    source_field: str | None = None
    start_char: int | None = Field(default=None, ge=0)
    end_char: int | None = Field(default=None, ge=0)
    token_start: int | None = Field(default=None, ge=0)
    token_end: int | None = Field(default=None, ge=0)
    selection_fingerprint: str | None = None
    selected_text_length: int | None = Field(default=None, ge=0)
    source_markup_path: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("source_field", "selection_fingerprint", "source_markup_path", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return clean_optional_text(value)

    @field_validator("selection_fingerprint")
    @classmethod
    def valid_fingerprint(cls, value: str | None) -> str | None:
        if value is not None and not _SHA256_RE.match(value):
            raise ValueError("selection_fingerprint must use sha256:<64 hex chars>")
        return value

    @model_validator(mode="after")
    def span_representation_matches_kind(self) -> TextSpan:
        if self.span_kind == "json_char_offsets":
            if self.start_char is None or self.end_char is None:
                raise ValueError("json_char_offsets spans require start_char and end_char")
            if self.end_char < self.start_char:
                raise ValueError("end_char must be greater than or equal to start_char")
        if self.span_kind in {"m2_token_offsets", "token_range"}:
            if self.token_start is None or self.token_end is None:
                raise ValueError(f"{self.span_kind} spans require token_start and token_end")
            if self.token_end < self.token_start:
                raise ValueError("token_end must be greater than or equal to token_start")
        if self.span_kind in {"xml_inline_selection", "efcamdat_selection_text"}:
            if self.selection_fingerprint is None or self.selected_text_length is None:
                raise ValueError(
                    f"{self.span_kind} spans require selection_fingerprint and selected_text_length",
                )
        return self


class ErrorCorrection(ErrorTaxonomyModel):
    correction_type: CorrectionType
    correction_fingerprint: str | None = None
    correction_length: int | None = Field(default=None, ge=0)
    correction_count: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("correction_fingerprint", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return clean_optional_text(value)

    @field_validator("correction_fingerprint")
    @classmethod
    def valid_fingerprint(cls, value: str | None) -> str | None:
        if value is not None and not _SHA256_RE.match(value):
            raise ValueError("correction_fingerprint must use sha256:<64 hex chars>")
        return value

    @model_validator(mode="after")
    def correction_metadata_is_clean(self) -> ErrorCorrection:
        validate_no_forbidden_free_text_keys(self.model_dump(mode="json"))
        if self.correction_type in {"replacement", "insertion"} and (
            self.correction_fingerprint is None or self.correction_length is None
        ):
            raise ValueError(
                "replacement/insertion corrections require fingerprint and length, not raw text",
            )
        return self


class SourceNativeErrorLabel(ErrorTaxonomyModel):
    label_system: str
    label: str
    label_path: str | None = None
    description: str | None = None

    @field_validator("label_system", "label")
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("label_path", "description", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return clean_optional_text(value)


class ErrorInstance(ErrorTaxonomyModel):
    error_instance_id: str
    source_record_id: str
    source_key: LearnerErrorSourceKey
    native_error_id: str | None = None
    source_native_label: SourceNativeErrorLabel | None = None
    span: TextSpan
    correction: ErrorCorrection | None = None
    status: ErrorInstanceStatus = "parsed"
    review_status: ReviewStatus = "pending"
    parser_notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)

    @field_validator("error_instance_id", "source_record_id")
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("native_error_id", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return clean_optional_text(value)

    @field_validator("parser_notes")
    @classmethod
    def clean_notes(cls, values: list[str]) -> list[str]:
        return [clean_required_text(value) for value in values]

    @model_validator(mode="after")
    def error_payload_is_clean(self) -> ErrorInstance:
        validate_no_forbidden_free_text_keys(self.model_dump(mode="json"))
        return self


class NormalizedErrorInstance(ErrorTaxonomyModel):
    normalized_error_id: str
    error_instance_id: str
    source_record_id: str
    source_key: LearnerErrorSourceKey
    category: NormalizedErrorCategory
    subtype: str | None = None
    status: MappingStatus
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    review_status: ReviewStatus = "pending"
    taxonomy_version: str = ERROR_TAXONOMY_VERSION
    canonical_skill_candidates: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)

    @field_validator("normalized_error_id", "error_instance_id", "source_record_id", "reason")
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("subtype", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return clean_optional_text(value)

    @field_validator("subtype")
    @classmethod
    def subtype_is_snake_case(cls, value: str | None) -> str | None:
        if value is not None and not _SNAKE_CASE_RE.match(value):
            raise ValueError("subtype must be lowercase snake_case")
        return value

    @field_validator("canonical_skill_candidates")
    @classmethod
    def clean_skill_candidates(cls, values: list[str]) -> list[str]:
        return [clean_required_text(value) for value in values]

    @model_validator(mode="after")
    def normalized_payload_is_clean(self) -> NormalizedErrorInstance:
        validate_no_forbidden_free_text_keys(self.model_dump(mode="json"))
        if self.status == "unmapped" and self.category != "unmapped":
            raise ValueError("unmapped normalized errors must use category='unmapped'")
        return self
