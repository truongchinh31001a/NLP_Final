from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from knowledge_core.service import open_knowledge_service
from knowledge_core.storage.artifacts import load_storage_artifacts
from knowledge_core.storage.loader import load_knowledge_core


class KnowledgeServiceV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls.temp_dir.name) / "knowledge_service.db"
        load_knowledge_core(
            db_path=cls.db_path,
            artifacts=load_storage_artifacts(),
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    def test_skill_and_context(self) -> None:
        with open_knowledge_service(self.db_path) as knowledge:
            skill = knowledge.get_skill("grammar.present_simple.affirmative")
            context = knowledge.get_skill_context(skill.canonical_id)

        self.assertEqual(skill.canonical_id, context.snapshot.skill.canonical_id)
        self.assertEqual(
            [item.canonical_id for item in context.ancestors],
            ["grammar.present_simple", "grammar"],
        )

    def test_learning_path_orders_prerequisite_before_target(self) -> None:
        with open_knowledge_service(self.db_path) as knowledge:
            path = knowledge.get_learning_path("grammar.passive.agent_by")

        self.assertEqual(
            [item.canonical_id for item in path],
            ["grammar.passive.be_past_participle", "grammar.passive.agent_by"],
        )

    def test_direct_and_transitive_prerequisite_queries(self) -> None:
        with open_knowledge_service(self.db_path) as knowledge:
            direct = knowledge.get_prerequisites("grammar.passive.agent_by")
            transitive = knowledge.get_prerequisites(
                "grammar.passive.agent_by",
                transitive=True,
            )

        expected = ["grammar.passive.be_past_participle"]
        self.assertEqual([item.canonical_id for item in direct], expected)
        self.assertEqual([item.canonical_id for item in transitive], expected)

    def test_unlock_logic_uses_only_direct_prerequisites(self) -> None:
        target = "grammar.passive.agent_by"
        prerequisite = "grammar.passive.be_past_participle"
        with open_knowledge_service(self.db_path) as knowledge:
            self.assertFalse(knowledge.is_unlocked(target, set()))
            self.assertTrue(knowledge.is_unlocked(target, {prerequisite}))
            unlocked = knowledge.get_unlocked_skills({prerequisite})

        self.assertIn(target, {item.canonical_id for item in unlocked})

    def test_objective_cefr_and_assessment_profiles(self) -> None:
        skill_id = "grammar.present_simple.affirmative"
        with open_knowledge_service(self.db_path) as knowledge:
            objectives = knowledge.get_learning_objectives(skill_id)
            cefr = knowledge.get_cefr_profile(skill_id)
            assessment = knowledge.get_assessment_profile(skill_id)

        self.assertEqual(len(objectives), 5)
        self.assertEqual(cefr.cefr_primary_level, "A1")
        self.assertEqual(len(assessment.criteria), 1)
        self.assertTrue(assessment.task_types)
        self.assertTrue(assessment.evidence_requirements)
        self.assertTrue(assessment.failure_signals)

    def test_misconception_and_diagnostic_context(self) -> None:
        skill_id = "grammar.present_simple.third_person_s"
        with open_knowledge_service(self.db_path) as knowledge:
            misconceptions = knowledge.get_misconceptions(skill_id)
            diagnostic = knowledge.get_diagnostic_signals(skill_id)

        self.assertEqual(len(misconceptions), 1)
        self.assertEqual(diagnostic.misconceptions, misconceptions)
        self.assertTrue(diagnostic.failure_signals)
        self.assertEqual(len(diagnostic.error_skill_mappings), 822)

    def test_related_learning_targets(self) -> None:
        with open_knowledge_service(self.db_path) as knowledge:
            related = knowledge.get_related_learning_targets(
                "grammar.articles.generic_reference",
            )

        self.assertTrue(related)
        self.assertEqual(related[0].other_skill_id, "grammar.articles.zero_article")

    def test_explicit_version_is_supported(self) -> None:
        with open_knowledge_service(self.db_path) as knowledge:
            skill = knowledge.get_skill(
                "grammar.present_simple.affirmative",
                version="knowledge_core_v1",
            )

        self.assertEqual(skill.knowledge_version, "knowledge_core_v1")


if __name__ == "__main__":
    unittest.main()
