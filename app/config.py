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


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


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
    postgres_database_url: str = os.getenv(
        "POSTGRES_DATABASE_URL",
        os.getenv(
            "DATABASE_URL",
            "postgresql://english_tutor:english_tutor@localhost:5432/english_tutor",
        ),
    )
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
    retrieval_mode: str = os.getenv("RETRIEVAL_MODE", "hybrid")
    reranker_enabled: bool = _bool_env("RERANKER_ENABLED", True)
    embedding_backend: str = os.getenv("EMBEDDING_BACKEND", "keyword_hash")
    pgvector_database_url: str = os.getenv(
        "PGVECTOR_DATABASE_URL",
        os.getenv(
            "POSTGRES_DATABASE_URL",
            "postgresql://english_tutor:english_tutor@localhost:5432/english_tutor",
        ),
    )
    pgvector_table_name: str = os.getenv("PGVECTOR_TABLE_NAME", "rag_documents")
    pgvector_embedding_dimension: int = _int_env(
        "PGVECTOR_EMBEDDING_DIMENSION",
        0,
    )
    openai_embedding_model: str = os.getenv(
        "OPENAI_EMBEDDING_MODEL",
        "text-embedding-3-small",
    )
    ollama_embedding_model: str = os.getenv(
        "OLLAMA_EMBEDDING_MODEL",
        "nomic-embed-text",
    )
    chroma_collection_name: str = os.getenv(
        "CHROMA_COLLECTION_NAME",
        "english_exercise_kb",
    )
    chroma_persist_directory: str = os.getenv(
        "CHROMA_PERSIST_DIRECTORY",
        "./data/vector_store/chroma",
    )
    auth_mode: str = os.getenv("AUTH_MODE", "disabled")
    auth_token_secret: str = os.getenv("AUTH_TOKEN_SECRET", "dev-secret-change-me")
    auth_token_ttl_seconds: int = _int_env("AUTH_TOKEN_TTL_SECONDS", 86400)
    observability_enabled: bool = _bool_env("OBSERVABILITY_ENABLED", True)
    otel_enabled: bool = _bool_env("OTEL_ENABLED", False)
    otel_service_name: str = os.getenv("OTEL_SERVICE_NAME", "adaptive-ai-english-tutor")
    otel_exporter_otlp_endpoint: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
