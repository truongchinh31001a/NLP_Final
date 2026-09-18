from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from knowledge_core.sources.clc_fce.parser import (
    build_error_instances,
    build_source_record,
    iter_json_records,
    parse_xml_answer_summaries,
)

from tests.knowledge_core.sources.clc_fce.fixtures import TRAIN_JSONL, TRAIN_XML


class CLCFCEParserTests(unittest.TestCase):
    def test_json_record_builds_source_record_without_raw_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "train.json"
            path.write_text(TRAIN_JSONL, encoding="utf-8")
            line_number, payload = next(iter_json_records(path))

            source_record = build_source_record(
                payload,
                split="train",
                source_path=path,
                line_number=line_number,
                xml_summary=None,
            )

        self.assertEqual(source_record.source_key, "clc_fce")
        self.assertEqual(source_record.record_unit, "answer")
        self.assertEqual(source_record.proficiency_label, "FCE_B2")
        self.assertTrue(source_record.text_fingerprint.startswith("sha256:"))
        dumped = source_record.model_dump_json()
        self.assertNotIn("She go school", dumped)

    def test_json_edits_build_error_instances_with_offsets_and_hashed_correction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "train.json"
            path.write_text(TRAIN_JSONL, encoding="utf-8")
            line_number, payload = next(iter_json_records(path))
            source_record = build_source_record(
                payload,
                split="train",
                source_path=path,
                line_number=line_number,
                xml_summary=None,
            )

            errors = build_error_instances(
                payload,
                split="train",
                source_record=source_record,
                source_path=path,
            )

        self.assertEqual(len(errors), 2)
        self.assertEqual(errors[0].span.start_char, 4)
        self.assertEqual(errors[0].span.end_char, 6)
        self.assertEqual(errors[0].source_native_label.label, "AGV")
        self.assertEqual(errors[1].span.start_char, 7)
        self.assertEqual(errors[1].span.end_char, 7)
        self.assertEqual(errors[1].correction.correction_type, "insertion")
        self.assertEqual(errors[1].review_status, "needs_review")
        self.assertNotIn("goes", errors[0].model_dump_json())

    def test_xml_parser_preserves_nested_error_structure_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "train.xml"
            path.write_text(TRAIN_XML, encoding="utf-8")

            summaries = parse_xml_answer_summaries({"train": path})

        self.assertEqual(len(summaries), 1)
        summary = next(iter(summaries.values()))
        self.assertEqual(summary.error_count, 3)
        self.assertGreaterEqual(summary.nested_error_count, 1)
        self.assertGreaterEqual(summary.max_error_depth, 2)
        labels = [node.label for node in summary.error_nodes]
        self.assertIn("UT", labels)
        self.assertTrue(all(node.correction_fingerprint is None or node.correction_fingerprint.startswith("sha256:") for node in summary.error_nodes))


if __name__ == "__main__":
    unittest.main()

