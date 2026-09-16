from __future__ import annotations

import unittest

from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILLS
from knowledge_core.relationships.builder import build_relationships
from knowledge_core.relationships.config import load_relationship_config
from knowledge_core.relationships.models import RelationshipRule
from knowledge_core.relationships.taxonomy import build_grammar_taxonomy


def _build_dataset(curated_relationships: list[RelationshipRule] | None = None):
    config = load_relationship_config()
    if curated_relationships is not None:
        config = config.model_copy(
            update={"curated_relationships": curated_relationships},
        )
    taxonomy = build_grammar_taxonomy(CANONICAL_GRAMMAR_V1_SKILLS)
    return build_relationships(
        taxonomy=taxonomy,
        config=config,
        skill_profiles=[],
        skill_alignments=[],
    )


class RelationshipBuilderTests(unittest.TestCase):
    def test_builds_structural_parent_edges_for_all_taxonomy_nodes(self) -> None:
        dataset = _build_dataset()
        parent_edges = [
            relationship
            for relationship in dataset.relationships
            if relationship.relation_type == "parent_of"
        ]

        self.assertEqual(len(parent_edges), len(dataset.taxonomy.all_node_ids) - 1)
        self.assertTrue(
            any(
                relationship.source_skill_id == "grammar"
                and relationship.target_skill_id == "grammar.present_simple"
                for relationship in parent_edges
            ),
        )
        self.assertTrue(
            any(
                relationship.source_skill_id == "grammar.present_simple"
                and relationship.target_skill_id
                == "grammar.present_simple.affirmative"
                for relationship in parent_edges
            ),
        )

    def test_builds_curated_edges_without_taxonomy_changes(self) -> None:
        dataset = _build_dataset()
        non_structural_edges = [
            relationship
            for relationship in dataset.relationships
            if relationship.relation_type != "parent_of"
        ]

        self.assertEqual(len(non_structural_edges), 40)
        self.assertEqual(len(dataset.taxonomy.atomic_skill_ids), 43)

    def test_bidirectional_edges_are_canonicalized(self) -> None:
        dataset = _build_dataset()
        relationship = next(
            relationship
            for relationship in dataset.relationships
            if relationship.relation_type == "related_to"
            and {
                relationship.source_skill_id,
                relationship.target_skill_id,
            }
            == {
                "grammar.modality.should_advice",
                "grammar.modality.must_obligation",
            }
        )

        self.assertTrue(relationship.bidirectional)
        self.assertEqual(
            relationship.source_skill_id,
            "grammar.modality.must_obligation",
        )
        self.assertEqual(
            relationship.target_skill_id,
            "grammar.modality.should_advice",
        )

    def test_duplicate_bidirectional_rules_merge_to_one_edge(self) -> None:
        rules = [
            RelationshipRule(
                source="grammar.modality.can_ability",
                target="grammar.modality.could_past_ability",
                relation_type="related_to",
                reason="Forward test rule.",
            ),
            RelationshipRule(
                source="grammar.modality.could_past_ability",
                target="grammar.modality.can_ability",
                relation_type="related_to",
                reason="Reverse test rule.",
            ),
        ]
        dataset = _build_dataset(curated_relationships=rules)

        related_edges = [
            relationship
            for relationship in dataset.relationships
            if relationship.relation_type == "related_to"
            and {
                relationship.source_skill_id,
                relationship.target_skill_id,
            }
            == {
                "grammar.modality.can_ability",
                "grammar.modality.could_past_ability",
            }
        ]

        self.assertEqual(len(related_edges), 1)
        self.assertEqual(
            {
                evidence.note
                for evidence in related_edges[0].evidence
                if evidence.source == "grammar_relationship_rules_v1"
            },
            {"Forward test rule.", "Reverse test rule."},
        )


if __name__ == "__main__":
    unittest.main()
