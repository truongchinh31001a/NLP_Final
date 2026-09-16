from __future__ import annotations

import unittest

from knowledge_core.sources.cefr.config import load_cefr_config
from knowledge_core.sources.cefr.models import (
    CEFRDescriptorRecord,
    CEFRLearningObjectiveCandidate,
)
from knowledge_core.sources.cefr.objective_extractor import (
    extract_learning_objective_candidates,
)
from knowledge_core.sources.cefr.validator import validate_records


class CEFRValidatorTests(unittest.TestCase):
    def test_valid_descriptor_and_candidate_pass(self) -> None:
        config = load_cefr_config()
        record = descriptor_record("cefr_valid")
        candidates = extract_learning_objective_candidates([record])

        result = validate_records([record], config, candidates=candidates)

        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.warning_count, 0)

    def test_explanatory_prose_is_rejected_for_descriptor_scales(self) -> None:
        config = load_cefr_config()
        record = descriptor_record(
            "cefr_prose",
            descriptor_text="This scale concerns narrative and description.",
        )

        result = validate_records([record], config)

        self.assertEqual(result.error_count, 1)
        self.assertEqual(result.issues[0].code, "non_descriptor_like_text")

    def test_grammatical_accuracy_requires_grammar_subdomain(self) -> None:
        config = load_cefr_config()
        record = descriptor_record(
            "cefr_grammar",
            domain="reception",
            subdomain="reading",
            scale_name="grammatical_accuracy",
            source_table="Grammatical accuracy",
        )

        result = validate_records([record], config)

        self.assertEqual(result.error_count, 1)
        self.assertEqual(
            result.issues[0].code,
            "grammatical_accuracy_domain_mismatch",
        )

    def test_duplicate_descriptor_rows_are_preserved_as_warnings(self) -> None:
        config = load_cefr_config()
        records = [
            descriptor_record("cefr_dupe_1"),
            descriptor_record("cefr_dupe_2"),
        ]

        result = validate_records(records, config)

        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.warning_count, 2)
        self.assertEqual(result.issues[0].code, "duplicate_descriptor_row")

    def test_candidate_from_no_descriptor_row_is_an_error(self) -> None:
        config = load_cefr_config()
        record = descriptor_record(
            "cefr_no_descriptor",
            descriptor_text="No descriptors available; see C1",
            descriptor_available=False,
            reference_level="C1",
        )
        candidate = CEFRLearningObjectiveCandidate(
            objective_id="cefr_obj_bad",
            source_record_id=record.source_record_id,
            cefr_level="C2",
            domain=record.domain,
            scale_name=record.scale_name,
            objective_text=record.descriptor_text,
            source_descriptor_text=record.descriptor_text,
        )

        result = validate_records([record], config, candidates=[candidate])

        self.assertEqual(result.error_count, 1)
        self.assertEqual(result.issues[0].code, "candidate_from_no_descriptor_row")


def descriptor_record(
    source_record_id: str,
    *,
    descriptor_text: str = "Can produce straightforward connected texts.",
    descriptor_available: bool = True,
    reference_level: str | None = None,
    domain: str = "production",
    subdomain: str = "written_production",
    scale_name: str = "overall_written_production",
    source_table: str = "Overall written production",
) -> CEFRDescriptorRecord:
    return CEFRDescriptorRecord(
        source_record_id=source_record_id,
        chapter="3",
        section="3.1.2 Production activities",
        domain=domain,
        subdomain=subdomain,
        scale_name=scale_name,
        descriptor_type="communicative_activity",
        cefr_level="B1" if descriptor_available else "C2",
        descriptor_text=descriptor_text,
        descriptor_available=descriptor_available,
        reference_level=reference_level,
        page_number=66,
        source_table=source_table,
        is_pre_a1=False,
        source_file="data/external/cefr/CEFR Companion Volume_eng.pdf",
    )


if __name__ == "__main__":
    unittest.main()

