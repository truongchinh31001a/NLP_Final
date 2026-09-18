from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Sequence

from pydantic import BaseModel, ConfigDict, Field

from knowledge_core.normalization.error_taxonomy.models import (
    ErrorInstance,
    LearnerCorpusSourceRecord,
)
from knowledge_core.normalization.error_taxonomy.validator import (
    ErrorSchemaValidationIssue,
    ErrorSchemaValidationResult,
    validate_error_schema_records,
)
from knowledge_core.sources.clc_fce.models import CLCFCEXMLAnswerSummary


class CLCFCEValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_validation: ErrorSchemaValidationResult
    issues: list[ErrorSchemaValidationIssue] = Field(default_factory=list)
    expected_answer_records: int | None = None
    expected_annotated_scripts: int | None = None
    parsed_splits: list[str] = Field(default_factory=list)
    source_record_counts_by_split: dict[str, int] = Field(default_factory=dict)
    error_counts_by_split: dict[str, int] = Field(default_factory=dict)
    xml_answer_summary_count: int = 0
    xml_nested_error_count: int = 0

    @property
    def errors(self) -> list[ErrorSchemaValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ErrorSchemaValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def error_count(self) -> int:
        return len(self.errors) + self.schema_validation.error_count

    @property
    def warning_count(self) -> int:
        return len(self.warnings) + self.schema_validation.warning_count

    @property
    def passed(self) -> bool:
        return self.error_count == 0


def validate_clc_fce_ingestion(
    *,
    source_records: Sequence[LearnerCorpusSourceRecord],
    error_instances: Sequence[ErrorInstance],
    xml_answer_summaries: dict[str, CLCFCEXMLAnswerSummary],
    json_files: dict[str, Path],
    xml_files: dict[str, Path],
    expected_answer_records: int | None = None,
    expected_annotated_scripts: int | None = None,
) -> CLCFCEValidationResult:
    schema_validation = validate_error_schema_records(
        source_records=source_records,
        error_instances=error_instances,
    )
    issues: list[ErrorSchemaValidationIssue] = []
    source_ids = {record.source_record_id for record in source_records}
    text_length_by_record = {
        record.source_record_id: record.text_length or 0 for record in source_records
    }

    for split, path in sorted(json_files.items()):
        if not path.exists():
            issues.append(
                ErrorSchemaValidationIssue(
                    severity="error",
                    code="missing_json_split_file",
                    message=f"Missing CLC FCE JSON split file: {split}",
                ),
            )
    for split, path in sorted(xml_files.items()):
        if not path.exists():
            issues.append(
                ErrorSchemaValidationIssue(
                    severity="error",
                    code="missing_xml_split_file",
                    message=f"Missing CLC FCE XML split file: {split}",
                ),
            )

    if expected_answer_records is not None and len(source_records) != expected_answer_records:
        issues.append(
            ErrorSchemaValidationIssue(
                severity="error",
                code="answer_record_count_mismatch",
                message=(
                    f"Expected {expected_answer_records} answer records, parsed "
                    f"{len(source_records)}"
                ),
            ),
        )

    if len(xml_answer_summaries) != len(source_records):
        issues.append(
            ErrorSchemaValidationIssue(
                severity="warning",
                code="xml_json_answer_count_mismatch",
                message=(
                    f"JSON source records={len(source_records)}; XML summaries="
                    f"{len(xml_answer_summaries)}"
                ),
            ),
        )

    for error in error_instances:
        if error.source_record_id not in source_ids:
            continue
        if error.span.start_char is not None and error.span.end_char is not None:
            text_length = text_length_by_record[error.source_record_id]
            if error.span.end_char > text_length:
                issues.append(
                    ErrorSchemaValidationIssue(
                        severity="warning",
                        code="span_exceeds_text_length",
                        message=(
                            "JSON edit span exceeds answer text length; preserved "
                            "as source offset requiring review"
                        ),
                        entity_id=error.error_instance_id,
                        source_record_id=error.source_record_id,
                    ),
                )

    source_counts = Counter(record.split or "unknown" for record in source_records)
    source_split_by_id = {
        record.source_record_id: record.split or "unknown" for record in source_records
    }
    error_counts = Counter(
        source_split_by_id.get(error.source_record_id, "unknown")
        for error in error_instances
    )
    return CLCFCEValidationResult(
        schema_validation=schema_validation,
        issues=issues,
        expected_answer_records=expected_answer_records,
        expected_annotated_scripts=expected_annotated_scripts,
        parsed_splits=sorted(source_counts),
        source_record_counts_by_split=dict(sorted(source_counts.items())),
        error_counts_by_split=dict(sorted(error_counts.items())),
        xml_answer_summary_count=len(xml_answer_summaries),
        xml_nested_error_count=sum(
            summary.nested_error_count for summary in xml_answer_summaries.values()
        ),
    )
