from __future__ import annotations

import unittest

from knowledge_core.alignment.models import (
    ObjectiveAlignmentConfig,
    ObjectiveRuleConfig,
)
from knowledge_core.alignment.objective_alignment import (
    SkillLevelContext,
    align_objectives_for_skill,
)
from knowledge_core.sources.cefr.models import CEFRLearningObjectiveCandidate


class ObjectiveAlignmentTests(unittest.TestCase):
    def test_direct_objective_alignment(self) -> None:
        config = ObjectiveAlignmentConfig(
            rules=[
                ObjectiveRuleConfig(
                    canonical_skill_id="grammar.modality.should_advice",
                    direct_terms=["offer advice"],
                ),
            ],
        )
        objective = objective_candidate(
            "obj_advice",
            "B1",
            "Can offer advice on simple matters within their field of experience.",
        )

        alignments = align_objectives_for_skill(
            "grammar.modality.should_advice",
            [objective],
            config,
            level_context=SkillLevelContext(
                inferred_min_level="B1",
                inferred_primary_level="B1",
            ),
        )

        self.assertEqual(len(alignments), 1)
        self.assertEqual(alignments[0].relevance, "direct")
        self.assertGreaterEqual(alignments[0].confidence, 0.8)

    def test_contextual_objective_alignment_respects_level_distance(self) -> None:
        config = ObjectiveAlignmentConfig(
            max_level_distance_for_aligned_skills=0,
            rules=[
                ObjectiveRuleConfig(
                    canonical_skill_id="grammar.present_perfect.experience",
                    contextual_terms=["personal experiences"],
                ),
            ],
        )
        b1 = objective_candidate(
            "obj_b1",
            "B1",
            "Can give detailed accounts of personal experiences.",
        )
        c2 = objective_candidate(
            "obj_c2",
            "C2",
            "Can relate descriptions of personal experiences.",
        )

        alignments = align_objectives_for_skill(
            "grammar.present_perfect.experience",
            [b1, c2],
            config,
            level_context=SkillLevelContext(
                inferred_min_level="B1",
                inferred_primary_level="B1",
            ),
        )

        self.assertEqual([alignment.objective_id for alignment in alignments], ["obj_b1"])
        self.assertEqual(alignments[0].relevance, "contextual")


def objective_candidate(
    objective_id: str,
    cefr_level: str,
    text: str,
) -> CEFRLearningObjectiveCandidate:
    return CEFRLearningObjectiveCandidate(
        objective_id=objective_id,
        source_record_id=f"cefr_{objective_id}",
        cefr_level=cefr_level,
        domain="interaction",
        scale_name="information_exchange",
        objective_text=text,
        source_descriptor_text=text,
        status="exact_source",
        confidence=1.0,
    )


if __name__ == "__main__":
    unittest.main()

