from __future__ import annotations

import unittest
from datetime import datetime, timezone

from knowledge_core.alignment.models import (
    CanonicalSkillEvidenceProfile,
    SkillCEFRAlignment,
)
from knowledge_core.assessment.builder import (
    AssessmentInputArtifacts,
    build_assessment_dataset,
)
from knowledge_core.assessment.config import load_assessment_config
from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILLS
from knowledge_core.relationships.models import RelationshipEvidence, SkillRelationship
from knowledge_core.sources.cefr.models import CEFRDescriptorRecord
from knowledge_core.sources.egp.models import RawEGPRecord


def _artifacts() -> AssessmentInputArtifacts:
    return AssessmentInputArtifacts(
        skill_profiles=[
            CanonicalSkillEvidenceProfile(
                canonical_skill_id="grammar.present_simple.affirmative",
                canonical_parent="grammar.present_simple",
                egp_evidence_count=1,
                egp_levels=["A1"],
                egp_source_record_ids=["egp_test_present_simple"],
                cefr_min_level="A1",
                cefr_primary_level="A1",
                grammatical_accuracy_context=["cefr_ga_a1"],
                direct_objective_ids=[],
                contextual_objective_ids=[],
                evidence_status="aligned",
                alignment_confidence=0.9,
                notes="Test profile.",
            ),
        ],
        skill_alignments=[
            SkillCEFRAlignment(
                canonical_skill_id="grammar.present_simple.affirmative",
                egp_levels=["A1"],
                inferred_min_level="A1",
                inferred_primary_level="A1",
                cefr_descriptor_ids=["cefr_ga_a1"],
                objective_ids=[],
                grammatical_accuracy_descriptor_ids=["cefr_ga_a1"],
                confidence=0.9,
                status="aligned",
                reason="Test alignment.",
                review_status="accepted",
            ),
        ],
        relationships=[
            SkillRelationship(
                relationship_id="rel_test_present_simple_negative",
                source_skill_id="grammar.present_simple.affirmative",
                target_skill_id="grammar.present_simple.negative",
                relation_type="prerequisite_of",
                dependency_strength="hard",
                confidence=0.95,
                status="candidate",
                reason="Test prerequisite context.",
                evidence=[
                    RelationshipEvidence(
                        evidence_type="curated_pedagogy",
                        source="test",
                    ),
                ],
                review_status="pending",
                created_by="test",
                version="test",
            ),
        ],
        cefr_descriptors=[
            CEFRDescriptorRecord(
                source_record_id="cefr_ga_a1",
                chapter="5",
                section="Linguistic competence",
                domain="linguistic_competence",
                subdomain="grammatical_accuracy",
                scale_name="grammatical_accuracy",
                descriptor_type="linguistic_competence",
                cefr_level="A1",
                descriptor_text="Shows only limited control of a few simple grammatical structures.",
                source_file="data/external/cefr/test.pdf",
            ),
        ],
        egp_records=[
            RawEGPRecord(
                source_record_id="egp_test_present_simple",
                category_id="present_simple",
                cefr_level="A1",
                feature_type="FORM",
                feature_name="AFFIRMATIVE",
                can_do_statement="Can use the affirmative form.",
                source_file="data/external/english_profile/test.xlsx",
                retrieved_at=datetime.now(timezone.utc),
            ),
        ],
    )


def _dataset():
    return build_assessment_dataset(
        config=load_assessment_config(),
        artifacts=_artifacts(),
    )


class AssessmentBuilderTests(unittest.TestCase):
    def test_all_canonical_skills_receive_assessment_criteria(self) -> None:
        dataset = _dataset()

        self.assertEqual(len(dataset.profiles), 43)
        self.assertEqual(
            {
                profile.canonical_skill_id
                for profile in dataset.profiles
            },
            set(CANONICAL_GRAMMAR_V1_SKILLS),
        )
        self.assertEqual(
            {
                criterion.canonical_skill_id
                for criterion in dataset.criteria
            },
            set(CANONICAL_GRAMMAR_V1_SKILLS),
        )

    def test_form_criterion_generation(self) -> None:
        dataset = _dataset()
        criterion = next(
            criterion
            for criterion in dataset.criteria
            if criterion.canonical_skill_id == "grammar.present_continuous.form"
            and criterion.criterion_type == "form_accuracy"
        )

        self.assertIn("be followed by the -ing form", criterion.observable_behavior)
        self.assertIn("fill_blank", criterion.acceptable_task_types)

    def test_meaning_and_production_generation(self) -> None:
        dataset = _dataset()
        types = {
            criterion.criterion_type
            for criterion in dataset.criteria
            if criterion.canonical_skill_id
            == "grammar.present_continuous.current_action"
        }

        self.assertEqual(types, {"meaning_use", "production"})

    def test_contrast_question_and_negative_generation(self) -> None:
        dataset = _dataset()
        by_skill = {}
        for criterion in dataset.criteria:
            by_skill.setdefault(criterion.canonical_skill_id, set()).add(
                criterion.criterion_type,
            )

        self.assertIn(
            "contrast_discrimination",
            by_skill["grammar.conditionals.first_vs_second"],
        )
        self.assertEqual(
            by_skill["grammar.present_simple.questions"],
            {"form_accuracy", "production"},
        )
        self.assertEqual(
            by_skill["grammar.present_simple.negative"],
            {"form_accuracy", "production"},
        )

    def test_cefr_egp_and_relationship_context_are_attached(self) -> None:
        dataset = _dataset()
        criterion = next(
            criterion
            for criterion in dataset.criteria
            if criterion.canonical_skill_id == "grammar.present_simple.affirmative"
        )
        provenance_types = {
            evidence.evidence_type
            for evidence in criterion.provenance
        }
        negative_profile = next(
            profile
            for profile in dataset.profiles
            if profile.canonical_skill_id == "grammar.present_simple.negative"
        )

        self.assertEqual(criterion.cefr_level, "A1")
        self.assertEqual(criterion.cefr_context_descriptor_ids, ["cefr_ga_a1"])
        self.assertIn("cefr_grammatical_accuracy", provenance_types)
        self.assertIn("egp_evidence", provenance_types)
        self.assertEqual(
            negative_profile.prerequisite_context,
            ["grammar.present_simple.affirmative"],
        )

    def test_thresholds_are_curated_recommendations(self) -> None:
        dataset = _dataset()

        for criterion in dataset.criteria:
            self.assertEqual(criterion.threshold_source, "curated_v1_default")
            self.assertIsNotNone(criterion.recommended_threshold)
            self.assertIsNotNone(criterion.recommended_min_items)
            self.assertNotIn("empirical_misconception", criterion.reason)


if __name__ == "__main__":
    unittest.main()
