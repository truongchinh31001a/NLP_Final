from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from knowledge_core.repository.assessment_repository import AssessmentRepository
from knowledge_core.repository.knowledge_node_repository import KnowledgeNodeRepository
from knowledge_core.repository.knowledge_query_repository import KnowledgeQueryRepository
from knowledge_core.repository.knowledge_version_repository import KnowledgeVersionRepository
from knowledge_core.repository.objective_repository import LearningObjectiveRepository
from knowledge_core.repository.relationship_repository import RelationshipRepository
from knowledge_core.repository.source_evidence_repository import SourceEvidenceRepository
from knowledge_core.storage.schema import sqlite_connection


class KnowledgeRepositorySession:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.versions = KnowledgeVersionRepository(connection)
        self.nodes = KnowledgeNodeRepository(connection)
        self.evidence = SourceEvidenceRepository(connection)
        self.objectives = LearningObjectiveRepository(connection)
        self.relationships = RelationshipRepository(connection)
        self.assessments = AssessmentRepository(connection)
        self.queries = KnowledgeQueryRepository(
            nodes=self.nodes,
            evidence=self.evidence,
            objectives=self.objectives,
            relationships=self.relationships,
            assessments=self.assessments,
        )


@contextmanager
def open_knowledge_repositories(
    db_path: str | Path | None = None,
) -> Iterator[KnowledgeRepositorySession]:
    with sqlite_connection(db_path) as connection:
        yield KnowledgeRepositorySession(connection)
