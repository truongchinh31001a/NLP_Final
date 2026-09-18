from __future__ import annotations

from pathlib import Path
from typing import Any

from knowledge_core.normalization.error_taxonomy.models import (
    ErrorInstance,
    LearnerCorpusSourceRecord,
)
from knowledge_core.sources.clc_fce.models import CLCFCEXMLAnswerSummary
from knowledge_core.sources.clc_fce.parser import build_error_instances, build_source_record


def normalize_answer_record(
    payload: dict[str, Any],
    *,
    split: str,
    source_path: Path,
    line_number: int,
    xml_summary: CLCFCEXMLAnswerSummary | None,
) -> LearnerCorpusSourceRecord:
    """Normalize a CLC FCE answer into the common source-record schema."""
    return build_source_record(
        payload,
        split=split,
        source_path=source_path,
        line_number=line_number,
        xml_summary=xml_summary,
    )


def normalize_answer_errors(
    payload: dict[str, Any],
    *,
    split: str,
    source_record: LearnerCorpusSourceRecord,
    source_path: Path,
) -> list[ErrorInstance]:
    """Normalize CLC FCE JSON edits into source-native ErrorInstance records."""
    return build_error_instances(
        payload,
        split=split,
        source_record=source_record,
        source_path=source_path,
    )

