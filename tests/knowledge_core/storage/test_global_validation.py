from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from knowledge_core.global_validation.report import run_global_validation
from knowledge_core.storage.artifacts import load_storage_artifacts


class KnowledgeCoreGlobalValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.artifacts = load_storage_artifacts()

    def test_global_validation_report_passes_and_gates_postgres_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            result = run_global_validation(
                db_path=workspace / "knowledge_core.db",
                report_path=workspace / "knowledge_core_v1_report.json",
                artifacts=self.artifacts,
                run_postgres_validation=False,
            )

            self.assertEqual(result.report["validation_result"], "pass")
            self.assertEqual(result.report["taxonomy"]["node_count"], 54)
            self.assertEqual(result.report["taxonomy"]["atomic_skill_count"], 43)
            self.assertTrue(result.report["storage"]["idempotency"]["passed"])
            self.assertTrue(result.report["storage"]["reconciliation"]["passed"])
            self.assertTrue(result.report["source_manifest"]["validation_passed"])
            self.assertEqual(result.report["source_manifest"]["source_count"], 6)
            self.assertEqual(
                result.report["postgres_validation"]["status"],
                "not_executed",
            )
            self.assertFalse(result.report["production_claim_allowed"])
            self.assertTrue((workspace / "knowledge_core_v1_report.json").exists())


if __name__ == "__main__":
    unittest.main()
