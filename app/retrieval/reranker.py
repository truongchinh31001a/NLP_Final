import re

from langchain_core.documents import Document


TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


class HeuristicReranker:
    """Metadata-aware reranker used when no cross-encoder is configured."""

    def rerank(
        self,
        documents: list[Document],
        *,
        query: str,
        topic: str,
        level: str,
        subtopic: str | None = None,
    ) -> list[Document]:
        query_tokens = set(self._tokens(query))
        scored = [
            (
                self._score(
                    document=document,
                    query_tokens=query_tokens,
                    topic=topic,
                    level=level,
                    subtopic=subtopic,
                ),
                rank,
                document,
            )
            for rank, document in enumerate(documents)
        ]
        scored.sort(key=lambda item: (item[0], -item[1]), reverse=True)
        return [document for _score, _rank, document in scored]

    def _score(
        self,
        *,
        document: Document,
        query_tokens: set[str],
        topic: str,
        level: str,
        subtopic: str | None,
    ) -> float:
        metadata = document.metadata
        document_tokens = set(
            self._tokens(
                " ".join(
                    [
                        document.page_content,
                        str(metadata.get("topic", "")),
                        str(metadata.get("subtopic", "")),
                    ]
                )
            )
        )
        overlap = len(query_tokens.intersection(document_tokens))
        score = float(overlap)
        if metadata.get("topic") == topic:
            score += 8.0
        if metadata.get("level") == level:
            score += 2.0
        else:
            score -= self._level_distance(str(metadata.get("level", "")), level)
        if subtopic and self._subtopic_matches(metadata.get("subtopic"), subtopic):
            score += 5.0
        return score

    def _tokens(self, text: str) -> list[str]:
        return TOKEN_RE.findall(text.lower().replace("-", "_"))

    def _level_distance(self, actual: str, expected: str) -> int:
        order = {"beginner": 0, "intermediate": 1, "advanced": 2}
        return abs(order.get(actual, 1) - order.get(expected, 1))

    def _subtopic_matches(self, actual: object, expected: str) -> bool:
        if not isinstance(actual, str):
            return False
        return actual == expected or actual.startswith(expected) or expected.startswith(actual)

