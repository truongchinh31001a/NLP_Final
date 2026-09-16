from __future__ import annotations

from datetime import datetime, timezone
import unittest

from knowledge_core.alignment.cefr_alignment import (
    build_knowledge_alignment,
    infer_levels_from_egp_evidence,
)
from knowledge_core.alignment.config import load_alignment_config
from knowledge_core.alignment.egp_evidence import collect_egp_evidence
from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILLS
from knowledge_core.mapping.egp.models import EGPCanonicalMapping
from knowledge_core.sources.cefr.models import (
    CEFRDescriptorRecord,
    CEFRLearningObjectiveCandidate,
)
from knowledge_core.sources.egp.models import RawEGPRecord


class CEFRAlignmentTests(unittest.TestCase):
    def test_infer_levels_prefers_exact_evidence_for_minimum(self) -> None:
        records = [
            egp_record("egp_exact", "B1"),
            egp_record("egp_candidate", "A2"),
        ]
        mappings = [
            egp_mapping("egp_exact", "grammar.present_perfect.experience", "exact", 1.0),
            egp_mapping(
                "egp_candidate",
                "grammar.present_perfect.experience",
                "candidate",
                0.78,
            ),
        ]
        bundle = collect_egp_evidence(
            records,
            mappings,
            establishing_statuses={"exact", "candidate"},
            ambiguous_statuses={"ambiguous"},
            status_weights={"exact": 1.0, "candidate": 0.65},
        )

        inferred = infer_levels_from_egp_evidence(
            bundle.direct_by_skill["grammar.present_perfect.experience"],
        )

        self.assertEqual(inferred.min_level, "B1")
        self.assertEqual(inferred.primary_level, "B1")

    def test_build_alignment_outputs_all_canonical_skills_and_attaches_ga_context(
        self,
    ) -> None:
        config = load_alignment_config()
        records = [egp_record("egp_b1", "B1")]
        mappings = [
            egp_mapping("egp_b1", "grammar.present_perfect.experience", "exact", 1.0),
        ]
        ga = cefr_descriptor(
            "cefr_ga_b1",
            "B1",
            "Uses reasonably accurately a repertoire of frequently used routines.",
            scale_name="grammatical_accuracy",
        )
        objective = objective_candidate(
            "obj_exp",
            "B1",
            "Can give detailed accounts of experiences, describing feelings and reactions.",
        )

        dataset = build_knowledge_alignment(
            canonical_skills=CANONICAL_GRAMMAR_V1_SKILLS,
            egp_records=records,
            egp_mappings=mappings,
            cefr_descriptors=[ga],
            cefr_objectives=[objective],
            config=config,
        )
        profile_by_skill = {
            profile.canonical_skill_id: profile for profile in dataset.profiles
        }

        self.assertEqual(len(dataset.profiles), 43)
        profile = profile_by_skill["grammar.present_perfect.experience"]
        self.assertEqual(profile.cefr_primary_level, "B1")
        self.assertEqual(profile.grammatical_accuracy_context, ["cefr_ga_b1"])
        self.assertIn("obj_exp", profile.contextual_objective_ids)
        self.assertEqual(
            set(profile_by_skill),
            set(CANONICAL_GRAMMAR_V1_SKILLS),
        )

    def test_conflicting_level_evidence_requires_partial_review(self) -> None:
        config = load_alignment_config()
        records = [
            egp_record("egp_a1", "A1"),
            egp_record("egp_b2", "B2"),
        ]
        mappings = [
            egp_mapping("egp_a1", "grammar.present_continuous.form", "exact", 1.0),
            egp_mapping("egp_b2", "grammar.present_continuous.form", "exact", 1.0),
        ]

        dataset = build_knowledge_alignment(
            canonical_skills=["grammar.present_continuous.form"],
            egp_records=records,
            egp_mappings=mappings,
            cefr_descriptors=[],
            cefr_objectives=[],
            config=config,
        )
        profile = dataset.profiles[0]

        self.assertEqual(profile.evidence_status, "no_cefr_evidence")
        self.assertTrue(profile.provenance["conflicting_level_evidence"])


def egp_record(source_record_id: str, cefr_level: str) -> RawEGPRecord:
    return RawEGPRecord(
        source_record_id=source_record_id,
        category_id="present_perfect_simple",
        cefr_level=cefr_level,
        can_do_statement="Can use the present perfect to describe experience.",
        source_row_number=2,
        source_file="source.xlsx",
        retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def egp_mapping(
    source_record_id: str,
    canonical_skill: str,
    status: str,
    confidence: float,
) -> EGPCanonicalMapping:
    return EGPCanonicalMapping(
        mapping_id=f"map_{source_record_id}",
        source_record_id=source_record_id,
        canonical_skill=canonical_skill,
        status=status,
        confidence=confidence,
        reason="Matched fixture.",
        matched_terms=["fixture"],
        review_status="approved" if status == "exact" else "pending",
    )


def cefr_descriptor(
    source_record_id: str,
    cefr_level: str,
    text: str,
    *,
    scale_name: str,
) -> CEFRDescriptorRecord:
    return CEFRDescriptorRecord(
        source_record_id=source_record_id,
        chapter="5",
        section="5.1 Linguistic competence",
        domain="linguistic_competence",
        subdomain="grammar",
        scale_name=scale_name,
        descriptor_type="linguistic_competence",
        cefr_level=cefr_level,
        descriptor_text=text,
        descriptor_available=True,
        page_number=132,
        source_table="Grammatical accuracy",
        is_pre_a1=False,
        source_file="data/external/cefr/CEFR Companion Volume_eng.pdf",
    )


def objective_candidate(
    objective_id: str,
    cefr_level: str,
    text: str,
) -> CEFRLearningObjectiveCandidate:
    return CEFRLearningObjectiveCandidate(
        objective_id=objective_id,
        source_record_id=f"cefr_{objective_id}",
        cefr_level=cefr_level,
        domain="production",
        scale_name="sustained_monologue_describing_experience",
        objective_text=text,
        source_descriptor_text=text,
        status="exact_source",
        confidence=1.0,
    )


if __name__ == "__main__":
    unittest.main()

