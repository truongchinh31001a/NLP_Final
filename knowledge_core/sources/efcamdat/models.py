from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from knowledge_core.normalization.error_taxonomy.models import (
    ErrorInstance,
    LearnerCorpusSourceRecord,
)


@dataclass(frozen=True, slots=True)
class EFCAMDATWritingBlock:
    source_record: LearnerCorpusSourceRecord
    error_instances: tuple[ErrorInstance, ...]
    parser_status: str
    parser_notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class EFCAMDATCSVSupportSummary:
    path: Path
    row_count: int
    chunk_count: int
    fieldnames: tuple[str, ...]
    rows_with_text_change_markup: int
    rows_with_support_field_change_markup: int
    unique_writing_id_count: int | None = None


@dataclass(slots=True)
class EFCAMDATIngestionCounters:
    source_record_count: int = 0
    error_instance_count: int = 0
    changed_writing_count: int = 0
    parser_fallback_count: int = 0
    malformed_writing_count: int = 0
    review_queue_count: int = 0

