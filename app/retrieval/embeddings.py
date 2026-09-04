import hashlib
import os
import re

from langchain_core.embeddings import Embeddings

from app.config import AppConfig


class KeywordHashEmbeddings(Embeddings):
    """
    Deterministic lightweight embeddings for local development.

    This is not a semantic embedding model, but it lets us exercise LangChain
    retrievers and vector stores before wiring a production embedding provider.
    """

    def __init__(self, size: int = 64) -> None:
        self.size = size

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.size
        tokens = re.findall(r"[a-zA-Z_]+", text.lower())

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], byteorder="big") % self.size
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        return vector


def build_embedding_model(config: AppConfig) -> Embeddings:
    backend = config.embedding_backend.strip().lower()
    if backend in {"keyword_hash", "hash", "fallback", "local"}:
        return KeywordHashEmbeddings()
    if backend == "openai":
        return _build_openai_embeddings(config)
    if backend == "ollama":
        return _build_ollama_embeddings(config)
    if backend == "auto":
        if os.getenv("OPENAI_API_KEY"):
            return _build_openai_embeddings(config)
        return KeywordHashEmbeddings()

    raise ValueError(
        "Unsupported EMBEDDING_BACKEND. Use auto, openai, ollama, or keyword_hash."
    )


def _build_openai_embeddings(config: AppConfig) -> Embeddings:
    try:
        from langchain_openai import OpenAIEmbeddings
    except ImportError as exc:
        raise RuntimeError(
            "EMBEDDING_BACKEND=openai requires the `langchain-openai` package. "
            "Install dependencies with `pip install -r requirements.txt`."
        ) from exc

    return OpenAIEmbeddings(model=config.openai_embedding_model)


def _build_ollama_embeddings(config: AppConfig) -> Embeddings:
    try:
        from langchain_ollama import OllamaEmbeddings
    except ImportError as exc:
        raise RuntimeError(
            "EMBEDDING_BACKEND=ollama requires the `langchain-ollama` package. "
            "Install dependencies with `pip install -r requirements.txt`."
        ) from exc

    return OllamaEmbeddings(
        model=config.ollama_embedding_model,
        base_url=config.ollama_base_url,
    )
