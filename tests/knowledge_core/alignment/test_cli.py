from __future__ import annotations

import unittest

from knowledge_core.alignment.cli import build_parser
from knowledge_core.alignment.config import DEFAULT_ALIGNMENT_CONFIG_PATH


class AlignmentCLITests(unittest.TestCase):
    def test_common_options_work_before_subcommand(self) -> None:
        args = build_parser().parse_args(
            [
                "--skill",
                "grammar.present_perfect.experience",
                "--min-confidence",
                "0.75",
                "run",
            ]
        )

        self.assertEqual(args.command, "run")
        self.assertEqual(args.skill, "grammar.present_perfect.experience")
        self.assertEqual(args.min_confidence, 0.75)
        self.assertEqual(args.config, str(DEFAULT_ALIGNMENT_CONFIG_PATH))

    def test_common_options_work_after_subcommand(self) -> None:
        args = build_parser().parse_args(
            ["report", "--level", "B1", "--dry-run"]
        )

        self.assertEqual(args.command, "report")
        self.assertEqual(args.level, "B1")
        self.assertTrue(args.dry_run)


if __name__ == "__main__":
    unittest.main()

