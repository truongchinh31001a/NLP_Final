from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from knowledge_core.normalization.error_taxonomy.models import (
    ErrorInstance,
    LearnerCorpusSourceRecord,
)


@dataclass(frozen=True, slots=True)
class CLCFCEInputFiles:
    json_by_split: dict[str, Path]
    xml_by_split: dict[str, Path]


@dataclass(frozen=True, slots=True)
class CLCFCEXMLErrorNode:
    label: str
    path: str
    depth: int
    incorrect_fingerprint: str | None
    incorrect_length: int | None
    correction_fingerprint: str | None
    correction_length: int | None
    child_error_count: int = 0


@dataclass(frozen=True, slots=True)
class CLCFCEXMLAnswerSummary:
    native_record_id: str
    split: str
    script_id: str
    session: str
    question_id: str
    source_path: str
    error_nodes: tuple[CLCFCEXMLErrorNode, ...] = field(default_factory=tuple)

    @property
    def error_count(self) -> int:
        return len(self.error_nodes)

    @property
    def nested_error_count(self) -> int:
        return sum(1 for node in self.error_nodes if node.depth > 1 or node.child_error_count)

    @property
    def max_error_depth(self) -> int:
        if not self.error_nodes:
            return 0
        return max(node.depth for node in self.error_nodes)


@dataclass(slots=True)
class ParsedCLCFCECorpus:
    source_records: list[LearnerCorpusSourceRecord]
    error_instances: list[ErrorInstance]
    xml_answer_summaries: dict[str, CLCFCEXMLAnswerSummary]
    input_files: CLCFCEInputFiles

