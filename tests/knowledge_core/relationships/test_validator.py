from __future__ import annotations

import unittest

from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILLS
from knowledge_core.relationships.builder import build_relationships
from knowledge_core.relationships.config import load_relationship_config
from knowledge_core.relationships.taxonomy import build_grammar_taxonomy
from knowledge_core.relationships.validator import validate_relationships


def _valid_relationships():
    taxonomy = build_grammar_taxonomy(CANONICAL_GRAMMAR_V1_SKILLS)
    dataset = build_relationships(
        taxonomy=taxonomy,
        config=load_relationship_config(),
        skill_profiles=[],
        skill_alignments=[],
    )
    return taxonomy, dataset.relationships


class RelationshipValidatorTests(unittest.TestCase):
    def test_generated_relationships_validate_without_errors(self) -> None:
        taxonomy, relationships = _valid_relationships()

        result = validate_relationships(relationships, taxonomy)

        self.assertEqual(result.error_count, 0)
        self.assertTrue(result.prerequisite_dag_valid)

    def test_self_loop_is_rejected(self) -> None:
        taxonomy, relationships = _valid_relationships()
        original = next(
            relationship
            for relationship in relationships
            if relationship.relation_type == "prerequisite_of"
        )
        bad_relationship = original.model_copy(
            update={
                "relationship_id": "rel_self_loop",
                "target_skill_id": original.source_skill_id,
            },
        )

        result = validate_relationships([*relationships, bad_relationship], taxonomy)

        self.assertIn("self_loop", {issue.code for issue in result.issues})

    def test_unknown_skill_id_is_rejected(self) -> None:
        taxonomy, relationships = _valid_relationships()
        original = next(
            relationship
            for relationship in relationships
            if relationship.relation_type == "recommended_before"
        )
        bad_relationship = original.model_copy(
            update={
                "relationship_id": "rel_unknown_skill",
                "target_skill_id": "grammar.missing.skill",
            },
        )

        result = validate_relationships([*relationships, bad_relationship], taxonomy)

        self.assertIn("unknown_skill_id", {issue.code for issue in result.issues})
        self.assertIn("grammar.missing.skill", result.invalid_references)

    def test_duplicate_edge_is_rejected(self) -> None:
        taxonomy, relationships = _valid_relationships()
        duplicate = relationships[0].model_copy(
            update={"relationship_id": "rel_duplicate_edge"},
        )

        result = validate_relationships([*relationships, duplicate], taxonomy)

        self.assertIn("duplicate_edge", {issue.code for issue in result.issues})
        self.assertTrue(result.duplicate_edges)

    def test_prerequisite_cycle_is_rejected(self) -> None:
        taxonomy, relationships = _valid_relationships()
        forward = next(
            relationship
            for relationship in relationships
            if relationship.relation_type == "prerequisite_of"
            and relationship.source_skill_id == "grammar.present_simple.affirmative"
            and relationship.target_skill_id == "grammar.present_simple.negative"
        )
        reverse = forward.model_copy(
            update={
                "relationship_id": "rel_cycle",
                "source_skill_id": "grammar.present_simple.negative",
                "target_skill_id": "grammar.present_simple.affirmative",
            },
        )

        result = validate_relationships([*relationships, reverse], taxonomy)

        self.assertIn("prerequisite_cycle", {issue.code for issue in result.issues})
        self.assertFalse(result.prerequisite_dag_valid)

    def test_bidirectional_inverse_duplicate_is_rejected(self) -> None:
        taxonomy, relationships = _valid_relationships()
        original = next(
            relationship
            for relationship in relationships
            if relationship.relation_type == "related_to"
        )
        mirrored = original.model_copy(
            update={
                "relationship_id": "rel_mirrored_bidirectional",
                "source_skill_id": original.target_skill_id,
                "target_skill_id": original.source_skill_id,
            },
        )

        result = validate_relationships([*relationships, mirrored], taxonomy)

        self.assertIn(
            "duplicate_inverse_bidirectional_edge",
            {issue.code for issue in result.issues},
        )

    def test_structural_parent_must_be_immediate_parent(self) -> None:
        taxonomy, relationships = _valid_relationships()
        original = next(
            relationship
            for relationship in relationships
            if relationship.relation_type == "parent_of"
        )
        bad_parent = original.model_copy(
            update={
                "relationship_id": "rel_bad_parent",
                "source_skill_id": "grammar",
                "target_skill_id": "grammar.present_simple.affirmative",
            },
        )

        result = validate_relationships([*relationships, bad_parent], taxonomy)

        self.assertIn(
            "invalid_structural_parent",
            {issue.code for issue in result.issues},
        )


if __name__ == "__main__":
    unittest.main()
