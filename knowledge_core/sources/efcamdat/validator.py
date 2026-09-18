from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class EFCAMDATValidationIssue:
    severity: str
    code: str
    message: str
    entity_id: str | None = None
    source_record_id: str | None = None


@dataclass(slots=True)
class EFCAMDATValidationSummary:
    issues: list[EFCAMDATValidationIssue] = field(default_factory=list)
    raw_learner_text_emitted: bool = False
    source_record_count: int = 0
    error_instance_count: int = 0
    parser_fallback_count: int = 0

    @property
    def errors(self) -> list[EFCAMDATValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[EFCAMDATValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def passed(self) -> bool:
        return self.error_count == 0 and not self.raw_learner_text_emitted

    def to_dict(self) -> dict[str, object]:
        return {
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [
                {
                    "severity": issue.severity,
                    "code": issue.code,
                    "message": issue.message,
                    "entity_id": issue.entity_id,
                    "source_record_id": issue.source_record_id,
                }
                for issue in self.issues
            ],
            "raw_learner_text_emitted": self.raw_learner_text_emitted,
            "source_record_count": self.source_record_count,
            "error_instance_count": self.error_instance_count,
            "parser_fallback_count": self.parser_fallback_count,
            "passed": self.passed,
        }


def build_validation_summary(
    *,
    source_record_count: int,
    error_instance_count: int,
    parser_fallback_count: int,
    malformed_writing_count: int,
) -> EFCAMDATValidationSummary:
    issues: list[EFCAMDATValidationIssue] = []
    if parser_fallback_count:
        issues.append(
            EFCAMDATValidationIssue(
                severity="warning",
                code="xml_regex_fallback_used",
                message=(
                    f"Regex fallback parsed {parser_fallback_count} malformed XML "
                    "writing block(s); records were preserved for review."
                ),
            ),
        )
    if malformed_writing_count:
        issues.append(
            EFCAMDATValidationIssue(
                severity="warning",
                code="malformed_writing_block",
                message=(
                    f"{malformed_writing_count} writing block(s) required malformed "
                    "source handling."
                ),
            ),
        )
    return EFCAMDATValidationSummary(
        issues=issues,
        raw_learner_text_emitted=False,
        source_record_count=source_record_count,
        error_instance_count=error_instance_count,
        parser_fallback_count=parser_fallback_count,
    )

