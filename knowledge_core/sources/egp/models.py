from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SOURCE_NAME = "english_grammar_profile"
DEFAULT_EGP_ONLINE_URL = "https://englishprofile.org/?menu=egp-online"
CEFR_LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}
CONFIG_LEVELS = CEFR_LEVELS | {"ALL"}
CATEGORY_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _clean_required_text(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("value must not be empty")
    return text


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class EGPModel(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)


class EGPSourceConfig(EGPModel):
    name: str = SOURCE_NAME
    level: str = "ALL"
    url: str = DEFAULT_EGP_ONLINE_URL

    @field_validator("name", "url")
    @classmethod
    def required_text(cls, value: str) -> str:
        return _clean_required_text(value)

    @field_validator("level")
    @classmethod
    def valid_level(cls, value: str) -> str:
        level = _clean_required_text(value).upper()
        if level not in CONFIG_LEVELS:
            allowed = ", ".join(sorted(CONFIG_LEVELS))
            raise ValueError(f"level must be one of: {allowed}")
        return level


class EGPCategoryConfig(EGPModel):
    id: str
    query: str
    raw_path: str | None = None
    expected_super_category: str | None = None
    expected_sub_category: str | None = None
    canonical_parent_hint: str | None = None

    @field_validator("id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        category_id = _clean_required_text(value)
        if not CATEGORY_ID_PATTERN.match(category_id):
            raise ValueError(
                "category id must be lowercase snake_case and start with a letter",
            )
        return category_id

    @field_validator("query")
    @classmethod
    def valid_query(cls, value: str) -> str:
        return _clean_required_text(value)

    @field_validator("raw_path", mode="before")
    @classmethod
    def valid_raw_path(cls, value: Any) -> str | None:
        text = _clean_optional_text(value)
        if text is None:
            return None
        normalized = text.replace("\\", "/")
        path = PurePosixPath(normalized)
        if (
            path.is_absolute()
            or ".." in path.parts
            or normalized.startswith("/")
            or re.match(r"^[a-zA-Z]:", normalized)
        ):
            raise ValueError("raw_path must be a relative path inside the raw root")
        return str(path)

    @field_validator(
        "expected_super_category",
        "expected_sub_category",
        "canonical_parent_hint",
        mode="before",
    )
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return _clean_optional_text(value)


class EGPConfig(EGPModel):
    source: EGPSourceConfig = Field(default_factory=EGPSourceConfig)
    categories: list[EGPCategoryConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def category_ids_are_unique(self) -> EGPConfig:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for category in self.categories:
            if category.id in seen:
                duplicates.add(category.id)
            seen.add(category.id)
        if duplicates:
            joined = ", ".join(sorted(duplicates))
            raise ValueError(f"duplicate EGP category ids: {joined}")
        return self

    def category_by_id(self) -> dict[str, EGPCategoryConfig]:
        return {category.id: category for category in self.categories}

    def select_categories(self, category_id: str | None = None) -> list[EGPCategoryConfig]:
        if category_id is None:
            return list(self.categories)
        categories = self.category_by_id()
        if category_id not in categories:
            raise KeyError(f"unknown EGP category id: {category_id}")
        return [categories[category_id]]


class RawEGPRecord(EGPModel):
    source: str = SOURCE_NAME
    source_record_id: str | None = None
    category_id: str

    super_category: str | None = None
    sub_category: str | None = None

    cefr_level: str

    feature_type: str | None = None
    feature_name: str | None = None

    can_do_statement: str

    example: str | None = None
    details: str | None = None

    source_row_number: int | None = Field(default=None, ge=1)
    source_file: str
    source_url: str | None = None

    retrieved_at: datetime

    canonical_parent_hint: str | None = None

    raw_payload: dict[str, Any] | None = None


DownloadStatus = Literal["downloaded", "skipped", "failed", "dry_run"]


class DownloadResult(EGPModel):
    category_id: str
    destination: Path
    status: DownloadStatus
    method: str
    source_url: str | None = None
    retrieved_at: datetime = Field(default_factory=now_utc)
    bytes_written: int = 0
    error: str | None = None


IssueSeverity = Literal["warning", "error"]


class ValidationIssue(EGPModel):
    severity: IssueSeverity
    code: str
    message: str
    category_id: str | None = None
    source_file: str | None = None
    source_row_number: int | None = None
    duplicate_key: str | None = None
    source_record_id: str | None = None


class ValidationResult(EGPModel):
    source: str = SOURCE_NAME
    run_at: datetime = Field(default_factory=now_utc)
    total_records: int = 0
    issues: list[ValidationIssue] = Field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def valid_records(self) -> int:
        error_rows = {
            (issue.source_file, issue.source_row_number, issue.category_id)
            for issue in self.errors
            if issue.source_file or issue.source_row_number or issue.category_id
        }
        return max(self.total_records - len(error_rows), 0)


class SourceRecordExclusion(EGPModel):
    source_record_id: str | None = None
    category_id: str
    source_file: str
    source_row_number: int | None = None
    reason_codes: list[str] = Field(default_factory=list)
    expected_super_category: str | None = None
    actual_super_category: str | None = None
    expected_sub_category: str | None = None
    actual_sub_category: str | None = None
    cefr_level: str | None = None
    feature_type: str | None = None
    feature_name: str | None = None
    can_do_statement: str | None = None
