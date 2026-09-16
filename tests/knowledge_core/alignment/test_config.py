from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from knowledge_core.alignment.config import (
    KnowledgeAlignmentConfigError,
    load_alignment_config,
)


class AlignmentConfigTests(unittest.TestCase):
    def test_default_config_loads_rules(self) -> None:
        config = load_alignment_config()

        self.assertIn("exact", config.egp.establishing_statuses)
        self.assertEqual(config.cefr.grammatical_accuracy_scale, "grammatical_accuracy")
        self.assertGreater(len(config.objective_alignment.rules), 0)

    def test_unknown_skill_rule_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "rules.yaml"
            path.write_text(
                """
objective_alignment:
  rules:
    - canonical_skill_id: grammar.not_real.skill
      direct_terms:
        - fixture
""",
                encoding="utf-8",
            )

            with self.assertRaises(KnowledgeAlignmentConfigError):
                load_alignment_config(path)


if __name__ == "__main__":
    unittest.main()

