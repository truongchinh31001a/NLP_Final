from __future__ import annotations

import unittest
from datetime import datetime, timezone

from knowledge_core.mapping.egp.mapper import create_mappings
from knowledge_core.mapping.egp.models import EGPCanonicalMapping
from knowledge_core.mapping.egp.validator import validate_mappings
from knowledge_core.sources.egp.models import RawEGPRecord


class EGPMappingValidatorTests(unittest.TestCase):
    def test_valid_mappings_have_no_errors(self) -> None:
        records = [self._record()]
        mappings = create_mappings(records)

        result = validate_mappings(records, mappings)

        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.total_records, 1)
        self.assertEqual(result.total_mappings, 1)

    def test_invalid_canonical_skill_is_error(self) -> None:
        records = [self._record()]
        mapping = self._mapping(canonical_skill="grammar.not.real")

        result = validate_mappings(records, [mapping])

        self.assertIn("invalid_canonical_skill", {issue.code for issue in result.issues})
        self.assertEqual(result.error_count, 1)

    def test_every_source_record_must_have_exactly_one_mapping(self) -> None:
        records = [self._record(source_record_id="egp_one")]

        result = validate_mappings(records, [])

        self.assertIn("source_record_mapping_count", {issue.code for issue in result.issues})
        self.assertEqual(result.error_count, 1)

    def test_duplicate_mapping_id_is_error(self) -> None:
        records = [
            self._record(source_record_id="egp_one"),
            self._record(source_record_id="egp_two"),
        ]
        first = self._mapping(source_record_id="egp_one", mapping_id="duplicate")
        second = self._mapping(source_record_id="egp_two", mapping_id="duplicate")

        result = validate_mappings(records, [first, second])

        self.assertIn("duplicate_mapping_id", {issue.code for issue in result.issues})
        self.assertEqual(result.error_count, 1)

    def test_unmapped_cannot_have_canonical_skill(self) -> None:
        records = [self._record()]
        mapping = self._mapping(status="unmapped")

        result = validate_mappings(records, [mapping])

        self.assertIn("unmapped_has_canonical_skill", {issue.code for issue in result.issues})

    def _record(self, *, source_record_id: str = "egp_one") -> RawEGPRecord:
        return RawEGPRecord(
            source_record_id=source_record_id,
            category_id="present_simple",
            super_category="PRESENT",
            sub_category="present simple",
            cefr_level="A1",
            feature_type="FORM",
            feature_name="AFFIRMATIVE",
            can_do_statement="Can use the affirmative form.",
            source_row_number=2,
            source_file="fixture.xlsx",
            retrieved_at=datetime(2026, 9, 7, tzinfo=timezone.utc),
        )

    def _mapping(
        self,
        *,
        source_record_id: str = "egp_one",
        mapping_id: str = "egp_map_one",
        canonical_skill: str | None = "grammar.present_simple.affirmative",
        status: str = "exact",
    ) -> EGPCanonicalMapping:
        return EGPCanonicalMapping(
            mapping_id=mapping_id,
            source_record_id=source_record_id,
            canonical_skill=canonical_skill,
            status=status,  # type: ignore[arg-type]
            confidence=1.0,
            reason="unit test",
            matched_terms=["FORM: AFFIRMATIVE"],
            review_status="approved",
        )


if __name__ == "__main__":
    unittest.main()
