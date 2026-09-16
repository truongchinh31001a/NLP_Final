from __future__ import annotations

import sqlite3

from knowledge_core.repository.base import BaseKnowledgeRepository, VersionSelector
from knowledge_core.repository.exceptions import KnowledgeIntegrityError, KnowledgeNotFoundError
from knowledge_core.repository.models import SourceEvidenceReadModel, SourceRecordReadModel


SOURCE_RECORD_SELECT = """
SELECT
    sr.external_record_id AS source_record_id,
    ks.source_key,
    ks.source_name,
    sd.title AS source_document_title,
    sd.file_name,
    sr.record_type,
    sr.cefr_level,
    sr.raw_text,
    sr.normalized_text,
    sr.page_number,
    sr.row_number,
    sr.sheet_name
FROM source_records sr
JOIN knowledge_sources ks ON ks.id = sr.knowledge_source_id
LEFT JOIN source_documents sd ON sd.id = sr.source_document_id
"""


SOURCE_EVIDENCE_SELECT = """
SELECT
    se.evidence_key AS evidence_id,
    n.canonical_id AS skill_id,
    ks.source_key,
    sr.external_record_id AS source_record_id,
    sr.record_type,
    sr.cefr_level AS source_cefr_level,
    se.evidence_type,
    se.confidence,
    se.status,
    se.review_status,
    se.reason,
    sr.normalized_text AS source_text,
    sr.page_number,
    sr.row_number
FROM skill_source_evidence se
JOIN knowledge_nodes n ON n.id = se.knowledge_node_id
JOIN source_records sr ON sr.id = se.source_record_id
JOIN knowledge_sources ks ON ks.id = sr.knowledge_source_id
"""


class SourceEvidenceRepository(BaseKnowledgeRepository):
    def list_skill_evidence(
        self,
        skill_id: str,
        source_key: str | None = None,
        evidence_type: str | None = None,
        status: str | None = None,
        review_status: str | None = None,
        version: VersionSelector = None,
    ) -> list[SourceEvidenceReadModel]:
        resolved = self.resolve_version(version)
        filters = ["n.knowledge_version_id = ?", "n.canonical_id = ?"]
        params: list[object] = [resolved.id, skill_id]
        if source_key is not None:
            filters.append("ks.source_key = ?")
            params.append(source_key)
        if evidence_type is not None:
            filters.append("se.evidence_type = ?")
            params.append(evidence_type)
        if status is not None:
            filters.append("se.status = ?")
            params.append(status)
        if review_status is not None:
            filters.append("se.review_status = ?")
            params.append(review_status)
        rows = self.fetchall(
            SOURCE_EVIDENCE_SELECT
            + f"""
            WHERE {' AND '.join(filters)}
            ORDER BY se.confidence DESC, se.evidence_key
            """,
            tuple(params),
        )
        return [source_evidence_from_row(row) for row in rows]

    def get_evidence(
        self,
        evidence_id: str,
        version: VersionSelector = None,
    ) -> SourceEvidenceReadModel:
        resolved = self.resolve_version(version)
        rows = self.fetchall(
            SOURCE_EVIDENCE_SELECT
            + """
            WHERE n.knowledge_version_id = ? AND se.evidence_key = ?
            """,
            (resolved.id, evidence_id),
        )
        if not rows:
            raise KnowledgeNotFoundError(f"Source evidence not found: {evidence_id}")
        if len(rows) > 1:
            raise KnowledgeIntegrityError(f"Duplicate source evidence key: {evidence_id}")
        return source_evidence_from_row(rows[0])

    def list_source_records(
        self,
        source_key: str | None = None,
        record_type: str | None = None,
        cefr_level: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[SourceRecordReadModel]:
        normalized_limit, normalized_offset = self.normalize_pagination(
            limit=limit,
            offset=offset,
        )
        filters: list[str] = []
        params: list[object] = []
        if source_key is not None:
            filters.append("ks.source_key = ?")
            params.append(source_key)
        if record_type is not None:
            filters.append("sr.record_type = ?")
            params.append(record_type)
        if cefr_level is not None:
            filters.append("sr.cefr_level = ?")
            params.append(cefr_level)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        rows = self.fetchall(
            SOURCE_RECORD_SELECT
            + f"""
            {where}
            ORDER BY ks.source_key, sr.external_record_id
            LIMIT ? OFFSET ?
            """,
            (*params, normalized_limit, normalized_offset),
        )
        return [source_record_from_row(row) for row in rows]

    def get_source_record(self, source_record_id: str) -> SourceRecordReadModel:
        rows = self.fetchall(
            SOURCE_RECORD_SELECT
            + """
            WHERE sr.external_record_id = ?
            LIMIT 2
            """,
            (source_record_id,),
        )
        if not rows:
            raise KnowledgeNotFoundError(f"Source record not found: {source_record_id}")
        if len(rows) > 1:
            raise KnowledgeIntegrityError(
                f"Source record id is ambiguous across sources: {source_record_id}",
            )
        return source_record_from_row(rows[0])


def source_evidence_from_row(row: sqlite3.Row) -> SourceEvidenceReadModel:
    return SourceEvidenceReadModel(
        evidence_id=row["evidence_id"],
        skill_id=row["skill_id"],
        source_key=row["source_key"],
        source_record_id=row["source_record_id"],
        record_type=row["record_type"],
        source_cefr_level=row["source_cefr_level"],
        evidence_type=row["evidence_type"],
        confidence=float(row["confidence"]),
        status=row["status"],
        review_status=row["review_status"],
        reason=row["reason"],
        source_text=row["source_text"],
        page_number=row["page_number"],
        row_number=row["row_number"],
    )


def source_record_from_row(row: sqlite3.Row) -> SourceRecordReadModel:
    return SourceRecordReadModel(
        source_record_id=row["source_record_id"],
        source_key=row["source_key"],
        source_name=row["source_name"],
        source_document_title=row["source_document_title"],
        file_name=row["file_name"],
        record_type=row["record_type"],
        cefr_level=row["cefr_level"],
        raw_text=row["raw_text"],
        normalized_text=row["normalized_text"],
        page_number=row["page_number"],
        row_number=row["row_number"],
        sheet_name=row["sheet_name"],
    )
