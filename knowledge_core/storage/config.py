from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.config import AppConfig


DEFAULT_VERSION_NAME = "knowledge_core_v1"


@dataclass(frozen=True, slots=True)
class KnowledgeStorageConfig:
    db_path: Path = field(default_factory=lambda: Path(AppConfig().sqlite_db_path))
    schema_path: Path = field(
        default_factory=lambda: Path("app/persistence/schema.sql"),
    )
    version_name: str = DEFAULT_VERSION_NAME
    version_description: str = "Knowledge Core Grammar V1 loaded from validated artifacts."


def resolve_db_path(db_path: str | Path | None = None) -> Path:
    return Path(db_path) if db_path is not None else Path(AppConfig().sqlite_db_path)


def resolve_schema_path(schema_path: str | Path | None = None) -> Path:
    return Path(schema_path) if schema_path is not None else Path("app/persistence/schema.sql")
