from langchain_core.documents import Document


class ReciprocalRankFusion:
    def __init__(self, rank_constant: int = 60) -> None:
        self.rank_constant = rank_constant

    def fuse(
        self,
        ranked_lists: list[list[Document]],
        weights: list[float] | None = None,
    ) -> list[Document]:
        scores: dict[str, float] = {}
        documents_by_id: dict[str, Document] = {}
        resolved_weights = weights or [1.0 for _ranked in ranked_lists]
        for ranked, weight in zip(ranked_lists, resolved_weights):
            for rank, document in enumerate(ranked, start=1):
                document_id = self._document_id(document)
                documents_by_id[document_id] = document
                scores[document_id] = scores.get(document_id, 0.0) + (
                    float(weight) / (self.rank_constant + rank)
                )

        return [
            documents_by_id[document_id]
            for document_id, _score in sorted(
                scores.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        ]

    def _document_id(self, document: Document) -> str:
        return str(document.metadata.get("chunk_id") or id(document))
