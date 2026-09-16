from __future__ import annotations

import unittest

from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILLS
from knowledge_core.relationships.builder import build_relationships
from knowledge_core.relationships.config import load_relationship_config
from knowledge_core.relationships.graph import SkillRelationshipGraph
from knowledge_core.relationships.taxonomy import build_grammar_taxonomy


def _graph() -> SkillRelationshipGraph:
    taxonomy = build_grammar_taxonomy(CANONICAL_GRAMMAR_V1_SKILLS)
    dataset = build_relationships(
        taxonomy=taxonomy,
        config=load_relationship_config(),
        skill_profiles=[],
        skill_alignments=[],
    )
    return SkillRelationshipGraph(dataset.relationships, taxonomy)


class RelationshipGraphTests(unittest.TestCase):
    def test_transitive_prerequisite_lookup(self) -> None:
        graph = _graph()

        self.assertEqual(
            set(
                graph.get_transitive_prerequisites(
                    "grammar.present_perfect.experience",
                ),
            ),
            {
                "grammar.present_perfect.past_participle",
                "grammar.present_perfect.form",
            },
        )

    def test_unlocked_skills_use_direct_hard_prerequisites(self) -> None:
        graph = _graph()
        mastered = {"grammar.present_simple.affirmative"}

        unlocked = set(graph.get_unlocked_skills(mastered))

        self.assertIn("grammar.present_simple.negative", unlocked)
        self.assertIn("grammar.present_simple.questions", unlocked)
        self.assertIn("grammar.present_simple.third_person_s", unlocked)
        self.assertTrue(
            graph.is_unlocked("grammar.present_simple.negative", mastered),
        )

    def test_learning_path_is_topological(self) -> None:
        graph = _graph()

        self.assertEqual(
            graph.get_learning_path("grammar.present_perfect.experience"),
            [
                "grammar.present_perfect.past_participle",
                "grammar.present_perfect.form",
                "grammar.present_perfect.experience",
            ],
        )

    def test_analysis_includes_all_atomic_and_curated_only_skills(self) -> None:
        graph = _graph()
        analysis = graph.analyze()

        self.assertEqual(analysis.total_atomic_skills, 43)
        self.assertEqual(len(analysis.node_summaries), 43)
        self.assertIn(
            "grammar.articles.first_vs_subsequent_mention",
            analysis.node_summaries,
        )
        self.assertEqual(analysis.isolated_skills, [])

    def test_related_and_contrast_neighbors_are_symmetric(self) -> None:
        graph = _graph()
        analysis = graph.analyze()

        self.assertIn(
            "grammar.modality.could_past_ability",
            analysis.node_summaries[
                "grammar.modality.can_ability"
            ].related_skills,
        )
        self.assertIn(
            "grammar.modality.can_permission",
            analysis.node_summaries[
                "grammar.modality.can_ability"
            ].related_skills,
        )
        self.assertIn(
            "grammar.modality.can_ability",
            analysis.node_summaries[
                "grammar.modality.can_permission"
            ].related_skills,
        )
        self.assertIn(
            "grammar.modality.can_ability",
            analysis.node_summaries[
                "grammar.modality.could_past_ability"
            ].related_skills,
        )
        self.assertIn(
            "grammar.conditionals.second",
            analysis.node_summaries["grammar.conditionals.first"].contrast_skills,
        )
        self.assertIn(
            "grammar.conditionals.first",
            analysis.node_summaries["grammar.conditionals.second"].contrast_skills,
        )


if __name__ == "__main__":
    unittest.main()
