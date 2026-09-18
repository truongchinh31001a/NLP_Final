from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from knowledge_core.misconceptions.models import (
    MisconceptionCandidate,
    MisconceptionEvidenceLink,
)
from knowledge_core.misconceptions.processor import run_misconception_mining
from knowledge_core.normalization.corpus_errors.rules import (
    normalize_error_payload,
    skill_mapping_payloads,
)
from tests.knowledge_core.normalization.test_corpus_errors import _error_payload


class MisconceptionMiningTests(unittest.TestCase):
    def test_accepted_candidate_requires_approved_review(self) -> None:
        link = MisconceptionEvidenceLink(
            normalized_error_id="normerr__subject_verb_agreement__1",
            error_instance_id="err__clc_fce__1",
            source_record_id="src__clc_fce__1",
            source_key="clc_fce",
            mapping_id="errskill__1",
            mapping_confidence=0.62,
        )
        with self.assertRaises(ValidationError):
            MisconceptionCandidate(
                misconception_id="mis_1",
                canonical_skill_id="grammar.present_simple.third_person_s",
                name="Possible agreement issue",
                description="Synthetic candidate.",
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
                status="accepted",
                review_status="pending",
                reason="Synthetic.",
            )

    def test_pipeline_mines_candidate_and_empty_accepted_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            normalized_path = workspace / "normalized.jsonl"
            mappings_path = workspace / "mappings.jsonl"
            report_path = workspace / "error_report.json"
            source_records_path = workspace / "source_records.jsonl"

            error_payload = _error_payload("clc_fce", "AGV")
            normalized_payload = normalize_error_payload(error_payload)
            mapping_payload = skill_mapping_payloads(normalized_payload, error_payload)[0]
            normalized_path.write_text(
                json.dumps(normalized_payload, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            mappings_path.write_text(
                json.dumps(mapping_payload, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            report_path.write_text(
                json.dumps({"source_error_counts": {"clc_fce": 10, "efcamdat": 0}}),
                encoding="utf-8",
            )
            source_records_path.write_text(
                json.dumps(
                    {
                        "source_record_id": normalized_payload["source_record_id"],
                        "source_key": "clc_fce",
                        "native_record_id": "script-1",
                        "record_unit": "answer",
                        "proficiency_label": "FCE_B2",
                        "task_id": "0102:q1",
                        "split": "train",
                        "text_fingerprint": "sha256:" + "a" * 64,
                        "text_length": 42,
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            result = run_misconception_mining(
                normalized_errors_path=normalized_path,
                error_skill_mappings_path=mappings_path,
                error_normalization_report=report_path,
                source_record_paths={"clc_fce": source_records_path},
                interim_dir=workspace / "interim",
                curated_dir=workspace / "curated",
                review_dir=workspace / "review",
                reports_dir=workspace / "reports",
            )

            self.assertTrue(result.report["validation"]["passed"])
            self.assertEqual(result.report["candidate_count"], 1)
            self.assertEqual(result.report["accepted_count"], 0)
            candidate = result.candidates[0]
            self.assertEqual(
                candidate.canonical_skill_id,
                "grammar.present_simple.third_person_s",
            )
            self.assertEqual(candidate.source_evidence_count, 1)
            self.assertEqual(candidate.proficiency_distribution, {"FCE_B2": 1})
            self.assertTrue(
                (workspace / "interim" / "candidate_misconceptions.jsonl").exists(),
            )
            self.assertEqual(
                (workspace / "curated" / "accepted_misconceptions.jsonl").read_text(
                    encoding="utf-8",
                ),
                "",
            )


if __name__ == "__main__":
    unittest.main()
