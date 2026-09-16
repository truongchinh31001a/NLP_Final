from __future__ import annotations

import sqlite3

from knowledge_core.repository.base import BaseKnowledgeRepository, VersionSelector
from knowledge_core.repository.exceptions import KnowledgeNotFoundError
from knowledge_core.repository.models import KnowledgeNodeReadModel, SkillProfileReadModel


NODE_SELECT = """
SELECT
    n.id,
    n.canonical_id,
    n.node_type,
    n.domain,
    n.name,
    n.description,
    parent.canonical_id AS parent_canonical_id,
    n.is_atomic,
    n.is_active,
    kv.version_name AS knowledge_version
FROM knowledge_nodes n
JOIN knowledge_versions kv ON kv.id = n.knowledge_version_id
LEFT JOIN knowledge_nodes parent ON parent.id = n.parent_node_id
"""


class KnowledgeNodeRepository(BaseKnowledgeRepository):
    def get_by_canonical_id(
        self,
        canonical_id: str,
        version: VersionSelector = None,
    ) -> KnowledgeNodeReadModel:
        resolved = self.resolve_version(version)
        rows = self.fetchall(
            NODE_SELECT
            + """
            WHERE n.knowledge_version_id = ? AND n.canonical_id = ?
            """,
            (resolved.id, canonical_id),
        )
        if not rows:
            raise KnowledgeNotFoundError(f"Knowledge node not found: {canonical_id}")
        return node_from_row(rows[0])

    def get_by_id(self, node_id: int) -> KnowledgeNodeReadModel:
        row = self.fetchone(NODE_SELECT + " WHERE n.id = ?", (node_id,))
        if row is None:
            raise KnowledgeNotFoundError(f"Knowledge node not found: {node_id}")
        return node_from_row(row)

    def list_atomic_skills(
        self,
        version: VersionSelector = None,
        domain: str | None = None,
    ) -> list[KnowledgeNodeReadModel]:
        resolved = self.resolve_version(version)
        filters = ["n.knowledge_version_id = ?", "n.is_atomic = 1", "n.is_active = 1"]
        params: list[object] = [resolved.id]
        if domain is not None:
            filters.append("n.domain = ?")
            params.append(domain)
        rows = self.fetchall(
            NODE_SELECT
            + f"""
            WHERE {' AND '.join(filters)}
            ORDER BY n.canonical_id
            """,
            tuple(params),
        )
        return [node_from_row(row) for row in rows]

    def list_children(
        self,
        canonical_id: str,
        version: VersionSelector = None,
    ) -> list[KnowledgeNodeReadModel]:
        resolved = self.resolve_version(version)
        parent = self.get_by_canonical_id(canonical_id, resolved)
        rows = self.fetchall(
            NODE_SELECT
            + """
            WHERE n.knowledge_version_id = ? AND n.parent_node_id = ?
            ORDER BY n.canonical_id
            """,
            (resolved.id, parent.id),
        )
        return [node_from_row(row) for row in rows]

    def get_parent(
        self,
        canonical_id: str,
        version: VersionSelector = None,
    ) -> KnowledgeNodeReadModel | None:
        resolved = self.resolve_version(version)
        node = self.get_by_canonical_id(canonical_id, resolved)
        if node.parent_canonical_id is None:
            return None
        return self.get_by_canonical_id(node.parent_canonical_id, resolved)

    def list_ancestors(
        self,
        canonical_id: str,
        version: VersionSelector = None,
    ) -> list[KnowledgeNodeReadModel]:
        resolved = self.resolve_version(version)
        node = self.get_by_canonical_id(canonical_id, resolved)
        rows = self.fetchall(
            """
            WITH RECURSIVE ancestors(id, depth) AS (
                SELECT parent.id, 1
                FROM knowledge_nodes child
                JOIN knowledge_nodes parent ON parent.id = child.parent_node_id
                WHERE child.id = ? AND parent.knowledge_version_id = ?

                UNION ALL

                SELECT parent.id, ancestors.depth + 1
                FROM ancestors
                JOIN knowledge_nodes current_node ON current_node.id = ancestors.id
                JOIN knowledge_nodes parent ON parent.id = current_node.parent_node_id
                WHERE parent.knowledge_version_id = ?
            )
            """
            + NODE_SELECT
            + """
            JOIN ancestors ON ancestors.id = n.id
            ORDER BY ancestors.depth
            """,
            (node.id, resolved.id, resolved.id),
        )
        return [node_from_row(row) for row in rows]

    def list_descendants(
        self,
        canonical_id: str,
        version: VersionSelector = None,
        atomic_only: bool = False,
    ) -> list[KnowledgeNodeReadModel]:
        resolved = self.resolve_version(version)
        node = self.get_by_canonical_id(canonical_id, resolved)
        atomic_filter = "AND n.is_atomic = 1" if atomic_only else ""
        rows = self.fetchall(
            """
            WITH RECURSIVE descendants(id, depth) AS (
                SELECT child.id, 1
                FROM knowledge_nodes child
                WHERE child.parent_node_id = ? AND child.knowledge_version_id = ?

                UNION ALL

                SELECT child.id, descendants.depth + 1
                FROM descendants
                JOIN knowledge_nodes child ON child.parent_node_id = descendants.id
                WHERE child.knowledge_version_id = ?
            )
            """
            + NODE_SELECT
            + f"""
            JOIN descendants ON descendants.id = n.id
            WHERE 1 = 1 {atomic_filter}
            ORDER BY descendants.depth, n.canonical_id
            """,
            (node.id, resolved.id, resolved.id),
        )
        return [node_from_row(row) for row in rows]

    def get_skill_profile(
        self,
        canonical_id: str,
        version: VersionSelector = None,
    ) -> SkillProfileReadModel:
        resolved = self.resolve_version(version)
        row = self.fetchone(
            """
            SELECT
                n.canonical_id,
                sp.cefr_min_level,
                sp.cefr_primary_level,
                sp.evidence_status,
                sp.alignment_confidence,
                sp.notes
            FROM skill_profiles sp
            JOIN knowledge_nodes n ON n.id = sp.knowledge_node_id
            WHERE n.knowledge_version_id = ? AND n.canonical_id = ?
            """,
            (resolved.id, canonical_id),
        )
        if row is None:
            raise KnowledgeNotFoundError(f"Skill profile not found: {canonical_id}")
        return SkillProfileReadModel(
            canonical_id=row["canonical_id"],
            cefr_min_level=row["cefr_min_level"],
            cefr_primary_level=row["cefr_primary_level"],
            evidence_status=row["evidence_status"],
            alignment_confidence=row["alignment_confidence"],
            notes=row["notes"],
        )


def node_from_row(row: sqlite3.Row) -> KnowledgeNodeReadModel:
    return KnowledgeNodeReadModel(
        id=int(row["id"]),
        canonical_id=row["canonical_id"],
        node_type=row["node_type"],
        domain=row["domain"],
        name=row["name"],
        description=row["description"],
        parent_canonical_id=row["parent_canonical_id"],
        is_atomic=bool(row["is_atomic"]),
        is_active=bool(row["is_active"]),
        knowledge_version=row["knowledge_version"],
    )
