import os
from dataclasses import dataclass


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    return float(value)


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class AppConfig:
    app_name: str = "Personalized English Exercise Chatbot"
    default_level: str = "beginner"
    default_difficulty: str = "easy"
    default_num_questions: int = 5
    learning_repository_backend: str = os.getenv(
        "LEARNING_REPOSITORY_BACKEND",
        "sqlite",
    )
    sqlite_db_path: str = os.getenv("SQLITE_DB_PATH", "./data/sqlite/app.db")
    retrieval_top_k: int = 3
    knowledge_chunks_path: str = os.getenv(
        "KNOWLEDGE_CHUNKS_PATH",
        "./data/processed/knowledge_chunks.json",
    )
    seed_exercises_path: str = os.getenv(
        "SEED_EXERCISES_PATH",
        "./data/processed/seed_exercises.json",
    )
    llm_backend: str = os.getenv("LLM_BACKEND", "auto")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_temperature: float = _float_env("OPENAI_TEMPERATURE", 0.2)
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_temperature: float = _float_env("OLLAMA_TEMPERATURE", 0.2)
    generation_llm_timeout_seconds: float = _float_env(
        "GENERATION_LLM_TIMEOUT_SECONDS",
        20.0,
    )
    seed_first_generation: bool = _bool_env("SEED_FIRST_GENERATION", False)
    review_llm_timeout_seconds: float = _float_env("REVIEW_LLM_TIMEOUT_SECONDS", 8.0)
    onboarding_llm_timeout_seconds: float = _float_env(
        "ONBOARDING_LLM_TIMEOUT_SECONDS",
        6.0,
    )
    practice_intent_llm_timeout_seconds: float = _float_env(
        "PRACTICE_INTENT_LLM_TIMEOUT_SECONDS",
        5.0,
    )
    vector_store_backend: str = os.getenv("VECTOR_STORE_BACKEND", "inmemory")
    chroma_collection_name: str = "english_exercise_kb"
    chroma_persist_directory: str = "./data/vector_store/chroma"
