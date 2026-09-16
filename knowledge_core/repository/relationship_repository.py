from __future__ import annotations

import sqlite3
from collections import deque
from typing import Sequence

from knowledge_core.relationships.models import BIDIRECTIONAL_RELATION_TYPES
from knowledge_core.repository.base import (
    BaseKnowledgeRepository,
    VersionSelector,
    placeholders,
)
from knowledge_core.repository.exceptions import KnowledgeIntegrityError, KnowledgeNotFoundError
from knowledge_core.repository.models import (
    RelationshipEvidenceReadModel,
    RelationshipReadModel,
)


RELATIONSHIP_SELECT = """
SELECT
    sr.relationship_key AS relationship_id,
    source_node.canonical_id AS source_skill_id,
    target_node.canonical_id AS target_skill_id,
    sr.relation_type,
    sr.dependency_strength,
    sr.confidence,
    sr.status,
    sr.review_status,
    sr.reason,
    sr.bidirectional
FROM skill_relationships sr
JOIN knowledge_nodes source_node ON source_node.id = sr.source_node_id
JOIN knowledge_nodes target_node ON target_node.id = sr.target_node_id
"""


class RelationshipRepository(BaseKnowledgeRepository):
    def list_all(
        self,
        relation_type: str | None = None,
        status: str | None = None,
        review_status: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        version: VersionSelector = None,
    ) -> list[RelationshipReadModel]:
        resolved = self.resolve_version(version)
        normalized_limit, normalized_offset = self.normalize_pagination(
            limit=limit,
            offset=offset,
        )
        filters = ["sr.knowledge_version_id = ?"]
        params: list[object] = [resolved.id]
        if relation_type is not None:
            filters.append("sr.relation_type = ?")
            params.append(relation_type)
        if status is not None:
            filters.append("sr.status = ?")
            params.append(status)
        if review_status is not None:
            filters.append("sr.review_status = ?")
            params.append(review_status)
        rows = self.fetchall(
            RELATIONSHIP_SELECT
            + f"""
            WHERE {' AND '.join(filters)}
            ORDER BY sr.relation_type, sr.relationship_key
            LIMIT ? OFFSET ?
            """,
            (*params, normalized_limit, normalized_offset),
        )
        return [relationship_from_row(row) for row in rows]

    def list_outgoing(
        self,
        skill_id: str,
        relation_type: str | None = None,
        version: VersionSelector = None,
    ) -> list[RelationshipReadModel]:
        resolved = self.resolve_version(version)
        return self._list_outgoing_for_version(skill_id, relation_type, resolved.id)

    def list_incoming(
        self,
        skill_id: str,
        relation_type: str | None = None,
        version: VersionSelector = None,
    ) -> list[RelationshipReadModel]:
        resolved = self.resolve_version(version)
        return self._list_incoming_for_version(skill_id, relation_type, resolved.id)

    def list_between(
        self,
        source_skill_id: str,
        target_skill_id: str,
        version: VersionSelector = None,
    ) -> list[RelationshipReadModel]:
        resolved = self.resolve_version(version)
        rows = self.fetchall(
            RELATIONSHIP_SELECT
            + """
            WHERE sr.knowledge_version_id = ?
              AND source_node.canonical_id = ?
              AND target_node.canonical_id = ?
            ORDER BY sr.relation_type, sr.relationship_key
            """,
            (resolved.id, source_skill_id, target_skill_id),
        )
        return [relationship_from_row(row) for row in rows]

    def list_related(
        self,
        skill_id: str,
        relation_types: Sequence[str] | None = None,
        version: VersionSelector = None,
    ) -> list[RelationshipReadModel]:
        resolved = self.resolve_version(version)
        selected_types = tuple(relation_types or sorted(BIDIRECTIONAL_RELATION_TYPES))
        if not selected_types:
            return []
        rows = self.fetchall(
            RELATIONSHIP_SELECT
            + f"""
            WHERE sr.knowledge_version_id = ?
              AND sr.relation_type IN ({placeholders(selected_types)})
              AND (source_node.canonical_id = ? OR target_node.canonical_id = ?)
            ORDER BY sr.relation_type, sr.relationship_key
            """,
            (resolved.id, *selected_types, skill_id, skill_id),
        )
        related: list[RelationshipReadModel] = []
        for row in rows:
            relationship = relationship_from_row(row)
            other_skill_id = (
                relationship.target_skill_id
                if relationship.source_skill_id == skill_id
                else relationship.source_skill_id
            )
            related.append(
                RelationshipReadModel(
                    relationship_id=relationship.relationship_id,
                    source_skill_id=relationship.source_skill_id,
                    target_skill_id=relationship.target_skill_id,
                    relation_type=relationship.relation_type,
                    dependency_strength=relationship.dependency_strength,
                    confidence=relationship.confidence,
                    status=relationship.status,
                    review_status=relationship.review_status,
                    reason=relationship.reason,
                    bidirectional=relationship.bidirectional,
                    other_skill_id=other_skill_id,
                ),
            )
        return related

    def get_relationship(
        self,
        relationship_id: str,
        version: VersionSelector = None,
    ) -> RelationshipReadModel:
        resolved = self.resolve_version(version)
        rows = self.fetchall(
            RELATIONSHIP_SELECT
            + """
            WHERE sr.knowledge_version_id = ? AND sr.relationship_key = ?
            """,
            (resolved.id, relationship_id),
        )
        if not rows:
            raise KnowledgeNotFoundError(f"Relationship not found: {relationship_id}")
        if len(rows) > 1:
            raise KnowledgeIntegrityError(f"Duplicate relationship key: {relationship_id}")
        return relationship_from_row(rows[0])

    def list_relationship_evidence(
        self,
        relationship_id: str,
        version: VersionSelector = None,
    ) -> list[RelationshipEvidenceReadModel]:
        resolved = self.resolve_version(version)
        rows = self.fetchall(
            """
            SELECT
                rel.relationship_key AS relationship_id,
                re.evidence_type,
                sr.external_record_id AS source_record_id,
                re.external_reference_id,
                ks.source_key,
                sr.record_type,
                sr.normalized_text AS source_text,
                sr.page_number,
                sr.row_number,
                re.note
            FROM relationship_evidence re
            JOIN skill_relationships rel ON rel.id = re.relationship_id
            LEFT JOIN source_records sr ON sr.id = re.source_record_id
            LEFT JOIN knowledge_sources ks ON ks.id = sr.knowledge_source_id
            WHERE rel.knowledge_version_id = ? AND rel.relationship_key = ?
            ORDER BY re.evidence_type, source_record_id, re.external_reference_id
            """,
            (resolved.id, relationship_id),
        )
        if not rows:
            self.get_relationship(relationship_id, resolved)
        return [relationship_evidence_from_row(row) for row in rows]

    def list_direct_prerequisites(
        self,
        skill_id: str,
        version: VersionSelector = None,
    ) -> list[RelationshipReadModel]:
        return self.list_incoming(skill_id, relation_type="prerequisite_of", version=version)

    def list_direct_unlocks(
        self,
        skill_id: str,
        version: VersionSelector = None,
    ) -> list[RelationshipReadModel]:
        return self.list_outgoing(skill_id, relation_type="prerequisite_of", version=version)

    def list_transitive_prerequisites(
        self,
        skill_id: str,
        version: VersionSelector = None,
    ) -> list[RelationshipReadModel]:
        resolved = self.resolve_version(version)
        return self._traverse_prerequisites(skill_id, resolved.id, incoming=True)

    def list_transitive_unlocks(
        self,
        skill_id: str,
        version: VersionSelector = None,
    ) -> list[RelationshipReadModel]:
        resolved = self.resolve_version(version)
        return self._traverse_prerequisites(skill_id, resolved.id, incoming=False)

    def _list_outgoing_for_version(
        self,
        skill_id: str,
        relation_type: str | None,
        version_id: int,
    ) -> list[RelationshipReadModel]:
        filters = ["sr.knowledge_version_id = ?", "source_node.canonical_id = ?"]
        params: list[object] = [version_id, skill_id]
        if relation_type is not None:
            filters.append("sr.relation_type = ?")
            params.append(relation_type)
        rows = self.fetchall(
            RELATIONSHIP_SELECT
            + f"""
            WHERE {' AND '.join(filters)}
            ORDER BY sr.relation_type, sr.relationship_key
            """,
            tuple(params),
        )
        return [relationship_from_row(row) for row in rows]

    def _list_incoming_for_version(
        self,
        skill_id: str,
        relation_type: str | None,
        version_id: int,
    ) -> list[RelationshipReadModel]:
        filters = ["sr.knowledge_version_id = ?", "target_node.canonical_id = ?"]
        params: list[object] = [version_id, skill_id]
        if relation_type is not None:
            filters.append("sr.relation_type = ?")
            params.append(relation_type)
        rows = self.fetchall(
            RELATIONSHIP_SELECT
            + f"""
            WHERE {' AND '.join(filters)}
            ORDER BY sr.relation_type, sr.relationship_key
            """,
            tuple(params),
        )
        return [relationship_from_row(row) for row in rows]

    def _traverse_prerequisites(
        self,
        skill_id: str,
        version_id: int,
        *,
        incoming: bool,
    ) -> list[RelationshipReadModel]:
        frontier: deque[str] = deque([skill_id])
        visited_skills: set[str] = {skill_id}
        relationships_by_id: dict[str, RelationshipReadModel] = {}

        while frontier:
            current_skill_id = frontier.popleft()
            relationships = (
                self._list_incoming_for_version(
                    current_skill_id,
                    "prerequisite_of",
                    version_id,
                )
                if incoming
                else self._list_outgoing_for_version(
                    current_skill_id,
                    "prerequisite_of",
                    version_id,
                )
            )
            for relationship in relationships:
                relationships_by_id.setdefault(relationship.relationship_id, relationship)
                next_skill_id = (
                    relationship.source_skill_id
                    if incoming
                    else relationship.target_skill_id
                )
                if next_skill_id not in visited_skills:
                    visited_skills.add(next_skill_id)
                    frontier.append(next_skill_id)

        return sorted(relationships_by_id.values(), key=lambda item: item.relationship_id)


def relationship_from_row(row: sqlite3.Row) -> RelationshipReadModel:
    return RelationshipReadModel(
        relationship_id=row["relationship_id"],
        source_skill_id=row["source_skill_id"],
        target_skill_id=row["target_skill_id"],
        relation_type=row["relation_type"],
        dependency_strength=row["dependency_strength"],
        confidence=float(row["confidence"]),
        status=row["status"],
        review_status=row["review_status"],
        reason=row["reason"],
        bidirectional=bool(row["bidirectional"]),
    )


def relationship_evidence_from_row(row: sqlite3.Row) -> RelationshipEvidenceReadModel:
    return RelationshipEvidenceReadModel(
        relationship_id=row["relationship_id"],
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
