from __future__ import annotations

import sqlite3

from knowledge_core.repository.base import BaseKnowledgeRepository, VersionSelector
from knowledge_core.repository.exceptions import KnowledgeIntegrityError, KnowledgeNotFoundError
from knowledge_core.repository.models import (
    MisconceptionEvidenceReadModel,
    MisconceptionReadModel,
)


MISCONCEPTION_SELECT = """
SELECT
    m.id AS misconception_db_id,
    m.misconception_key,
    n.canonical_id AS canonical_skill_id,
    m.name,
    m.description,
    m.error_category,
    m.error_subtype,
    m.expected_pattern,
    m.observed_pattern,
    m.diagnostic_rule,
    m.source_evidence_count,
    m.frequency,
    m.frequency_scope,
    m.severity,
    m.confidence,
    m.status,
    m.review_status,
    m.reason
FROM misconceptions m
JOIN knowledge_nodes n ON n.id = m.knowledge_node_id
"""


class MisconceptionRepository(BaseKnowledgeRepository):
    def list_for_skill(
        self,
        skill_id: str,
        status: str | None = None,
        review_status: str | None = None,
        include_evidence: bool = False,
        version: VersionSelector = None,
    ) -> list[MisconceptionReadModel]:
        resolved = self.resolve_version(version)
        filters = ["m.knowledge_version_id = ?", "n.canonical_id = ?"]
        params: list[object] = [resolved.id, skill_id]
        if status is not None:
            filters.append("m.status = ?")
            params.append(status)
        if review_status is not None:
            filters.append("m.review_status = ?")
            params.append(review_status)
        rows = self.fetchall(
            MISCONCEPTION_SELECT
            + f"""
            WHERE {' AND '.join(filters)}
            ORDER BY m.status, m.confidence DESC, m.misconception_key
            """,
            tuple(params),
        )
        return self._misconceptions_from_rows(
            rows,
            include_evidence=include_evidence,
            version=resolved,
        )

    def list_all(
        self,
        status: str | None = None,
        review_status: str | None = None,
        version: VersionSelector = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[MisconceptionReadModel]:
        resolved = self.resolve_version(version)
        normalized_limit, normalized_offset = self.normalize_pagination(
            limit=limit,
            offset=offset,
        )
        filters = ["m.knowledge_version_id = ?"]
        params: list[object] = [resolved.id]
        if status is not None:
            filters.append("m.status = ?")
            params.append(status)
        if review_status is not None:
            filters.append("m.review_status = ?")
            params.append(review_status)
        rows = self.fetchall(
            MISCONCEPTION_SELECT
            + f"""
            WHERE {' AND '.join(filters)}
            ORDER BY n.canonical_id, m.status, m.misconception_key
            LIMIT ? OFFSET ?
            """,
            (*params, normalized_limit, normalized_offset),
        )
        return self._misconceptions_from_rows(
            rows,
            include_evidence=False,
            version=resolved,
        )

    def get_misconception(
        self,
        misconception_id: str,
        version: VersionSelector = None,
    ) -> MisconceptionReadModel:
        resolved = self.resolve_version(version)
        rows = self.fetchall(
            MISCONCEPTION_SELECT
            + """
            WHERE m.knowledge_version_id = ? AND m.misconception_key = ?
            """,
            (resolved.id, misconception_id),
        )
        if not rows:
            raise KnowledgeNotFoundError(f"Misconception not found: {misconception_id}")
        if len(rows) > 1:
            raise KnowledgeIntegrityError(f"Duplicate misconception key: {misconception_id}")
        return self._misconceptions_from_rows(
            rows,
            include_evidence=True,
            version=resolved,
        )[0]

    def list_evidence(
        self,
        misconception_id: str,
        version: VersionSelector = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[MisconceptionEvidenceReadModel]:
        resolved = self.resolve_version(version)
        normalized_limit, normalized_offset = self.normalize_pagination(
            limit=limit,
            offset=offset,
        )
        rows = self.fetchall(
            """
            SELECT
                m.misconception_key,
                csm.mapping_key AS error_skill_mapping_id,
                me.normalized_error_id,
                me.error_instance_id,
                me.external_source_record_id,
                me.source_key,
                me.source_label,
                me.proficiency_label,
                me.task_id,
                me.split,
                me.mapping_confidence
            FROM misconception_evidence me
            JOIN misconceptions m ON m.id = me.misconception_id
            LEFT JOIN corpus_error_skill_mappings csm
                ON csm.id = me.error_skill_mapping_id
            WHERE m.knowledge_version_id = ? AND m.misconception_key = ?
            ORDER BY me.source_key, me.error_instance_id
            LIMIT ? OFFSET ?
            """,
            (resolved.id, misconception_id, normalized_limit, normalized_offset),
        )
        return [misconception_evidence_from_row(row) for row in rows]

    def _misconceptions_from_rows(
        self,
        rows: list[sqlite3.Row],
        *,
        include_evidence: bool,
        version: VersionSelector,
    ) -> list[MisconceptionReadModel]:
        evidence_by_id: dict[str, tuple[MisconceptionEvidenceReadModel, ...]] = {}
        if include_evidence:
            for row in rows:
                key = row["misconception_key"]
                evidence_by_id[key] = tuple(self.list_evidence(key, version=version, limit=1000))
        return [
            misconception_from_row(
                row,
                evidence=evidence_by_id.get(row["misconception_key"], ()),
            )
            for row in rows
        ]


def misconception_from_row(
    row: sqlite3.Row,
    *,
    evidence: tuple[MisconceptionEvidenceReadModel, ...],
) -> MisconceptionReadModel:
    return MisconceptionReadModel(
        misconception_id=row["misconception_key"],
        canonical_skill_id=row["canonical_skill_id"],
        name=row["name"],
        description=row["description"],
        error_category=row["error_category"],
        error_subtype=row["error_subtype"],
        expected_pattern=row["expected_pattern"],
        observed_pattern=row["observed_pattern"],
        diagnostic_rule=row["diagnostic_rule"],
        source_evidence_count=int(row["source_evidence_count"]),
        frequency=float(row["frequency"]),
        frequency_scope=row["frequency_scope"],
        severity=row["severity"],
        confidence=float(row["confidence"]),
        status=row["status"],
        review_status=row["review_status"],
        reason=row["reason"],
        evidence=evidence,
    )


def misconception_evidence_from_row(row: sqlite3.Row) -> MisconceptionEvidenceReadModel:
    return MisconceptionEvidenceReadModel(
        misconception_id=row["misconception_key"],
        error_skill_mapping_id=row["error_skill_mapping_id"],
        normalized_error_id=row["normalized_error_id"],
        error_instance_id=row["error_instance_id"],
        source_record_id=row["external_source_record_id"],
        source_key=row["source_key"],
        source_label=row["source_label"],
        proficiency_label=row["proficiency_label"],
        task_id=row["task_id"],
        split=row["split"],
        mapping_confidence=float(row["mapping_confidence"]),
    )
