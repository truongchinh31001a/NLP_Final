from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from knowledge_core.error_mapping.processor import (
    apply_review_decisions,
    prepare_review_package,
)


class ErrorMappingHumanReviewTests(unittest.TestCase):
    def test_prepare_and_apply_explicit_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            paths = _fixture(workspace)
            prepared = prepare_review_package(**paths["prepare"])

            self.assertEqual(prepared.report["mapping_review_queue"], 3)
            self.assertEqual(prepared.report["legacy_normalization_review_rows"], 1)
            groups = _read_csv(workspace / "review" / "error_skill_mapping_review_groups.csv")
            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0]["group_can_share_decision"], "false")

            decisions = [
                {
                    "mapping_id": "map_approve",
                    "reviewer_decision": "APPROVE",
                    "reviewer_note": "Context confirms third-person present simple.",
                    "reviewed_by": "reviewer@example.test",
                    "reviewed_at": "2026-09-17T10:00:00Z",
                },
                {
                    "mapping_id": "map_reject",
                    "reviewer_decision": "REJECT",
                    "reviewer_note": "Context is not present simple.",
                    "reviewed_by": "reviewer@example.test",
                    "reviewed_at": "2026-09-17T10:01:00Z",
                },
                {
                    "mapping_id": "map_review",
                    "reviewer_decision": "NEEDS_REVIEW",
                    "reviewer_note": "Insufficient sanitized context.",
                    "reviewed_by": "",
                    "reviewed_at": "",
                },
            ]
            _write_csv(
                workspace / "review" / "error_skill_mapping_review_decisions.csv",
                decisions,
            )
            result = apply_review_decisions(**paths["apply"])

            self.assertTrue(result.report["validation"]["passed"])
            self.assertEqual(result.report["approved_mappings"], 1)
            self.assertEqual(result.report["rejected_mappings"], 1)
            self.assertEqual(result.report["needs_review_mappings"], 1)
            self.assertEqual(result.report["misconception_evidence_before"], 3)
            self.assertEqual(result.report["misconception_evidence_after"], 1)
            self.assertTrue(result.report["taxonomy"]["taxonomy_unchanged"])
            accepted = _read_jsonl(workspace / "curated" / "accepted_error_skill_mappings.jsonl")
            rejected = _read_jsonl(workspace / "curated" / "rejected_error_skill_mappings.jsonl")
            unresolved = _read_jsonl(workspace / "curated" / "unresolved_error_skill_mappings.jsonl")
            self.assertEqual(accepted[0]["status"], "accepted")
            self.assertEqual(accepted[0]["review_status"], "approved")
            self.assertEqual(rejected[0]["status"], "rejected")
            self.assertEqual(unresolved[0]["review_status"], "needs_review")
            candidate = _read_jsonl(workspace / "candidate_misconceptions.jsonl")[0]
            self.assertEqual(candidate["source_evidence_count"], 1)

    def test_invalid_decision_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            paths = _fixture(workspace)
            prepare_review_package(**paths["prepare"])
            decision_path = workspace / "review" / "error_skill_mapping_review_decisions.csv"
            rows = _read_csv(decision_path)
            rows[0]["reviewer_decision"] = "YES"
            _write_csv(decision_path, rows)

            result = apply_review_decisions(**paths["apply"])

            self.assertFalse(result.report["validation"]["passed"])
            self.assertEqual(result.report["invalid_reviewer_decisions"], 1)

    def test_unsafe_group_propagation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            paths = _fixture(workspace)
            prepare_review_package(**paths["prepare"])
            group = _read_csv(
                workspace / "review" / "error_skill_mapping_review_groups.csv",
            )[0]
            _write_csv(
                workspace / "review" / "review_group_decision.csv",
                [
                    {
                        "review_group_id": group["review_group_id"],
                        "reviewer_decision": "APPROVE",
                        "reviewer_note": "Unsafe synthetic bulk approval.",
                        "reviewed_by": "reviewer@example.test",
                        "reviewed_at": "2026-09-17T10:00:00Z",
                    }
                ],
            )

            result = apply_review_decisions(**paths["apply"])

            self.assertFalse(result.report["validation"]["passed"])
            self.assertIn(
                "unsafe_group_propagation",
                {issue["code"] for issue in result.report["validation"]["issues"]},
            )

    def test_safe_group_decision_propagates_when_explicitly_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            paths = _fixture(workspace)
            prepare_review_package(**paths["prepare"])
            groups_path = workspace / "review" / "error_skill_mapping_review_groups.csv"
            groups = _read_csv(groups_path)
            groups[0]["group_can_share_decision"] = "true"
            _write_csv(groups_path, groups)
            _write_csv(
                workspace / "review" / "error_skill_mapping_review_decisions.csv",
                [],
                fields=[
                    "mapping_id",
                    "reviewer_decision",
                    "reviewer_note",
                    "reviewed_by",
                    "reviewed_at",
                ],
            )
            _write_csv(
                workspace / "review" / "review_group_decision.csv",
                [
                    {
                        "review_group_id": groups[0]["review_group_id"],
                        "reviewer_decision": "APPROVE",
                        "reviewer_note": "Synthetic safe group approval.",
                        "reviewed_by": "reviewer@example.test",
                        "reviewed_at": "2026-09-17T10:00:00Z",
                    }
                ],
            )

            result = apply_review_decisions(**paths["apply"])

            self.assertTrue(result.report["validation"]["passed"])
            self.assertEqual(result.report["approved_mappings"], 3)
            self.assertEqual(result.report["group_approved_rows"], 3)


def _fixture(workspace: Path) -> dict[str, dict]:
    mappings_path = workspace / "mappings.jsonl"
    normalized_path = workspace / "normalized.jsonl"
    errors_path = workspace / "errors.jsonl"
    misconceptions_path = workspace / "candidate_misconceptions.jsonl"
    error_report_path = workspace / "error_report.json"
    misconception_report_path = workspace / "misconception_report.json"
    misconception_review_path = workspace / "misconception_review.csv"
    review_dir = workspace / "review"
    curated_dir = workspace / "curated"
    report_path = workspace / "reports" / "review.json"
    mapping_ids = ["map_approve", "map_reject", "map_review"]

    mappings = []
    normalized = []
    errors = []
    evidence = []
    for index, mapping_id in enumerate(mapping_ids):
        normalized_id = f"norm_{index}"
        error_id = f"error_{index}"
        record_id = f"record_{index}"
        mappings.append(
            {
                "mapping_id": mapping_id,
                "normalized_error_id": normalized_id,
                "error_instance_id": error_id,
                "source_record_id": record_id,
                "source_key": "clc_fce",
                "canonical_skill_id": "grammar.present_simple.third_person_s",
                "status": "candidate",
                "confidence": 0.62,
                "reason": "Agreement label is broader than the atomic skill.",
                "review_status": "pending",
                "provenance": {
                    "skill_mapping_rule_version": "rules_v1",
                    "source_label": "AGV",
                },
            }
        )
        normalized.append(
            {
                "normalized_error_id": normalized_id,
                "category": "subject_verb_agreement",
                "subtype": "clc_agv",
            }
        )
        errors.append(
            {
                "error_instance_id": error_id,
                "span": {
                    "span_kind": "json_char_offsets",
                    "start_char": index,
                    "end_char": index + 1,
                },
                "correction": {
                    "correction_type": "replacement",
                    "correction_length": 2,
                    "correction_fingerprint": "sha256:" + str(index) * 64,
                },
            }
        )
        evidence.append(
            {
                "normalized_error_id": normalized_id,
                "error_instance_id": error_id,
                "source_record_id": record_id,
                "source_key": "clc_fce",
                "source_label": "AGV",
                "proficiency_label": "FCE_B2",
                "mapping_id": mapping_id,
                "mapping_confidence": 0.62,
            }
        )
    _write_jsonl(mappings_path, mappings)
    _write_jsonl(normalized_path, normalized)
    _write_jsonl(errors_path, errors)
    _write_jsonl(
        misconceptions_path,
        [
            {
                "misconception_id": "mis_test",
                "canonical_skill_id": "grammar.present_simple.third_person_s",
                "name": "Possible agreement issue",
                "description": "Synthetic candidate.",
                "error_category": "subject_verb_agreement",
                "error_subtype": "clc_agv",
                "source_labels": ["AGV"],
                "expected_pattern": "Expected agreement.",
                "observed_pattern": "Observed agreement label.",
                "diagnostic_rule": "Synthetic diagnostic rule.",
                "source_evidence_count": 3,
                "source_distribution": {"clc_fce": 3},
                "frequency": 0.3,
                "frequency_scope": "synthetic",
                "source_frequencies": {"clc_fce": 0.3},
                "proficiency_distribution": {"FCE_B2": 3},
                "evidence_links": evidence,
                "severity": "low",
                "confidence": 0.7,
                "status": "candidate",
                "review_status": "pending",
                "reason": "Synthetic.",
                "provenance": {},
                "version": "misconceptions_v1",
            }
        ],
    )
    error_report_path.write_text(
        json.dumps({"source_error_counts": {"clc_fce": 10}}),
        encoding="utf-8",
    )
    misconception_report_path.write_text(
        json.dumps({"inputs": {}, "validation": {}}),
        encoding="utf-8",
    )
    _write_csv(
        misconception_review_path,
        [{"misconception_id": "mis_test", "source_evidence_count": "3"}],
    )
    review_dir.mkdir(parents=True)
    _write_csv(
        review_dir / "error_skill_mapping_review.csv",
        [{"review_row_id": "legacy", "source_label": "AGV"}],
    )
    return {
        "prepare": {
            "mappings_path": mappings_path,
            "normalized_errors_path": normalized_path,
            "error_instance_paths": {"clc_fce": errors_path},
            "misconceptions_path": misconceptions_path,
            "review_dir": review_dir,
        },
        "apply": {
            "mappings_path": mappings_path,
            "misconceptions_path": misconceptions_path,
            "error_report_path": error_report_path,
            "misconception_report_path": misconception_report_path,
            "misconception_review_path": misconception_review_path,
            "review_dir": review_dir,
            "curated_dir": curated_dir,
            "report_path": report_path,
        },
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write_csv(
    path: Path,
    rows: list[dict[str, str]],
    *,
    fields: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or (list(rows[0]) if rows else [
        "review_group_id",
        "reviewer_decision",
        "reviewer_note",
        "reviewed_by",
        "reviewed_at",
    ])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


if __name__ == "__main__":
    unittest.main()
