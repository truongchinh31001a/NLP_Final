from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from knowledge_core.relationships.config import (
    GrammarRelationshipConfigError,
    load_relationship_config,
)


class RelationshipConfigTests(unittest.TestCase):
    def test_default_config_loads_curated_relationship_rules(self) -> None:
        config = load_relationship_config()

        self.assertEqual(len(config.curated_relationships), 40)
        self.assertEqual(
            config.inputs.skill_evidence_profiles,
            "data/interim/knowledge_alignment/grammar_skill_evidence.jsonl",
        )
        self.assertEqual(config.outputs.relationships_dir, "data/curated/relationships")

    def test_config_rejects_unknown_taxonomy_node(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "relationships.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "curated_relationships:",
                        "  - source: grammar.present_simple.affirmative",
                        "    target: grammar.unknown.skill",
                        "    relation_type: prerequisite_of",
                        "    reason: Invalid test relationship.",
                    ],
                ),
                encoding="utf-8",
            )

            with self.assertRaises(GrammarRelationshipConfigError):
                load_relationship_config(config_path)


if __name__ == "__main__":
    unittest.main()
