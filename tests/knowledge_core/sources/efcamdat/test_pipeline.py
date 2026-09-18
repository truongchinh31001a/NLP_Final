from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from knowledge_core.sources.efcamdat.processor import run_efcamdat_ingestion

from tests.knowledge_core.sources.efcamdat.fixtures import CSV_FIXTURE, XML_FIXTURE


class EFCAMDATPipelineTests(unittest.TestCase):
    def test_run_ingestion_writes_outputs_without_raw_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            xml_path = workspace / "EFCAMDAT_Database.xml"
            csv_path = workspace / "support.csv"
            xml_path.write_text(XML_FIXTURE, encoding="utf-8")
            csv_path.write_text(CSV_FIXTURE, encoding="utf-8")

            result = run_efcamdat_ingestion(
                xml_path=xml_path,
                csv_path=csv_path,
                interim_dir=workspace / "interim",
                review_dir=workspace / "review",
                reports_dir=workspace / "reports",
            )

            self.assertTrue(result.report["definition_of_done_satisfied"])
            self.assertEqual(result.report["source_record_count"], 2)
            self.assertEqual(result.report["error_instance_count"], 2)
            self.assertTrue((workspace / "interim" / "source_records.jsonl").exists())
            self.assertTrue((workspace / "interim" / "error_instances.jsonl").exists())
            self.assertTrue((workspace / "reports" / "ingestion_report.json").exists())

            source_payload = (workspace / "interim" / "source_records.jsonl").read_text(
                encoding="utf-8",
            )
            error_payload = (workspace / "interim" / "error_instances.jsonl").read_text(
                encoding="utf-8",
            )
            self.assertNotIn("goes", error_payload)
            self.assertNotIn("I go", source_payload)
            report = json.loads(
                (workspace / "reports" / "ingestion_report.json").read_text(encoding="utf-8"),
            )
            self.assertFalse(report["privacy"]["raw_learner_text_emitted"])
            self.assertEqual(report["csv_support"]["row_count"], 1)


if __name__ == "__main__":
    unittest.main()

