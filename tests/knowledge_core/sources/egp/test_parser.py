from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from knowledge_core.sources.egp.models import EGPCategoryConfig
from knowledge_core.sources.egp.parser import EGPParseError, parse_workbook
from tests.egp_workbook_fixtures import write_xlsx


class EGPParserTests(unittest.TestCase):
    def test_parser_tolerates_column_order_and_normalizes_headers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_file = Path(temp_dir) / "present_perfect_simple.xlsx"
            write_xlsx(
                source_file,
                [
                    [
                        "Example",
                        "Can-DoStatement",
                        "Level",
                        "SubCategory",
                        "SuperCategory",
                        "guideword",
                        "Comments",
                    ],
                    [
                        "I have already eaten.",
                        "Can use the present perfect simple with already.",
                        "b1",
                        "present perfect simple",
                        "PAST",
                        "FORM/USE: WITH 'ALREADY'",
                        "Common in affirmative clauses.",
                    ],
                ],
            )
            category = EGPCategoryConfig(
                id="present_perfect_simple",
                query="present perfect simple",
                expected_super_category="PAST",
                expected_sub_category="present perfect simple",
                canonical_parent_hint="grammar.tenses.present_perfect",
            )

            records = parse_workbook(
                source_file,
                category,
                retrieved_at=datetime(2026, 9, 7, tzinfo=timezone.utc),
                source_url="https://englishprofile.org/?menu=egp-online",
            )

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.category_id, "present_perfect_simple")
        self.assertEqual(record.cefr_level, "B1")
        self.assertEqual(record.super_category, "PAST")
        self.assertEqual(record.sub_category, "present perfect simple")
        self.assertEqual(record.feature_type, "FORM/USE")
        self.assertEqual(record.feature_name, "WITH 'ALREADY'")
        self.assertEqual(record.source_row_number, 2)
        self.assertEqual(record.source_url, "https://englishprofile.org/?menu=egp-online")
        self.assertEqual(
            record.raw_payload["Can-DoStatement"],
            "Can use the present perfect simple with already.",
        )

    def test_parser_finds_header_after_blank_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_file = Path(temp_dir) / "past_simple.xlsx"
            write_xlsx(
                source_file,
                [
                    [],
                    ["metadata", None],
                    ["Level", "Can Do Statement"],
                    ["A2", "Can use past simple for finished past time."],
                ],
            )
            category = EGPCategoryConfig(id="past_simple", query="past simple")

            records = parse_workbook(source_file, category)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].source_row_number, 4)
        self.assertEqual(records[0].cefr_level, "A2")

    def test_parser_fails_clearly_without_can_do_column(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_file = Path(temp_dir) / "bad.xlsx"
            write_xlsx(source_file, [["Level", "Example"], ["A1", "Example only"]])
            category = EGPCategoryConfig(id="present_simple", query="present simple")

            with self.assertRaisesRegex(EGPParseError, "Can-DoStatement"):
                parse_workbook(source_file, category)

    def test_parser_reports_empty_xlsx_as_no_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_file = Path(temp_dir) / "empty.xlsx"
            write_xlsx(source_file, [["Level", "Can-DoStatement"]])
            category = EGPCategoryConfig(id="present_simple", query="present simple")

            records = parse_workbook(source_file, category)

        self.assertEqual(records, [])


if __name__ == "__main__":
    unittest.main()
