from __future__ import annotations

import unittest

from knowledge_core.sources.cefr.cli import build_parser
from knowledge_core.sources.cefr.paths import DEFAULT_CEFR_PDF_PATH


class CEFRCLITests(unittest.TestCase):
    def test_common_options_work_before_subcommand(self) -> None:
        args = build_parser().parse_args(
            ["--domain", "production", "--level", "B1", "run"]
        )

        self.assertEqual(args.command, "run")
        self.assertEqual(args.domain, "production")
        self.assertEqual(args.level, "B1")
        self.assertEqual(args.pdf, str(DEFAULT_CEFR_PDF_PATH))

    def test_common_options_work_after_subcommand(self) -> None:
        args = build_parser().parse_args(
            ["run", "--section", "chapter5", "--level", "C1"]
        )

        self.assertEqual(args.command, "run")
        self.assertEqual(args.section, "chapter5")
        self.assertEqual(args.level, "C1")


if __name__ == "__main__":
    unittest.main()

