from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SOURCE_NAME = "cefr_companion_volume"
SOURCE_DOCUMENT = (
    "Common European Framework of Reference for Languages: "
    "Learning, teaching, assessment - Companion volume"
)
SOURCE_YEAR = 2020

PRIMARY_CEFR_LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}
PRESERVED_CEFR_LEVELS = {"Pre-A1", "A2+", "B1+", "B2+"}
VALID_CEFR_LEVELS = PRIMARY_CEFR_LEVELS | PRESERVED_CEFR_LEVELS

DOMAIN_NAMES = {
    "reception",
    "production",
    "interaction",
    "linguistic_competence",
    "assessment",
    "level_summary",
}
DESCRIPTOR_TYPES = {
    "communicative_activity",
    "communicative_strategy",
    "linguistic_competence",
    "assessment_descriptor",
    "level_summary",
}
SCALE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

DescriptorType = Literal[
    "communicative_activity",
    "communicative_strategy",
    "linguistic_competence",
    "assessment_descriptor",
    "level_summary",
]
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


class CEFRModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CEFRSourceConfig(CEFRModel):
    name: str = SOURCE_NAME
    document: str = SOURCE_DOCUMENT
    short_document: str = "CEFR Companion Volume 2020"
    language: str = "English"
    year: int = SOURCE_YEAR
    publisher: str | None = "Council of Europe"
    source_file: str = "data/external/cefr/CEFR Companion Volume_eng.pdf"

    @field_validator("name", "document", "short_document", "language", "source_file")
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("publisher", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return clean_optional_text(value)

    @field_validator("source_file")
    @classmethod
    def source_file_must_be_relative(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        path = PurePosixPath(normalized)
        if (
            path.is_absolute()
            or ".." in path.parts
            or normalized.startswith("/")
            or re.match(r"^[a-zA-Z]:", normalized)
        ):
            raise ValueError("source_file must be a relative path inside the workspace")
        return str(path)


class CEFRLevelsConfig(CEFRModel):
    include: list[str] = Field(default_factory=lambda: sorted(PRIMARY_CEFR_LEVELS))
    preserve: list[str] = Field(default_factory=lambda: sorted(PRESERVED_CEFR_LEVELS))

    @field_validator("include", "preserve")
    @classmethod
    def normalize_levels(cls, values: list[str]) -> list[str]:
        normalized = [_normalize_level(value) for value in values]
        invalid = [value for value in normalized if value not in VALID_CEFR_LEVELS]
        if invalid:
            allowed = ", ".join(sorted(VALID_CEFR_LEVELS))
            raise ValueError(
                f"CEFR levels must be one of {allowed}; invalid: {invalid}",
            )
        return normalized

    @property
    def valid(self) -> set[str]:
        return set(self.include) | set(self.preserve)


class CEFRChapter2Config(CEFRModel):
    section: str
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    primary_levels: dict[str, str] = Field(default_factory=dict)
    documentation_only: list[str] = Field(default_factory=list)

    @field_validator("section")
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("primary_levels")
    @classmethod
    def validate_primary_level_map(cls, value: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for level, category in value.items():
            normalized_level = _normalize_level(level)
            if normalized_level not in PRIMARY_CEFR_LEVELS:
                raise ValueError(f"primary_levels contains non-primary level: {level}")
            normalized[normalized_level] = clean_required_text(category)
        return normalized

    @model_validator(mode="after")
    def page_range_is_ordered(self) -> CEFRChapter2Config:
        if self.page_end < self.page_start:
            raise ValueError("page_end must be greater than or equal to page_start")
        return self


class CEFRScaleConfig(CEFRModel):
    id: str
    name: str
    subdomain: str | None = None
    enabled: bool = True
    chapter: str | None = None
    section: str | None = None
    domain: str | None = None
    descriptor_type: DescriptorType | None = None
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)

    @field_validator("id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        scale_id = clean_required_text(value)
        if not SCALE_ID_PATTERN.match(scale_id):
            raise ValueError("scale id must be lowercase snake_case")
        return scale_id

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("subdomain", "chapter", "section", "domain", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return clean_optional_text(value)

    @model_validator(mode="after")
    def page_range_is_ordered(self) -> CEFRScaleConfig:
        if (
            self.page_start is not None
            and self.page_end is not None
            and self.page_end < self.page_start
        ):
            raise ValueError("page_end must be greater than or equal to page_start")
        return self


class CEFRSectionConfig(CEFRModel):
    enabled: bool = True
    chapter: str
    section: str
    descriptor_type: DescriptorType
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    scales: list[CEFRScaleConfig] = Field(default_factory=list)

    @field_validator("chapter", "section")
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @model_validator(mode="after")
    def page_range_is_ordered(self) -> CEFRSectionConfig:
        if self.page_end < self.page_start:
            raise ValueError("page_end must be greater than or equal to page_start")
        return self


class CEFRAppendixConfig(CEFRModel):
    id: str
    name: str
    enabled: bool = False
    extraction: str
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)

    @field_validator("id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        appendix_id = clean_required_text(value)
        if not SCALE_ID_PATTERN.match(appendix_id):
            raise ValueError("appendix id must be lowercase snake_case")
        return appendix_id

    @field_validator("name", "extraction")
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @model_validator(mode="after")
    def page_range_is_ordered(self) -> CEFRAppendixConfig:
        if self.page_end < self.page_start:
            raise ValueError("page_end must be greater than or equal to page_start")
        return self


class CEFRConfig(CEFRModel):
    source: CEFRSourceConfig = Field(default_factory=CEFRSourceConfig)
    levels: CEFRLevelsConfig = Field(default_factory=CEFRLevelsConfig)
    chapter2: CEFRChapter2Config
    sections: dict[str, CEFRSectionConfig] = Field(default_factory=dict)
    appendices: list[CEFRAppendixConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def sections_are_valid(self) -> CEFRConfig:
        duplicates: set[str] = set()
        seen: set[str] = set()
        for domain, section in self.sections.items():
            if domain not in DOMAIN_NAMES and domain != "mediation":
                raise ValueError(f"unknown CEFR domain: {domain}")
            for scale in section.scales:
                if scale.id in seen:
                    duplicates.add(scale.id)
                seen.add(scale.id)
        if duplicates:
            joined = ", ".join(sorted(duplicates))
            raise ValueError(f"duplicate CEFR scale ids: {joined}")
        return self

    def select_scales(
        self,
        *,
        section: str | None = None,
        domain: str | None = None,
    ) -> list[CEFRScaleConfig]:
        section_filter = clean_optional_text(section)
        domain_filter = clean_optional_text(domain)
        selected: list[CEFRScaleConfig] = []
        for domain_name, section_config in self.sections.items():
            if not section_config.enabled:
                continue
            if domain_filter and domain_name != domain_filter:
                continue
            if section_filter and not _section_matches(section_filter, section_config):
                continue
            for scale in section_config.scales:
                if not scale.enabled:
                    continue
                selected.append(
                    scale.model_copy(
                        update={
                            "chapter": scale.chapter or section_config.chapter,
                            "section": scale.section or section_config.section,
                            "domain": scale.domain or domain_name,
                            "descriptor_type": (
                                scale.descriptor_type
                                or section_config.descriptor_type
                            ),
                            "page_start": scale.page_start or section_config.page_start,
                            "page_end": scale.page_end or section_config.page_end,
                        },
                    ),
                )
        return selected

    def scale_by_id(self) -> dict[str, CEFRScaleConfig]:
        return {scale.id: scale for scale in self.select_scales()}

    def known_domains(self) -> set[str]:
        return {domain for domain, section in self.sections.items() if section.enabled} | {
            "level_summary",
            "assessment",
        }

    def include_level_summaries(
        self,
        *,
        section: str | None = None,
        domain: str | None = None,
    ) -> bool:
        domain_filter = clean_optional_text(domain)
        if domain_filter and domain_filter != "level_summary":
            return False
        section_filter = clean_optional_text(section)
        if section_filter is None:
            return True
        normalized = section_filter.casefold().replace("_", "").replace("-", "")
        return normalized in {"chapter2", "appendix1", "appendices", "levelsummary"}

    def appendix_by_id(self) -> dict[str, CEFRAppendixConfig]:
        return {appendix.id: appendix for appendix in self.appendices}


class CEFRDescriptorRecord(CEFRModel):
    source: str = SOURCE_NAME
    source_document: str = SOURCE_DOCUMENT
    source_year: int = SOURCE_YEAR
    source_record_id: str
    chapter: str | None = None
    section: str | None = None
    domain: str
    subdomain: str | None = None
    scale_name: str
    descriptor_type: DescriptorType
    cefr_level: str
    descriptor_text: str
    descriptor_available: bool = True
    reference_level: str | None = None
    page_number: int | None = None
    source_table: str | None = None
    is_pre_a1: bool = False
    source_file: str
    raw_payload: dict[str, Any] | None = None

    @field_validator(
        "source",
        "source_document",
        "source_record_id",
        "domain",
        "scale_name",
        "cefr_level",
        "descriptor_text",
        "source_file",
    )
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("chapter", "section", "subdomain", "reference_level", "source_table", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return clean_optional_text(value)


class CEFRLearningObjectiveCandidate(CEFRModel):
    objective_id: str
    source_record_id: str
    cefr_level: str
    domain: str
    scale_name: str
    objective_text: str
    source_descriptor_text: str
    status: Literal["exact_source", "candidate", "needs_review"] = "exact_source"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    canonical_skill_hint: str | None = None

    @field_validator(
        "objective_id",
        "source_record_id",
        "cefr_level",
        "domain",
        "scale_name",
        "objective_text",
        "source_descriptor_text",
    )
    @classmethod
    def required_text(cls, value: str) -> str:
        return clean_required_text(value)

    @field_validator("canonical_skill_hint", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return clean_optional_text(value)


class CEFRExtractionIssue(CEFRModel):
    severity: IssueSeverity
    code: str
    message: str
    page_number: int | None = None
    scale_name: str | None = None
    source_table: str | None = None
    row_index: int | None = None
    raw_payload: dict[str, Any] | None = None


class CEFRValidationIssue(CEFRModel):
    severity: IssueSeverity
    code: str
    message: str
    source_record_id: str | None = None
    objective_id: str | None = None
    cefr_level: str | None = None
    domain: str | None = None
    scale_name: str | None = None
    page_number: int | None = None
    duplicate_key: str | None = None


class CEFRValidationResult(CEFRModel):
    source: str = SOURCE_NAME
    run_at: datetime = Field(default_factory=now_utc)
    total_records: int = 0
    total_candidates: int = 0
    issues: list[CEFRValidationIssue] = Field(default_factory=list)

    @property
    def errors(self) -> list[CEFRValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[CEFRValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)


def _normalize_level(value: str) -> str:
    text = clean_required_text(value).replace(" ", "-")
    folded = text.casefold()
    if folded in {"pre-a1", "prea1"}:
        return "Pre-A1"
    return text.upper()


def _section_matches(section_filter: str, section: CEFRSectionConfig) -> bool:
    normalized = _normalize_section_filter(section_filter)
    chapter = _normalize_section_filter(f"chapter{section.chapter}")
    raw_chapter = _normalize_section_filter(section.chapter)
    section_text = _normalize_section_filter(section.section)
    return normalized in {chapter, raw_chapter} or normalized in section_text


def _normalize_section_filter(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", clean_required_text(value).casefold())
