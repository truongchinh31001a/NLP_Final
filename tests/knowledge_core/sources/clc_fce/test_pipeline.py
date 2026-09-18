from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from knowledge_core.sources.clc_fce.processor import run_clc_fce_ingestion

from tests.knowledge_core.sources.clc_fce.fixtures import TRAIN_JSONL, TRAIN_XML


class CLCFCEPipelineTests(unittest.TestCase):
    def test_run_ingestion_writes_schema_artifacts_and_review_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            raw = workspace / "raw"
            raw.mkdir()
            for split in ("train", "dev", "test", "outliers"):
                (raw / f"{split}(fixture).json").write_text(TRAIN_JSONL, encoding="utf-8")
                (raw / f"{split}(fixture).xml").write_text(
                    TRAIN_XML.replace("<train>", f"<{split}>").replace("</train>", f"</{split}>"),
                    encoding="utf-8",
                )
            inventory = workspace / "clc_fce_inspection.json"
            inventory.write_text(
                json.dumps({"total_answer_records": {"count": 4}}),
                encoding="utf-8",
            )

            result = run_clc_fce_ingestion(
                raw_root=raw,
                interim_dir=workspace / "interim",
                reports_dir=workspace / "reports",
                review_dir=workspace / "review",
                source_inventory_report=inventory,
            )

            self.assertTrue(result.validation.passed)
            self.assertEqual(len(result.parsed.source_records), 4)
            self.assertEqual(len(result.parsed.error_instances), 8)
            self.assertTrue((workspace / "interim" / "source_records.jsonl").exists())
            self.assertTrue((workspace / "interim" / "error_instances.jsonl").exists())
            self.assertTrue((workspace / "reports" / "ingestion_report.json").exists())
            review_path = workspace / "review" / "clc_fce_error_review.csv"
            self.assertTrue(review_path.exists())

            source_jsonl = (workspace / "interim" / "source_records.jsonl").read_text(
                encoding="utf-8",
            )
            errors_jsonl = (workspace / "interim" / "error_instances.jsonl").read_text(
                encoding="utf-8",
            )
            self.assertNotIn("She go school", source_jsonl)
            self.assertNotIn("goes", errors_jsonl)
            report = json.loads((workspace / "reports" / "ingestion_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["source_record_count"], 4)
            self.assertEqual(report["error_instance_count"], 8)
            self.assertFalse(report["privacy"]["raw_learner_text_emitted"])


if __name__ == "__main__":
    unittest.main()

