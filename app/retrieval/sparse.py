import math
import re
from collections import Counter

from langchain_core.documents import Document


TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


class SparseKeywordRetriever:
    """Small BM25-like keyword retriever over local knowledge documents."""

    def __init__(self, documents: list[Document]) -> None:
        self.documents = documents
        self.document_tokens = [self._tokens(self._document_text(doc)) for doc in documents]
        self.document_frequencies = self._document_frequencies(self.document_tokens)
        self.average_length = (
            sum(len(tokens) for tokens in self.document_tokens)
            / max(len(self.document_tokens), 1)
        )

    def search(
        self,
        query: str,
        *,
        topic: str | None = None,
        level: str | None = None,
        subtopic: str | None = None,
        limit: int = 20,
    ) -> list[Document]:
        query_tokens = self._tokens(query)
        scored: list[tuple[float, Document]] = []
        for document, tokens in zip(self.documents, self.document_tokens):
            score = self._bm25_score(query_tokens, tokens)
            score += self._metadata_score(document, topic, level, subtopic)
            if score > 0:
                scored.append((score, document))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [document for _, document in scored[:limit]]

    def _bm25_score(
        self,
        query_tokens: list[str],
        document_tokens: list[str],
    ) -> float:
        if not query_tokens or not document_tokens:
            return 0.0

        counts = Counter(document_tokens)
        document_length = len(document_tokens)
        k1 = 1.5
        b = 0.75
        score = 0.0
        for token in query_tokens:
            term_frequency = counts.get(token, 0)
            if not term_frequency:
                continue
            document_frequency = self.document_frequencies.get(token, 0)
            inverse_document_frequency = math.log(
                1
                + (
                    (len(self.documents) - document_frequency + 0.5)
                    / (document_frequency + 0.5)
                )
            )
            denominator = term_frequency + k1 * (
                1 - b + b * (document_length / max(self.average_length, 1))
            )
            score += inverse_document_frequency * (
                (term_frequency * (k1 + 1)) / denominator
            )
        return score

    def _metadata_score(
        self,
        document: Document,
        topic: str | None,
        level: str | None,
        subtopic: str | None,
    ) -> float:
        metadata = document.metadata
        score = 0.0
        if topic and metadata.get("topic") == topic:
            score += 4.0
        if level and metadata.get("level") == level:
            score += 1.5
        elif level:
            score -= 0.25
        if subtopic and self._subtopic_matches(metadata.get("subtopic"), subtopic):
            score += 4.0
        return score

    def _document_frequencies(
        self,
        documents: list[list[str]],
    ) -> dict[str, int]:
        frequencies: dict[str, int] = {}
        for tokens in documents:
            for token in set(tokens):
                frequencies[token] = frequencies.get(token, 0) + 1
        return frequencies

    def _document_text(self, document: Document) -> str:
        metadata = document.metadata
        return " ".join(
            [
                document.page_content,
                str(metadata.get("topic", "")),
                str(metadata.get("subtopic", "")),
                str(metadata.get("skill", "")),
                str(metadata.get("level", "")),
                str(metadata.get("cefr", "")),
                str(metadata.get("source", "")),
            ]
        )

    def _tokens(self, text: str) -> list[str]:
        normalized = text.lower().replace("-", "_")
        return TOKEN_RE.findall(normalized)

    def _subtopic_matches(self, actual: object, expected: str) -> bool:
        if not isinstance(actual, str):
            return False
        return actual == expected or actual.startswith(expected) or expected.startswith(actual)
