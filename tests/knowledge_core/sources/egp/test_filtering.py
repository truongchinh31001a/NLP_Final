from __future__ import annotations

import unittest
from datetime import datetime, timezone

from knowledge_core.sources.egp.filtering import partition_v1_category_records
from knowledge_core.sources.egp.models import (
    EGPCategoryConfig,
    EGPConfig,
    RawEGPRecord,
)


class EGPFilteringTests(unittest.TestCase):
    def test_partition_excludes_category_mismatches_and_invalid_rows(self) -> None:
        config = EGPConfig(
            categories=[
                EGPCategoryConfig(
                    id="future_will",
                    query="future simple",
                    expected_super_category="FUTURE",
                    expected_sub_category="future simple (with will and shall)",
                ),
            ],
        )
        included = self._record(
            source_record_id="egp_included",
            sub_category="future simple (with will and shall)",
            can_do_statement="Can use will to make predictions.",
        )
        mismatched = self._record(
            source_record_id="egp_mismatched",
            sub_category="future continuous",
            can_do_statement="Can use future continuous.",
        )
        invalid = self._record(
            source_record_id="egp_invalid",
            sub_category="future simple (with will and shall)",
            can_do_statement="",
        )

        partition = partition_v1_category_records(
            [included, mismatched, invalid],
            config,
        )

        self.assertEqual(
            [record.source_record_id for record in partition.included_records],
            ["egp_included"],
        )
        reasons = {
            exclusion.source_record_id: exclusion.reason_codes
            for exclusion in partition.excluded_records
        }
        self.assertEqual(reasons["egp_mismatched"], ["category_mismatch"])
        self.assertEqual(reasons["egp_invalid"], ["empty_can_do_statement"])

    def _record(
        self,
        *,
        source_record_id: str,
        sub_category: str,
        can_do_statement: str,
    ) -> RawEGPRecord:
        return RawEGPRecord(
            source_record_id=source_record_id,
            category_id="future_will",
            super_category="FUTURE",
            sub_category=sub_category,
            cefr_level="A2",
            feature_type="USE",
            feature_name="PREDICTIONS WITH 'WILL'",
            can_do_statement=can_do_statement,
            source_row_number=2,
            source_file="future_will.xlsx",
            retrieved_at=datetime(2026, 9, 7, tzinfo=timezone.utc),
        )


if __name__ == "__main__":
    unittest.main()
