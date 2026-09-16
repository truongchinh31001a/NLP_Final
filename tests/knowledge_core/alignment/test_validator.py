from __future__ import annotations

from datetime import datetime, timezone
import unittest

from knowledge_core.alignment.cefr_alignment import build_knowledge_alignment
from knowledge_core.alignment.config import load_alignment_config
from knowledge_core.alignment.models import CanonicalSkillEvidenceProfile
from knowledge_core.alignment.validator import validate_alignment
from knowledge_core.mapping.egp.models import EGPCanonicalMapping
from knowledge_core.sources.egp.models import RawEGPRecord


class AlignmentValidatorTests(unittest.TestCase):
    def test_valid_curated_only_profiles_pass(self) -> None:
        config = load_alignment_config()
        dataset = build_knowledge_alignment(
            canonical_skills=["grammar.present_simple.third_person_s"],
            egp_records=[],
            egp_mappings=[],
            cefr_descriptors=[],
            cefr_objectives=[],
            config=config,
        )

        result = validate_alignment(
            canonical_skills=["grammar.present_simple.third_person_s"],
            dataset=dataset,
            egp_records=[],
            egp_mappings=[],
            cefr_descriptors=[],
            cefr_objectives=[],
        )

        self.assertEqual(result.error_count, 0)

    def test_curated_only_profile_with_source_evidence_is_rejected(self) -> None:
        config = load_alignment_config()
        records = [egp_record("egp_1", "A2")]
        mappings = [
            EGPCanonicalMapping(
                mapping_id="map_1",
                source_record_id="egp_1",
                canonical_skill="grammar.present_simple.affirmative",
                status="exact",
                confidence=1.0,
                reason="fixture",
                matched_terms=["fixture"],
                review_status="approved",
            ),
        ]
        dataset = build_knowledge_alignment(
            canonical_skills=["grammar.present_simple.affirmative"],
            egp_records=records,
            egp_mappings=mappings,
            cefr_descriptors=[],
            cefr_objectives=[],
            config=config,
        )
        dataset.profiles[0] = dataset.profiles[0].model_copy(
            update={"evidence_status": "curated_only"},
        )

        result = validate_alignment(
            canonical_skills=["grammar.present_simple.affirmative"],
            dataset=dataset,
            egp_records=records,
            egp_mappings=mappings,
            cefr_descriptors=[],
            cefr_objectives=[],
        )

        self.assertEqual(result.error_count, 1)
        self.assertEqual(result.issues[0].code, "curated_only_has_source_evidence")

    def test_ambiguous_mapping_cannot_establish_level_by_itself(self) -> None:
        profile = CanonicalSkillEvidenceProfile(
            canonical_skill_id="grammar.past_simple.regular_verbs",
            canonical_parent="grammar.past_simple",
            egp_evidence_count=0,
            egp_levels=[],
            egp_source_record_ids=[],
            cefr_min_level="A2",
            cefr_primary_level="A2",
            grammatical_accuracy_context=[],
            direct_objective_ids=[],
            contextual_objective_ids=[],
            evidence_status="ambiguous",
            alignment_confidence=0.45,
            notes="fixture",
            provenance={"ambiguous_egp_source_record_ids": ["egp_ambiguous"]},
        )
        config = load_alignment_config()
        dataset = build_knowledge_alignment(
            canonical_skills=["grammar.past_simple.regular_verbs"],
            egp_records=[],
            egp_mappings=[],
            cefr_descriptors=[],
            cefr_objectives=[],
            config=config,
        )
        dataset.profiles[0] = profile
        mapping = EGPCanonicalMapping(
            mapping_id="map_ambiguous",
            source_record_id="egp_ambiguous",
            canonical_skill=None,
            secondary_candidates=["grammar.past_simple.regular_verbs"],
            status="ambiguous",
            confidence=0.55,
            reason="ambiguous fixture",
            matched_terms=["regular and irregular"],
            review_status="needs_review",
        )

        result = validate_alignment(
            canonical_skills=["grammar.past_simple.regular_verbs"],
            dataset=dataset,
            egp_records=[],
            egp_mappings=[mapping],
            cefr_descriptors=[],
            cefr_objectives=[],
        )

        self.assertEqual(result.error_count, 1)
        self.assertEqual(result.issues[0].code, "ambiguous_mapping_established_level")


def egp_record(source_record_id: str, cefr_level: str) -> RawEGPRecord:
    return RawEGPRecord(
        source_record_id=source_record_id,
        category_id="present_simple",
        cefr_level=cefr_level,
        can_do_statement="Can use the affirmative form.",
        source_row_number=2,
        source_file="source.xlsx",
        retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


if __name__ == "__main__":
    unittest.main()

