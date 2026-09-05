from pathlib import Path
from typing import Protocol

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore

from app.config import AppConfig
from app.retrieval.hybrid import ReciprocalRankFusion
from app.retrieval.reranker import HeuristicReranker
from app.retrieval.embeddings import build_embedding_model
from app.retrieval.knowledge_loader import load_knowledge_documents
from app.retrieval.sparse import SparseKeywordRetriever
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
        self.embeddings = build_embedding_model(config)
        self._documents = load_knowledge_documents(self.config.knowledge_chunks_path)
        self.sparse_retriever = SparseKeywordRetriever(self._documents)
        self.fusion = ReciprocalRankFusion()
        self.reranker = HeuristicReranker()
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
        retrieval_limit = max(limit * 8, 20)
        mode = self.config.retrieval_mode.strip().lower()

        if mode == "sparse":
            documents = self.sparse_retriever.search(
                query,
                topic=topic,
                level=level,
                subtopic=subtopic,
                limit=retrieval_limit,
            )
        else:
            dense_documents = self._safe_dense_search(query, retrieval_limit)
            if mode == "dense" and not dense_documents:
                dense_documents = self._dense_search(query, retrieval_limit)
            if mode == "dense":
                documents = dense_documents
            else:
                sparse_documents = self.sparse_retriever.search(
                    query,
                    topic=topic,
                    level=level,
                    subtopic=subtopic,
                    limit=retrieval_limit,
                )
                documents = self.fusion.fuse(
                    [dense_documents, sparse_documents],
                    weights=[0.45, 0.55],
                )

        if self.config.reranker_enabled:
            documents = self.reranker.rerank(
                documents,
                query=query,
                topic=topic,
                level=level,
                subtopic=subtopic,
            )

        prioritized = self._prioritize_documents(documents, topic, level, subtopic)
        return [self._document_to_chunk(doc) for doc in prioritized[:limit]]

    def _safe_dense_search(self, query: str, limit: int) -> list[Document]:
        try:
            return self._dense_search(query, limit)
        except Exception:
            return []

    def _dense_search(self, query: str, limit: int) -> list[Document]:
        retriever = self._vector_store.as_retriever(
            search_kwargs={"k": limit}
        )
        return retriever.invoke(query)

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
        return self._documents

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
