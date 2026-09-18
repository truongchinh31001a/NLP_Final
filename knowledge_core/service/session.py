from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from knowledge_core.repository.session import open_knowledge_repositories
from knowledge_core.service.service import KnowledgeService


@contextmanager
def open_knowledge_service(
    db_path: str | Path | None = None,
) -> Iterator[KnowledgeService]:
    with open_knowledge_repositories(db_path) as repositories:
        yield KnowledgeService(repositories)
