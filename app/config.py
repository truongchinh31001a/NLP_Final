import os
from dataclasses import dataclass


@dataclass(slots=True)
class AppConfig:
    app_name: str = "Personalized English Exercise Chatbot"
    default_level: str = "beginner"
    default_difficulty: str = "easy"
    default_num_questions: int = 5
    retrieval_top_k: int = 3
    knowledge_chunks_path: str = os.getenv(
        "KNOWLEDGE_CHUNKS_PATH",
        "./data/processed/knowledge_chunks.json",
    )
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_temperature: float = 0.2
    vector_store_backend: str = os.getenv("VECTOR_STORE_BACKEND", "inmemory")
    chroma_collection_name: str = "english_exercise_kb"
    chroma_persist_directory: str = "./data/vector_store/chroma"
