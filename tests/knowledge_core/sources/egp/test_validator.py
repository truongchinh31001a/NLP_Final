from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from knowledge_core.sources.egp.models import EGPCategoryConfig, EGPConfig, EGPSourceConfig, RawEGPRecord
from knowledge_core.sources.egp.validator import duplicate_key, validate_records


class EGPValidatorTests(unittest.TestCase):
    def test_valid_record_has_no_issues(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_file = Path(temp_dir) / "present_simple.xlsx"
            source_file.write_bytes(b"placeholder")
            record = self._record(source_file=source_file)
            result = validate_records([record], self._config())

        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.warning_count, 0)
        self.assertEqual(result.valid_records, 1)

    def test_invalid_cefr_empty_statement_missing_source_and_bad_hint(self) -> None:
        record = self._record(
            cefr_level="B3",
            can_do_statement="",
            source_file=Path("missing-egp-source.xlsx"),
            canonical_parent_hint="grammar.not_real",
        )

        result = validate_records([record], self._config())
        codes = {issue.code for issue in result.issues}

        self.assertIn("invalid_cefr_level", codes)
        self.assertIn("empty_can_do_statement", codes)
        self.assertIn("missing_source_file", codes)
        self.assertIn("invalid_canonical_parent_hint", codes)
        self.assertGreaterEqual(result.error_count, 4)

    def test_duplicate_records_are_reported_without_dropping(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_file = Path(temp_dir) / "present_simple.xlsx"
            source_file.write_bytes(b"placeholder")
            first = self._record(source_file=source_file, source_row_number=2)
            second = self._record(source_file=source_file, source_row_number=3)

            result = validate_records([first, second], self._config())

        duplicate_issues = [
            issue for issue in result.issues if issue.code == "duplicate_record"
        ]
        self.assertEqual(len(duplicate_issues), 2)
        self.assertEqual(duplicate_issues[0].duplicate_key, duplicate_key(first))
        self.assertEqual(result.total_records, 2)

    def test_duplicate_source_record_ids_are_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_file = Path(temp_dir) / "present_simple.xlsx"
            source_file.write_bytes(b"placeholder")
            first = self._record(
                source_file=source_file,
                source_row_number=2,
                source_record_id="egp_duplicate",
            )
            second = self._record(
                source_file=source_file,
                source_row_number=3,
                source_record_id="egp_duplicate",
            )

            result = validate_records([first, second], self._config())

        self.assertIn("duplicate_source_record_id", {issue.code for issue in result.issues})
        self.assertGreaterEqual(result.error_count, 1)

    def test_expected_source_taxonomy_mismatches_are_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_file = Path(temp_dir) / "present_simple.xlsx"
            source_file.write_bytes(b"placeholder")
            record = self._record(
                source_file=source_file,
                super_category="PAST",
                sub_category="past simple",
            )

            result = validate_records([record], self._config())
            codes = {issue.code for issue in result.issues}

        self.assertIn("expected_super_category_mismatch", codes)
        self.assertIn("expected_sub_category_mismatch", codes)
        self.assertEqual(result.error_count, 0)

    def test_unknown_category_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_file = Path(temp_dir) / "unknown.xlsx"
            source_file.write_bytes(b"placeholder")
            record = self._record(source_file=source_file, category_id="unknown")

            result = validate_records([record], self._config())

        self.assertIn("unknown_category_id", {issue.code for issue in result.issues})
        self.assertEqual(result.error_count, 1)

    def _config(self) -> EGPConfig:
        return EGPConfig(
            source=EGPSourceConfig(),
            categories=[
                EGPCategoryConfig(
                    id="present_simple",
                    query="present simple",
                    expected_super_category="PRESENT",
                    expected_sub_category="present simple",
                    canonical_parent_hint="grammar.tenses.present_simple",
                ),
            ],
        )

    def _record(
        self,
        *,
        source_file: Path,
        category_id: str = "present_simple",
        super_category: str = "PRESENT",
        sub_category: str = "present simple",
        cefr_level: str = "A1",
        can_do_statement: str = "Can use present simple.",
        canonical_parent_hint: str = "grammar.tenses.present_simple",
        source_row_number: int = 2,
        source_record_id: str | None = None,
    ) -> RawEGPRecord:
        return RawEGPRecord(
            source_record_id=source_record_id
            or f"egp_{category_id}_{source_row_number}",
            category_id=category_id,
            super_category=super_category,
            sub_category=sub_category,
            cefr_level=cefr_level,
            can_do_statement=can_do_statement,
            example="I play tennis.",
            source_row_number=source_row_number,
            source_file=str(source_file),
            retrieved_at=datetime(2026, 9, 7, tzinfo=timezone.utc),
            canonical_parent_hint=canonical_parent_hint,
        )


if __name__ == "__main__":
    unittest.main()
