from __future__ import annotations

import sqlite3

from knowledge_core.repository.base import BaseKnowledgeRepository, VersionSelector
from knowledge_core.repository.exceptions import KnowledgeIntegrityError, KnowledgeNotFoundError
from knowledge_core.repository.models import (
    AssessmentCriterionReadModel,
    AssessmentEvidenceReadModel,
)


CRITERION_SELECT = """
SELECT
    ac.id AS criterion_db_id,
    ac.criterion_key,
    n.canonical_id AS canonical_skill_id,
    ac.criterion_type,
    ac.name,
    ac.description,
    ac.observable_behavior,
    ac.cefr_level,
    ac.recommended_threshold,
    ac.recommended_min_items,
    ac.threshold_source,
    ac.confidence,
    ac.status,
    ac.review_status
FROM assessment_criteria ac
JOIN knowledge_nodes n ON n.id = ac.knowledge_node_id
"""


class AssessmentRepository(BaseKnowledgeRepository):
    def list_all(
        self,
        criterion_type: str | None = None,
        cefr_level: str | None = None,
        status: str | None = None,
        review_status: str | None = None,
        version: VersionSelector = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[AssessmentCriterionReadModel]:
        resolved = self.resolve_version(version)
        normalized_limit, normalized_offset = self.normalize_pagination(
            limit=limit,
            offset=offset,
        )
        filters = ["ac.knowledge_version_id = ?"]
        params: list[object] = [resolved.id]
        if criterion_type is not None:
            filters.append("ac.criterion_type = ?")
            params.append(criterion_type)
        if cefr_level is not None:
            filters.append("ac.cefr_level = ?")
            params.append(cefr_level)
        if status is not None:
            filters.append("ac.status = ?")
            params.append(status)
        if review_status is not None:
            filters.append("ac.review_status = ?")
            params.append(review_status)
        rows = self.fetchall(
            CRITERION_SELECT
            + f"""
            WHERE {' AND '.join(filters)}
            ORDER BY ac.cefr_level, ac.criterion_type, ac.criterion_key
            LIMIT ? OFFSET ?
            """,
            (*params, normalized_limit, normalized_offset),
        )
        return self._criteria_from_rows(rows)

    def list_for_skill(
        self,
        skill_id: str,
        criterion_type: str | None = None,
        version: VersionSelector = None,
    ) -> list[AssessmentCriterionReadModel]:
        resolved = self.resolve_version(version)
        filters = ["ac.knowledge_version_id = ?", "n.canonical_id = ?"]
        params: list[object] = [resolved.id, skill_id]
        if criterion_type is not None:
            filters.append("ac.criterion_type = ?")
            params.append(criterion_type)
        rows = self.fetchall(
            CRITERION_SELECT
            + f"""
            WHERE {' AND '.join(filters)}
            ORDER BY ac.criterion_type, ac.criterion_key
            """,
            tuple(params),
        )
        return self._criteria_from_rows(rows)

    def get_by_criterion_key(
        self,
        criterion_key: str,
        version: VersionSelector = None,
    ) -> AssessmentCriterionReadModel:
        return self.get_full_criterion(criterion_key, version)

    def get_full_criterion(
        self,
        criterion_key: str,
        version: VersionSelector = None,
    ) -> AssessmentCriterionReadModel:
        resolved = self.resolve_version(version)
        rows = self.fetchall(
            CRITERION_SELECT
            + """
            WHERE ac.knowledge_version_id = ? AND ac.criterion_key = ?
            """,
            (resolved.id, criterion_key),
        )
        if not rows:
            raise KnowledgeNotFoundError(f"Assessment criterion not found: {criterion_key}")
        if len(rows) > 1:
            raise KnowledgeIntegrityError(f"Duplicate criterion key: {criterion_key}")
        return self._criteria_from_rows(rows)[0]

    def list_by_task_type(
        self,
        task_type: str,
        version: VersionSelector = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[AssessmentCriterionReadModel]:
        resolved = self.resolve_version(version)
        normalized_limit, normalized_offset = self.normalize_pagination(
            limit=limit,
            offset=offset,
        )
        rows = self.fetchall(
            CRITERION_SELECT
            + """
            JOIN assessment_task_types att
                ON att.assessment_criterion_id = ac.id
            WHERE ac.knowledge_version_id = ? AND att.task_type = ?
            ORDER BY ac.cefr_level, ac.criterion_key
            LIMIT ? OFFSET ?
            """,
            (resolved.id, task_type, normalized_limit, normalized_offset),
        )
        return self._criteria_from_rows(rows)

    def list_by_cefr_level(
        self,
        cefr_level: str,
        version: VersionSelector = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[AssessmentCriterionReadModel]:
        resolved = self.resolve_version(version)
        normalized_limit, normalized_offset = self.normalize_pagination(
            limit=limit,
            offset=offset,
        )
        rows = self.fetchall(
            CRITERION_SELECT
            + """
            WHERE ac.knowledge_version_id = ? AND ac.cefr_level = ?
            ORDER BY ac.criterion_type, ac.criterion_key
            LIMIT ? OFFSET ?
            """,
            (resolved.id, cefr_level, normalized_limit, normalized_offset),
        )
        return self._criteria_from_rows(rows)

    def _criteria_from_rows(
        self,
        rows: list[sqlite3.Row],
    ) -> list[AssessmentCriterionReadModel]:
        if not rows:
            return []
        criterion_ids = [int(row["criterion_db_id"]) for row in rows]
        requirements = self._child_texts(
            "assessment_evidence_requirements",
            "requirement_text",
            criterion_ids,
        )
        failure_signals = self._child_texts(
            "assessment_failure_signals",
            "signal_text",
            criterion_ids,
        )
        task_types = self._task_types(criterion_ids)
        evidence = self._assessment_evidence(criterion_ids)
        return [
            criterion_from_row(
                row,
                requirements=tuple(requirements.get(int(row["criterion_db_id"]), ())),
                failure_signals=tuple(
                    failure_signals.get(int(row["criterion_db_id"]), ()),
                ),
                task_types=tuple(task_types.get(int(row["criterion_db_id"]), ())),
                evidence=tuple(evidence.get(int(row["criterion_db_id"]), ())),
            )
            for row in rows
        ]

    def _child_texts(
        self,
        table_name: str,
        text_column: str,
        criterion_ids: list[int],
    ) -> dict[int, list[str]]:
        rows = self.fetchall(
            f"""
            SELECT assessment_criterion_id, {text_column} AS text_value
            FROM {table_name}
            WHERE assessment_criterion_id IN ({','.join('?' for _ in criterion_ids)})
            ORDER BY assessment_criterion_id, position
            """,
            tuple(criterion_ids),
        )
        grouped: dict[int, list[str]] = {}
        for row in rows:
            grouped.setdefault(int(row["assessment_criterion_id"]), []).append(
                row["text_value"],
            )
        return grouped

    def _task_types(self, criterion_ids: list[int]) -> dict[int, list[str]]:
        rows = self.fetchall(
            f"""
            SELECT assessment_criterion_id, task_type
            FROM assessment_task_types
            WHERE assessment_criterion_id IN ({','.join('?' for _ in criterion_ids)})
            ORDER BY assessment_criterion_id, task_type
            """,
            tuple(criterion_ids),
        )
        grouped: dict[int, list[str]] = {}
        for row in rows:
            grouped.setdefault(int(row["assessment_criterion_id"]), []).append(
                row["task_type"],
            )
        return grouped

    def _assessment_evidence(
        self,
        criterion_ids: list[int],
    ) -> dict[int, list[AssessmentEvidenceReadModel]]:
        rows = self.fetchall(
            f"""
            SELECT
                ae.assessment_criterion_id,
                ac.criterion_key,
                ae.evidence_type,
                sr.external_record_id AS source_record_id,
                ae.external_reference_id,
                ks.source_key,
                sr.record_type,
                sr.normalized_text AS source_text,
                sr.page_number,
                sr.row_number,
                ae.note
            FROM assessment_evidence ae
            JOIN assessment_criteria ac ON ac.id = ae.assessment_criterion_id
            LEFT JOIN source_records sr ON sr.id = ae.source_record_id
            LEFT JOIN knowledge_sources ks ON ks.id = sr.knowledge_source_id
            WHERE ae.assessment_criterion_id IN ({','.join('?' for _ in criterion_ids)})
            ORDER BY ae.assessment_criterion_id, ae.evidence_type, source_record_id
            """,
            tuple(criterion_ids),
        )
        grouped: dict[int, list[AssessmentEvidenceReadModel]] = {}
        for row in rows:
            grouped.setdefault(int(row["assessment_criterion_id"]), []).append(
                assessment_evidence_from_row(row),
            )
        return grouped


def criterion_from_row(
    row: sqlite3.Row,
    *,
    requirements: tuple[str, ...],
    failure_signals: tuple[str, ...],
    task_types: tuple[str, ...],
    evidence: tuple[AssessmentEvidenceReadModel, ...],
) -> AssessmentCriterionReadModel:
    return AssessmentCriterionReadModel(
        criterion_key=row["criterion_key"],
        canonical_skill_id=row["canonical_skill_id"],
        criterion_type=row["criterion_type"],
        name=row["name"],
        description=row["description"],
        observable_behavior=row["observable_behavior"],
        cefr_level=row["cefr_level"],
        recommended_threshold=row["recommended_threshold"],
        recommended_min_items=row["recommended_min_items"],
        threshold_source=row["threshold_source"],
        confidence=float(row["confidence"]),
        status=row["status"],
        review_status=row["review_status"],
        evidence_requirements=requirements,
        failure_signals=failure_signals,
        task_types=task_types,
        evidence=evidence,
    )


def assessment_evidence_from_row(row: sqlite3.Row) -> AssessmentEvidenceReadModel:
    return AssessmentEvidenceReadModel(
        criterion_key=row["criterion_key"],
        evidence_type=row["evidence_type"],
        source_record_id=row["source_record_id"],
        external_reference_id=row["external_reference_id"],
        source_key=row["source_key"],
        record_type=row["record_type"],
        source_text=row["source_text"],
        page_number=row["page_number"],
        row_number=row["row_number"],
        note=row["note"],
    )
