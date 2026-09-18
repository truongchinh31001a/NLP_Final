from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from knowledge_core.sources.efcamdat.parser import (
    inspect_csv_support,
    iter_writing_blocks,
    parse_writing_block,
)

from tests.knowledge_core.sources.efcamdat.fixtures import (
    CSV_FIXTURE,
    MALFORMED_WRITING_BLOCK,
    XML_FIXTURE,
)


class EFCAMDATParserTests(unittest.TestCase):
    def test_iter_writing_blocks_parses_xml_changes_to_common_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "EFCAMDAT_Database.xml"
            path.write_text(XML_FIXTURE, encoding="utf-8")

            blocks = list(iter_writing_blocks(path))

        self.assertEqual(len(blocks), 2)
        first = blocks[0]
        self.assertEqual(first.source_record.source_key, "efcamdat")
        self.assertEqual(first.source_record.record_unit, "writing")
        self.assertEqual(first.source_record.metadata["level"], "6")
        self.assertEqual(len(first.error_instances), 1)
        error = first.error_instances[0]
        self.assertEqual(error.source_native_label.label, "AGV")
        self.assertEqual(error.span.span_kind, "efcamdat_selection_text")
        self.assertTrue(error.span.selection_fingerprint.startswith("sha256:"))
        self.assertEqual(error.correction.correction_type, "replacement")
        dumped = first.source_record.model_dump_json() + error.model_dump_json()
        self.assertNotIn("goes", dumped)
        self.assertNotIn("I go", dumped)

    def test_malformed_writing_block_uses_regex_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "EFCAMDAT_Database.xml"
            block = parse_writing_block(
                MALFORMED_WRITING_BLOCK,
                source_path=path,
                start_line_number=10,
            )

        self.assertEqual(block.parser_status, "regex_fallback")
        self.assertEqual(block.source_record.native_record_id, "3")
        self.assertEqual(len(block.error_instances), 1)
        self.assertEqual(block.error_instances[0].source_native_label.label, "VT")
        self.assertEqual(block.error_instances[0].review_status, "needs_review")

    def test_csv_support_is_processed_in_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "support.csv"
            path.write_text(CSV_FIXTURE, encoding="utf-8")

            summary = inspect_csv_support(path, chunk_size=1)

        self.assertEqual(summary.row_count, 1)
        self.assertEqual(summary.chunk_count, 1)
        self.assertEqual(summary.rows_with_text_change_markup, 1)
        self.assertEqual(summary.unique_writing_id_count, 1)


if __name__ == "__main__":
    unittest.main()

