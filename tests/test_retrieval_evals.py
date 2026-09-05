import unittest
from pathlib import Path

from langchain_core.documents import Document

from app.retrieval.hybrid import ReciprocalRankFusion
from app.retrieval.knowledge_loader import knowledge_record_to_document
from scripts.evaluate_retrieval import load_queries, metadata_matches


class RetrievalEvalContractTests(unittest.TestCase):
    def test_retrieval_eval_queries_have_metadata_labels(self) -> None:
        rows = load_queries(Path("data/evaluation/retrieval_eval_queries.csv"))

        self.assertGreaterEqual(len(rows), 30)
        for row in rows:
            self.assertTrue(row["expected_subtopic"])
            self.assertTrue(row["expected_cefr"])
            self.assertTrue(row["expected_source"])
            self.assertTrue(row["expected_chunk_ids"])

    def test_knowledge_loader_derives_cefr_metadata(self) -> None:
        document = knowledge_record_to_document(
            {
                "chunk_id": "chunk",
                "topic_code": "passive_voice",
                "subtopic": "present_simple_passive",
                "skill": "grammar",
                "level": "intermediate",
                "language": "english",
                "content": "Passive voice context.",
                "examples": [],
                "common_mistakes": [],
                "source": "teacher_authored_mvp_notes",
            }
        )

        self.assertEqual(document.metadata["cefr"], "B1")
        self.assertIn("CEFR: B1", document.page_content)

    def test_metadata_match_checks_source_cefr_and_subtopic(self) -> None:
        self.assertTrue(
            metadata_matches(
                topic="passive_voice",
                level="beginner",
                subtopic="present_simple_passive",
                cefr="A1",
                source="teacher_authored_mvp_notes",
                expected={
                    "expected_topic": "passive_voice",
                    "expected_level": "beginner",
                    "expected_subtopic": "present_simple_passive",
                    "expected_cefr": "A1",
                    "expected_source": "teacher_authored_mvp_notes",
                },
            )
        )
        self.assertFalse(
            metadata_matches(
                topic="passive_voice",
                level="beginner",
                subtopic="present_simple_passive",
                cefr="A1",
                source="wrong_source",
                expected={
                    "expected_topic": "passive_voice",
                    "expected_level": "beginner",
                    "expected_subtopic": "present_simple_passive",
                    "expected_cefr": "A1",
                    "expected_source": "teacher_authored_mvp_notes",
                },
            )
        )

    def test_weighted_rrf_can_prefer_sparse_rank(self) -> None:
        dense_first = Document(page_content="dense", metadata={"chunk_id": "dense"})
        sparse_first = Document(page_content="sparse", metadata={"chunk_id": "sparse"})
        fused = ReciprocalRankFusion(rank_constant=1).fuse(
            [[dense_first, sparse_first], [sparse_first, dense_first]],
            weights=[0.1, 2.0],
        )

        self.assertEqual(fused[0].metadata["chunk_id"], "sparse")


if __name__ == "__main__":
    unittest.main()
