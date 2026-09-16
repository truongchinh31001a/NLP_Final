from __future__ import annotations

import sqlite3

from knowledge_core.repository.base import BaseKnowledgeRepository, VersionSelector
from knowledge_core.repository.exceptions import KnowledgeIntegrityError, KnowledgeNotFoundError
from knowledge_core.repository.models import LearningObjectiveReadModel


OBJECTIVE_SELECT = """
SELECT
    lo.objective_key,
    lo.cefr_level,
    lo.domain,
    lo.scale_name,
    lo.objective_text,
    lo.status,
    slo.alignment_type,
    slo.confidence AS alignment_confidence,
    slo.review_status,
    slo.reason,
    n.canonical_id AS skill_id,
    sr.external_record_id AS source_record_id
FROM learning_objectives lo
LEFT JOIN skill_learning_objectives slo ON slo.learning_objective_id = lo.id
LEFT JOIN knowledge_nodes n ON n.id = slo.knowledge_node_id
LEFT JOIN source_records sr ON sr.id = lo.source_record_id
"""


class LearningObjectiveRepository(BaseKnowledgeRepository):
    def list_all(
        self,
        domain: str | None = None,
        cefr_level: str | None = None,
        status: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        version: VersionSelector = None,
    ) -> list[LearningObjectiveReadModel]:
        resolved = self.resolve_version(version)
        normalized_limit, normalized_offset = self.normalize_pagination(
            limit=limit,
            offset=offset,
        )
        filters = ["lo.knowledge_version_id = ?"]
        params: list[object] = [resolved.id]
        if domain is not None:
            filters.append("lo.domain = ?")
            params.append(domain)
        if cefr_level is not None:
            filters.append("lo.cefr_level = ?")
            params.append(cefr_level)
        if status is not None:
            filters.append("lo.status = ?")
            params.append(status)
        rows = self.fetchall(
            """
            SELECT
                lo.objective_key,
                lo.cefr_level,
                lo.domain,
                lo.scale_name,
                lo.objective_text,
                lo.status,
                NULL AS alignment_type,
                NULL AS alignment_confidence,
                NULL AS review_status,
                NULL AS reason,
                NULL AS skill_id,
                sr.external_record_id AS source_record_id
            FROM learning_objectives lo
            LEFT JOIN source_records sr ON sr.id = lo.source_record_id
            """
            + f"""
            WHERE {' AND '.join(filters)}
            ORDER BY lo.cefr_level, lo.domain, lo.objective_key
            LIMIT ? OFFSET ?
            """,
            (*params, normalized_limit, normalized_offset),
        )
        return [objective_from_row(row) for row in rows]

    def list_for_skill(
        self,
        skill_id: str,
        alignment_type: str | None = None,
        cefr_level: str | None = None,
        version: VersionSelector = None,
    ) -> list[LearningObjectiveReadModel]:
        resolved = self.resolve_version(version)
        filters = ["lo.knowledge_version_id = ?", "n.canonical_id = ?"]
        params: list[object] = [resolved.id, skill_id]
        if alignment_type is not None:
            filters.append("slo.alignment_type = ?")
            params.append(alignment_type)
        if cefr_level is not None:
            filters.append("lo.cefr_level = ?")
            params.append(cefr_level)
        rows = self.fetchall(
            OBJECTIVE_SELECT
            + f"""
            WHERE {' AND '.join(filters)}
            ORDER BY lo.cefr_level, slo.alignment_type, lo.objective_key
            """,
            tuple(params),
        )
        return [objective_from_row(row) for row in rows]

    def get_by_objective_key(
        self,
        objective_key: str,
        version: VersionSelector = None,
    ) -> LearningObjectiveReadModel:
        resolved = self.resolve_version(version)
        rows = self.fetchall(
            """
            SELECT
                lo.objective_key,
                lo.cefr_level,
                lo.domain,
                lo.scale_name,
                lo.objective_text,
                lo.status,
                NULL AS alignment_type,
                NULL AS alignment_confidence,
                NULL AS review_status,
                NULL AS reason,
                NULL AS skill_id,
                sr.external_record_id AS source_record_id
            FROM learning_objectives lo
            LEFT JOIN source_records sr ON sr.id = lo.source_record_id
            WHERE lo.knowledge_version_id = ? AND lo.objective_key = ?
            """,
            (resolved.id, objective_key),
        )
        if not rows:
            raise KnowledgeNotFoundError(f"Learning objective not found: {objective_key}")
        if len(rows) > 1:
            raise KnowledgeIntegrityError(f"Duplicate objective key: {objective_key}")
        return objective_from_row(rows[0])

    def list_by_cefr_level(
        self,
        cefr_level: str,
        domain: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        version: VersionSelector = None,
    ) -> list[LearningObjectiveReadModel]:
        resolved = self.resolve_version(version)
        normalized_limit, normalized_offset = self.normalize_pagination(
            limit=limit,
            offset=offset,
        )
        filters = ["lo.knowledge_version_id = ?", "lo.cefr_level = ?"]
        params: list[object] = [resolved.id, cefr_level]
        if domain is not None:
            filters.append("lo.domain = ?")
            params.append(domain)
        rows = self.fetchall(
            """
            SELECT
                lo.objective_key,
                lo.cefr_level,
                lo.domain,
                lo.scale_name,
                lo.objective_text,
                lo.status,
                NULL AS alignment_type,
                NULL AS alignment_confidence,
                NULL AS review_status,
                NULL AS reason,
                NULL AS skill_id,
                sr.external_record_id AS source_record_id
            FROM learning_objectives lo
            LEFT JOIN source_records sr ON sr.id = lo.source_record_id
            """
            + f"""
            WHERE {' AND '.join(filters)}
            ORDER BY lo.domain, lo.scale_name, lo.objective_key
            LIMIT ? OFFSET ?
            """,
            (*params, normalized_limit, normalized_offset),
        )
        return [objective_from_row(row) for row in rows]

    def list_unaligned_objectives(
        self,
        version: VersionSelector = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[LearningObjectiveReadModel]:
        resolved = self.resolve_version(version)
        normalized_limit, normalized_offset = self.normalize_pagination(
            limit=limit,
            offset=offset,
        )
        rows = self.fetchall(
            """
            SELECT
                lo.objective_key,
                lo.cefr_level,
                lo.domain,
                lo.scale_name,
                lo.objective_text,
                lo.status,
                NULL AS alignment_type,
                NULL AS alignment_confidence,
                NULL AS review_status,
                NULL AS reason,
                NULL AS skill_id,
                sr.external_record_id AS source_record_id
            FROM learning_objectives lo
            LEFT JOIN source_records sr ON sr.id = lo.source_record_id
            WHERE lo.knowledge_version_id = ?
              AND NOT EXISTS (
                  SELECT 1
                  FROM skill_learning_objectives slo
                  WHERE slo.learning_objective_id = lo.id
              )
            ORDER BY lo.cefr_level, lo.domain, lo.objective_key
            LIMIT ? OFFSET ?
            """,
            (resolved.id, normalized_limit, normalized_offset),
        )
        return [objective_from_row(row) for row in rows]


def objective_from_row(row: sqlite3.Row) -> LearningObjectiveReadModel:
    return LearningObjectiveReadModel(
        objective_key=row["objective_key"],
        cefr_level=row["cefr_level"],
        domain=row["domain"],
        scale_name=row["scale_name"],
        objective_text=row["objective_text"],
        status=row["status"],
        alignment_type=row["alignment_type"],
        alignment_confidence=(
            float(row["alignment_confidence"])
            if row["alignment_confidence"] is not None
            else None
        ),
        review_status=row["review_status"],
        skill_id=row["skill_id"],
        source_record_id=row["source_record_id"],
        reason=row["reason"],
    )
