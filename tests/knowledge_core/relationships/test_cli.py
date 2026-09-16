from __future__ import annotations

import unittest

from knowledge_core.relationships.cli import build_parser
from knowledge_core.relationships.config import DEFAULT_RELATIONSHIP_CONFIG_PATH


class RelationshipCLITests(unittest.TestCase):
    def test_common_options_work_before_subcommand(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "--dry-run",
                "--show-path",
                "grammar.present_perfect.experience",
                "validate",
            ],
        )

        self.assertEqual(args.command, "validate")
        self.assertTrue(args.dry_run)
        self.assertEqual(
            args.show_path,
            "grammar.present_perfect.experience",
        )

    def test_common_options_work_after_subcommand(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "report",
                "--relation",
                "prerequisite_of",
                "--skill",
                "grammar.passive.present_simple",
            ],
        )

        self.assertEqual(args.command, "report")
        self.assertEqual(args.relation, "prerequisite_of")
        self.assertEqual(args.skill, "grammar.passive.present_simple")
        self.assertEqual(args.config, str(DEFAULT_RELATIONSHIP_CONFIG_PATH))


if __name__ == "__main__":
    unittest.main()
