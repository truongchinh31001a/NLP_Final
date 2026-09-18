from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from knowledge_core.misconceptions.review_processor import (
    apply_misconception_review,
    prepare_misconception_review,
)


class MisconceptionHumanReviewTests(unittest.TestCase):
    def test_approve_generates_accepted_artifact_and_proposed_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _fixture(Path(tmp), evidence=True, decision="APPROVE")
            result = apply_misconception_review(**paths)
            self.assertTrue(result.report["validation"]["passed"])
            self.assertEqual(result.report["approved"], 1)
            self.assertEqual(result.report["assessment_links_proposed"], 1)
            accepted = _read_jsonl(Path(paths["curated_dir"]) / "accepted_misconceptions.jsonl")
            links = _read_jsonl(Path(paths["links_path"]))
            self.assertEqual(accepted[0]["review_status"], "approved")
            self.assertEqual(links[0]["review_status"], "pending")
            self.assertFalse(links[0]["provenance"]["assessment_artifact_mutated"])

    def test_reject_and_needs_review_are_partitioned(self) -> None:
        for decision, filename, status in (
            ("REJECT", "rejected_misconceptions.jsonl", "rejected"),
            ("NEEDS_REVIEW", "unresolved_misconceptions.jsonl", "candidate"),
        ):
            with self.subTest(decision=decision), tempfile.TemporaryDirectory() as tmp:
                paths = _fixture(Path(tmp), evidence=True, decision=decision)
                result = apply_misconception_review(**paths)
                self.assertTrue(result.report["validation"]["passed"])
                record = _read_jsonl(Path(paths["curated_dir"]) / filename)[0]
                self.assertEqual(record["status"], status)

    def test_approval_without_evidence_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _fixture(Path(tmp), evidence=False, decision="APPROVE")
            result = apply_misconception_review(**paths)
            self.assertFalse(result.report["validation"]["passed"])
            self.assertIn(
                "accepted_without_approved_evidence",
                {item["code"] for item in result.report["validation"]["issues"]},
            )

    def test_invalid_skill_fails_and_taxonomy_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _fixture(root, evidence=True, decision="NEEDS_REVIEW")
            candidate = _read_jsonl(Path(paths["candidates_path"]))[0]
            candidate["canonical_skill_id"] = "grammar.not_a_skill"
            _write_jsonl(Path(paths["candidates_path"]), [candidate])
            result = apply_misconception_review(**paths)
            self.assertFalse(result.report["validation"]["passed"])
            self.assertIn(
                "invalid_skill_reference",
                {item["code"] for item in result.report["validation"]["issues"]},
            )
            self.assertTrue(result.report["taxonomy"]["taxonomy_unchanged"])

    def test_prepare_defaults_to_explicit_needs_review_without_pii(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _fixture(root, evidence=False, decision="NEEDS_REVIEW")
            review = root / "review.csv"
            decisions = root / "prepared_decisions.csv"
            result = prepare_misconception_review(
                candidates_path=paths["candidates_path"],
                review_path=review,
                decisions_path=decisions,
            )
            self.assertEqual(result.report["total_candidates"], 1)
            self.assertFalse(result.report["privacy"]["learner_pii_emitted"])
            with decisions.open("r", encoding="utf-8", newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["reviewer_decision"], "NEEDS_REVIEW")


def _fixture(root: Path, *, evidence: bool, decision: str) -> dict[str, Path]:
    candidates = root / "candidates.jsonl"
    criteria = root / "criteria.jsonl"
    approved_mappings = root / "approved_mappings.jsonl"
    decisions = root / "decisions.csv"
    evidence_links = []
    if evidence:
        evidence_links = [{
            "normalized_error_id": "norm_1", "error_instance_id": "err_1",
            "source_record_id": "rec_1", "source_key": "clc_fce",
            "source_label": "AGV", "proficiency_label": "FCE_B2",
            "task_id": None, "split": None, "mapping_id": "map_approved",
            "mapping_confidence": 0.9,
        }]
    candidate = {
        "misconception_id": "mis_test",
        "canonical_skill_id": "grammar.present_simple.third_person_s",
        "name": "Possible agreement misconception", "description": "Repeatable pattern.",
        "error_category": "subject_verb_agreement", "error_subtype": "clc_agv",
        "source_labels": ["AGV"], "expected_pattern": "Expected agreement.",
        "observed_pattern": "Agreement error.", "diagnostic_rule": "Detect agreement pattern.",
        "source_evidence_count": len(evidence_links),
        "source_distribution": {"clc_fce": 1} if evidence else {},
        "frequency": 0.1 if evidence else 0.0, "frequency_scope": "fixture",
        "source_frequencies": {"clc_fce": 0.1} if evidence else {},
        "proficiency_distribution": {"FCE_B2": 1} if evidence else {},
        "evidence_links": evidence_links, "severity": "medium", "confidence": 0.7,
        "status": "candidate", "review_status": "pending", "reason": "Fixture.",
        "provenance": {"approved_mapping_evidence_only": True}, "version": "misconceptions_v1",
    }
    criterion = {
        "criterion_id": "crit_test",
        "canonical_skill_id": "grammar.present_simple.third_person_s",
        "criterion_type": "error_correction", "name": "Correction", "description": "Correct it.",
        "observable_behavior": "Corrects agreement.", "evidence_requirements": ["correct form"],
        "acceptable_task_types": ["error_correction"], "failure_signals": ["wrong form"],
        "cefr_level": None, "cefr_context_descriptor_ids": [], "recommended_threshold": None,
        "recommended_min_items": None, "threshold_source": None, "confidence": 0.8,
        "status": "candidate", "review_status": "pending", "reason": "Fixture.",
        "provenance": [], "version": "assessment_v1",
    }
    _write_jsonl(candidates, [candidate])
    _write_jsonl(criteria, [criterion])
    _write_jsonl(
        approved_mappings,
        [{"mapping_id": "map_approved"}] if evidence else [],
    )
    decisions.parent.mkdir(parents=True, exist_ok=True)
    with decisions.open("w", encoding="utf-8", newline="") as handle:
        fields = ["misconception_id", "reviewer_decision", "reviewer_note", "reviewed_by", "reviewed_at"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow({
            "misconception_id": "mis_test", "reviewer_decision": decision,
            "reviewer_note": "Fixture decision.",
            "reviewed_by": "reviewer" if decision != "NEEDS_REVIEW" else "",
            "reviewed_at": "2026-09-17T12:00:00Z" if decision != "NEEDS_REVIEW" else "",
        })
    return {
        "candidates_path": candidates, "decisions_path": decisions,
        "criteria_path": criteria, "curated_dir": root / "curated",
        "approved_mappings_path": approved_mappings,
        "links_path": root / "links.jsonl", "report_path": root / "report.json",
    }


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(item) + "\n" for item in records), encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


if __name__ == "__main__":
    unittest.main()
