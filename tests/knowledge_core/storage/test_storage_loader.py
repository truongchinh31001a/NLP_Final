from __future__ import annotations

import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from knowledge_core.storage.artifacts import load_storage_artifacts
from knowledge_core.storage.loader import (
    KnowledgeStorageLoadError,
    load_knowledge_core,
)
from knowledge_core.storage.schema import (
    KNOWLEDGE_TABLES,
    KNOWLEDGE_VIEWS,
    initialize_schema,
    sqlite_connection,
)
from knowledge_core.storage.validator import validate_storage


class KnowledgeStorageLoaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.artifacts = load_storage_artifacts()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "knowledge_core.db"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_schema_initialization_creates_tables_and_views(self) -> None:
        result = initialize_schema(self.db_path)

        self.assertEqual(result["knowledge_tables"], len(KNOWLEDGE_TABLES))
        self.assertEqual(result["knowledge_views"], len(KNOWLEDGE_VIEWS))

    def test_load_persists_expected_counts(self) -> None:
        load_knowledge_core(db_path=self.db_path, artifacts=self.artifacts)

        validation = validate_storage(db_path=self.db_path, artifacts=self.artifacts)

        self.assertTrue(validation.is_valid, validation.errors)
        self.assertEqual(validation.counts["taxonomy_nodes"], 54)
        self.assertEqual(validation.counts["atomic_skills"], 43)
        self.assertEqual(validation.counts["egp_source_records"], 273)
        self.assertEqual(validation.counts["cefr_source_records"], 334)
        self.assertEqual(validation.counts["source_records"], 607)
        self.assertEqual(validation.counts["skill_source_evidence"], 205)
        self.assertEqual(validation.counts["learning_objectives"], 292)
        self.assertEqual(validation.counts["skill_objective_links"], 31)
        self.assertEqual(validation.counts["cefr_alignments"], 43)
        self.assertEqual(validation.counts["relationships"], 93)
        self.assertEqual(validation.counts["assessment_criteria"], 79)
        self.assertEqual(validation.counts["corpus_error_statistics"], 737)
        self.assertEqual(validation.counts["corpus_error_skill_mappings"], 432)
        self.assertEqual(validation.counts["misconceptions"], 1)
        self.assertEqual(validation.counts["candidate_misconceptions"], 0)
        self.assertEqual(validation.counts["accepted_misconceptions"], 1)
        self.assertEqual(validation.counts["misconception_evidence"], 432)
        self.assertEqual(validation.counts["skill_misconception_links"], 1)

    def test_idempotent_load_does_not_create_duplicates(self) -> None:
        first = load_knowledge_core(db_path=self.db_path, artifacts=self.artifacts)
        second = load_knowledge_core(db_path=self.db_path, artifacts=self.artifacts)
        validation = validate_storage(db_path=self.db_path, artifacts=self.artifacts)

        self.assertEqual(first.db_counts, second.db_counts)
        self.assertEqual(validation.counts["duplicate_count"], 0)
        self.assertEqual(validation.counts["invalid_fk_count"], 0)

    def test_foreign_keys_are_enforced(self) -> None:
        initialize_schema(self.db_path)

        with self.assertRaises(sqlite3.IntegrityError):
            with sqlite_connection(self.db_path) as connection:
                connection.execute(
                    """
                    INSERT INTO skill_profiles (
                        knowledge_node_id,
                        evidence_status
                    )
                    VALUES (999, 'aligned')
                    """,
                )

    def test_canonical_id_uniqueness_is_enforced(self) -> None:
        load_knowledge_core(db_path=self.db_path, artifacts=self.artifacts)

        with self.assertRaises(sqlite3.IntegrityError):
            with sqlite_connection(self.db_path) as connection:
                row = connection.execute(
                    """
                    SELECT knowledge_version_id, canonical_id
                    FROM knowledge_nodes
                    WHERE canonical_id = 'grammar.present_simple.affirmative'
                    """,
                ).fetchone()
                connection.execute(
                    """
                    INSERT INTO knowledge_nodes (
                        knowledge_version_id,
                        canonical_id,
                        node_type,
                        domain,
                        name,
                        is_atomic,
                        is_active,
                        metadata_json
                    )
                    VALUES (?, ?, 'atomic_skill', 'grammar', 'duplicate', 1, 1, '{}')
                    """,
                    (row["knowledge_version_id"], row["canonical_id"]),
                )

    def test_relationship_self_loop_is_rejected(self) -> None:
        load_knowledge_core(db_path=self.db_path, artifacts=self.artifacts)

        with self.assertRaises(sqlite3.IntegrityError):
            with sqlite_connection(self.db_path) as connection:
                row = connection.execute(
                    """
                    SELECT kv.id AS version_id, n.id AS node_id
                    FROM knowledge_versions kv
                    CROSS JOIN knowledge_nodes n
                    WHERE kv.version_name = 'knowledge_core_v1'
                      AND n.canonical_id = 'grammar.present_simple.affirmative'
                    """
                ).fetchone()
                connection.execute(
                    """
                    INSERT INTO skill_relationships (
                        knowledge_version_id,
                        relationship_key,
                        source_node_id,
                        target_node_id,
                        relation_type,
                        dependency_strength,
                        confidence,
                        status,
                        review_status,
                        reason,
                        bidirectional
                    )
                    VALUES (?, 'rel_self_loop_test', ?, ?, 'related_to', 'none', 0.5,
                            'candidate', 'pending', 'test self loop', 0)
                    """,
                    (row["version_id"], row["node_id"], row["node_id"]),
                )

    def test_source_record_uniqueness_is_enforced(self) -> None:
        load_knowledge_core(db_path=self.db_path, artifacts=self.artifacts)

        with self.assertRaises(sqlite3.IntegrityError):
            with sqlite_connection(self.db_path) as connection:
                row = connection.execute(
                    """
                    SELECT
                        knowledge_source_id,
                        source_document_id,
                        external_record_id,
                        record_type,
                        cefr_level,
                        raw_text,
                        normalized_text,
                        page_number,
                        row_number,
                        sheet_name,
                        raw_payload_json,
                        record_hash
                    FROM source_records
                    LIMIT 1
                    """,
                ).fetchone()
                connection.execute(
                    """
                    INSERT INTO source_records (
                        knowledge_source_id,
                        source_document_id,
                        external_record_id,
                        record_type,
                        cefr_level,
                        raw_text,
                        normalized_text,
                        page_number,
                        row_number,
                        sheet_name,
                        raw_payload_json,
                        record_hash
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    tuple(row),
                )

    def test_transactional_rollback_preserves_previous_version(self) -> None:
        load_knowledge_core(db_path=self.db_path, artifacts=self.artifacts)
        before = validate_storage(db_path=self.db_path, artifacts=self.artifacts).counts
        bad_relationship = self.artifacts.relationships[0].model_copy(
            update={
                "relationship_id": "rel_bad_self_loop_storage_test",
                "target_skill_id": self.artifacts.relationships[0].source_skill_id,
            },
        )
        bad_artifacts = replace(
            self.artifacts,
            relationships=[bad_relationship, *self.artifacts.relationships[1:]],
        )

        with self.assertRaises(KnowledgeStorageLoadError):
            load_knowledge_core(db_path=self.db_path, artifacts=bad_artifacts)

        after = validate_storage(db_path=self.db_path, artifacts=self.artifacts).counts
        self.assertEqual(after["relationships"], before["relationships"])
        self.assertEqual(after["taxonomy_nodes"], before["taxonomy_nodes"])
        self.assertEqual(after["duplicate_count"], 0)

    def test_views_return_expected_counts(self) -> None:
        load_knowledge_core(db_path=self.db_path, artifacts=self.artifacts)

        with sqlite_connection(self.db_path) as connection:
            atomic_count = connection.execute(
                "SELECT COUNT(*) AS count FROM v_atomic_skills",
            ).fetchone()["count"]
            prerequisite_count = connection.execute(
                "SELECT COUNT(*) AS count FROM v_skill_prerequisites",
            ).fetchone()["count"]
            assessment_count = connection.execute(
                "SELECT COUNT(*) AS count FROM v_skill_assessment_summary",
            ).fetchone()["count"]
            misconception_count = connection.execute(
                "SELECT COUNT(*) AS count FROM v_skill_misconceptions",
            ).fetchone()["count"]
            error_stat_count = connection.execute(
                "SELECT COUNT(*) AS count FROM v_corpus_error_statistics",
            ).fetchone()["count"]

        self.assertEqual(atomic_count, 43)
        self.assertEqual(prerequisite_count, 15)
        self.assertEqual(assessment_count, 79)
        self.assertEqual(misconception_count, 1)
        self.assertEqual(error_stat_count, 737)


if __name__ == "__main__":
    unittest.main()
