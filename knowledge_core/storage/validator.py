from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILLS
from knowledge_core.relationships.taxonomy import build_grammar_taxonomy
from knowledge_core.storage.artifacts import StorageArtifacts, load_storage_artifacts
from knowledge_core.storage.config import DEFAULT_VERSION_NAME
from knowledge_core.storage.schema import (
    KNOWLEDGE_TABLES,
    KNOWLEDGE_VIEWS,
    count_existing_tables,
    count_existing_views,
    sqlite_connection,
)


@dataclass(frozen=True, slots=True)
class KnowledgeStorageValidationResult:
    active_version: dict[str, Any] | None
    counts: dict[str, int]
    expected_counts: dict[str, int]
    taxonomy_hash_expected: str
    taxonomy_hash_actual: str | None
    taxonomy_hash_matches: bool
    errors: list[str]
    warnings: list[str]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_result": "pass" if self.is_valid else "fail",
            "active_version": self.active_version,
            "counts": self.counts,
            "expected_counts": self.expected_counts,
            "taxonomy_hash_expected": self.taxonomy_hash_expected,
            "taxonomy_hash_actual": self.taxonomy_hash_actual,
            "taxonomy_hash_matches": self.taxonomy_hash_matches,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def validate_storage(
    *,
    db_path: str | Path | None = None,
    version_name: str = DEFAULT_VERSION_NAME,
    artifacts: StorageArtifacts | None = None,
) -> KnowledgeStorageValidationResult:
    resolved_artifacts = artifacts or load_storage_artifacts()
    taxonomy = build_grammar_taxonomy(CANONICAL_GRAMMAR_V1_SKILLS)
    expected_counts = _expected_counts(resolved_artifacts, taxonomy)
    errors: list[str] = []
    warnings: list[str] = []

    with sqlite_connection(db_path) as connection:
        table_count = count_existing_tables(connection, KNOWLEDGE_TABLES)
        view_count = count_existing_views(connection, KNOWLEDGE_VIEWS)
        active_version = _active_version(connection, version_name)
        version_id = int(active_version["id"]) if active_version else None

        counts = {
            "knowledge_core_tables": table_count,
            "knowledge_core_views": view_count,
            "knowledge_versions": _table_count(connection, "knowledge_versions"),
            "knowledge_sources": _table_count(connection, "knowledge_sources"),
            "source_documents": _table_count(connection, "source_documents"),
            "source_records": _table_count(connection, "source_records"),
            "egp_source_records": _source_record_count(
                connection,
                "english_grammar_profile",
                "egp_grammar_record",
            ),
            "cefr_source_records": _source_record_count(
                connection,
                "cefr_companion_volume",
                "cefr_descriptor",
            ),
            "invalid_fk_count": _foreign_key_violation_count(connection),
            "orphan_count": _orphan_node_count(connection, version_id),
            "duplicate_count": _duplicate_count(connection, version_id),
        }
        if version_id is not None:
            counts.update(_version_counts(connection, version_id))
            counts.update(_view_counts(connection))
            counts["assessment_profile_reconstructable_skills"] = (
                _reconstructable_assessment_profile_count(
                    connection,
                    version_id,
                    resolved_artifacts,
                )
            )
        else:
            counts.update(_empty_version_counts())

        taxonomy_hash_actual = active_version["taxonomy_hash"] if active_version else None
        taxonomy_hash_matches = taxonomy_hash_actual == taxonomy.taxonomy_hash

    if table_count != len(KNOWLEDGE_TABLES):
        errors.append(
            f"Expected {len(KNOWLEDGE_TABLES)} Knowledge Core tables, found {table_count}.",
        )
    if view_count != len(KNOWLEDGE_VIEWS):
        errors.append(
            f"Expected {len(KNOWLEDGE_VIEWS)} Knowledge Core views, found {view_count}.",
        )
    if active_version is None:
        errors.append(f"Active knowledge version not found: {version_name}.")
    if not taxonomy_hash_matches:
        errors.append("Taxonomy hash does not match canonical Grammar V1 hash.")

    for key, expected in expected_counts.items():
        actual = counts.get(key)
        if actual != expected:
            errors.append(f"Expected {key}={expected}, found {actual}.")

    if counts["invalid_fk_count"] != 0:
        errors.append(f"Foreign key violations found: {counts['invalid_fk_count']}.")
    if counts["duplicate_count"] != 0:
        errors.append(f"Duplicate logical rows found: {counts['duplicate_count']}.")
    if counts["orphan_count"] != 0:
        errors.append(f"Orphan nodes found: {counts['orphan_count']}.")
    if counts.get("skill_source_evidence_missing_keys", 0) != 0:
        errors.append(
            "Skill source evidence rows are missing stable evidence keys: "
            f"{counts['skill_source_evidence_missing_keys']}.",
        )

    return KnowledgeStorageValidationResult(
        active_version=active_version,
        counts=counts,
        expected_counts=expected_counts,
        taxonomy_hash_expected=taxonomy.taxonomy_hash,
        taxonomy_hash_actual=taxonomy_hash_actual,
        taxonomy_hash_matches=taxonomy_hash_matches,
        errors=errors,
        warnings=warnings,
    )


def _expected_counts(
    artifacts: StorageArtifacts,
    taxonomy: Any,
) -> dict[str, int]:
    return {
        "knowledge_core_tables": len(KNOWLEDGE_TABLES),
        "knowledge_core_views": len(KNOWLEDGE_VIEWS),
        "taxonomy_nodes": len(taxonomy.all_node_ids),
        "atomic_skills": len(taxonomy.atomic_skill_ids),
        "skill_profiles": len(artifacts.skill_profiles),
        "egp_source_records": len(artifacts.egp_records),
        "cefr_source_records": len(artifacts.cefr_descriptors),
        "skill_source_evidence": len(artifacts.skill_evidence),
        "learning_objectives": len(artifacts.learning_objectives),
        "skill_objective_links": sum(
            len(profile.direct_objective_ids) + len(profile.contextual_objective_ids)
            for profile in artifacts.skill_profiles
        ),
        "cefr_alignments": len(artifacts.skill_alignments),
        "relationships": len(artifacts.relationships),
        "assessment_criteria": len(artifacts.assessment_criteria),
        "assessment_requirements": sum(
            len(criterion.evidence_requirements)
            for criterion in artifacts.assessment_criteria
        ),
        "assessment_failure_signals": sum(
            len(criterion.failure_signals)
            for criterion in artifacts.assessment_criteria
        ),
        "assessment_task_type_links": sum(
            len(criterion.acceptable_task_types)
            for criterion in artifacts.assessment_criteria
        ),
        "assessment_profile_reconstructable_skills": len(artifacts.assessment_profiles),
        "corpus_error_statistics": artifacts.counts()["corpus_error_statistics"],
        "corpus_error_skill_mappings": len(artifacts.error_skill_mappings),
        "misconceptions": artifacts.counts()["misconceptions"],
        "candidate_misconceptions": artifacts.counts()["candidate_misconceptions"],
        "accepted_misconceptions": artifacts.counts()["accepted_misconceptions"],
        "misconception_evidence": artifacts.counts()["misconception_evidence"],
        "skill_misconception_links": len(artifacts.skill_misconception_links),
    }


def _active_version(
    connection: sqlite3.Connection,
    version_name: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT id, version_name, description, taxonomy_hash, status, created_at, activated_at
        FROM knowledge_versions
        WHERE version_name = ? AND status = 'active'
        """,
        (version_name,),
    ).fetchone()
    return dict(row) if row else None


def _version_counts(connection: sqlite3.Connection, version_id: int) -> dict[str, int]:
    node_scope = "SELECT id FROM knowledge_nodes WHERE knowledge_version_id = ?"
    criterion_scope = "SELECT id FROM assessment_criteria WHERE knowledge_version_id = ?"
    relationship_scope = "SELECT id FROM skill_relationships WHERE knowledge_version_id = ?"
    return {
        "taxonomy_nodes": _count(
            connection,
            "SELECT COUNT(*) AS count FROM knowledge_nodes WHERE knowledge_version_id = ?",
            (version_id,),
        ),
        "atomic_skills": _count(
            connection,
            """
            SELECT COUNT(*) AS count
            FROM knowledge_nodes
            WHERE knowledge_version_id = ? AND is_atomic = 1
            """,
            (version_id,),
        ),
        "skill_profiles": _count(
            connection,
            f"SELECT COUNT(*) AS count FROM skill_profiles WHERE knowledge_node_id IN ({node_scope})",
            (version_id,),
        ),
        "skill_source_evidence": _count(
            connection,
            f"SELECT COUNT(*) AS count FROM skill_source_evidence WHERE knowledge_node_id IN ({node_scope})",
            (version_id,),
        ),
        "skill_source_evidence_missing_keys": _count(
            connection,
            f"""
            SELECT COUNT(*) AS count
            FROM skill_source_evidence
            WHERE knowledge_node_id IN ({node_scope})
              AND (evidence_key IS NULL OR evidence_key = '')
            """,
            (version_id,),
        ),
        "learning_objectives": _count(
            connection,
            "SELECT COUNT(*) AS count FROM learning_objectives WHERE knowledge_version_id = ?",
            (version_id,),
        ),
        "skill_objective_links": _count(
            connection,
            f"SELECT COUNT(*) AS count FROM skill_learning_objectives WHERE knowledge_node_id IN ({node_scope})",
            (version_id,),
        ),
        "cefr_alignments": _count(
            connection,
            f"SELECT COUNT(*) AS count FROM skill_cefr_alignments WHERE knowledge_node_id IN ({node_scope})",
            (version_id,),
        ),
        "relationships": _count(
            connection,
            "SELECT COUNT(*) AS count FROM skill_relationships WHERE knowledge_version_id = ?",
            (version_id,),
        ),
        "prerequisite_relationships": _count(
            connection,
            """
            SELECT COUNT(*) AS count
            FROM skill_relationships
            WHERE knowledge_version_id = ? AND relation_type = 'prerequisite_of'
            """,
            (version_id,),
        ),
        "relationship_evidence": _count(
            connection,
            f"SELECT COUNT(*) AS count FROM relationship_evidence WHERE relationship_id IN ({relationship_scope})",
            (version_id,),
        ),
        "assessment_criteria": _count(
            connection,
            "SELECT COUNT(*) AS count FROM assessment_criteria WHERE knowledge_version_id = ?",
            (version_id,),
        ),
        "assessment_requirements": _count(
            connection,
            f"""
            SELECT COUNT(*) AS count
            FROM assessment_evidence_requirements
            WHERE assessment_criterion_id IN ({criterion_scope})
            """,
            (version_id,),
        ),
        "assessment_failure_signals": _count(
            connection,
            f"""
            SELECT COUNT(*) AS count
            FROM assessment_failure_signals
            WHERE assessment_criterion_id IN ({criterion_scope})
            """,
            (version_id,),
        ),
        "assessment_task_type_links": _count(
            connection,
            f"""
            SELECT COUNT(*) AS count
            FROM assessment_task_types
            WHERE assessment_criterion_id IN ({criterion_scope})
            """,
            (version_id,),
        ),
        "assessment_evidence": _count(
            connection,
            f"""
            SELECT COUNT(*) AS count
            FROM assessment_evidence
            WHERE assessment_criterion_id IN ({criterion_scope})
            """,
            (version_id,),
        ),
        "corpus_error_statistics": _count(
            connection,
            "SELECT COUNT(*) AS count FROM corpus_error_statistics WHERE knowledge_version_id = ?",
            (version_id,),
        ),
        "corpus_error_skill_mappings": _count(
            connection,
            "SELECT COUNT(*) AS count FROM corpus_error_skill_mappings WHERE knowledge_version_id = ?",
            (version_id,),
        ),
        "misconceptions": _count(
            connection,
            "SELECT COUNT(*) AS count FROM misconceptions WHERE knowledge_version_id = ?",
            (version_id,),
        ),
        "candidate_misconceptions": _count(
            connection,
            """
            SELECT COUNT(*) AS count
            FROM misconceptions
            WHERE knowledge_version_id = ? AND status = 'candidate'
            """,
            (version_id,),
        ),
        "accepted_misconceptions": _count(
            connection,
            """
            SELECT COUNT(*) AS count
            FROM misconceptions
            WHERE knowledge_version_id = ? AND status = 'accepted'
            """,
            (version_id,),
        ),
        "misconception_evidence": _count(
            connection,
            """
            SELECT COUNT(*) AS count
            FROM misconception_evidence
            WHERE misconception_id IN (
                SELECT id FROM misconceptions WHERE knowledge_version_id = ?
            )
            """,
            (version_id,),
        ),
        "skill_misconception_links": _count(
            connection,
            "SELECT COUNT(*) AS count FROM skill_misconception_links WHERE knowledge_version_id = ?",
            (version_id,),
        ),
    }


def _empty_version_counts() -> dict[str, int]:
    return {
        "taxonomy_nodes": 0,
        "atomic_skills": 0,
        "skill_profiles": 0,
        "skill_source_evidence": 0,
        "skill_source_evidence_missing_keys": 0,
        "learning_objectives": 0,
        "skill_objective_links": 0,
        "cefr_alignments": 0,
        "relationships": 0,
        "prerequisite_relationships": 0,
        "relationship_evidence": 0,
        "assessment_criteria": 0,
        "assessment_requirements": 0,
        "assessment_failure_signals": 0,
        "assessment_task_type_links": 0,
        "assessment_evidence": 0,
        "view_atomic_skills": 0,
        "view_skill_prerequisites": 0,
        "view_skill_assessment_summary": 0,
        "assessment_profile_reconstructable_skills": 0,
        "corpus_error_statistics": 0,
        "corpus_error_skill_mappings": 0,
        "misconceptions": 0,
        "candidate_misconceptions": 0,
        "accepted_misconceptions": 0,
        "misconception_evidence": 0,
        "skill_misconception_links": 0,
        "view_skill_misconceptions": 0,
        "view_corpus_error_statistics": 0,
    }


def _view_counts(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        "view_atomic_skills": _count(
            connection,
            "SELECT COUNT(*) AS count FROM v_atomic_skills",
        ),
        "view_skill_prerequisites": _count(
            connection,
            "SELECT COUNT(*) AS count FROM v_skill_prerequisites",
        ),
        "view_skill_assessment_summary": _count(
            connection,
            "SELECT COUNT(*) AS count FROM v_skill_assessment_summary",
        ),
        "view_skill_misconceptions": _count(
            connection,
            "SELECT COUNT(*) AS count FROM v_skill_misconceptions",
        ),
        "view_corpus_error_statistics": _count(
            connection,
            "SELECT COUNT(*) AS count FROM v_corpus_error_statistics",
        ),
    }


def _reconstructable_assessment_profile_count(
    connection: sqlite3.Connection,
    version_id: int,
    artifacts: StorageArtifacts,
) -> int:
    rows = connection.execute(
        """
        SELECT n.canonical_id, ac.criterion_key
        FROM assessment_criteria ac
        JOIN knowledge_nodes n ON n.id = ac.knowledge_node_id
        WHERE ac.knowledge_version_id = ?
        """,
        (version_id,),
    ).fetchall()
    criterion_ids_by_skill: dict[str, set[str]] = {}
    for row in rows:
        criterion_ids_by_skill.setdefault(row["canonical_id"], set()).add(
            row["criterion_key"],
        )

    reconstructable = 0
    for profile in artifacts.assessment_profiles:
        if criterion_ids_by_skill.get(profile.canonical_skill_id, set()) == set(
            profile.criterion_ids,
        ):
            reconstructable += 1
    return reconstructable


def _source_record_count(
    connection: sqlite3.Connection,
    source_key: str,
    record_type: str,
) -> int:
    return _count(
        connection,
        """
        SELECT COUNT(*) AS count
        FROM source_records sr
        JOIN knowledge_sources ks ON ks.id = sr.knowledge_source_id
        WHERE ks.source_key = ? AND sr.record_type = ?
        """,
        (source_key, record_type),
    )


def _table_count(connection: sqlite3.Connection, table_name: str) -> int:
    return _count(connection, f"SELECT COUNT(*) AS count FROM {table_name}")


def _foreign_key_violation_count(connection: sqlite3.Connection) -> int:
    return len(connection.execute("PRAGMA foreign_key_check").fetchall())


def _orphan_node_count(connection: sqlite3.Connection, version_id: int | None) -> int:
    if version_id is None:
        return 0
    return _count(
        connection,
        """
        SELECT COUNT(*) AS count
        FROM knowledge_nodes
        WHERE knowledge_version_id = ?
          AND canonical_id != 'grammar'
          AND parent_node_id IS NULL
        """,
        (version_id,),
    )


def _duplicate_count(connection: sqlite3.Connection, version_id: int | None) -> int:
    if version_id is None:
        return 0
    duplicate_queries = [
        (
            """
            SELECT COALESCE(SUM(row_count - 1), 0) AS count
            FROM (
                SELECT COUNT(*) AS row_count
                FROM knowledge_nodes
                WHERE knowledge_version_id = ?
                GROUP BY knowledge_version_id, canonical_id
                HAVING COUNT(*) > 1
            )
            """,
            (version_id,),
        ),
        (
            """
            SELECT COALESCE(SUM(row_count - 1), 0) AS count
            FROM (
                SELECT COUNT(*) AS row_count
                FROM source_records
                GROUP BY knowledge_source_id, external_record_id, record_type
                HAVING COUNT(*) > 1
            )
            """,
            (),
        ),
        (
            """
            SELECT COALESCE(SUM(row_count - 1), 0) AS count
            FROM (
                SELECT COUNT(*) AS row_count
                FROM skill_source_evidence
                WHERE knowledge_node_id IN (
                    SELECT id FROM knowledge_nodes WHERE knowledge_version_id = ?
                )
                GROUP BY knowledge_node_id, source_record_id, evidence_type, status
                HAVING COUNT(*) > 1
            )
            """,
            (version_id,),
        ),
        (
            """
            SELECT COALESCE(SUM(row_count - 1), 0) AS count
            FROM (
                SELECT COUNT(*) AS row_count
                FROM learning_objectives
                WHERE knowledge_version_id = ?
                GROUP BY knowledge_version_id, objective_key
                HAVING COUNT(*) > 1
            )
            """,
            (version_id,),
        ),
        (
            """
            SELECT COALESCE(SUM(row_count - 1), 0) AS count
            FROM (
                SELECT COUNT(*) AS row_count
                FROM skill_relationships
                WHERE knowledge_version_id = ?
                GROUP BY knowledge_version_id, source_node_id, target_node_id, relation_type
                HAVING COUNT(*) > 1
            )
            """,
            (version_id,),
        ),
        (
            """
            SELECT COALESCE(SUM(row_count - 1), 0) AS count
            FROM (
                SELECT COUNT(*) AS row_count
                FROM assessment_criteria
                WHERE knowledge_version_id = ?
                GROUP BY knowledge_version_id, criterion_key
                HAVING COUNT(*) > 1
            )
            """,
            (version_id,),
        ),
        (
            """
            SELECT COALESCE(SUM(row_count - 1), 0) AS count
            FROM (
                SELECT COUNT(*) AS row_count
                FROM corpus_error_statistics
                WHERE knowledge_version_id = ?
                GROUP BY knowledge_version_id, statistic_key
                HAVING COUNT(*) > 1
            )
            """,
            (version_id,),
        ),
        (
            """
            SELECT COALESCE(SUM(row_count - 1), 0) AS count
            FROM (
                SELECT COUNT(*) AS row_count
                FROM corpus_error_skill_mappings
                WHERE knowledge_version_id = ?
                GROUP BY knowledge_version_id, mapping_key
                HAVING COUNT(*) > 1
            )
            """,
            (version_id,),
        ),
        (
            """
            SELECT COALESCE(SUM(row_count - 1), 0) AS count
            FROM (
                SELECT COUNT(*) AS row_count
                FROM misconceptions
                WHERE knowledge_version_id = ?
                GROUP BY knowledge_version_id, misconception_key
                HAVING COUNT(*) > 1
            )
            """,
            (version_id,),
        ),
        (
            """
            SELECT COALESCE(SUM(row_count - 1), 0) AS count
            FROM (
                SELECT COUNT(*) AS row_count
                FROM skill_misconception_links
                WHERE knowledge_version_id = ?
                GROUP BY knowledge_version_id, link_key
                HAVING COUNT(*) > 1
            )
            """,
            (version_id,),
        ),
    ]
    return sum(_count(connection, sql, params) for sql, params in duplicate_queries)


def _count(
    connection: sqlite3.Connection,
    sql: str,
    params: tuple[Any, ...] = (),
) -> int:
    row = connection.execute(sql, params).fetchone()
    return int(row["count"] if row else 0)
