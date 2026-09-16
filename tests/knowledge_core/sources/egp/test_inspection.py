from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from knowledge_core.sources.egp.inspection import inspect_source_file
from knowledge_core.sources.egp.models import EGPCategoryConfig
from tests.egp_workbook_fixtures import write_xlsx


class EGPSourceInspectionTests(unittest.TestCase):
    def test_inspection_reports_schema_and_row_quality(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_file = Path(temp_dir) / "present_simple.xlsx"
            write_xlsx(
                source_file,
                [
                    [
                        "id",
                        "SuperCategory",
                        "SubCategory",
                        "Level",
                        "Guideword",
                        "Can-do statement",
                    ],
                    [
                        "one",
                        "PRESENT",
                        "present simple",
                        "A1",
                        "FORM: AFFIRMATIVE",
                        "Can use the affirmative form.",
                    ],
                    [
                        "one",
                        "PRESENT",
                        "present simple",
                        "A1",
                        "FORM: AFFIRMATIVE",
                        "Can use the affirmative form.",
                    ],
                    [],
                    ["bad", "PRESENT", "present simple", "B3", "FORM: BAD", None],
                ],
            )
            category = EGPCategoryConfig(
                id="present_simple",
                query="present simple",
                expected_super_category="PRESENT",
                expected_sub_category="present simple",
            )

            report = inspect_source_file(source_file, category)

        self.assertEqual(report["data_row_count"], 3)
        self.assertEqual(report["empty_rows"], 1)
        self.assertEqual(report["duplicate_row_count"], 1)
        self.assertEqual(report["cefr_distribution"]["A1"], 2)
        self.assertEqual(len(report["malformed_rows"]), 1)


if __name__ == "__main__":
    unittest.main()
