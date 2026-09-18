from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from knowledge_core.assessment.models import (
    AssessmentCriterion,
    AssessmentEvidence,
    SkillAssessmentProfile,
)
from knowledge_core.enrichment.processor import run_knowledge_enrichment
from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILLS
from knowledge_core.misconceptions.models import (
    MisconceptionCandidate,
    MisconceptionEvidenceLink,
)


class KnowledgeEnrichmentTests(unittest.TestCase):
    def test_pending_candidates_are_not_used_as_empirical_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            criteria_path, profiles_path = _write_assessment_inputs(workspace)
            accepted_path = workspace / "accepted.jsonl"
            candidate_path = workspace / "candidates.jsonl"
            accepted_path.write_text("", encoding="utf-8")
            _write_jsonl(
                [_misconception(status="candidate", review_status="pending")],
                candidate_path,
            )

            result = run_knowledge_enrichment(
                assessment_criteria_path=criteria_path,
                assessment_profiles_path=profiles_path,
                accepted_misconceptions_path=accepted_path,
                candidate_misconceptions_path=candidate_path,
                curated_dir=workspace / "curated",
                review_dir=workspace / "review",
                reports_dir=workspace / "reports",
            )

            self.assertTrue(result.report["validation"]["passed"])
            self.assertEqual(result.report["counts"]["accepted_misconceptions"], 0)
            self.assertEqual(result.report["counts"]["skill_misconception_links"], 0)
            self.assertEqual(
                result.report["counts"]["criteria_with_empirical_failure_signals"],
                0,
            )
            pending_profile = next(
                profile
                for profile in result.enriched_profiles
                if profile.profile.canonical_skill_id
                == "grammar.present_simple.third_person_s"
            )
            self.assertEqual(
                pending_profile.diagnostic_evidence_status,
                "empirical_pending_review",
            )
            self.assertEqual(
                pending_profile.pending_misconception_candidate_ids,
                ["mis_test_third_person_s"],
            )

    def test_accepted_misconceptions_link_to_skills_and_failure_signals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            criteria_path, profiles_path = _write_assessment_inputs(workspace)
            accepted_path = workspace / "accepted.jsonl"
            candidate_path = workspace / "candidates.jsonl"
            _write_jsonl(
                [_misconception(status="accepted", review_status="approved")],
                accepted_path,
            )
            candidate_path.write_text("", encoding="utf-8")

            result = run_knowledge_enrichment(
                assessment_criteria_path=criteria_path,
                assessment_profiles_path=profiles_path,
                accepted_misconceptions_path=accepted_path,
                candidate_misconceptions_path=candidate_path,
                curated_dir=workspace / "curated",
                review_dir=workspace / "review",
                reports_dir=workspace / "reports",
            )

            self.assertTrue(result.report["validation"]["passed"])
            self.assertEqual(result.report["counts"]["accepted_misconceptions"], 1)
            self.assertEqual(result.report["counts"]["skill_misconception_links"], 1)
            self.assertGreater(
                result.report["counts"]["criteria_with_empirical_failure_signals"],
                0,
            )
            enriched = [
                criterion
                for criterion in result.enriched_criteria
                if criterion.criterion.canonical_skill_id
                == "grammar.present_simple.third_person_s"
            ]
            self.assertEqual(enriched[0].enrichment_status, "empirically_enriched")
            self.assertEqual(
                enriched[0].empirical_failure_signals[0].misconception_id,
                "mis_test_third_person_s",
            )


def _write_assessment_inputs(workspace: Path) -> tuple[Path, Path]:
    criteria = []
    profiles = []
    for index, skill_id in enumerate(CANONICAL_GRAMMAR_V1_SKILLS, start=1):
        criterion = AssessmentCriterion(
            criterion_id=f"crit_test_{index}",
            canonical_skill_id=skill_id,
            criterion_type="form_accuracy",
            name=f"{skill_id} form accuracy",
            description="Synthetic assessment criterion.",
            observable_behavior="Learner shows the target form.",
            evidence_requirements=["target form evidence"],
            acceptable_task_types=["fill_blank"],
            failure_signals=["curated signal"],
            confidence=0.8,
            status="candidate",
            review_status="pending",
            reason="Synthetic test criterion.",
            provenance=[
                AssessmentEvidence(
                    evidence_type="curated_assessment_rule",
                    source="test",
                    note="Synthetic.",
                ),
            ],
            version="assessment_v1",
        )
        profile = SkillAssessmentProfile(
            canonical_skill_id=skill_id,
            criterion_ids=[criterion.criterion_id],
            criterion_types=["form_accuracy"],
            recommended_task_types=["fill_blank"],
            assessment_coverage_status="covered",
            review_status="pending",
            version="assessment_v1",
        )
        criteria.append(criterion)
        profiles.append(profile)
    criteria_path = workspace / "criteria.jsonl"
    profiles_path = workspace / "profiles.jsonl"
    _write_jsonl(criteria, criteria_path)
    _write_jsonl(profiles, profiles_path)
    return criteria_path, profiles_path


def _misconception(*, status: str, review_status: str) -> MisconceptionCandidate:
    link = MisconceptionEvidenceLink(
        normalized_error_id="normerr__subject_verb_agreement__1",
        error_instance_id="err__clc_fce__1",
        source_record_id="src__clc_fce__1",
        source_key="clc_fce",
        source_label="AGV",
        proficiency_label="FCE_B2",
        mapping_id="errskill__1",
        mapping_confidence=0.62,
    )
    return MisconceptionCandidate(
        misconception_id="mis_test_third_person_s",
        canonical_skill_id="grammar.present_simple.third_person_s",
        name="Possible missing third-person singular -s",
        description="Synthetic misconception.",
        error_category="subject_verb_agreement",
        error_subtype="clc_agv",
        source_labels=["AGV"],
        expected_pattern="Expected third-person -s.",
        observed_pattern="Observed verb agreement source label.",
        diagnostic_rule="Synthetic rule.",
        source_evidence_count=1,
        source_distribution={"clc_fce": 1},
        frequency=0.1,
        frequency_scope="synthetic",
        proficiency_distribution={"FCE_B2": 1},
        evidence_links=[link],
        severity="low",
        confidence=0.7,
        status=status,
        review_status=review_status,
        reason="Synthetic.",
    )


def _write_jsonl(records, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record.model_dump(mode="json"), sort_keys=True))
            handle.write("\n")


if __name__ == "__main__":
    unittest.main()

