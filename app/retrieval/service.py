from app.config import AppConfig
from app.retrieval.vector_store import VectorStore
from app.schemas import KnowledgeChunk, PracticePlan


class RetrievalService:
    def __init__(self, config: AppConfig, vector_store: VectorStore) -> None:
        self.config = config
        self.vector_store = vector_store

    def retrieve(self, plan: PracticePlan, learner_level: str) -> list[KnowledgeChunk]:
        return self.vector_store.search(
            topic=plan.topic,
            level=learner_level,
            limit=self.config.retrieval_top_k,
        )
