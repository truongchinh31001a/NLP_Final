from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from knowledge_core.storage.config import resolve_db_path, resolve_schema_path


KNOWLEDGE_TABLES = (
    "knowledge_versions",
    "knowledge_sources",
    "source_documents",
    "source_records",
    "knowledge_nodes",
    "skill_profiles",
    "skill_source_evidence",
    "learning_objectives",
    "skill_learning_objectives",
    "skill_cefr_alignments",
    "skill_relationships",
    "relationship_evidence",
    "assessment_criteria",
    "assessment_evidence_requirements",
    "assessment_failure_signals",
    "assessment_task_types",
    "assessment_evidence",
)

KNOWLEDGE_VIEWS = (
    "v_atomic_skills",
    "v_skill_prerequisites",
    "v_skill_assessment_summary",
)


@contextmanager
def sqlite_connection(db_path: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    resolved = resolve_db_path(db_path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(resolved)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_schema(
    db_path: str | Path | None = None,
    schema_path: str | Path | None = None,
) -> dict[str, int | str]:
    resolved_schema = resolve_schema_path(schema_path)
    schema_sql = resolved_schema.read_text(encoding="utf-8")
    with sqlite_connection(db_path) as connection:
        connection.executescript(schema_sql)
        _ensure_sqlite_knowledge_migrations(connection)
        return {
            "db_path": str(resolve_db_path(db_path)),
            "schema_path": str(resolved_schema),
            "knowledge_tables": count_existing_tables(connection, KNOWLEDGE_TABLES),
            "knowledge_views": count_existing_views(connection, KNOWLEDGE_VIEWS),
        }


def count_existing_tables(
    connection: sqlite3.Connection,
    table_names: tuple[str, ...] = KNOWLEDGE_TABLES,
) -> int:
    return _count_sqlite_objects(connection, table_names, "table")


def count_existing_views(
    connection: sqlite3.Connection,
    view_names: tuple[str, ...] = KNOWLEDGE_VIEWS,
) -> int:
    return _count_sqlite_objects(connection, view_names, "view")


def _count_sqlite_objects(
    connection: sqlite3.Connection,
    names: tuple[str, ...],
    object_type: str,
) -> int:
    placeholders = ",".join("?" for _ in names)
    row = connection.execute(
        f"""
        SELECT COUNT(*) AS count
        FROM sqlite_master
        WHERE type = ? AND name IN ({placeholders})
        """,
        (object_type, *names),
    ).fetchone()
    return int(row["count"])


def _ensure_sqlite_knowledge_migrations(connection: sqlite3.Connection) -> None:
    """Apply additive SQLite migrations for existing local databases."""
    if _table_exists(connection, "skill_source_evidence") and not _column_exists(
        connection,
        "skill_source_evidence",
        "evidence_key",
    ):
        connection.execute("ALTER TABLE skill_source_evidence ADD COLUMN evidence_key TEXT")
    connection.execute("DROP INDEX IF EXISTS uq_skill_source_evidence_key")
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_skill_source_evidence_node_key
        ON skill_source_evidence (knowledge_node_id, evidence_key)
        """,
    )


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def _column_exists(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
) -> bool:
    return any(
        row["name"] == column_name
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    )
