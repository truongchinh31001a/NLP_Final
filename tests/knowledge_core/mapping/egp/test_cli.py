from __future__ import annotations

import unittest

from knowledge_core.mapping.egp.cli import build_parser
from knowledge_core.sources.egp.paths import DEFAULT_INTERIM_GRAMMAR_DIR


class EGPMappingCLITests(unittest.TestCase):
    def test_common_options_work_before_subcommand(self) -> None:
        args = build_parser().parse_args(["--dry-run", "--category", "articles", "run"])

        self.assertEqual(args.command, "run")
        self.assertTrue(args.dry_run)
        self.assertEqual(args.category, "articles")
        self.assertEqual(args.interim_dir, str(DEFAULT_INTERIM_GRAMMAR_DIR))

    def test_common_options_work_after_subcommand(self) -> None:
        args = build_parser().parse_args(["run", "--dry-run", "--category", "articles"])

        self.assertEqual(args.command, "run")
        self.assertTrue(args.dry_run)
        self.assertEqual(args.category, "articles")


if __name__ == "__main__":
    unittest.main()
