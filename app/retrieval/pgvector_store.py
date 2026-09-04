import re
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from langchain_core.documents import Document
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.config import AppConfig
from app.retrieval.embeddings import build_embedding_model
from app.retrieval.knowledge_loader import load_knowledge_documents
from app.retrieval.reranker import HeuristicReranker
from app.schemas import KnowledgeChunk


IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class PgVectorKnowledgeStore:
    """PostgreSQL + pgvector retrieval backend for production deployments."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.database_url = config.pgvector_database_url
        self.table_name = self._safe_identifier(config.pgvector_table_name)
        self.embeddings = build_embedding_model(config)
        self.documents = load_knowledge_documents(config.knowledge_chunks_path)
        self.reranker = HeuristicReranker()
        self.dimension = (
            config.pgvector_embedding_dimension
            or len(self.embeddings.embed_query("english tutor dimension probe"))
        )
        self._init_db()
        self._seed_documents_if_needed()

    def search(
        self,
        topic: str,
        level: str,
        limit: int,
        subtopic: str | None = None,
    ) -> list[KnowledgeChunk]:
        query = self._query_text(topic, level, subtopic)
        query_vector = self._vector_literal(self.embeddings.embed_query(query))
        retrieval_limit = max(limit * 4, 20)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    chunk_id,
                    topic,
                    level,
                    subtopic,
                    skill,
                    source,
                    content,
                    metadata_json,
                    1 - (embedding <=> %s::vector) AS score
                FROM {self.table_name}
                WHERE topic = %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (query_vector, topic, query_vector, retrieval_limit),
            ).fetchall()

        documents = [self._document_from_row(row) for row in rows]
        if self.config.reranker_enabled:
            documents = self.reranker.rerank(
                documents,
                query=query,
                topic=topic,
                level=level,
                subtopic=subtopic,
            )
        return [
            self._document_to_chunk(document)
            for document in self._prioritize(documents, topic, level, subtopic)[:limit]
        ]

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    chunk_id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    level TEXT NOT NULL,
                    subtopic TEXT,
                    skill TEXT,
                    source TEXT,
                    content TEXT NOT NULL,
                    metadata_json JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    embedding vector({self.dimension}),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            connection.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_topic_level
                ON {self.table_name}(topic, level)
                """
            )
            connection.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_embedding
                ON {self.table_name}
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
                """
            )

    def _seed_documents_if_needed(self) -> None:
        with self._connect() as connection:
            count = connection.execute(
                f"SELECT COUNT(*) AS count FROM {self.table_name}"
            ).fetchone()["count"]
            if count:
                return
            embeddings = self.embeddings.embed_documents(
                [document.page_content for document in self.documents]
            )
            for document, embedding in zip(self.documents, embeddings):
                metadata = dict(document.metadata)
                connection.execute(
                    f"""
                    INSERT INTO {self.table_name} (
                        chunk_id,
                        topic,
                        level,
                        subtopic,
                        skill,
                        source,
                        content,
                        metadata_json,
                        embedding
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                    ON CONFLICT (chunk_id)
                    DO UPDATE SET
                        topic = EXCLUDED.topic,
                        level = EXCLUDED.level,
                        subtopic = EXCLUDED.subtopic,
                        skill = EXCLUDED.skill,
                        source = EXCLUDED.source,
                        content = EXCLUDED.content,
                        metadata_json = EXCLUDED.metadata_json,
                        embedding = EXCLUDED.embedding,
                        updated_at = now()
                    """,
                    (
                        str(metadata.get("chunk_id")),
                        str(metadata.get("topic") or metadata.get("topic_code")),
                        str(metadata.get("level") or "beginner"),
                        metadata.get("subtopic"),
                        metadata.get("skill"),
                        metadata.get("source"),
                        document.page_content,
                        Jsonb(metadata),
                        self._vector_literal(embedding),
                    ),
                )

    @contextmanager
    def _connect(self) -> Iterator[Connection]:
        connection = psycopg.connect(self.database_url, row_factory=dict_row)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _document_from_row(self, row: dict[str, Any]) -> Document:
        metadata = row["metadata_json"] if isinstance(row["metadata_json"], dict) else {}
        merged_metadata = {
            **metadata,
            "chunk_id": row["chunk_id"],
            "topic": row["topic"],
            "level": row["level"],
            "subtopic": row["subtopic"],
            "skill": row["skill"],
            "source": row["source"],
            "pgvector_score": float(row["score"] or 0.0),
        }
        return Document(page_content=row["content"], metadata=merged_metadata)

    def _document_to_chunk(self, document: Document) -> KnowledgeChunk:
        metadata = dict(document.metadata)
        return KnowledgeChunk(
            chunk_id=str(metadata.pop("chunk_id", "unknown-chunk")),
            topic=str(metadata.get("topic", "general")),
            level=str(metadata.get("level", "beginner")),
            content=document.page_content,
            source=str(metadata.get("source", "unknown")),
            metadata=metadata,
        )

    def _prioritize(
        self,
        documents: list[Document],
        topic: str,
        level: str,
        subtopic: str | None,
    ) -> list[Document]:
        exact_subtopic = [
            document
            for document in documents
            if self._subtopic_matches(document.metadata.get("subtopic"), subtopic)
        ]
        exact_level = [
            document
            for document in documents
            if document.metadata.get("topic") == topic
            and document.metadata.get("level") == level
            and document not in exact_subtopic
        ]
        remaining = [
            document
            for document in documents
            if document not in [*exact_subtopic, *exact_level]
        ]
        return exact_subtopic + exact_level + remaining

    def _query_text(
        self,
        topic: str,
        level: str,
        subtopic: str | None,
    ) -> str:
        parts = [topic.replace("_", " "), level]
        if subtopic:
            parts.append(subtopic.replace("_", " "))
        return " ".join(parts)

    def _safe_identifier(self, value: str) -> str:
        if not IDENTIFIER_RE.match(value):
            raise ValueError(f"Invalid PostgreSQL identifier: {value}")
        return value

    def _vector_literal(self, values: list[float]) -> str:
        return "[" + ",".join(f"{float(value):.8f}" for value in values) + "]"

    def _subtopic_matches(self, actual: object, expected: str | None) -> bool:
        if not expected or not isinstance(actual, str):
            return False
        return actual == expected or actual.startswith(expected) or expected.startswith(actual)
