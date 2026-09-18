from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field

from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILL_SET
from knowledge_core.normalization.error_taxonomy.models import (
    ErrorInstance,
    LearnerCorpusSourceRecord,
    NormalizedErrorInstance,
)
from knowledge_core.normalization.error_taxonomy.policy import (
    find_forbidden_free_text_keys,
)
from knowledge_core.normalization.error_taxonomy.vocabulary import (
    ERROR_TAXONOMY_VERSION,
    VALID_NORMALIZED_ERROR_CATEGORY_SET,
)


IssueSeverity = Literal["warning", "error"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class ErrorSchemaValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: IssueSeverity
    code: str
    message: str
    entity_id: str | None = None
    source_record_id: str | None = None


class ErrorSchemaValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_at: datetime = Field(default_factory=now_utc)
    taxonomy_version: str = ERROR_TAXONOMY_VERSION
    source_record_count: int = 0
    error_instance_count: int = 0
    normalized_error_count: int = 0
    issues: list[ErrorSchemaValidationIssue] = Field(default_factory=list)
    no_raw_learner_text: bool = True
    taxonomy_unchanged: bool = True

    @property
    def errors(self) -> list[ErrorSchemaValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ErrorSchemaValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def passed(self) -> bool:
        return self.error_count == 0


def validate_error_schema_records(
    *,
    source_records: Sequence[LearnerCorpusSourceRecord],
    error_instances: Sequence[ErrorInstance],
    normalized_errors: Sequence[NormalizedErrorInstance] = (),
) -> ErrorSchemaValidationResult:
    issues: list[ErrorSchemaValidationIssue] = []
    _add_duplicate_id_issues(
        issues,
        ids=[record.source_record_id for record in source_records],
        code="duplicate_source_record_id",
        label="source record",
    )
    _add_duplicate_id_issues(
        issues,
        ids=[error.error_instance_id for error in error_instances],
        code="duplicate_error_instance_id",
        label="error instance",
    )
    _add_duplicate_id_issues(
        issues,
        ids=[error.normalized_error_id for error in normalized_errors],
        code="duplicate_normalized_error_id",
        label="normalized error",
    )

    source_ids = {record.source_record_id for record in source_records}
    error_ids = {error.error_instance_id for error in error_instances}

    for error in error_instances:
        if error.source_record_id not in source_ids:
            issues.append(
                ErrorSchemaValidationIssue(
                    severity="error",
                    code="missing_source_record_reference",
                    message="ErrorInstance source_record_id does not resolve",
                    entity_id=error.error_instance_id,
                    source_record_id=error.source_record_id,
                ),
            )

    for normalized in normalized_errors:
        if normalized.error_instance_id not in error_ids:
            issues.append(
                ErrorSchemaValidationIssue(
                    severity="error",
                    code="missing_error_instance_reference",
                    message="NormalizedErrorInstance error_instance_id does not resolve",
                    entity_id=normalized.normalized_error_id,
                    source_record_id=normalized.source_record_id,
                ),
            )
        if normalized.source_record_id not in source_ids:
            issues.append(
                ErrorSchemaValidationIssue(
                    severity="error",
                    code="missing_normalized_source_record_reference",
                    message="NormalizedErrorInstance source_record_id does not resolve",
                    entity_id=normalized.normalized_error_id,
                    source_record_id=normalized.source_record_id,
                ),
            )
        if normalized.category not in VALID_NORMALIZED_ERROR_CATEGORY_SET:
            issues.append(
                ErrorSchemaValidationIssue(
                    severity="error",
                    code="invalid_normalized_error_category",
                    message=f"Invalid normalized error category: {normalized.category}",
                    entity_id=normalized.normalized_error_id,
                    source_record_id=normalized.source_record_id,
                ),
            )
        if normalized.taxonomy_version != ERROR_TAXONOMY_VERSION:
            issues.append(
                ErrorSchemaValidationIssue(
                    severity="error",
                    code="taxonomy_version_mismatch",
                    message=(
                        f"Expected {ERROR_TAXONOMY_VERSION}, found "
                        f"{normalized.taxonomy_version}"
                    ),
                    entity_id=normalized.normalized_error_id,
                    source_record_id=normalized.source_record_id,
                ),
            )
        invalid_skills = [
            skill
            for skill in normalized.canonical_skill_candidates
            if skill not in CANONICAL_GRAMMAR_V1_SKILL_SET
        ]
        if invalid_skills:
            issues.append(
                ErrorSchemaValidationIssue(
                    severity="error",
                    code="invalid_canonical_skill_candidate",
                    message=f"Invalid canonical skill candidate(s): {invalid_skills}",
                    entity_id=normalized.normalized_error_id,
                    source_record_id=normalized.source_record_id,
                ),
            )

    privacy_violations = _privacy_violations(
        source_records=source_records,
        error_instances=error_instances,
        normalized_errors=normalized_errors,
    )
    for entity_id, violation in privacy_violations:
        issues.append(
            ErrorSchemaValidationIssue(
                severity="error",
                code="raw_learner_text_field",
                message=f"Forbidden learner free-text field found: {violation}",
                entity_id=entity_id,
            ),
        )

    return ErrorSchemaValidationResult(
        source_record_count=len(source_records),
        error_instance_count=len(error_instances),
        normalized_error_count=len(normalized_errors),
        issues=issues,
        no_raw_learner_text=not privacy_violations,
        taxonomy_unchanged=True,
    )


def _add_duplicate_id_issues(
    issues: list[ErrorSchemaValidationIssue],
    *,
    ids: list[str],
    code: str,
    label: str,
) -> None:
    counts = Counter(ids)
    for entity_id, count in sorted(counts.items()):
        if count > 1:
            issues.append(
                ErrorSchemaValidationIssue(
                    severity="error",
                    code=code,
                    message=f"Duplicate {label} id appears {count} times",
                    entity_id=entity_id,
                ),
            )


def _privacy_violations(
    *,
    source_records: Sequence[LearnerCorpusSourceRecord],
    error_instances: Sequence[ErrorInstance],
    normalized_errors: Sequence[NormalizedErrorInstance],
) -> list[tuple[str, str]]:
    violations: list[tuple[str, str]] = []
    for record in source_records:
        for violation in find_forbidden_free_text_keys(record.model_dump(mode="json")):
            violations.append((record.source_record_id, violation))
    for error in error_instances:
        for violation in find_forbidden_free_text_keys(error.model_dump(mode="json")):
            violations.append((error.error_instance_id, violation))
    for normalized in normalized_errors:
        for violation in find_forbidden_free_text_keys(normalized.model_dump(mode="json")):
            violations.append((normalized.normalized_error_id, violation))
    return violations

