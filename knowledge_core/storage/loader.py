from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel

from knowledge_core.alignment.models import (
    CanonicalSkillEvidenceProfile,
    SkillCEFRAlignment,
    SkillSourceEvidence,
)
from knowledge_core.assessment.models import (
    AssessmentCriterion,
    AssessmentEvidence,
)
from knowledge_core.enrichment.models import SkillMisconceptionLink
from knowledge_core.assessment.rules import SKILL_ASSESSMENT_SPECS
from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILLS
from knowledge_core.misconceptions.models import MisconceptionCandidate
from knowledge_core.normalization.corpus_errors.models import ErrorSkillMapping
from knowledge_core.relationships.models import RelationshipEvidence, SkillRelationship
from knowledge_core.relationships.taxonomy import build_grammar_taxonomy
from knowledge_core.sources.cefr.models import SOURCE_DOCUMENT, SOURCE_YEAR
from knowledge_core.sources.egp.models import DEFAULT_EGP_ONLINE_URL
from knowledge_core.storage.artifacts import (
    StorageArtifacts,
    corpus_error_statistic_rows,
    load_storage_artifacts,
    merged_misconceptions,
)
from knowledge_core.storage.config import DEFAULT_VERSION_NAME, resolve_db_path
from knowledge_core.storage.schema import initialize_schema, sqlite_connection


class KnowledgeStorageLoadError(RuntimeError):
    """Raised when the Knowledge Core database load cannot complete safely."""


@dataclass(frozen=True, slots=True)
class KnowledgeStorageLoadResult:
    version_id: int
    version_name: str
    taxonomy_hash: str
    artifact_counts: dict[str, int]
    db_counts: dict[str, int]


def load_knowledge_core(
    *,
    db_path: str | Path | None = None,
    version_name: str = DEFAULT_VERSION_NAME,
    version_description: str = "Knowledge Core Grammar V1 loaded from validated artifacts.",
    artifacts: StorageArtifacts | None = None,
    ensure_schema: bool = True,
) -> KnowledgeStorageLoadResult:
    if ensure_schema:
        initialize_schema(db_path)

    resolved_artifacts = artifacts or load_storage_artifacts()
    taxonomy = build_grammar_taxonomy(CANONICAL_GRAMMAR_V1_SKILLS)
    metadata = {
        "artifact_counts": resolved_artifacts.counts(),
        "taxonomy_root": taxonomy.root_id,
        "taxonomy_atomic_skills": len(taxonomy.atomic_skill_ids),
        "taxonomy_group_nodes": len(taxonomy.group_node_ids),
    }

    try:
        with sqlite_connection(db_path) as connection:
            version_id = _upsert_loading_version(
                connection,
                version_name=version_name,
                description=version_description,
                taxonomy_hash=taxonomy.taxonomy_hash,
                metadata=metadata,
            )
            _clear_version_scoped_data(connection, version_id)

            source_ids = _load_sources(connection)
            document_ids = _load_source_documents(
                connection,
                artifacts=resolved_artifacts,
                source_ids=source_ids,
            )
            source_record_ids = _load_source_records(
                connection,
                artifacts=resolved_artifacts,
                source_ids=source_ids,
                document_ids=document_ids,
            )
            node_ids = _load_knowledge_nodes(
                connection,
                version_id=version_id,
                taxonomy=taxonomy,
            )
            objective_ids = _load_learning_objectives(
                connection,
                version_id=version_id,
                objectives=resolved_artifacts.learning_objectives,
                source_record_ids=source_record_ids,
            )
            _load_skill_profiles(
                connection,
                profiles=resolved_artifacts.skill_profiles,
                node_ids=node_ids,
            )
            _load_skill_source_evidence(
                connection,
                evidence_items=resolved_artifacts.skill_evidence,
                node_ids=node_ids,
                source_record_ids=source_record_ids,
            )
            _load_skill_learning_objectives(
                connection,
                profiles=resolved_artifacts.skill_profiles,
                node_ids=node_ids,
                objective_ids=objective_ids,
            )
            _load_skill_cefr_alignments(
                connection,
                alignments=resolved_artifacts.skill_alignments,
                node_ids=node_ids,
            )
            relationship_ids = _load_relationships(
                connection,
                version_id=version_id,
                relationships=resolved_artifacts.relationships,
                node_ids=node_ids,
                source_record_ids=source_record_ids,
            )
            _load_assessment_criteria(
                connection,
                version_id=version_id,
                criteria=resolved_artifacts.assessment_criteria,
                node_ids=node_ids,
                source_record_ids=source_record_ids,
            )
            mapping_ids = _load_corpus_error_skill_mappings(
                connection,
                version_id=version_id,
                mappings=resolved_artifacts.error_skill_mappings,
                source_ids=source_ids,
                node_ids=node_ids,
            )
            _load_corpus_error_statistics(
                connection,
                version_id=version_id,
                artifacts=resolved_artifacts,
                source_ids=source_ids,
                node_ids=node_ids,
            )
            misconception_ids = _load_misconceptions(
                connection,
                version_id=version_id,
                misconceptions=merged_misconceptions(
                    candidates=resolved_artifacts.candidate_misconceptions,
                    accepted=resolved_artifacts.accepted_misconceptions,
                ),
                source_ids=source_ids,
                node_ids=node_ids,
                mapping_ids=mapping_ids,
            )
            _load_skill_misconception_links(
                connection,
                version_id=version_id,
                links=resolved_artifacts.skill_misconception_links,
                node_ids=node_ids,
                misconception_ids=misconception_ids,
            )

            _activate_version(connection, version_id)
            db_counts = _database_counts(connection, version_id)
            db_counts["relationship_evidence_keys"] = len(relationship_ids)

            return KnowledgeStorageLoadResult(
                version_id=version_id,
                version_name=version_name,
                taxonomy_hash=taxonomy.taxonomy_hash,
                artifact_counts=resolved_artifacts.counts(),
                db_counts=db_counts,
            )
    except Exception as exc:
        if isinstance(exc, KnowledgeStorageLoadError):
            raise
        raise KnowledgeStorageLoadError(
            f"Knowledge Core load failed and was rolled back: {exc}",
        ) from exc


def _upsert_loading_version(
    connection: sqlite3.Connection,
    *,
    version_name: str,
    description: str,
    taxonomy_hash: str,
    metadata: dict[str, Any],
) -> int:
    connection.execute(
        """
        INSERT INTO knowledge_versions (
            version_name,
            description,
            taxonomy_hash,
            status,
            activated_at,
            metadata_json
        )
        VALUES (?, ?, ?, 'loading', NULL, ?)
        ON CONFLICT(version_name) DO UPDATE SET
            description = excluded.description,
            taxonomy_hash = excluded.taxonomy_hash,
            status = 'loading',
            activated_at = NULL,
            metadata_json = excluded.metadata_json
        """,
        (version_name, description, taxonomy_hash, _json(metadata)),
    )
    row = connection.execute(
        "SELECT id FROM knowledge_versions WHERE version_name = ?",
        (version_name,),
    ).fetchone()
    if row is None:
        raise KnowledgeStorageLoadError(f"Could not create version {version_name!r}.")
    return int(row["id"])


def _clear_version_scoped_data(connection: sqlite3.Connection, version_id: int) -> None:
    node_scope = "SELECT id FROM knowledge_nodes WHERE knowledge_version_id = ?"
    relationship_scope = "SELECT id FROM skill_relationships WHERE knowledge_version_id = ?"
    criterion_scope = "SELECT id FROM assessment_criteria WHERE knowledge_version_id = ?"
    misconception_scope = "SELECT id FROM misconceptions WHERE knowledge_version_id = ?"

    connection.execute(
        f"DELETE FROM skill_misconception_links WHERE knowledge_version_id = ?",
        (version_id,),
    )
    connection.execute(
        f"DELETE FROM misconception_evidence WHERE misconception_id IN ({misconception_scope})",
        (version_id,),
    )
    connection.execute(
        "DELETE FROM misconceptions WHERE knowledge_version_id = ?",
        (version_id,),
    )
    connection.execute(
        "DELETE FROM corpus_error_skill_mappings WHERE knowledge_version_id = ?",
        (version_id,),
    )
    connection.execute(
        "DELETE FROM corpus_error_statistics WHERE knowledge_version_id = ?",
        (version_id,),
    )
    connection.execute(
        f"DELETE FROM assessment_evidence WHERE assessment_criterion_id IN ({criterion_scope})",
        (version_id,),
    )
    connection.execute(
        f"DELETE FROM assessment_task_types WHERE assessment_criterion_id IN ({criterion_scope})",
        (version_id,),
    )
    connection.execute(
        f"DELETE FROM assessment_failure_signals WHERE assessment_criterion_id IN ({criterion_scope})",
        (version_id,),
    )
    connection.execute(
        f"DELETE FROM assessment_evidence_requirements WHERE assessment_criterion_id IN ({criterion_scope})",
        (version_id,),
    )
    connection.execute(
        "DELETE FROM assessment_criteria WHERE knowledge_version_id = ?",
        (version_id,),
    )
    connection.execute(
        f"DELETE FROM relationship_evidence WHERE relationship_id IN ({relationship_scope})",
        (version_id,),
    )
    connection.execute(
        "DELETE FROM skill_relationships WHERE knowledge_version_id = ?",
        (version_id,),
    )
    connection.execute(
        f"DELETE FROM skill_learning_objectives WHERE knowledge_node_id IN ({node_scope})",
        (version_id,),
    )
    connection.execute(
        f"DELETE FROM skill_cefr_alignments WHERE knowledge_node_id IN ({node_scope})",
        (version_id,),
    )
    connection.execute(
        f"DELETE FROM skill_source_evidence WHERE knowledge_node_id IN ({node_scope})",
        (version_id,),
    )
    connection.execute(
        f"DELETE FROM skill_profiles WHERE knowledge_node_id IN ({node_scope})",
        (version_id,),
    )
    connection.execute(
        "DELETE FROM learning_objectives WHERE knowledge_version_id = ?",
        (version_id,),
    )
    connection.execute(
        "DELETE FROM knowledge_nodes WHERE knowledge_version_id = ?",
        (version_id,),
    )


def _load_sources(connection: sqlite3.Connection) -> dict[str, int]:
    source_rows = [
        {
            "source_key": "clc_fce",
            "source_name": "CLC FCE Dataset",
            "source_type": "annotated_error_corpus",
            "source_version": "fce_released_dataset_1.1",
            "source_year": None,
            "source_url": None,
            "license_note": "Learner corpus source files remain local raw data; redistribution requires manual review.",
            "metadata_json": _json({"source_system": "cambridge_learner_corpus"}),
        },
        {
            "source_key": "efcamdat",
            "source_name": "EFCAMDAT",
            "source_type": "learner_error_corpus",
            "source_version": None,
            "source_year": None,
            "source_url": None,
            "license_note": "Learner corpus source files remain local raw data; redistribution requires manual review.",
            "metadata_json": _json({"source_system": "efcamdat"}),
        },
        {
            "source_key": "write_improve",
            "source_name": "Write & Improve",
            "source_type": "revision_corpus",
            "source_version": None,
            "source_year": None,
            "source_url": None,
            "license_note": "Learner corpus source files remain local raw data; redistribution requires manual review.",
            "metadata_json": _json({"source_system": "write_and_improve"}),
        },
        {
            "source_key": "ud_english_ewt",
            "source_name": "Universal Dependencies English EWT",
            "source_type": "linguistic_structure_resource",
            "source_version": None,
            "source_year": None,
            "source_url": None,
            "license_note": "Local source inventory records licensing details separately.",
            "metadata_json": _json({"source_system": "universal_dependencies"}),
        },
        {
            "source_key": "english_grammar_profile",
            "source_name": "English Grammar Profile",
            "source_type": "grammar_profile",
            "source_version": "egp_online_export_v1",
            "source_year": None,
            "source_url": DEFAULT_EGP_ONLINE_URL,
            "license_note": "Downloaded source workbooks are retained as raw source data.",
            "metadata_json": _json({"source_system": "englishprofile.org"}),
        },
        {
            "source_key": "cefr_companion_volume",
            "source_name": SOURCE_DOCUMENT,
            "source_type": "cefr_companion_volume",
            "source_version": "2020",
            "source_year": SOURCE_YEAR,
            "source_url": None,
            "license_note": "Council of Europe CEFR Companion Volume metadata retained from source artifacts.",
            "metadata_json": _json({"source_year": SOURCE_YEAR}),
        },
    ]
    ids: dict[str, int] = {}
    for row in source_rows:
        connection.execute(
            """
            INSERT INTO knowledge_sources (
                source_key,
                source_name,
                source_type,
                source_version,
                source_year,
                source_url,
                license_note,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_key) DO UPDATE SET
                source_name = excluded.source_name,
                source_type = excluded.source_type,
                source_version = excluded.source_version,
                source_year = excluded.source_year,
                source_url = excluded.source_url,
                license_note = excluded.license_note,
                metadata_json = excluded.metadata_json
            """,
            (
                row["source_key"],
                row["source_name"],
                row["source_type"],
                row["source_version"],
                row["source_year"],
                row["source_url"],
                row["license_note"],
                row["metadata_json"],
            ),
        )
        ids[row["source_key"]] = _lookup_id(
            connection,
            "knowledge_sources",
            "source_key",
            row["source_key"],
        )
    return ids


def _load_source_documents(
    connection: sqlite3.Connection,
    *,
    artifacts: StorageArtifacts,
    source_ids: dict[str, int],
) -> dict[tuple[str, str], int]:
    document_specs: dict[tuple[str, str], dict[str, Any]] = {}

    for record in artifacts.egp_records:
        source_file = _normalized_path(record.source_file)
        document_specs[("english_grammar_profile", source_file)] = {
            "document_key": _stable_key("doc", "english_grammar_profile", source_file),
            "title": _title_from_path(source_file),
            "file_name": Path(source_file).name,
            "file_hash": _file_hash(source_file),
            "language": "English",
            "publication_year": None,
            "page_count": None,
            "metadata_json": _json({"source_file": source_file}),
        }

    cefr_pages: dict[str, int] = {}
    for record in artifacts.cefr_descriptors:
        source_file = _normalized_path(record.source_file)
        if record.page_number is not None:
            cefr_pages[source_file] = max(cefr_pages.get(source_file, 0), record.page_number)
        document_specs[("cefr_companion_volume", source_file)] = {
            "document_key": _stable_key("doc", "cefr_companion_volume", source_file),
            "title": record.source_document,
            "file_name": Path(source_file).name,
            "file_hash": _file_hash(source_file),
            "language": "English",
            "publication_year": record.source_year,
            "page_count": cefr_pages.get(source_file),
            "metadata_json": _json({"source_file": source_file}),
        }

    ids: dict[tuple[str, str], int] = {}
    for (source_key, source_file), spec in sorted(document_specs.items()):
        connection.execute(
            """
            INSERT INTO source_documents (
                knowledge_source_id,
                document_key,
                title,
                file_name,
                file_hash,
                language,
                publication_year,
                page_count,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(knowledge_source_id, document_key) DO UPDATE SET
                title = excluded.title,
                file_name = excluded.file_name,
                file_hash = excluded.file_hash,
                language = excluded.language,
                publication_year = excluded.publication_year,
                page_count = excluded.page_count,
                metadata_json = excluded.metadata_json
            """,
            (
                source_ids[source_key],
                spec["document_key"],
                spec["title"],
                spec["file_name"],
                spec["file_hash"],
                spec["language"],
                spec["publication_year"],
                spec["page_count"],
                spec["metadata_json"],
            ),
        )
        ids[(source_key, source_file)] = _lookup_composite_id(
            connection,
            "source_documents",
            "knowledge_source_id = ? AND document_key = ?",
            (source_ids[source_key], spec["document_key"]),
        )
    return ids


def _load_source_records(
    connection: sqlite3.Connection,
    *,
    artifacts: StorageArtifacts,
    source_ids: dict[str, int],
    document_ids: dict[tuple[str, str], int],
) -> dict[str, int]:
    ids: dict[str, int] = {}

    for record in artifacts.egp_records:
        external_id = record.source_record_id or _stable_key(
            "egp_missing",
            record.category_id,
            record.source_file,
            record.source_row_number,
            record.can_do_statement,
        )
        source_file = _normalized_path(record.source_file)
        payload = _payload(record)
        _upsert_source_record(
            connection,
            knowledge_source_id=source_ids["english_grammar_profile"],
            source_document_id=document_ids[("english_grammar_profile", source_file)],
            external_record_id=external_id,
            record_type="egp_grammar_record",
            cefr_level=record.cefr_level,
            raw_text=record.can_do_statement,
            normalized_text=record.can_do_statement,
            page_number=None,
            row_number=record.source_row_number,
            sheet_name=record.category_id,
            raw_payload=payload,
        )
        ids[external_id] = _lookup_source_record_id(
            connection,
            source_ids["english_grammar_profile"],
            external_id,
            "egp_grammar_record",
        )

    for record in artifacts.cefr_descriptors:
        source_file = _normalized_path(record.source_file)
        payload = _payload(record)
        _upsert_source_record(
            connection,
            knowledge_source_id=source_ids["cefr_companion_volume"],
            source_document_id=document_ids[("cefr_companion_volume", source_file)],
            external_record_id=record.source_record_id,
            record_type="cefr_descriptor",
            cefr_level=record.cefr_level,
            raw_text=record.descriptor_text,
            normalized_text=record.descriptor_text,
            page_number=record.page_number,
            row_number=None,
            sheet_name=record.source_table,
            raw_payload=payload,
        )
        ids[record.source_record_id] = _lookup_source_record_id(
            connection,
            source_ids["cefr_companion_volume"],
            record.source_record_id,
            "cefr_descriptor",
        )

    return ids


def _upsert_source_record(
    connection: sqlite3.Connection,
    *,
    knowledge_source_id: int,
    source_document_id: int | None,
    external_record_id: str,
    record_type: str,
    cefr_level: str | None,
    raw_text: str | None,
    normalized_text: str | None,
    page_number: int | None,
    row_number: int | None,
    sheet_name: str | None,
    raw_payload: dict[str, Any],
) -> None:
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
        ON CONFLICT(knowledge_source_id, external_record_id, record_type) DO UPDATE SET
            source_document_id = excluded.source_document_id,
            cefr_level = excluded.cefr_level,
            raw_text = excluded.raw_text,
            normalized_text = excluded.normalized_text,
            page_number = excluded.page_number,
            row_number = excluded.row_number,
            sheet_name = excluded.sheet_name,
            raw_payload_json = excluded.raw_payload_json,
            record_hash = excluded.record_hash
        """,
        (
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
            _json(raw_payload),
            _hash_payload(raw_payload),
        ),
    )


def _load_knowledge_nodes(
    connection: sqlite3.Connection,
    *,
    version_id: int,
    taxonomy: Any,
) -> dict[str, int]:
    node_ids: dict[str, int] = {}
    for node_id in sorted(taxonomy.all_node_ids, key=lambda item: (item.count("."), item)):
        parent_id = taxonomy.parent_by_node.get(node_id)
        spec = SKILL_ASSESSMENT_SPECS.get(node_id)
        if node_id == taxonomy.root_id:
            node_type = "root"
            name = "Grammar"
            description = "Grammar domain root."
        elif node_id in taxonomy.atomic_skill_ids:
            node_type = "atomic_skill"
            name = spec.label if spec else _humanize_node_id(node_id)
            description = spec.observable if spec else None
        else:
            node_type = "group"
            name = _humanize_node_id(node_id)
            description = None

        connection.execute(
            """
            INSERT INTO knowledge_nodes (
                knowledge_version_id,
                canonical_id,
                node_type,
                domain,
                name,
                description,
                parent_node_id,
                is_atomic,
                is_active,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                version_id,
                node_id,
                node_type,
                node_id.split(".")[0],
                name,
                description,
                node_ids[parent_id] if parent_id else None,
                1 if node_type == "atomic_skill" else 0,
                _json({"taxonomy_hash": taxonomy.taxonomy_hash}),
            ),
        )
        node_ids[node_id] = int(connection.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
    return node_ids


def _load_skill_profiles(
    connection: sqlite3.Connection,
    *,
    profiles: Iterable[CanonicalSkillEvidenceProfile],
    node_ids: dict[str, int],
) -> None:
    for profile in profiles:
        node_id = _required_node_id(node_ids, profile.canonical_skill_id)
        connection.execute(
            """
            INSERT INTO skill_profiles (
                knowledge_node_id,
                cefr_min_level,
                cefr_primary_level,
                evidence_status,
                alignment_confidence,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                node_id,
                profile.cefr_min_level,
                profile.cefr_primary_level,
                profile.evidence_status,
                profile.alignment_confidence,
                profile.notes,
            ),
        )


def _load_skill_source_evidence(
    connection: sqlite3.Connection,
    *,
    evidence_items: Iterable[SkillSourceEvidence],
    node_ids: dict[str, int],
    source_record_ids: dict[str, int],
) -> None:
    for item in evidence_items:
        source_record_id = _required_source_record_id(source_record_ids, item.source_record_id)
        connection.execute(
            """
            INSERT INTO skill_source_evidence (
                evidence_key,
                knowledge_node_id,
                source_record_id,
                evidence_type,
                confidence,
                status,
                review_status,
                reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.evidence_id,
                _required_node_id(node_ids, item.canonical_skill_id),
                source_record_id,
                item.evidence_type,
                item.confidence,
                item.status,
                _review_status(item.provenance, default="pending"),
                _reason(item.provenance),
            ),
        )


def _load_learning_objectives(
    connection: sqlite3.Connection,
    *,
    version_id: int,
    objectives: Iterable[Any],
    source_record_ids: dict[str, int],
) -> dict[str, int]:
    objective_ids: dict[str, int] = {}
    for objective in objectives:
        source_record_id = _required_source_record_id(
            source_record_ids,
            objective.source_record_id,
        )
        connection.execute(
            """
            INSERT INTO learning_objectives (
                knowledge_version_id,
                objective_key,
                cefr_level,
                domain,
                scale_name,
                objective_text,
                source_record_id,
                status,
                confidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                objective.objective_id,
                objective.cefr_level,
                objective.domain,
                objective.scale_name,
                objective.objective_text,
                source_record_id,
                objective.status,
                objective.confidence,
            ),
        )
        objective_ids[objective.objective_id] = int(
            connection.execute("SELECT last_insert_rowid() AS id").fetchone()["id"],
        )
    return objective_ids


def _load_skill_learning_objectives(
    connection: sqlite3.Connection,
    *,
    profiles: Iterable[CanonicalSkillEvidenceProfile],
    node_ids: dict[str, int],
    objective_ids: dict[str, int],
) -> None:
    for profile in profiles:
        objective_alignment_by_id = {
            alignment.get("objective_id"): alignment
            for alignment in profile.provenance.get("objective_alignments", [])
            if alignment.get("objective_id")
        }
        for alignment_type, profile_objective_ids in [
            ("direct", profile.direct_objective_ids),
            ("contextual", profile.contextual_objective_ids),
        ]:
            for objective_id in profile_objective_ids:
                alignment = objective_alignment_by_id.get(objective_id, {})
                connection.execute(
                    """
                    INSERT INTO skill_learning_objectives (
                        knowledge_node_id,
                        learning_objective_id,
                        alignment_type,
                        confidence,
                        reason,
                        review_status
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _required_node_id(node_ids, profile.canonical_skill_id),
                        _required_objective_id(objective_ids, objective_id),
                        alignment_type,
                        float(alignment.get("confidence", profile.alignment_confidence)),
                        alignment.get("reason", profile.notes),
                        alignment.get("review_status", "pending"),
                    ),
                )


def _load_skill_cefr_alignments(
    connection: sqlite3.Connection,
    *,
    alignments: Iterable[SkillCEFRAlignment],
    node_ids: dict[str, int],
) -> None:
    for alignment in alignments:
        connection.execute(
            """
            INSERT INTO skill_cefr_alignments (
                knowledge_node_id,
                inferred_min_level,
                inferred_primary_level,
                confidence,
                status,
                review_status,
                reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _required_node_id(node_ids, alignment.canonical_skill_id),
                alignment.inferred_min_level,
                alignment.inferred_primary_level,
                alignment.confidence,
                alignment.status,
                alignment.review_status,
                alignment.reason,
            ),
        )


def _load_relationships(
    connection: sqlite3.Connection,
    *,
    version_id: int,
    relationships: Iterable[SkillRelationship],
    node_ids: dict[str, int],
    source_record_ids: dict[str, int],
) -> dict[str, int]:
    relationship_ids: dict[str, int] = {}
    for relationship in relationships:
        source_node_id = _required_node_id(node_ids, relationship.source_skill_id)
        target_node_id = _required_node_id(node_ids, relationship.target_skill_id)
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                relationship.relationship_id,
                source_node_id,
                target_node_id,
                relationship.relation_type,
                relationship.dependency_strength,
                relationship.confidence,
                relationship.status,
                relationship.review_status,
                relationship.reason,
                1 if relationship.bidirectional else 0,
            ),
        )
        relationship_db_id = int(
            connection.execute("SELECT last_insert_rowid() AS id").fetchone()["id"],
        )
        relationship_ids[relationship.relationship_id] = relationship_db_id
        _load_relationship_evidence(
            connection,
            relationship_db_id=relationship_db_id,
            evidence_items=relationship.evidence,
            source_record_ids=source_record_ids,
        )
    return relationship_ids


def _load_relationship_evidence(
    connection: sqlite3.Connection,
    *,
    relationship_db_id: int,
    evidence_items: Iterable[RelationshipEvidence],
    source_record_ids: dict[str, int],
) -> None:
    for item in evidence_items:
        if not item.source_record_ids:
            _insert_relationship_evidence(
                connection,
                relationship_db_id=relationship_db_id,
                source_record_id=None,
                external_reference_id=None,
                evidence_type=item.evidence_type,
                note=item.note,
            )
            continue
        for external_id in sorted(set(item.source_record_ids)):
            db_source_record_id = source_record_ids.get(external_id)
            _insert_relationship_evidence(
                connection,
                relationship_db_id=relationship_db_id,
                source_record_id=db_source_record_id,
                external_reference_id=None if db_source_record_id is not None else external_id,
                evidence_type=item.evidence_type,
                note=item.note,
            )


def _insert_relationship_evidence(
    connection: sqlite3.Connection,
    *,
    relationship_db_id: int,
    source_record_id: int | None,
    external_reference_id: str | None,
    evidence_type: str,
    note: str | None,
) -> None:
    connection.execute(
        """
        INSERT INTO relationship_evidence (
            relationship_id,
            source_record_id,
            external_reference_id,
            evidence_type,
            note
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (relationship_db_id, source_record_id, external_reference_id, evidence_type, note),
    )


def _load_assessment_criteria(
    connection: sqlite3.Connection,
    *,
    version_id: int,
    criteria: Iterable[AssessmentCriterion],
    node_ids: dict[str, int],
    source_record_ids: dict[str, int],
) -> None:
    for criterion in criteria:
        connection.execute(
            """
            INSERT INTO assessment_criteria (
                knowledge_version_id,
                criterion_key,
                knowledge_node_id,
                criterion_type,
                name,
                description,
                observable_behavior,
                cefr_level,
                recommended_threshold,
                recommended_min_items,
                threshold_source,
                confidence,
                status,
                review_status,
                reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                criterion.criterion_id,
                _required_node_id(node_ids, criterion.canonical_skill_id),
                criterion.criterion_type,
                criterion.name,
                criterion.description,
                criterion.observable_behavior,
                criterion.cefr_level,
                criterion.recommended_threshold,
                criterion.recommended_min_items,
                criterion.threshold_source,
                criterion.confidence,
                criterion.status,
                criterion.review_status,
                criterion.reason,
            ),
        )
        criterion_db_id = int(
            connection.execute("SELECT last_insert_rowid() AS id").fetchone()["id"],
        )
        _load_assessment_children(connection, criterion_db_id, criterion)
        _load_assessment_evidence(
            connection,
            criterion_db_id=criterion_db_id,
            evidence_items=criterion.provenance,
            source_record_ids=source_record_ids,
        )


def _load_assessment_children(
    connection: sqlite3.Connection,
    criterion_db_id: int,
    criterion: AssessmentCriterion,
) -> None:
    for position, requirement in enumerate(criterion.evidence_requirements, start=1):
        connection.execute(
            """
            INSERT INTO assessment_evidence_requirements (
                assessment_criterion_id,
                requirement_text,
                position
            )
            VALUES (?, ?, ?)
            """,
            (criterion_db_id, requirement, position),
        )
    for position, signal in enumerate(criterion.failure_signals, start=1):
        connection.execute(
            """
            INSERT INTO assessment_failure_signals (
                assessment_criterion_id,
                signal_text,
                position
            )
            VALUES (?, ?, ?)
            """,
            (criterion_db_id, signal, position),
        )
    for task_type in criterion.acceptable_task_types:
        connection.execute(
            """
            INSERT INTO assessment_task_types (
                assessment_criterion_id,
                task_type
            )
            VALUES (?, ?)
            """,
            (criterion_db_id, task_type),
        )


def _load_assessment_evidence(
    connection: sqlite3.Connection,
    *,
    criterion_db_id: int,
    evidence_items: Iterable[AssessmentEvidence],
    source_record_ids: dict[str, int],
) -> None:
    for item in evidence_items:
        if not item.source_record_ids:
            _insert_assessment_evidence(
                connection,
                criterion_db_id=criterion_db_id,
                source_record_id=None,
                external_reference_id=None,
                evidence_type=item.evidence_type,
                note=item.note,
            )
            continue
        for external_id in sorted(set(item.source_record_ids)):
            db_source_record_id = source_record_ids.get(external_id)
            _insert_assessment_evidence(
                connection,
                criterion_db_id=criterion_db_id,
                source_record_id=db_source_record_id,
                external_reference_id=None if db_source_record_id is not None else external_id,
                evidence_type=item.evidence_type,
                note=item.note,
            )


def _insert_assessment_evidence(
    connection: sqlite3.Connection,
    *,
    criterion_db_id: int,
    source_record_id: int | None,
    external_reference_id: str | None,
    evidence_type: str,
    note: str | None,
) -> None:
    connection.execute(
        """
        INSERT INTO assessment_evidence (
            assessment_criterion_id,
            source_record_id,
            external_reference_id,
            evidence_type,
            note
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (criterion_db_id, source_record_id, external_reference_id, evidence_type, note),
    )


def _load_corpus_error_statistics(
    connection: sqlite3.Connection,
    *,
    version_id: int,
    artifacts: StorageArtifacts,
    source_ids: dict[str, int],
    node_ids: dict[str, int],
) -> None:
    for row in corpus_error_statistic_rows(artifacts):
        statistic_key = _stable_key(
            "errstat",
            row.get("statistic_type"),
            row.get("source_key"),
            row.get("canonical_skill_id"),
            row.get("normalized_category"),
            row.get("normalized_subtype"),
            row.get("mapping_status"),
            row.get("source_label"),
        )
        source_key = row.get("source_key")
        skill_id = row.get("canonical_skill_id")
        connection.execute(
            """
            INSERT INTO corpus_error_statistics (
                knowledge_version_id,
                statistic_key,
                knowledge_source_id,
                knowledge_node_id,
                statistic_type,
                normalized_category,
                normalized_subtype,
                mapping_status,
                source_label,
                count,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                statistic_key,
                source_ids.get(str(source_key)) if source_key else None,
                node_ids.get(str(skill_id)) if skill_id else None,
                row["statistic_type"],
                row.get("normalized_category"),
                row.get("normalized_subtype"),
                row.get("mapping_status"),
                row.get("source_label"),
                int(row["count"]),
                _json(
                    {
                        key: value
                        for key, value in row.items()
                        if key
                        not in {
                            "statistic_type",
                            "source_key",
                            "canonical_skill_id",
                            "normalized_category",
                            "normalized_subtype",
                            "mapping_status",
                            "source_label",
                            "count",
                        }
                    },
                ),
            ),
        )


def _load_corpus_error_skill_mappings(
    connection: sqlite3.Connection,
    *,
    version_id: int,
    mappings: Iterable[ErrorSkillMapping],
    source_ids: dict[str, int],
    node_ids: dict[str, int],
) -> dict[str, int]:
    ids: dict[str, int] = {}
    for mapping in mappings:
        connection.execute(
            """
            INSERT INTO corpus_error_skill_mappings (
                knowledge_version_id,
                mapping_key,
                knowledge_source_id,
                knowledge_node_id,
                normalized_error_id,
                error_instance_id,
                external_source_record_id,
                source_key,
                status,
                confidence,
                review_status,
                reason,
                provenance_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                mapping.mapping_id,
                _required_source_id(source_ids, mapping.source_key),
                _required_node_id(node_ids, mapping.canonical_skill_id),
                mapping.normalized_error_id,
                mapping.error_instance_id,
                mapping.source_record_id,
                mapping.source_key,
                mapping.status,
                mapping.confidence,
                mapping.review_status,
                mapping.reason,
                _json(mapping.provenance),
            ),
        )
        ids[mapping.mapping_id] = int(
            connection.execute("SELECT last_insert_rowid() AS id").fetchone()["id"],
        )
    return ids


def _load_misconceptions(
    connection: sqlite3.Connection,
    *,
    version_id: int,
    misconceptions: Iterable[MisconceptionCandidate],
    source_ids: dict[str, int],
    node_ids: dict[str, int],
    mapping_ids: dict[str, int],
) -> dict[str, int]:
    ids: dict[str, int] = {}
    for misconception in misconceptions:
        connection.execute(
            """
            INSERT INTO misconceptions (
                knowledge_version_id,
                misconception_key,
                knowledge_node_id,
                name,
                description,
                error_category,
                error_subtype,
                expected_pattern,
                observed_pattern,
                diagnostic_rule,
                source_evidence_count,
                frequency,
                frequency_scope,
                severity,
                confidence,
                status,
                review_status,
                reason,
                provenance_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                misconception.misconception_id,
                _required_node_id(node_ids, misconception.canonical_skill_id),
                misconception.name,
                misconception.description,
                misconception.error_category,
                misconception.error_subtype,
                misconception.expected_pattern,
                misconception.observed_pattern,
                misconception.diagnostic_rule,
                misconception.source_evidence_count,
                misconception.frequency,
                misconception.frequency_scope,
                misconception.severity,
                misconception.confidence,
                misconception.status,
                misconception.review_status,
                misconception.reason,
                _json(
                    {
                        **misconception.provenance,
                        "source_labels": misconception.source_labels,
                        "source_distribution": misconception.source_distribution,
                        "source_frequencies": misconception.source_frequencies,
                        "proficiency_distribution": misconception.proficiency_distribution,
                        "version": misconception.version,
                    },
                ),
            ),
        )
        misconception_db_id = int(
            connection.execute("SELECT last_insert_rowid() AS id").fetchone()["id"],
        )
        ids[misconception.misconception_id] = misconception_db_id
        _load_misconception_evidence(
            connection,
            misconception_db_id=misconception_db_id,
            evidence_links=misconception.evidence_links,
            source_ids=source_ids,
            mapping_ids=mapping_ids,
        )
    return ids


def _load_misconception_evidence(
    connection: sqlite3.Connection,
    *,
    misconception_db_id: int,
    evidence_links: Iterable[Any],
    source_ids: dict[str, int],
    mapping_ids: dict[str, int],
) -> None:
    for link in evidence_links:
        connection.execute(
            """
            INSERT INTO misconception_evidence (
                misconception_id,
                error_skill_mapping_id,
                knowledge_source_id,
                normalized_error_id,
                error_instance_id,
                external_source_record_id,
                source_key,
                source_label,
                proficiency_label,
                task_id,
                split,
                mapping_confidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                misconception_db_id,
                mapping_ids.get(link.mapping_id),
                _required_source_id(source_ids, link.source_key),
                link.normalized_error_id,
                link.error_instance_id,
                link.source_record_id,
                link.source_key,
                link.source_label,
                link.proficiency_label,
                link.task_id,
                link.split,
                link.mapping_confidence,
            ),
        )


def _load_skill_misconception_links(
    connection: sqlite3.Connection,
    *,
    version_id: int,
    links: Iterable[SkillMisconceptionLink],
    node_ids: dict[str, int],
    misconception_ids: dict[str, int],
) -> None:
    for link in links:
        connection.execute(
            """
            INSERT INTO skill_misconception_links (
                knowledge_version_id,
                link_key,
                misconception_id,
                knowledge_node_id,
                evidence_status,
                source_evidence_count,
                confidence,
                review_status,
                reason,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                link.link_id,
                _required_misconception_id(misconception_ids, link.misconception_id),
                _required_node_id(node_ids, link.canonical_skill_id),
                link.evidence_status,
                link.source_evidence_count,
                link.confidence,
                link.review_status,
                link.reason,
                _json(
                    {
                        "source_distribution": link.source_distribution,
                        "proficiency_distribution": link.proficiency_distribution,
                        "version": link.version,
                    },
                ),
            ),
        )


def _activate_version(connection: sqlite3.Connection, version_id: int) -> None:
    connection.execute(
        "UPDATE knowledge_versions SET status = 'inactive' WHERE id != ? AND status = 'active'",
        (version_id,),
    )
    connection.execute(
        """
        UPDATE knowledge_versions
        SET status = 'active', activated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (version_id,),
    )


def _database_counts(connection: sqlite3.Connection, version_id: int) -> dict[str, int]:
    node_scope = "SELECT id FROM knowledge_nodes WHERE knowledge_version_id = ?"
    criterion_scope = "SELECT id FROM assessment_criteria WHERE knowledge_version_id = ?"
    relationship_scope = "SELECT id FROM skill_relationships WHERE knowledge_version_id = ?"
    return {
        "knowledge_nodes": _count(
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
        "egp_source_records": _count(
            connection,
            """
            SELECT COUNT(*) AS count
            FROM source_records sr
            JOIN knowledge_sources ks ON ks.id = sr.knowledge_source_id
            WHERE ks.source_key = 'english_grammar_profile'
              AND sr.record_type = 'egp_grammar_record'
            """,
        ),
        "cefr_source_records": _count(
            connection,
            """
            SELECT COUNT(*) AS count
            FROM source_records sr
            JOIN knowledge_sources ks ON ks.id = sr.knowledge_source_id
            WHERE ks.source_key = 'cefr_companion_volume'
              AND sr.record_type = 'cefr_descriptor'
            """,
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


def _count(
    connection: sqlite3.Connection,
    sql: str,
    params: tuple[Any, ...] = (),
) -> int:
    row = connection.execute(sql, params).fetchone()
    return int(row["count"])


def _lookup_id(
    connection: sqlite3.Connection,
    table_name: str,
    key_column: str,
    value: str,
) -> int:
    row = connection.execute(
        f"SELECT id FROM {table_name} WHERE {key_column} = ?",
        (value,),
    ).fetchone()
    if row is None:
        raise KnowledgeStorageLoadError(f"Missing {table_name}.{key_column}: {value}")
    return int(row["id"])


def _lookup_composite_id(
    connection: sqlite3.Connection,
    table_name: str,
    where_sql: str,
    params: tuple[Any, ...],
) -> int:
    row = connection.execute(
        f"SELECT id FROM {table_name} WHERE {where_sql}",
        params,
    ).fetchone()
    if row is None:
        raise KnowledgeStorageLoadError(f"Missing {table_name} row for {where_sql}")
    return int(row["id"])


def _lookup_source_record_id(
    connection: sqlite3.Connection,
    knowledge_source_id: int,
    external_record_id: str,
    record_type: str,
) -> int:
    return _lookup_composite_id(
        connection,
        "source_records",
        "knowledge_source_id = ? AND external_record_id = ? AND record_type = ?",
        (knowledge_source_id, external_record_id, record_type),
    )


def _required_node_id(node_ids: dict[str, int], canonical_id: str) -> int:
    try:
        return node_ids[canonical_id]
    except KeyError as exc:
        raise KnowledgeStorageLoadError(f"Unknown canonical skill/node id: {canonical_id}") from exc


def _required_source_record_id(source_record_ids: dict[str, int], source_record_id: str) -> int:
    try:
        return source_record_ids[source_record_id]
    except KeyError as exc:
        raise KnowledgeStorageLoadError(f"Unknown source_record_id: {source_record_id}") from exc


def _required_objective_id(objective_ids: dict[str, int], objective_id: str) -> int:
    try:
        return objective_ids[objective_id]
    except KeyError as exc:
        raise KnowledgeStorageLoadError(f"Unknown objective_id: {objective_id}") from exc


def _required_source_id(source_ids: dict[str, int], source_key: str) -> int:
    try:
        return source_ids[source_key]
    except KeyError as exc:
        raise KnowledgeStorageLoadError(f"Unknown knowledge source key: {source_key}") from exc


def _required_misconception_id(
    misconception_ids: dict[str, int],
    misconception_id: str,
) -> int:
    try:
        return misconception_ids[misconception_id]
    except KeyError as exc:
        raise KnowledgeStorageLoadError(
            f"Unknown misconception_id: {misconception_id}",
        ) from exc


def _payload(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


def _json(payload: dict[str, Any] | list[Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def _hash_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


def _stable_key(prefix: str, *parts: Any) -> str:
    raw = "\x1f".join("" if part is None else str(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return f"{prefix}_{digest}"


def _normalized_path(path: str) -> str:
    return path.replace("\\", "/")


def _file_hash(path: str) -> str | None:
    source_path = Path(path)
    if not source_path.exists():
        return None
    digest = hashlib.sha256()
    with source_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _title_from_path(path: str) -> str:
    title = Path(path).stem.replace("_", " ").replace("-", " ").strip()
    return " ".join(title.split()).title() or path


def _humanize_node_id(node_id: str) -> str:
    return node_id.split(".")[-1].replace("_", " ")


def _review_status(provenance: dict[str, Any], *, default: str) -> str:
    return str(provenance.get("review_status") or default)


def _reason(provenance: dict[str, Any]) -> str | None:
    reason = provenance.get("reason")
    return str(reason) if reason else None
