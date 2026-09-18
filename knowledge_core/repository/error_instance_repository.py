from __future__ import annotations

import sqlite3

from knowledge_core.repository.base import BaseKnowledgeRepository, VersionSelector
from knowledge_core.repository.exceptions import KnowledgeNotFoundError
from knowledge_core.repository.models import ErrorInstanceReadModel, ErrorPatternByCefrReadModel


_ERROR_SELECT = """
SELECT ei.error_instance_id, nei.normalized_error_id, ei.source_record_id,
       ei.source_key, ei.native_error_id, ei.source_label, ei.label_system,
       ei.span_kind, ei.start_char, ei.end_char, ei.token_start, ei.token_end,
       ei.correction_type, nei.category, nei.subtype,
       nei.status AS normalization_status, nei.confidence, ei.review_status,
       lcsr.proficiency_label, lcsr.task_id, lcsr.split
FROM normalized_error_instances nei
JOIN error_instances ei ON ei.id = nei.error_instance_db_id
LEFT JOIN learner_corpus_source_records lcsr ON lcsr.id = ei.corpus_source_record_id
"""


class ErrorInstanceRepository(BaseKnowledgeRepository):
    def get(self, error_instance_id: str, version: VersionSelector = None) -> ErrorInstanceReadModel:
        resolved = self.resolve_version(version)
        row = self.fetchone(
            _ERROR_SELECT + " WHERE ei.knowledge_version_id = ? AND ei.error_instance_id = ?",
            (resolved.id, error_instance_id),
        )
        if row is None:
            raise KnowledgeNotFoundError(f"Error instance not found: {error_instance_id}")
        return _error_from_row(row)

    def list(
        self, *, source_key: str | None = None, category: str | None = None,
        subtype: str | None = None, proficiency_label: str | None = None,
        version: VersionSelector = None, limit: int | None = None,
        offset: int | None = None,
    ) -> list[ErrorInstanceReadModel]:
        resolved = self.resolve_version(version)
        page_limit, page_offset = self.normalize_pagination(limit=limit, offset=offset)
        filters = ["nei.knowledge_version_id = ?"]
        params: list[object] = [resolved.id]
        for column, value in (("ei.source_key", source_key), ("nei.category", category),
                              ("nei.subtype", subtype),
                              ("lcsr.proficiency_label", proficiency_label)):
            if value is not None:
                filters.append(f"{column} = ?")
                params.append(value)
        rows = self.fetchall(
            _ERROR_SELECT + f" WHERE {' AND '.join(filters)} "
            "ORDER BY ei.error_instance_id LIMIT ? OFFSET ?",
            (*params, page_limit, page_offset),
        )
        return [_error_from_row(row) for row in rows]

    def count(self, *, source_key: str | None = None, version: VersionSelector = None) -> int:
        resolved = self.resolve_version(version)
        sql = "SELECT COUNT(*) AS count FROM error_instances WHERE knowledge_version_id = ?"
        params: tuple[object, ...] = (resolved.id,)
        if source_key is not None:
            sql += " AND source_key = ?"
            params += (source_key,)
        row = self.fetchone(sql, params)
        return int(row["count"])

    def list_patterns_by_cefr(
        self, *, source_key: str | None = None, proficiency_label: str | None = None,
        version: VersionSelector = None, limit: int | None = None,
        offset: int | None = None,
    ) -> list[ErrorPatternByCefrReadModel]:
        resolved = self.resolve_version(version)
        page_limit, page_offset = self.normalize_pagination(limit=limit, offset=offset)
        filters = ["knowledge_version_id = ?"]
        params: list[object] = [resolved.id]
        if source_key is not None:
            filters.append("source_key = ?")
            params.append(source_key)
        if proficiency_label is not None:
            filters.append("proficiency_label = ?")
            params.append(proficiency_label)
        rows = self.fetchall(
            f"SELECT source_key, proficiency_label, category, subtype, error_count "
            f"FROM v_error_patterns_by_cefr WHERE {' AND '.join(filters)} "
            "ORDER BY error_count DESC, source_key, proficiency_label, category, subtype "
            "LIMIT ? OFFSET ?",
            (*params, page_limit, page_offset),
        )
        return [ErrorPatternByCefrReadModel(
            source_key=row["source_key"], proficiency_label=row["proficiency_label"],
            category=row["category"], subtype=row["subtype"],
            error_count=int(row["error_count"]),
        ) for row in rows]


def _error_from_row(row: sqlite3.Row) -> ErrorInstanceReadModel:
    return ErrorInstanceReadModel(
        error_instance_id=row["error_instance_id"], normalized_error_id=row["normalized_error_id"],
        source_record_id=row["source_record_id"], source_key=row["source_key"],
        native_error_id=row["native_error_id"], source_label=row["source_label"],
        label_system=row["label_system"], span_kind=row["span_kind"],
        start_char=row["start_char"], end_char=row["end_char"],
        token_start=row["token_start"], token_end=row["token_end"],
        correction_type=row["correction_type"], category=row["category"],
        subtype=row["subtype"], normalization_status=row["normalization_status"],
        confidence=float(row["confidence"]) if row["confidence"] is not None else None,
        review_status=row["review_status"], proficiency_label=row["proficiency_label"],
        task_id=row["task_id"], split=row["split"],
    )
