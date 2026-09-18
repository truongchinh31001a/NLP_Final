from __future__ import annotations

import unittest

from pydantic import ValidationError

from knowledge_core.normalization.error_taxonomy import (
    ErrorCorrection,
    ErrorInstance,
    LearnerCorpusSourceRecord,
    NormalizedErrorInstance,
    SourceNativeErrorLabel,
    TextSpan,
    make_error_instance_id,
    make_normalized_error_id,
    make_review_row_id,
    make_source_record_id,
)
from knowledge_core.normalization.error_taxonomy.ids import stable_hash
from knowledge_core.normalization.error_taxonomy.policy import fingerprint_text
from knowledge_core.normalization.error_taxonomy.validator import (
    validate_error_schema_records,
)
from knowledge_core.normalization.error_taxonomy.vocabulary import (
    ERROR_TAXONOMY_VERSION,
    NORMALIZED_ERROR_CATEGORIES,
    NORMALIZED_ERROR_CATEGORY_DEFINITIONS,
)


class ErrorTaxonomySchemaTests(unittest.TestCase):
    def test_vocabulary_is_frozen_and_documented(self) -> None:
        self.assertEqual(ERROR_TAXONOMY_VERSION, "error_taxonomy_v1")
        self.assertEqual(len(NORMALIZED_ERROR_CATEGORIES), len(set(NORMALIZED_ERROR_CATEGORIES)))
        self.assertIn("subject_verb_agreement", NORMALIZED_ERROR_CATEGORIES)
        self.assertIn("unmapped", NORMALIZED_ERROR_CATEGORIES)
        self.assertEqual(
            set(NORMALIZED_ERROR_CATEGORIES),
            set(NORMALIZED_ERROR_CATEGORY_DEFINITIONS),
        )

    def test_deterministic_ids_are_stable(self) -> None:
        first = make_source_record_id(
            source_key="clc_fce",
            native_record_id="script-1-answer-2",
            split="train",
        )
        second = make_source_record_id(
            split="train",
            native_record_id="script-1-answer-2",
            source_key="clc_fce",
        )
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("src__clc_fce__"))

        error_id = make_error_instance_id(
            source_key="clc_fce",
            source_record_id=first,
            native_error_id="e1",
            span_payload={"start_char": 2, "end_char": 4},
            label_payload={"label": "M:DET"},
        )
        self.assertEqual(
            error_id,
            make_error_instance_id(
                label_payload={"label": "M:DET"},
                span_payload={"end_char": 4, "start_char": 2},
                native_error_id="e1",
                source_record_id=first,
                source_key="clc_fce",
            ),
        )
        self.assertTrue(
            make_normalized_error_id(
                error_instance_id=error_id,
                category="article",
            ).startswith("normerr__article__"),
        )
        self.assertTrue(
            make_review_row_id(
                review_queue="clc_fce_error_review",
                entity_id=error_id,
            ).startswith("review__clc_fce_error_review__"),
        )

    def test_span_policies_cover_source_representations(self) -> None:
        fingerprint, length = fingerprint_text("synthetic")
        json_span = TextSpan(
            span_kind="json_char_offsets",
            source_field="answer",
            start_char=1,
            end_char=4,
        )
        self.assertEqual(json_span.start_char, 1)

        m2_span = TextSpan(
            span_kind="m2_token_offsets",
            token_start=2,
            token_end=2,
        )
        self.assertEqual(m2_span.token_end, 2)

        insertion_span = TextSpan(
            span_kind="json_char_offsets",
            source_field="text",
            start_char=4,
            end_char=4,
        )
        self.assertEqual(insertion_span.end_char, insertion_span.start_char)

        xml_span = TextSpan(
            span_kind="xml_inline_selection",
            selection_fingerprint=fingerprint,
            selected_text_length=length,
            source_markup_path="/coded_answer/e[1]",
        )
        self.assertEqual(xml_span.selection_fingerprint, fingerprint)

        efcamdat_span = TextSpan(
            span_kind="efcamdat_selection_text",
            selection_fingerprint=fingerprint,
            selected_text_length=length,
            source_markup_path="/selection/writing/text/change[1]/selection",
        )
        self.assertEqual(efcamdat_span.span_kind, "efcamdat_selection_text")

        with self.assertRaises(ValidationError):
            TextSpan(span_kind="json_char_offsets", start_char=4, end_char=1)
        with self.assertRaises(ValidationError):
            TextSpan(span_kind="efcamdat_selection_text", selected_text_length=length)

    def test_models_store_fingerprints_not_learner_text(self) -> None:
        text_fingerprint, text_length = fingerprint_text("synthetic learner text")
        correction_fingerprint, correction_length = fingerprint_text("synthetic correction")
        source_record_id = make_source_record_id(
            source_key="efcamdat",
            native_record_id="w1",
        )
        source_record = LearnerCorpusSourceRecord(
            source_record_id=source_record_id,
            source_key="efcamdat",
            native_record_id="w1",
            record_unit="writing",
            learner_id_pseudonym="learner-hash",
            document_id_pseudonym="writing-hash",
            task_id="topic-1",
            text_fingerprint=text_fingerprint,
            text_length=text_length,
            metadata={"course_level": "1"},
        )

        error_id = make_error_instance_id(
            source_key="efcamdat",
            source_record_id=source_record_id,
            native_error_id="change-1",
        )
        error = ErrorInstance(
            error_instance_id=error_id,
            source_record_id=source_record_id,
            source_key="efcamdat",
            native_error_id="change-1",
            source_native_label=SourceNativeErrorLabel(
                label_system="efcamdat_symbol",
                label="AGV",
            ),
            span=TextSpan(
                span_kind="efcamdat_selection_text",
                selection_fingerprint=text_fingerprint,
                selected_text_length=text_length,
            ),
            correction=ErrorCorrection(
                correction_type="replacement",
                correction_fingerprint=correction_fingerprint,
                correction_length=correction_length,
            ),
            provenance={"source_file": "data/raw/EFCAMDAT/EFCAMDAT_Database.xml"},
        )
        normalized = NormalizedErrorInstance(
            normalized_error_id=make_normalized_error_id(
                error_instance_id=error_id,
                category="subject_verb_agreement",
            ),
            error_instance_id=error_id,
            source_record_id=source_record_id,
            source_key="efcamdat",
            category="subject_verb_agreement",
            subtype="agreement_verbal",
            status="candidate",
            confidence=0.62,
            reason="Source-native label is compatible with agreement; requires review.",
            canonical_skill_candidates=["grammar.present_simple.third_person_s"],
        )

        result = validate_error_schema_records(
            source_records=[source_record],
            error_instances=[error],
            normalized_errors=[normalized],
        )

        self.assertTrue(result.passed)
        self.assertTrue(result.no_raw_learner_text)
        self.assertEqual(result.source_record_count, 1)
        self.assertEqual(result.error_instance_count, 1)
        self.assertEqual(result.normalized_error_count, 1)

    def test_privacy_policy_rejects_raw_free_text_fields(self) -> None:
        fingerprint, length = fingerprint_text("synthetic")
        with self.assertRaises(ValidationError):
            LearnerCorpusSourceRecord(
                source_record_id="src__clc_fce__x",
                source_key="clc_fce",
                native_record_id="x",
                record_unit="answer",
                text_fingerprint=fingerprint,
                text_length=length,
                metadata={"original_text": "must not be stored"},
            )

        with self.assertRaises(ValidationError):
            ErrorCorrection(
                correction_type="replacement",
                correction_fingerprint=fingerprint,
                correction_length=length,
                metadata={"corrected_text": "must not be stored"},
            )

    def test_validator_reports_reference_and_skill_errors(self) -> None:
        fingerprint, length = fingerprint_text("synthetic")
        source_record = LearnerCorpusSourceRecord(
            source_record_id="src__clc_fce__1",
            source_key="clc_fce",
            native_record_id="1",
            record_unit="answer",
            text_fingerprint=fingerprint,
            text_length=length,
        )
        error = ErrorInstance(
            error_instance_id="err__clc_fce__1",
            source_record_id="src__clc_fce__missing",
            source_key="clc_fce",
            span=TextSpan(span_kind="json_char_offsets", start_char=0, end_char=1),
        )
        normalized = NormalizedErrorInstance(
            normalized_error_id="normerr__article__1",
            error_instance_id="err__clc_fce__missing",
            source_record_id=source_record.source_record_id,
            source_key="clc_fce",
            category="article",
            status="candidate",
            confidence=0.5,
            reason="Synthetic candidate.",
            canonical_skill_candidates=["grammar.fake.skill"],
        )

        result = validate_error_schema_records(
            source_records=[source_record],
            error_instances=[error],
            normalized_errors=[normalized],
        )

        self.assertFalse(result.passed)
        codes = {issue.code for issue in result.issues}
        self.assertIn("missing_source_record_reference", codes)
        self.assertIn("missing_error_instance_reference", codes)
        self.assertIn("invalid_canonical_skill_candidate", codes)

    def test_stable_hash_uses_canonical_json(self) -> None:
        self.assertEqual(
            stable_hash({"b": 2, "a": 1}),
            stable_hash({"a": 1, "b": 2}),
        )


if __name__ == "__main__":
    unittest.main()
