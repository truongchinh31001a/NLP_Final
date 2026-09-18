from __future__ import annotations

import sqlite3

from knowledge_core.repository.base import BaseKnowledgeRepository, VersionSelector
from knowledge_core.repository.models import (
    CorpusErrorStatisticReadModel,
    ErrorSkillMappingReadModel,
)


class CorpusErrorRepository(BaseKnowledgeRepository):
    def list_statistics(
        self,
        statistic_type: str | None = None,
        source_key: str | None = None,
        skill_id: str | None = None,
        normalized_category: str | None = None,
        mapping_status: str | None = None,
        version: VersionSelector = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[CorpusErrorStatisticReadModel]:
        resolved = self.resolve_version(version)
        normalized_limit, normalized_offset = self.normalize_pagination(
            limit=limit,
            offset=offset,
        )
        filters = ["ces.knowledge_version_id = ?"]
        params: list[object] = [resolved.id]
        if statistic_type is not None:
            filters.append("ces.statistic_type = ?")
            params.append(statistic_type)
        if source_key is not None:
            filters.append("ks.source_key = ?")
            params.append(source_key)
        if skill_id is not None:
            filters.append("n.canonical_id = ?")
            params.append(skill_id)
        if normalized_category is not None:
            filters.append("ces.normalized_category = ?")
            params.append(normalized_category)
        if mapping_status is not None:
            filters.append("ces.mapping_status = ?")
            params.append(mapping_status)
        rows = self.fetchall(
            """
            SELECT
                ces.statistic_key,
                ces.statistic_type,
                ks.source_key,
                n.canonical_id AS skill_id,
                ces.normalized_category,
                ces.normalized_subtype,
                ces.mapping_status,
                ces.source_label,
                ces.count
            FROM corpus_error_statistics ces
            LEFT JOIN knowledge_sources ks ON ks.id = ces.knowledge_source_id
            LEFT JOIN knowledge_nodes n ON n.id = ces.knowledge_node_id
            """
            + f"""
            WHERE {' AND '.join(filters)}
            ORDER BY ces.statistic_type, ks.source_key, n.canonical_id, ces.statistic_key
            LIMIT ? OFFSET ?
            """,
            (*params, normalized_limit, normalized_offset),
        )
        return [corpus_error_statistic_from_row(row) for row in rows]

    def list_skill_mappings(
        self,
        skill_id: str | None = None,
        source_key: str | None = None,
        status: str | None = None,
        review_status: str | None = None,
        version: VersionSelector = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ErrorSkillMappingReadModel]:
        resolved = self.resolve_version(version)
        normalized_limit, normalized_offset = self.normalize_pagination(
            limit=limit,
            offset=offset,
        )
        filters = ["csm.knowledge_version_id = ?"]
        params: list[object] = [resolved.id]
        if skill_id is not None:
            filters.append("n.canonical_id = ?")
            params.append(skill_id)
        if source_key is not None:
            filters.append("csm.source_key = ?")
            params.append(source_key)
        if status is not None:
            filters.append("csm.status = ?")
            params.append(status)
        if review_status is not None:
            filters.append("csm.review_status = ?")
            params.append(review_status)
        rows = self.fetchall(
            """
            SELECT
                csm.mapping_key,
                n.canonical_id AS skill_id,
                csm.source_key,
                csm.normalized_error_id,
                csm.error_instance_id,
                csm.external_source_record_id,
                csm.status,
                csm.confidence,
                csm.review_status,
                csm.reason
            FROM corpus_error_skill_mappings csm
            JOIN knowledge_nodes n ON n.id = csm.knowledge_node_id
            """
            + f"""
            WHERE {' AND '.join(filters)}
            ORDER BY csm.confidence DESC, csm.mapping_key
            LIMIT ? OFFSET ?
            """,
            (*params, normalized_limit, normalized_offset),
        )
        return [error_skill_mapping_from_row(row) for row in rows]


def corpus_error_statistic_from_row(row: sqlite3.Row) -> CorpusErrorStatisticReadModel:
    return CorpusErrorStatisticReadModel(
        statistic_key=row["statistic_key"],
        statistic_type=row["statistic_type"],
        source_key=row["source_key"],
        skill_id=row["skill_id"],
        normalized_category=row["normalized_category"],
        normalized_subtype=row["normalized_subtype"],
        mapping_status=row["mapping_status"],
        source_label=row["source_label"],
        count=int(row["count"]),
    )


def error_skill_mapping_from_row(row: sqlite3.Row) -> ErrorSkillMappingReadModel:
    return ErrorSkillMappingReadModel(
        mapping_id=row["mapping_key"],
        skill_id=row["skill_id"],
        source_key=row["source_key"],
        normalized_error_id=row["normalized_error_id"],
        error_instance_id=row["error_instance_id"],
        source_record_id=row["external_source_record_id"],
        status=row["status"],
        confidence=float(row["confidence"]),
        review_status=row["review_status"],
        reason=row["reason"],
    )

