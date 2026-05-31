from pathlib import Path
from typing import Any, Protocol

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore

from app.config import AppConfig
from app.retrieval.embeddings import KeywordHashEmbeddings
from app.schemas import KnowledgeChunk


class VectorStore(Protocol):
    def search(self, topic: str, level: str, limit: int) -> list[KnowledgeChunk]:
        """Return knowledge chunks that best match the topic and learner level."""


class LangChainVectorStore:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.embeddings = KeywordHashEmbeddings()
        self._seeded = False
        self._vector_store = self._build_store()
        self._seed_documents_if_needed()

    def search(self, topic: str, level: str, limit: int) -> list[KnowledgeChunk]:
        query = f"{topic.replace('_', ' ')} {level}"
        retriever = self._vector_store.as_retriever(
            search_kwargs={"k": max(limit * 3, limit)}
        )
        documents = retriever.invoke(query)
        prioritized = self._prioritize_documents(documents, topic, level)
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
        return [
            Document(
                page_content=(
                    "Passive voice is formed with be plus past participle. "
                    "Use it when the receiver of the action is more important than the doer."
                ),
                metadata={
                    "chunk_id": "grammar-passive-001",
                    "topic": "passive_voice",
                    "level": "beginner",
                    "source": "seed",
                    "category": "grammar",
                },
            ),
            Document(
                page_content=(
                    "Past simple passive uses was or were plus past participle, "
                    "for example: The window was broken yesterday."
                ),
                metadata={
                    "chunk_id": "grammar-passive-002",
                    "topic": "passive_voice",
                    "level": "intermediate",
                    "source": "seed",
                    "category": "grammar",
                },
            ),
            Document(
                page_content=(
                    "Relative clauses give more information about a noun. "
                    "Who is used for people, which for things, and that for both in many cases."
                ),
                metadata={
                    "chunk_id": "grammar-relative-001",
                    "topic": "relative_clause",
                    "level": "beginner",
                    "source": "seed",
                    "category": "grammar",
                },
            ),
            Document(
                page_content=(
                    "Travel vocabulary often includes itinerary, destination, luggage, "
                    "boarding pass, reservation, and accommodation."
                ),
                metadata={
                    "chunk_id": "vocab-travel-001",
                    "topic": "travel_vocabulary",
                    "level": "beginner",
                    "source": "seed",
                    "category": "vocabulary",
                },
            ),
            Document(
                page_content=(
                    "Conditionals describe real or unreal situations. "
                    "Zero conditional describes facts, first conditional describes real future possibilities."
                ),
                metadata={
                    "chunk_id": "grammar-conditional-001",
                    "topic": "conditional_sentence",
                    "level": "beginner",
                    "source": "seed",
                    "category": "grammar",
                },
            ),
        ]

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
    ) -> list[Document]:
        exact_topic_level = [
            doc
            for doc in documents
            if doc.metadata.get("topic") == topic and doc.metadata.get("level") == level
        ]
        exact_topic = [
            doc
            for doc in documents
            if doc.metadata.get("topic") == topic and doc not in exact_topic_level
        ]
        others = [doc for doc in documents if doc not in exact_topic_level + exact_topic]
        return exact_topic_level + exact_topic + others
