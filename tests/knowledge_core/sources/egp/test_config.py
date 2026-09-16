from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from knowledge_core.sources.egp.config import EGPConfigError, load_egp_config


class EGPConfigTests(unittest.TestCase):
    def test_default_config_loads_v1_categories(self) -> None:
        config = load_egp_config()

        self.assertEqual(config.source.name, "english_grammar_profile")
        self.assertEqual(config.source.level, "ALL")
        self.assertEqual(len(config.categories), 14)
        self.assertEqual(config.categories[0].id, "present_simple")
        self.assertEqual(
            config.categories[0].raw_path,
            "Tenses/Present Simple/present_simple.xlsx",
        )
        self.assertEqual(
            config.category_by_id()["present_perfect_simple"].canonical_parent_hint,
            "grammar.tenses.present_perfect",
        )

    def test_config_rejects_duplicate_category_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "egp_categories.yaml"
            path.write_text(
                """
source:
  name: english_grammar_profile
  level: ALL
categories:
  - id: present_simple
    query: present simple
  - id: present_simple
    query: present simple again
""",
                encoding="utf-8",
            )

            with self.assertRaises(EGPConfigError):
                load_egp_config(path)

    def test_config_rejects_raw_paths_outside_raw_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "egp_categories.yaml"
            path.write_text(
                """
source:
  name: english_grammar_profile
  level: ALL
categories:
  - id: present_simple
    query: present simple
    raw_path: ../present_simple.xlsx
""",
                encoding="utf-8",
            )

            with self.assertRaises(EGPConfigError):
                load_egp_config(path)

    def test_config_rejects_unknown_category_selection(self) -> None:
        config = load_egp_config()

        with self.assertRaises(KeyError):
            config.select_categories("not_a_category")


if __name__ == "__main__":
    unittest.main()
