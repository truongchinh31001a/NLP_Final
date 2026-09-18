from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from knowledge_core.normalization.corpus_errors.processor import (
    run_corpus_error_normalization,
)
from knowledge_core.normalization.corpus_errors.rules import (
    build_error_skill_mapping,
    normalize_error_instance,
    normalize_error_payload,
)
from knowledge_core.normalization.error_taxonomy import (
    ErrorCorrection,
    ErrorInstance,
    SourceNativeErrorLabel,
    TextSpan,
    make_error_instance_id,
    make_source_record_id,
)
from knowledge_core.normalization.error_taxonomy.policy import fingerprint_text


class CorpusErrorNormalizationTests(unittest.TestCase):
    def test_clc_known_labels_normalize_conservatively(self) -> None:
        tv = normalize_error_payload(_error_payload("clc_fce", "TV"))
        self.assertEqual(tv["category"], "verb_tense")
        self.assertEqual(tv["status"], "exact")
        self.assertEqual(tv["canonical_skill_candidates"], [])

        agv = normalize_error_payload(_error_payload("clc_fce", "AGV"))
        self.assertEqual(agv["category"], "subject_verb_agreement")
        self.assertEqual(agv["canonical_skill_candidates"], ["grammar.present_simple.third_person_s"])

        compound = normalize_error_payload(_error_payload("clc_fce", "FN(RN)"))
        self.assertEqual(compound["status"], "ambiguous")
        self.assertEqual(compound["review_status"], "needs_review")

    def test_efcamdat_known_and_unknown_labels(self) -> None:
        spelling = normalize_error_payload(_error_payload("efcamdat", "SP"))
        self.assertEqual(spelling["category"], "spelling")
        self.assertEqual(spelling["status"], "exact")

        undefined = normalize_error_payload(_error_payload("efcamdat", "undefined"))
        self.assertEqual(undefined["category"], "unmapped")
        self.assertEqual(undefined["status"], "unmapped")

        multi = normalize_error_payload(_error_payload("efcamdat", "VT and WC"))
        self.assertEqual(multi["category"], "other")
        self.assertEqual(multi["status"], "ambiguous")

    def test_skill_mapping_model_rejects_unknown_skills(self) -> None:
        error = _error_model("clc_fce", "AGV")
        normalized = normalize_error_instance(error)
        mappings = build_error_skill_mapping(normalized, error)
        self.assertEqual(len(mappings), 1)
        self.assertEqual(mappings[0].canonical_skill_id, "grammar.present_simple.third_person_s")
        self.assertEqual(mappings[0].status, "candidate")

    def test_pipeline_writes_outputs_and_review_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            clc_path = workspace / "clc_errors.jsonl"
            efcamdat_path = workspace / "efcamdat_errors.jsonl"
            clc_path.write_text(
                json.dumps(_error_payload("clc_fce", "AGV"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            efcamdat_path.write_text(
                json.dumps(_error_payload("efcamdat", "undefined"), sort_keys=True) + "\n",
                encoding="utf-8",
            )

            result = run_corpus_error_normalization(
                input_paths={"clc_fce": clc_path, "efcamdat": efcamdat_path},
                interim_dir=workspace / "interim",
                review_dir=workspace / "review",
                reports_dir=workspace / "reports",
            )

            self.assertTrue(result.report["validation"]["passed"])
            self.assertEqual(result.report["normalized_error_count"], 2)
            self.assertEqual(result.report["skill_mapping_count"], 1)
            self.assertTrue((workspace / "interim" / "normalized_error_instances.jsonl").exists())
            self.assertTrue((workspace / "interim" / "error_skill_mappings.jsonl").exists())
            review_text = (workspace / "review" / "error_skill_mapping_review.csv").read_text(
                encoding="utf-8",
            )
            self.assertIn("undefined", review_text)
            self.assertNotIn("learner text", review_text)


def _error_payload(source_key: str, label: str) -> dict[str, object]:
    return _error_model(source_key, label).model_dump(mode="json")


def _error_model(source_key: str, label: str) -> ErrorInstance:
    fingerprint, length = fingerprint_text("synthetic")
    source_record_id = make_source_record_id(
        source_key=source_key,
        native_record_id=f"{source_key}-record-1",
    )
    error_id = make_error_instance_id(
        source_key=source_key,
        source_record_id=source_record_id,
        native_error_id=f"{label}-1",
        label_payload={"label": label},
    )
    return ErrorInstance(
        error_instance_id=error_id,
        source_record_id=source_record_id,
        source_key=source_key,  # type: ignore[arg-type]
        native_error_id=f"{label}-1",
        source_native_label=SourceNativeErrorLabel(
            label_system=f"{source_key}_error_code",
            label=label,
        ),
        span=TextSpan(
            span_kind="efcamdat_selection_text",
            selection_fingerprint=fingerprint,
            selected_text_length=length,
        ),
        correction=ErrorCorrection(
            correction_type="replacement",
            correction_fingerprint=fingerprint,
            correction_length=length,
        ),
    )


if __name__ == "__main__":
    unittest.main()
