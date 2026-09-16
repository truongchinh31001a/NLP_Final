from __future__ import annotations

import unittest

from knowledge_core.assessment.cli import build_parser
from knowledge_core.assessment.config import DEFAULT_ASSESSMENT_CONFIG_PATH, load_assessment_config


class AssessmentConfigCLITests(unittest.TestCase):
    def test_default_config_loads_thresholds_and_paths(self) -> None:
        config = load_assessment_config()

        self.assertEqual(
            config.inputs.skill_evidence_profiles,
            "data/interim/knowledge_alignment/grammar_skill_evidence.jsonl",
        )
        self.assertEqual(config.outputs.assessment_dir, "data/curated/assessment")
        self.assertEqual(
            config.thresholds.form_accuracy.recommended_threshold,
            0.80,
        )
        self.assertEqual(config.defaults.threshold_source, "curated_v1_default")

    def test_cli_accepts_common_options_before_subcommand(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "--dry-run",
                "--skill",
                "grammar.present_simple.questions",
                "validate",
            ],
        )

        self.assertEqual(args.command, "validate")
        self.assertTrue(args.dry_run)
        self.assertEqual(args.skill, "grammar.present_simple.questions")

    def test_cli_accepts_common_options_after_subcommand(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "report",
                "--criterion-type",
                "form_accuracy",
            ],
        )

        self.assertEqual(args.command, "report")
        self.assertEqual(args.criterion_type, "form_accuracy")
        self.assertEqual(args.config, str(DEFAULT_ASSESSMENT_CONFIG_PATH))


if __name__ == "__main__":
    unittest.main()
