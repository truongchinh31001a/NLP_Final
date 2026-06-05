from pathlib import Path
from typing import Protocol

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore

from app.config import AppConfig
from app.retrieval.embeddings import KeywordHashEmbeddings
from app.retrieval.knowledge_loader import load_knowledge_documents
from app.schemas import KnowledgeChunk


class VectorStore(Protocol):
    def search(
        self,
        topic: str,
        level: str,
        limit: int,
        subtopic: str | None = None,
    ) -> list[KnowledgeChunk]:
        """Return knowledge chunks that best match the topic and learner level."""


class LangChainVectorStore:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.embeddings = KeywordHashEmbeddings()
        self._seeded = False
        self._vector_store = self._build_store()
        self._seed_documents_if_needed()

    def search(
        self,
        topic: str,
        level: str,
        limit: int,
        subtopic: str | None = None,
    ) -> list[KnowledgeChunk]:
        subtopic_query = f" {subtopic.replace('_', ' ')}" if subtopic else ""
        query = f"{topic.replace('_', ' ')}{subtopic_query} {level}"
        retriever = self._vector_store.as_retriever(
            search_kwargs={"k": max(limit * 10, 50)}
        )
        documents = retriever.invoke(query)
        prioritized = self._prioritize_documents(documents, topic, level, subtopic)
        return [self._document_to_chunk(doc) for doc in prioritized[:limit]]

    def _build_store(self) -> InMemoryVectorStore | Chroma:
        if self.config.vector_store_backend.lower() == "chroma":
            persist_path = Path(self.config.chroma_persist_directory)
            persist_path.mkdir(parents=True, exist_ok=True)
            return Chroma(
                collection_name=self.config.chroma_collection_name,
                embedding_function=self.embeddings,
                persist_directory=str(persist_path),
            )

        return InMemoryVectorStore(embedding=self.embeddings)

    def _seed_documents_if_needed(self) -> None:
        if isinstance(self._vector_store, Chroma):
            existing = self._vector_store.get()
            if existing.get("ids"):
                return
        elif self._seeded:
            return

        self._vector_store.add_documents(self._seed_documents())
        self._seeded = True

    def _seed_documents(self) -> list[Document]:
        return load_knowledge_documents(self.config.knowledge_chunks_path)

    def _document_to_chunk(self, document: Document) -> KnowledgeChunk:
        metadata = dict(document.metadata)
        return KnowledgeChunk(
            chunk_id=metadata.pop("chunk_id", "unknown-chunk"),
            topic=metadata.get("topic", "general"),
            level=metadata.get("level", "beginner"),
            content=document.page_content,
            source=metadata.get("source", "unknown"),
            metadata=metadata,
        )

    def _prioritize_documents(
        self,
        documents: list[Document],
        topic: str,
        level: str,
        subtopic: str | None = None,
    ) -> list[Document]:
        exact_subtopic = [
            doc
            for doc in documents
            if doc.metadata.get("topic") == topic
            and self._subtopic_matches(doc.metadata.get("subtopic"), subtopic)
        ]
        exact_topic_level = [
            doc
            for doc in documents
            if doc.metadata.get("topic") == topic and doc.metadata.get("level") == level
            and doc not in exact_subtopic
        ]
        exact_topic = [
            doc
            for doc in documents
            if doc.metadata.get("topic") == topic
            and doc not in [*exact_subtopic, *exact_topic_level]
        ]
        exact_topic.sort(key=lambda doc: self._level_distance(doc, level))
        others = [
            doc
            for doc in documents
            if doc not in [*exact_subtopic, *exact_topic_level, *exact_topic]
        ]
        return exact_subtopic + exact_topic_level + exact_topic + others

    def _level_distance(self, document: Document, target_level: str) -> int:
        level_order = {
            "beginner": 0,
            "intermediate": 1,
            "advanced": 2,
        }
        document_rank = level_order.get(document.metadata.get("level", ""), 0)
        target_rank = level_order.get(target_level, 0)
        return abs(document_rank - target_rank)

    def _subtopic_matches(self, actual: object, expected: str | None) -> bool:
        if not expected or not isinstance(actual, str):
            return False
        return (
            actual == expected
            or actual.startswith(expected)
            or expected.startswith(actual)
        )
