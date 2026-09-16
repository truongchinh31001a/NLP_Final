from __future__ import annotations

import unittest

from knowledge_core.sources.cefr.table_parser import (
    descriptor_availability,
    parse_descriptor_table_rows,
    split_descriptor_cell,
)


class CEFRTableParserTests(unittest.TestCase):
    def test_multiline_cell_splits_independent_descriptors(self) -> None:
        descriptors = split_descriptor_cell(
            "Can understand short texts.\n"
            "Can recognise familiar names and words.\n"
            "provided the text is simple."
        )

        self.assertEqual(
            descriptors,
            [
                "Can understand short texts.",
                "Can recognise familiar names and words. provided the text is simple.",
            ],
        )

    def test_parse_table_inherits_level_from_previous_row(self) -> None:
        table = [
            ["", "Overall reading comprehension"],
            ["B2", "Can understand complex texts."],
            ["", "Can adapt reading speed to different texts."],
        ]

        descriptors, issues = parse_descriptor_table_rows(
            table,
            page_number=54,
            scale_name="overall_reading_comprehension",
            source_table="Overall reading comprehension",
        )

        self.assertEqual(issues, [])
        self.assertEqual([descriptor.cefr_level for descriptor in descriptors], ["B2", "B2"])
        self.assertEqual(descriptors[1].row_index, 2)

    def test_no_descriptor_rows_are_preserved_as_unavailable(self) -> None:
        table = [
            ["", "Reading instructions"],
            ["C2", "No descriptors available; see C1"],
        ]

        descriptors, issues = parse_descriptor_table_rows(
            table,
            page_number=58,
            scale_name="reading_instructions",
            source_table="Reading instructions",
        )

        self.assertEqual(issues, [])
        self.assertEqual(len(descriptors), 1)
        self.assertFalse(descriptors[0].descriptor_available)
        self.assertEqual(descriptors[0].reference_level, "C1")

    def test_invalid_level_is_reported(self) -> None:
        table = [["", "Scale"], ["X1", "Can do a thing."]]

        descriptors, issues = parse_descriptor_table_rows(
            table,
            page_number=1,
            scale_name="scale",
            source_table="Scale",
        )

        self.assertEqual(descriptors, [])
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].code, "invalid_cefr_level")

    def test_descriptor_availability_without_reference(self) -> None:
        available, reference = descriptor_availability("No descriptors available")

        self.assertFalse(available)
        self.assertIsNone(reference)


if __name__ == "__main__":
    unittest.main()

