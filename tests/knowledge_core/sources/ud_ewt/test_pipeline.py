from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pyarrow.parquet as pq

from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILLS
from knowledge_core.sources.ud_ewt.processor import run_ud_ewt_ingestion
from knowledge_core.sources.ud_ewt.reporting import build_grammar_evidence_report

from tests.knowledge_core.sources.ud_ewt.fixtures import SAMPLE_CONLLU


class UDEWTPipelineTests(unittest.TestCase):
    def test_run_ingestion_writes_outputs_and_preserves_taxonomy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            root = workspace / "ud"
            root.mkdir()
            for split in ("train", "dev", "test"):
                (root / f"en_ewt-ud-{split}.conllu").write_text(
                    SAMPLE_CONLLU,
                    encoding="utf-8",
                )
            inventory = workspace / "ud_ewt_inspection.json"
            inventory.write_text(
                json.dumps(
                    {
                        "detected_version": "fixture UD EWT",
                        "sentence_counts": {
                            split: {"count": 3}
                            for split in ("train", "dev", "test")
                        },
                        "token_counts": {
                            split: {"count": 15}
                            for split in ("train", "dev", "test")
                        },
                    },
                ),
                encoding="utf-8",
            )

            dataset = run_ud_ewt_ingestion(
                root_dir=root,
                interim_dir=workspace / "interim",
                review_dir=workspace / "review",
                reports_dir=workspace / "reports",
                source_inventory_report=inventory,
            )

            self.assertEqual(dataset.validation.error_count, 0)
            self.assertEqual(len(dataset.sentences), 9)
            self.assertTrue(dataset.validation.taxonomy_unchanged)
            self.assertEqual(len(CANONICAL_GRAMMAR_V1_SKILLS), 43)
            self.assertTrue(dataset.validation.no_cefr_inference_introduced)
            self.assertTrue((workspace / "interim" / "sentences.jsonl").exists())
            self.assertTrue((workspace / "interim" / "tokens.parquet").exists())
            self.assertTrue((workspace / "interim" / "dependencies.parquet").exists())
            self.assertTrue((workspace / "interim" / "morphology.parquet").exists())
            self.assertTrue(
                (workspace / "interim" / "grammar_structural_evidence.jsonl").exists(),
            )
            self.assertTrue(
                (workspace / "review" / "ud_grammar_structural_evidence_review.csv").exists(),
            )
            self.assertTrue((workspace / "reports" / "ingestion_report.json").exists())

            token_table = pq.read_table(workspace / "interim" / "tokens.parquet")
            self.assertEqual(token_table.num_rows, len(dataset.tokens))
            skill_ids = {item.canonical_skill_id for item in dataset.evidence}
            self.assertIn("grammar.passive.be_past_participle", skill_ids)
            self.assertIn("grammar.present_perfect.form", skill_ids)
            self.assertIn("grammar.articles.the_specific_reference", skill_ids)
            self.assertIn("grammar.modality.can_ability", skill_ids)
            report = build_grammar_evidence_report(
                dataset.evidence,
                validation=dataset.validation,
            )
            self.assertGreater(report["candidate_mappings_requiring_review_count"], 0)


if __name__ == "__main__":
    unittest.main()

