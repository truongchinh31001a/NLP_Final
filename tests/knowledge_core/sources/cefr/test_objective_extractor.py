from __future__ import annotations

import unittest

from knowledge_core.sources.cefr.models import CEFRDescriptorRecord
from knowledge_core.sources.cefr.objective_extractor import (
    extract_learning_objective_candidates,
)


class CEFRObjectiveExtractorTests(unittest.TestCase):
    def test_available_primary_descriptors_become_exact_source_candidates(self) -> None:
        record = descriptor_record("B1", "Can produce straightforward connected texts.")

        candidates = extract_learning_objective_candidates([record])

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].source_record_id, record.source_record_id)
        self.assertEqual(candidates[0].status, "exact_source")
        self.assertEqual(candidates[0].canonical_skill_hint, None)
        self.assertEqual(candidates[0].objective_text, record.descriptor_text)

    def test_no_descriptor_pre_a1_and_level_summary_records_do_not_become_candidates(
        self,
    ) -> None:
        records = [
            descriptor_record(
                "C2",
                "No descriptors available; see C1",
                descriptor_available=False,
                reference_level="C1",
            ),
            descriptor_record(
                "Pre-A1",
                "Can recognise familiar words.",
                source_record_id="cefr_pre_a1",
            ),
            descriptor_record(
                "A2",
                "Can understand sentences and frequently used expressions.",
                descriptor_type="level_summary",
                domain="level_summary",
                scale_name="common_reference_levels",
                source_record_id="cefr_summary_a2",
            ),
        ]

        candidates = extract_learning_objective_candidates(records)

        self.assertEqual(candidates, [])


def descriptor_record(
    cefr_level: str,
    descriptor_text: str,
    *,
    descriptor_available: bool = True,
    reference_level: str | None = None,
    descriptor_type: str = "communicative_activity",
    domain: str = "production",
    scale_name: str = "overall_written_production",
    source_record_id: str = "cefr_record",
) -> CEFRDescriptorRecord:
    return CEFRDescriptorRecord(
        source_record_id=source_record_id,
        chapter="3",
        section="3.1.2 Production activities",
        domain=domain,
        subdomain="written_production",
        scale_name=scale_name,
        descriptor_type=descriptor_type,
        cefr_level=cefr_level,
        descriptor_text=descriptor_text,
        descriptor_available=descriptor_available,
        reference_level=reference_level,
        page_number=66,
        source_table="Overall written production",
        is_pre_a1=cefr_level == "Pre-A1",
        source_file="data/external/cefr/CEFR Companion Volume_eng.pdf",
    )


if __name__ == "__main__":
    unittest.main()

