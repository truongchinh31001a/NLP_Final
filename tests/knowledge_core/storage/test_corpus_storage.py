from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from knowledge_core.repository import open_knowledge_repositories
from knowledge_core.storage.corpus_loader import load_corpus_error_storage
from knowledge_core.storage.cli import _reset_version
from knowledge_core.storage.schema import initialize_schema, sqlite_connection


class CorpusErrorStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.db_path = root / "knowledge.db"
        self.source_path = root / "source_records.jsonl"
        self.error_path = root / "error_instances.jsonl"
        self.normalized_path = root / "normalized.jsonl"
        initialize_schema(self.db_path)
        with sqlite_connection(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO knowledge_versions
                    (version_name, description, taxonomy_hash, status, activated_at)
                VALUES ('knowledge_core_v1', 'test', 'test-hash', 'active', CURRENT_TIMESTAMP)
                """
            )
        self._write_fixture()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_streaming_load_and_repository_queries(self) -> None:
        result = self._load()
        self.assertTrue(result.is_valid)
        self.assertEqual(result.source_record_count, 1)
        self.assertEqual(result.error_instance_count, 1)
        self.assertEqual(result.normalized_error_count, 1)
        self.assertEqual(result.cefr_pattern_count, 1)

        with open_knowledge_repositories(self.db_path) as repos:
            error = repos.error_instances.get("err__test__1")
            filtered = repos.error_instances.list(
                category="agreement", proficiency_label="B2"
            )
            patterns = repos.error_instances.list_patterns_by_cefr(source_key="clc_fce")

        self.assertEqual(error.normalized_error_id, "normerr__test__1")
        self.assertEqual(error.source_label, "AGV")
        self.assertEqual(error.proficiency_label, "B2")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(patterns[0].error_count, 1)

    def test_reload_is_idempotent(self) -> None:
        first = self._load()
        second = self._load()
        self.assertEqual(first.source_record_count, second.source_record_count)
        with open_knowledge_repositories(self.db_path) as repos:
            self.assertEqual(repos.error_instances.count(), 1)

    def test_reset_version_clears_corpus_rows(self) -> None:
        self._load()
        self.assertTrue(_reset_version(self.db_path, "knowledge_core_v1"))
        with sqlite_connection(self.db_path) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM error_instances").fetchone()[0], 0
            )

    def _load(self):
        return load_corpus_error_storage(
            db_path=self.db_path,
            source_record_paths=[self.source_path],
            error_paths=[self.error_path],
            normalized_path=self.normalized_path,
            batch_size=1,
        )

    def _write_fixture(self) -> None:
        source = {
            "source_record_id": "src__test__1", "source_key": "clc_fce",
            "native_record_id": "native-1", "record_unit": "answer",
            "split": "train", "task_id": "task-1", "proficiency_label": "B2",
            "metadata": {}, "provenance": {},
        }
        error = {
            "error_instance_id": "err__test__1", "source_record_id": "src__test__1",
            "source_key": "clc_fce", "native_error_id": "native-error-1",
            "source_native_label": {"label_system": "test", "label": "AGV"},
            "span": {"span_kind": "json_char_offsets", "source_field": "text",
                     "start_char": 1, "end_char": 3, "confidence": 0.9},
            "correction": {"correction_type": "replacement", "correction_length": 2},
            "status": "parsed", "review_status": "pending", "parser_notes": [],
            "metadata": {}, "provenance": {},
        }
        normalized = {
            "normalized_error_id": "normerr__test__1", "error_instance_id": "err__test__1",
            "source_record_id": "src__test__1", "source_key": "clc_fce",
            "category": "agreement", "subtype": "verb_agreement", "status": "exact",
            "confidence": 0.9, "reason": "test", "review_status": "pending",
            "taxonomy_version": "error_taxonomy_v1", "canonical_skill_candidates": [],
            "metadata": {}, "provenance": {},
        }
        for path, value in ((self.source_path, source), (self.error_path, error),
                            (self.normalized_path, normalized)):
            path.write_text(json.dumps(value) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
