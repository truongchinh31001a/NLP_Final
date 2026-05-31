import hashlib
import re

from langchain_core.embeddings import Embeddings


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
