from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from knowledge_core.repository.exceptions import (
    KnowledgeIntegrityError,
    KnowledgeRepositoryError,
    KnowledgeVersionNotFoundError,
)
from knowledge_core.repository.models import KnowledgeVersionReadModel
from knowledge_core.storage.config import DEFAULT_VERSION_NAME


VersionSelector = str | int | KnowledgeVersionReadModel | None


class BaseKnowledgeRepository:
    DEFAULT_LIMIT = 100
    MAX_LIMIT = 1000

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def resolve_version(self, version: VersionSelector = None) -> KnowledgeVersionReadModel:
        if isinstance(version, KnowledgeVersionReadModel):
            return version
        if isinstance(version, int):
            rows = self.fetchall(
                """
                SELECT id, version_name, description, taxonomy_hash, status, created_at, activated_at
                FROM knowledge_versions
                WHERE id = ?
                """,
                (version,),
            )
        elif isinstance(version, str):
            rows = self.fetchall(
                """
                SELECT id, version_name, description, taxonomy_hash, status, created_at, activated_at
                FROM knowledge_versions
                WHERE version_name = ?
                """,
                (version,),
            )
        else:
            rows = self.fetchall(
                """
                SELECT id, version_name, description, taxonomy_hash, status, created_at, activated_at
                FROM knowledge_versions
                WHERE status = 'active'
                ORDER BY id
                """,
            )

        if not rows:
            label = DEFAULT_VERSION_NAME if version is None else str(version)
            raise KnowledgeVersionNotFoundError(f"Knowledge version not found: {label}")
        if len(rows) > 1:
            names = ", ".join(row["version_name"] for row in rows)
            raise KnowledgeIntegrityError(f"Multiple active knowledge versions found: {names}")
        return version_from_row(rows[0])

    def fetchone(
        self,
        sql: str,
        params: tuple[Any, ...] = (),
    ) -> sqlite3.Row | None:
        try:
            return self.connection.execute(sql, params).fetchone()
        except sqlite3.DatabaseError as exc:
            raise KnowledgeRepositoryError(f"Knowledge repository query failed: {exc}") from exc

    def fetchall(
        self,
        sql: str,
        params: tuple[Any, ...] = (),
    ) -> list[sqlite3.Row]:
        try:
            return list(self.connection.execute(sql, params).fetchall())
        except sqlite3.DatabaseError as exc:
            raise KnowledgeRepositoryError(f"Knowledge repository query failed: {exc}") from exc

    def normalize_pagination(
        self,
        *,
        limit: int | None,
        offset: int | None,
    ) -> tuple[int, int]:
        normalized_limit = self.DEFAULT_LIMIT if limit is None else limit
        normalized_offset = 0 if offset is None else offset
        if normalized_limit < 1:
            raise ValueError("limit must be greater than zero")
        if normalized_offset < 0:
            raise ValueError("offset must not be negative")
        return min(normalized_limit, self.MAX_LIMIT), normalized_offset


def version_from_row(row: sqlite3.Row) -> KnowledgeVersionReadModel:
    return KnowledgeVersionReadModel(
        id=int(row["id"]),
        version_name=row["version_name"],
        description=row["description"],
        taxonomy_hash=row["taxonomy_hash"],
        status=row["status"],
        created_at=row["created_at"],
        activated_at=row["activated_at"],
    )


def placeholders(values: list[Any] | tuple[Any, ...]) -> str:
    return ",".join("?" for _ in values)
