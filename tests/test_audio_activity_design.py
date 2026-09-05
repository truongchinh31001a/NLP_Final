import json
import unittest
from pathlib import Path

from scripts.run_evals import evaluate_audio_activity_contract


class AudioActivityDesignTests(unittest.TestCase):
    def setUp(self) -> None:
        self.design = Path("docs/audio_activity_design.md").read_text(encoding="utf-8")
        self.cases = json.loads(
            Path("evals/datasets/audio_activity_cases.json").read_text(
                encoding="utf-8",
            )
        )

    def test_design_records_phase_21_decisions(self) -> None:
        required_terms = [
            "browser Web Speech API",
            "browser SpeechSynthesis",
            "LearningActivity.metadata",
            "POST /api/activities/{activity_id}/submit",
            "No raw audio is stored by default",
        ]

        for term in required_terms:
            with self.subTest(term=term):
                self.assertIn(term, self.design)

    def test_dataset_covers_listening_and_speaking(self) -> None:
        self.assertGreaterEqual(len(self.cases), 4)
        activity_types = {case["activity_type"] for case in self.cases}

        self.assertEqual(activity_types, {"LISTENING", "SPEAKING"})

    def test_listening_cases_define_metadata_and_submit_contract(self) -> None:
        listening_cases = [
            case for case in self.cases if case["activity_type"] == "LISTENING"
        ]
        self.assertGreaterEqual(len(listening_cases), 2)

        for case in listening_cases:
            metadata = case["metadata"]
            submission = case["submission"]
            with self.subTest(case_id=case["case_id"]):
                self.assertEqual(metadata["mode"], "listening")
                self.assertEqual(metadata["audio_source"]["kind"], "browser_tts")
                self.assertTrue(metadata["transcript"])
                self.assertTrue(metadata["target_skills"])
                self.assertTrue(metadata["comprehension_prompts"])
                self.assertIn("max_replays", metadata["replay_policy"])
                self.assertIn("answers", submission)
                self.assertNotIn("audio", submission)
                self.assertFalse(metadata["privacy"]["store_raw_audio_by_default"])

    def test_speaking_cases_define_metadata_and_submit_contract(self) -> None:
        speaking_cases = [
            case for case in self.cases if case["activity_type"] == "SPEAKING"
        ]
        self.assertGreaterEqual(len(speaking_cases), 2)

        for case in speaking_cases:
            metadata = case["metadata"]
            submission = case["submission"]
            with self.subTest(case_id=case["case_id"]):
                self.assertEqual(metadata["mode"], "speaking")
                self.assertTrue(metadata["prompt"])
                self.assertTrue(metadata["expected_patterns"])
                self.assertIn("pronunciation", metadata["rubric"])
                self.assertIn("fluency", metadata["rubric"])
                self.assertIn("grammar", metadata["rubric"])
                self.assertIn("task_completion", metadata["rubric"])
                self.assertGreater(metadata["retry_policy"]["max_attempts"], 0)
                self.assertEqual(metadata["stt"]["preferred"], "browser_web_speech")
                self.assertTrue(metadata["stt"]["allow_manual_transcript"])
                self.assertTrue(submission["transcript"])
                self.assertNotIn("audio", submission)
                self.assertFalse(metadata["privacy"]["store_raw_audio_by_default"])

    def test_audio_activity_eval_passes_dataset(self) -> None:
        report = evaluate_audio_activity_contract()

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["score"], 1.0)
        self.assertEqual(report["total"], len(self.cases))


if __name__ == "__main__":
    unittest.main()
