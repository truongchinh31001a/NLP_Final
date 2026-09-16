from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

from knowledge_core.sources.egp.models import RawEGPRecord
from knowledge_core.sources.egp.normalizer import normalize_record, parse_feature_label
from knowledge_core.sources.egp.reporting import (
    write_records_jsonl,
    write_records_parquet,
)


class EGPNormalizerTests(unittest.TestCase):
    def test_feature_label_parsing(self) -> None:
        feature_type, feature_name = parse_feature_label("FORM/USE: WITH 'ALREADY'")

        self.assertEqual(feature_type, "FORM/USE")
        self.assertEqual(feature_name, "WITH 'ALREADY'")
        self.assertEqual(parse_feature_label("Can use a colon: in an example"), (None, None))

    def test_record_normalization_is_source_only(self) -> None:
        record = RawEGPRecord(
            source=" english_grammar_profile ",
            category_id="present_simple",
            super_category=" present ",
            sub_category=" present simple ",
            cefr_level=" a1 ",
            can_do_statement=" FORM: AUXILIARY DO ",
            source_file="source.xlsx",
            retrieved_at=datetime(2026, 9, 7, tzinfo=timezone.utc),
            example=" ",
            details=" none ",
        )

        normalized = normalize_record(record)

        self.assertEqual(normalized.source, "english_grammar_profile")
        self.assertEqual(normalized.super_category, "PRESENT")
        self.assertEqual(normalized.sub_category, "present simple")
        self.assertEqual(normalized.cefr_level, "A1")
        self.assertEqual(normalized.feature_type, "FORM")
        self.assertEqual(normalized.feature_name, "AUXILIARY DO")
        self.assertIsNone(normalized.example)
        self.assertIsNone(normalized.details)

    def test_output_jsonl_and_parquet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            source_file = output_dir / "source.xlsx"
            source_file.write_bytes(b"placeholder")
            record = RawEGPRecord(
                category_id="present_simple",
                super_category="PRESENT",
                sub_category="present simple",
                cefr_level="A1",
                can_do_statement="Can use present simple.",
                source_file=str(source_file),
                retrieved_at=datetime(2026, 9, 7, tzinfo=timezone.utc),
                raw_payload={"Level": "A1"},
            )

            jsonl_path = write_records_jsonl([record], output_dir / "records.jsonl")
            parquet_path = write_records_parquet([record], output_dir / "records.parquet")

            payload = json.loads(jsonl_path.read_text(encoding="utf-8"))
            table = pq.read_table(parquet_path)

        self.assertEqual(payload["cefr_level"], "A1")
        self.assertEqual(payload["raw_payload"], {"Level": "A1"})
        self.assertEqual(table.num_rows, 1)
        self.assertEqual(table.column("raw_payload").to_pylist(), ['{"Level": "A1"}'])


if __name__ == "__main__":
    unittest.main()
