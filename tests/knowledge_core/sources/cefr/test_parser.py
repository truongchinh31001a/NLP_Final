from __future__ import annotations

import unittest
from pathlib import Path

from knowledge_core.sources.cefr.config import load_cefr_config
from knowledge_core.sources.cefr.parser import build_descriptor_record
from knowledge_core.sources.cefr.table_parser import parse_descriptor_table_rows


class CEFRParserTests(unittest.TestCase):
    def test_build_descriptor_record_preserves_provenance_and_domain(self) -> None:
        config = load_cefr_config()
        scale = config.scale_by_id()["grammatical_accuracy"]
        table = [
            ["", "Grammatical accuracy"],
            ["A1", "Shows only limited control of a few simple grammatical structures."],
        ]
        descriptors, issues = parse_descriptor_table_rows(
            table,
            page_number=132,
            scale_name=scale.id,
            source_table=scale.name,
        )

        record = build_descriptor_record(
            descriptors[0],
            config=config,
            scale=scale,
            page_number=132,
            table_index=1,
            source_file=Path(config.source.source_file),
        )

        self.assertEqual(issues, [])
        self.assertEqual(record.scale_name, "grammatical_accuracy")
        self.assertEqual(record.domain, "linguistic_competence")
        self.assertEqual(record.subdomain, "grammar")
        self.assertEqual(record.descriptor_type, "linguistic_competence")
        self.assertEqual(record.page_number, 132)
        self.assertEqual(record.raw_payload["row_index"], 1)
        self.assertTrue(record.source_record_id.startswith("cefr_"))


if __name__ == "__main__":
    unittest.main()

