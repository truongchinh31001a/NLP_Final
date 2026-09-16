from __future__ import annotations

import unittest

from knowledge_core.sources.egp.cli import build_parser
from knowledge_core.sources.egp.paths import DEFAULT_RAW_GRAMMAR_DIR


class EGPCLITests(unittest.TestCase):
    def test_common_options_work_before_subcommand(self) -> None:
        args = build_parser().parse_args(
            ["--category", "present_simple", "--headed", "run"]
        )

        self.assertEqual(args.command, "run")
        self.assertEqual(args.category, "present_simple")
        self.assertFalse(args.headless)
        self.assertEqual(args.raw_dir, str(DEFAULT_RAW_GRAMMAR_DIR))

    def test_common_options_work_after_subcommand(self) -> None:
        args = build_parser().parse_args(
            ["run", "--category", "present_simple", "--headed"]
        )

        self.assertEqual(args.command, "run")
        self.assertEqual(args.category, "present_simple")
        self.assertFalse(args.headless)


if __name__ == "__main__":
    unittest.main()
