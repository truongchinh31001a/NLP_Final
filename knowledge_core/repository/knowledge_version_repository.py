from __future__ import annotations

from knowledge_core.repository.base import BaseKnowledgeRepository, version_from_row
from knowledge_core.repository.exceptions import KnowledgeVersionNotFoundError
from knowledge_core.repository.models import KnowledgeVersionReadModel


class KnowledgeVersionRepository(BaseKnowledgeRepository):
    def get_active_version(self) -> KnowledgeVersionReadModel:
        return self.resolve_version(None)

    def get_version(self, version_name: str) -> KnowledgeVersionReadModel:
        return self.resolve_version(version_name)

    def get_version_by_id(self, version_id: int) -> KnowledgeVersionReadModel:
        return self.resolve_version(version_id)

    def list_versions(self) -> list[KnowledgeVersionReadModel]:
        rows = self.fetchall(
            """
            SELECT id, version_name, description, taxonomy_hash, status, created_at, activated_at
            FROM knowledge_versions
            ORDER BY created_at DESC, id DESC
            """,
        )
        return [version_from_row(row) for row in rows]

    def exists(self, version_name: str) -> bool:
        row = self.fetchone(
            "SELECT 1 FROM knowledge_versions WHERE version_name = ?",
            (version_name,),
        )
        return row is not None

    def require_exists(self, version_name: str) -> None:
        if not self.exists(version_name):
            raise KnowledgeVersionNotFoundError(
                f"Knowledge version not found: {version_name}",
            )
