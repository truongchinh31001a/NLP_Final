import unittest

from scripts.run_evals import (
    evaluate_explanation_grounding,
    evaluate_tutor_response_quality,
    has_repeated_menu,
    normalize_eval_text,
)


class TutorResponseEvalTests(unittest.TestCase):
    def test_offline_tutor_response_eval_passes_dataset(self) -> None:
        report = evaluate_tutor_response_quality()

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["score"], 1.0)
        case_ids = {row["case_id"] for row in report["rows"]}
        self.assertIn("learning_focus_reading", case_ids)
        self.assertIn("listening_complaint_not_focus", case_ids)
        self.assertGreaterEqual(report["response_sources"]["guided-choice"], 2)
        self.assertGreaterEqual(report["response_sources"]["activity-route"], 2)

    def test_repeated_menu_detector_catches_old_template(self) -> None:
        old_reply = "Ban muon tap noi, nghe, doc hay viet?"

        self.assertTrue(has_repeated_menu(normalize_eval_text(old_reply)))

    def test_explanation_grounding_eval_requires_source_metadata(self) -> None:
        report = evaluate_explanation_grounding()

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["score"], 1.0)
        self.assertEqual(report["rows"][0]["sources"][0]["chunk_id"], "grammar_passive_002")


if __name__ == "__main__":
    unittest.main()
