from __future__ import annotations

import unittest

from knowledge_core.assessment.models import AssessmentEvidence
from knowledge_core.assessment.validator import validate_assessment_dataset
from tests.knowledge_core.assessment.test_builder import _artifacts, _dataset


class AssessmentValidatorTests(unittest.TestCase):
    def test_generated_assessment_dataset_validates_without_errors(self) -> None:
        dataset = _dataset()
        result = validate_assessment_dataset(
            criteria=dataset.criteria,
            profiles=dataset.profiles,
            artifacts=_artifacts(),
        )

        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.warning_count, 0)
        self.assertTrue(result.taxonomy_unchanged)

    def test_invalid_task_type_is_rejected(self) -> None:
        dataset = _dataset()
        bad = dataset.criteria[0].model_copy(
            update={"acceptable_task_types": ["invalid_task"]},
        )
        result = validate_assessment_dataset(
            criteria=[bad, *dataset.criteria[1:]],
            profiles=dataset.profiles,
            artifacts=_artifacts(),
        )

        self.assertIn("invalid_task_type", {issue.code for issue in result.issues})

    def test_duplicate_semantics_are_rejected(self) -> None:
        dataset = _dataset()
        duplicate = dataset.criteria[0].model_copy(
            update={"criterion_id": "crit_duplicate_semantics"},
        )
        result = validate_assessment_dataset(
            criteria=[*dataset.criteria, duplicate],
            profiles=dataset.profiles,
            artifacts=_artifacts(),
        )

        self.assertIn(
            "duplicate_criterion_semantics",
            {issue.code for issue in result.issues},
        )

    def test_unknown_skill_id_is_rejected(self) -> None:
        dataset = _dataset()
        bad = dataset.criteria[0].model_copy(
            update={
                "criterion_id": "crit_unknown_skill",
                "canonical_skill_id": "grammar.unknown.skill",
            },
        )
        result = validate_assessment_dataset(
            criteria=[bad, *dataset.criteria[1:]],
            profiles=dataset.profiles,
            artifacts=_artifacts(),
        )

        self.assertIn("unknown_skill_id", {issue.code for issue in result.issues})

    def test_invalid_egp_reference_is_rejected(self) -> None:
        dataset = _dataset()
        bad = dataset.criteria[0].model_copy(
            update={
                "provenance": [
                    AssessmentEvidence(
                        evidence_type="egp_evidence",
                        source="english_grammar_profile_alignment",
                        source_record_ids=["egp_missing"],
                    ),
                ],
            },
        )
        result = validate_assessment_dataset(
            criteria=[bad, *dataset.criteria[1:]],
            profiles=dataset.profiles,
            artifacts=_artifacts(),
        )

        self.assertIn(
            "unknown_egp_source_record_id",
            {issue.code for issue in result.issues},
        )

    def test_unsupported_empirical_misconception_claim_is_rejected(self) -> None:
        dataset = _dataset()
        bad_evidence = dataset.criteria[0].provenance[0].model_copy(
            update={"source": "efcamdat"},
        )
        bad = dataset.criteria[0].model_copy(
            update={"provenance": [bad_evidence]},
        )
        result = validate_assessment_dataset(
            criteria=[bad, *dataset.criteria[1:]],
            profiles=dataset.profiles,
            artifacts=_artifacts(),
        )

        self.assertIn(
            "unsupported_empirical_misconception_claim",
            {issue.code for issue in result.issues},
        )

    def test_taxonomy_change_is_rejected(self) -> None:
        dataset = _dataset()
        result = validate_assessment_dataset(
            criteria=dataset.criteria,
            profiles=dataset.profiles,
            artifacts=_artifacts(),
            canonical_skill_ids=["grammar.present_simple.affirmative"],
        )

        self.assertIn("taxonomy_changed", {issue.code for issue in result.issues})
        self.assertFalse(result.taxonomy_unchanged)


if __name__ == "__main__":
    unittest.main()
