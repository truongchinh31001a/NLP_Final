from __future__ import annotations

import unittest

from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILLS
from knowledge_core.relationships.taxonomy import (
    build_grammar_taxonomy,
    is_immediate_parent,
)


class GrammarTaxonomyTests(unittest.TestCase):
    def test_taxonomy_derives_all_atomic_skills_without_adding_skills(self) -> None:
        taxonomy = build_grammar_taxonomy(CANONICAL_GRAMMAR_V1_SKILLS)

        self.assertEqual(len(taxonomy.atomic_skill_ids), 43)
        self.assertEqual(tuple(CANONICAL_GRAMMAR_V1_SKILLS), taxonomy.atomic_skill_ids)
        self.assertEqual(taxonomy.root_id, "grammar")
        self.assertIn("grammar.present_simple", taxonomy.group_node_ids)
        self.assertIn("grammar.present_simple", taxonomy.children_by_parent["grammar"])

    def test_immediate_parent_relationships_match_skill_namespace(self) -> None:
        taxonomy = build_grammar_taxonomy(CANONICAL_GRAMMAR_V1_SKILLS)

        self.assertEqual(
            taxonomy.parent_by_node["grammar.present_simple.affirmative"],
            "grammar.present_simple",
        )
        self.assertTrue(
            is_immediate_parent(
                "grammar.present_simple",
                "grammar.present_simple.affirmative",
            ),
        )
        self.assertFalse(
            is_immediate_parent(
                "grammar",
                "grammar.present_simple.affirmative",
            ),
        )


if __name__ == "__main__":
    unittest.main()
