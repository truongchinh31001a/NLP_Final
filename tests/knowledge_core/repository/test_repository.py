from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from knowledge_core.repository import (
    KnowledgeIntegrityError,
    KnowledgeNotFoundError,
    KnowledgeVersionNotFoundError,
    open_knowledge_repositories,
)
from knowledge_core.storage.artifacts import load_storage_artifacts
from knowledge_core.storage.loader import load_knowledge_core
from knowledge_core.storage.schema import sqlite_connection


class KnowledgeRepositoryV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls.temp_dir.name) / "knowledge_repository.db"
        cls.artifacts = load_storage_artifacts()
        load_knowledge_core(db_path=cls.db_path, artifacts=cls.artifacts)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    def test_active_version_resolved(self) -> None:
        with open_knowledge_repositories(self.db_path) as repos:
            version = repos.versions.get_active_version()

        self.assertEqual(version.version_name, "knowledge_core_v1")
        self.assertEqual(version.status, "active")

    def test_missing_version_raises(self) -> None:
        with open_knowledge_repositories(self.db_path) as repos:
            with self.assertRaises(KnowledgeVersionNotFoundError):
                repos.versions.get_version("missing_version")

    def test_multiple_active_versions_raise_integrity_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "multiple_active.db"
            load_knowledge_core(
                db_path=db_path,
                version_name="knowledge_core_v1",
                artifacts=self.artifacts,
            )
            load_knowledge_core(
                db_path=db_path,
                version_name="knowledge_core_v2",
                artifacts=self.artifacts,
            )
            with sqlite_connection(db_path) as connection:
                connection.execute(
                    "UPDATE knowledge_versions SET status = 'active'",
                )

            with open_knowledge_repositories(db_path) as repos:
                with self.assertRaises(KnowledgeIntegrityError):
                    repos.versions.get_active_version()

    def test_get_existing_skill(self) -> None:
        with open_knowledge_repositories(self.db_path) as repos:
            skill = repos.nodes.get_by_canonical_id(
                "grammar.present_simple.affirmative",
            )

        self.assertTrue(skill.is_atomic)
        self.assertEqual(skill.parent_canonical_id, "grammar.present_simple")

    def test_missing_canonical_id_raises(self) -> None:
        with open_knowledge_repositories(self.db_path) as repos:
            with self.assertRaises(KnowledgeNotFoundError):
                repos.nodes.get_by_canonical_id("grammar.nope.missing")

    def test_atomic_skill_count(self) -> None:
        with open_knowledge_repositories(self.db_path) as repos:
            skills = repos.nodes.list_atomic_skills()

        self.assertEqual(len(skills), 43)

    def test_children_parent_and_descendants(self) -> None:
        with open_knowledge_repositories(self.db_path) as repos:
            children = repos.nodes.list_children("grammar.present_simple")
            parent = repos.nodes.get_parent("grammar.present_simple.affirmative")
            descendants = repos.nodes.list_descendants(
                "grammar.present_simple",
                atomic_only=True,
            )
            ancestors = repos.nodes.list_ancestors(
                "grammar.present_simple.affirmative",
            )

        self.assertIn(
            "grammar.present_simple.affirmative",
            {child.canonical_id for child in children},
        )
        self.assertEqual(parent.canonical_id, "grammar.present_simple")
        self.assertEqual(len(descendants), 4)
        self.assertEqual(
            [ancestor.canonical_id for ancestor in ancestors],
            ["grammar.present_simple", "grammar"],
        )

    def test_skill_profile(self) -> None:
        with open_knowledge_repositories(self.db_path) as repos:
            profile = repos.nodes.get_skill_profile(
                "grammar.present_simple.affirmative",
            )

        self.assertEqual(profile.cefr_primary_level, "A1")
        self.assertEqual(profile.evidence_status, "aligned")

    def test_skill_evidence_retrieval_and_source_filter(self) -> None:
        with open_knowledge_repositories(self.db_path) as repos:
            evidence = repos.evidence.list_skill_evidence(
                "grammar.present_simple.affirmative",
            )
            egp_evidence = repos.evidence.list_skill_evidence(
                "grammar.present_simple.affirmative",
                source_key="english_grammar_profile",
            )
            loaded = repos.evidence.get_evidence(evidence[0].evidence_id)

        self.assertEqual(len(evidence), 8)
        self.assertEqual(len(egp_evidence), 2)
        self.assertEqual(loaded.evidence_id, evidence[0].evidence_id)
        self.assertIsNotNone(loaded.source_text)

    def test_empty_evidence_result(self) -> None:
        with open_knowledge_repositories(self.db_path) as repos:
            evidence = repos.evidence.list_skill_evidence(
                "grammar.present_simple.affirmative",
                source_key="missing_source",
            )

        self.assertEqual(evidence, [])

    def test_source_record_queries(self) -> None:
        with open_knowledge_repositories(self.db_path) as repos:
            records = repos.evidence.list_source_records(limit=1000)
            egp_records = repos.evidence.list_source_records(
                source_key="english_grammar_profile",
                record_type="egp_grammar_record",
                limit=500,
            )
            loaded = repos.evidence.get_source_record(egp_records[0].source_record_id)

        self.assertEqual(len(records), 607)
        self.assertEqual(len(egp_records), 273)
        self.assertEqual(loaded.source_key, "english_grammar_profile")

    def test_learning_objective_queries(self) -> None:
        with open_knowledge_repositories(self.db_path) as repos:
            objectives = repos.objectives.list_for_skill(
                "grammar.present_simple.affirmative",
            )
            contextual = repos.objectives.list_for_skill(
                "grammar.present_simple.affirmative",
                alignment_type="contextual",
            )
            direct = repos.objectives.list_for_skill(
                "grammar.modality.can_ability",
                alignment_type="direct",
            )
            a2_objectives = repos.objectives.list_by_cefr_level("A2", limit=20)
            unaligned = repos.objectives.list_unaligned_objectives(limit=1000)
            all_objectives = repos.objectives.list_all(limit=500)

        self.assertEqual(len(objectives), 5)
        self.assertEqual(len(contextual), 5)
        self.assertEqual(len(direct), 1)
        self.assertTrue(all(item.cefr_level == "A2" for item in a2_objectives))
        self.assertGreater(len(unaligned), 0)
        self.assertTrue(all(item.alignment_type is None for item in unaligned))
        self.assertEqual(len(all_objectives), 292)

    def test_get_objective_by_key(self) -> None:
        objective_key = self.artifacts.learning_objectives[0].objective_id
        with open_knowledge_repositories(self.db_path) as repos:
            objective = repos.objectives.get_by_objective_key(objective_key)

        self.assertEqual(objective.objective_key, objective_key)

    def test_relationship_queries(self) -> None:
        with open_knowledge_repositories(self.db_path) as repos:
            all_relationships = repos.relationships.list_all(limit=200)
            prerequisites = repos.relationships.list_all(
                relation_type="prerequisite_of",
                limit=100,
            )
            incoming = repos.relationships.list_incoming(
                "grammar.passive.agent_by",
                relation_type="prerequisite_of",
            )
            outgoing = repos.relationships.list_outgoing(
                "grammar.passive.be_past_participle",
                relation_type="prerequisite_of",
            )
            direct_prerequisites = repos.relationships.list_direct_prerequisites(
                "grammar.passive.agent_by",
            )
            direct_unlocks = repos.relationships.list_direct_unlocks(
                "grammar.passive.be_past_participle",
            )
            related = repos.relationships.list_related(
                "grammar.articles.generic_reference",
            )
            between = repos.relationships.list_between(
                "grammar.passive.be_past_participle",
                "grammar.passive.agent_by",
            )

        self.assertEqual(len(all_relationships), 93)
        self.assertEqual(len(prerequisites), 15)
        self.assertEqual(len(incoming), 1)
        self.assertTrue(outgoing)
        self.assertEqual(direct_prerequisites, incoming)
        self.assertIn("grammar.passive.agent_by", {item.target_skill_id for item in direct_unlocks})
        self.assertEqual(related[0].other_skill_id, "grammar.articles.zero_article")
        self.assertEqual(len(between), 1)

    def test_transitive_prerequisite_and_unlock_queries(self) -> None:
        with open_knowledge_repositories(self.db_path) as repos:
            transitive_prerequisites = repos.relationships.list_transitive_prerequisites(
                "grammar.passive.agent_by",
            )
            transitive_unlocks = repos.relationships.list_transitive_unlocks(
                "grammar.passive.be_past_participle",
            )

        self.assertTrue(transitive_prerequisites)
        self.assertTrue(transitive_unlocks)

    def test_relationship_evidence(self) -> None:
        relationship_id = self.artifacts.relationships[0].relationship_id
        with open_knowledge_repositories(self.db_path) as repos:
            relationship = repos.relationships.get_relationship(relationship_id)
            evidence = repos.relationships.list_relationship_evidence(relationship_id)

        self.assertEqual(relationship.relationship_id, relationship_id)
        self.assertTrue(evidence)

    def test_assessment_queries(self) -> None:
        with open_knowledge_repositories(self.db_path) as repos:
            criteria = repos.assessments.list_for_skill(
                "grammar.present_simple.affirmative",
            )
            all_criteria = repos.assessments.list_all(limit=100)
            task_matches = repos.assessments.list_by_task_type(
                "error_correction",
                limit=20,
            )
            level_matches = repos.assessments.list_by_cefr_level("A1", limit=100)
            full = repos.assessments.get_full_criterion(criteria[0].criterion_key)

        self.assertEqual(len(criteria), 1)
        self.assertEqual(len(all_criteria), 79)
        self.assertTrue(task_matches)
        self.assertTrue(all(item.cefr_level == "A1" for item in level_matches))
        self.assertTrue(full.evidence_requirements)
        self.assertTrue(full.failure_signals)
        self.assertTrue(full.task_types)
        self.assertTrue(full.evidence)

    def test_composite_skill_snapshot(self) -> None:
        with open_knowledge_repositories(self.db_path) as repos:
            snapshot = repos.queries.get_skill_snapshot(
                "grammar.present_simple.affirmative",
            )

        self.assertEqual(snapshot.skill.canonical_id, "grammar.present_simple.affirmative")
        self.assertEqual(snapshot.profile.cefr_primary_level, "A1")
        self.assertEqual(len(snapshot.learning_objectives), 5)
        self.assertEqual(len(snapshot.assessment_criteria), 1)
        self.assertEqual(snapshot.source_evidence_summary["total"], 8)

    def test_version_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "version_isolation.db"
            load_knowledge_core(
                db_path=db_path,
                version_name="knowledge_core_v1",
                artifacts=self.artifacts,
            )
            load_knowledge_core(
                db_path=db_path,
                version_name="knowledge_core_v2",
                artifacts=self.artifacts,
            )
            with sqlite_connection(db_path) as connection:
                connection.execute(
                    """
                    UPDATE knowledge_nodes
                    SET name = 'version two affirmative'
                    WHERE canonical_id = 'grammar.present_simple.affirmative'
                      AND knowledge_version_id = (
                          SELECT id
                          FROM knowledge_versions
                          WHERE version_name = 'knowledge_core_v2'
                      )
                    """,
                )

            with open_knowledge_repositories(db_path) as repos:
                v1_skill = repos.nodes.get_by_canonical_id(
                    "grammar.present_simple.affirmative",
                    version="knowledge_core_v1",
                )
                v2_skill = repos.nodes.get_by_canonical_id(
                    "grammar.present_simple.affirmative",
                    version="knowledge_core_v2",
                )
                active_skill = repos.nodes.get_by_canonical_id(
                    "grammar.present_simple.affirmative",
                )

        self.assertNotEqual(v1_skill.name, "version two affirmative")
        self.assertEqual(v2_skill.name, "version two affirmative")
        self.assertEqual(active_skill.name, "version two affirmative")


if __name__ == "__main__":
    unittest.main()
