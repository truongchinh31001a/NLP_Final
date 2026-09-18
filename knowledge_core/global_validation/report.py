from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import AppConfig
from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILLS
from knowledge_core.relationships.graph import SkillRelationshipGraph
from knowledge_core.relationships.taxonomy import build_grammar_taxonomy
from knowledge_core.relationships.validator import validate_relationships
from knowledge_core.storage.artifacts import StorageArtifacts, load_storage_artifacts
from knowledge_core.storage.config import DEFAULT_VERSION_NAME
from knowledge_core.storage.loader import KnowledgeStorageLoadResult, load_knowledge_core
from knowledge_core.storage.schema import KNOWLEDGE_TABLES, KNOWLEDGE_VIEWS, initialize_schema
from knowledge_core.storage.validator import KnowledgeStorageValidationResult, validate_storage


@dataclass(frozen=True, slots=True)
class KnowledgeCoreV1ReportResult:
    report: dict[str, Any]
    report_path: Path | None
    first_load: KnowledgeStorageLoadResult
    second_load: KnowledgeStorageLoadResult
    storage_validation: KnowledgeStorageValidationResult


def run_global_validation(
    *,
    db_path: str | Path | None = None,
    version_name: str = DEFAULT_VERSION_NAME,
    report_path: str | Path = "data/reports/knowledge_core_v1_report.json",
    artifacts: StorageArtifacts | None = None,
    dry_run: bool = False,
    run_postgres_validation: bool | None = None,
) -> KnowledgeCoreV1ReportResult:
    resolved_artifacts = artifacts or load_storage_artifacts()
    initialize_schema(db_path)
    first = load_knowledge_core(
        db_path=db_path,
        version_name=version_name,
        artifacts=resolved_artifacts,
        ensure_schema=False,
    )
    second = load_knowledge_core(
        db_path=db_path,
        version_name=version_name,
        artifacts=resolved_artifacts,
        ensure_schema=False,
    )
    storage_validation = validate_storage(
        db_path=db_path,
        version_name=version_name,
        artifacts=resolved_artifacts,
    )

    report = build_global_report(
        artifacts=resolved_artifacts,
        first_load=first,
        second_load=second,
        storage_validation=storage_validation,
        db_path=db_path,
        run_postgres_validation=run_postgres_validation,
    )
    destination = Path(report_path)
    written_path = None
    if not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written_path = destination
    return KnowledgeCoreV1ReportResult(
        report=report,
        report_path=written_path,
        first_load=first,
        second_load=second,
        storage_validation=storage_validation,
    )


def build_global_report(
    *,
    artifacts: StorageArtifacts,
    first_load: KnowledgeStorageLoadResult,
    second_load: KnowledgeStorageLoadResult,
    storage_validation: KnowledgeStorageValidationResult,
    db_path: str | Path | None,
    run_postgres_validation: bool | None,
) -> dict[str, Any]:
    taxonomy = build_grammar_taxonomy(CANONICAL_GRAMMAR_V1_SKILLS)
    relationship_validation = validate_relationships(artifacts.relationships, taxonomy)
    graph = SkillRelationshipGraph(artifacts.relationships, taxonomy)
    graph_analysis = graph.analyze()
    source_validation = _validate_source_and_provenance_references(artifacts)
    source_manifest = _source_manifest_status()
    reconciliation = _reconcile_counts(
        artifacts=artifacts,
        db_counts=storage_validation.counts,
    )
    idempotency = {
        "passed": first_load.db_counts == second_load.db_counts,
        "first_load_counts": first_load.db_counts,
        "second_load_counts": second_load.db_counts,
        "differences": _count_differences(first_load.db_counts, second_load.db_counts),
    }
    postgres = _postgres_validation_status(run_postgres_validation)
    validation_errors = []
    if not storage_validation.is_valid:
        validation_errors.extend(storage_validation.errors)
    if relationship_validation.error_count:
        validation_errors.extend(issue.message for issue in relationship_validation.errors)
    if source_validation["error_count"]:
        validation_errors.extend(issue["message"] for issue in source_validation["issues"])
    if not source_manifest["validation_passed"]:
        validation_errors.append("Knowledge source manifest is missing or invalid.")
    if not idempotency["passed"]:
        validation_errors.append("Storage reload is not idempotent.")
    if not reconciliation["passed"]:
        validation_errors.extend(reconciliation["errors"])

    production_claim_allowed = (
        not validation_errors
        and postgres["status"] == "passed"
    )
    return {
        "schema_version": "knowledge_core_v1_global_validation_report",
        "version_name": second_load.version_name,
        "db_path": str(AppConfig().sqlite_db_path if db_path is None else db_path),
        "taxonomy": {
            "root_id": taxonomy.root_id,
            "node_count": len(taxonomy.all_node_ids),
            "expected_node_count": 54,
            "atomic_skill_count": len(taxonomy.atomic_skill_ids),
            "expected_atomic_skill_count": 43,
            "group_node_count": len(taxonomy.group_node_ids),
            "taxonomy_hash": taxonomy.taxonomy_hash,
            "taxonomy_unchanged": tuple(taxonomy.atomic_skill_ids)
            == tuple(CANONICAL_GRAMMAR_V1_SKILLS),
            "validation_passed": len(taxonomy.all_node_ids) == 54
            and len(taxonomy.atomic_skill_ids) == 43,
        },
        "artifact_counts": artifacts.counts(),
        "storage": {
            "tables_expected": len(KNOWLEDGE_TABLES),
            "views_expected": len(KNOWLEDGE_VIEWS),
            "validation": storage_validation.to_dict(),
            "idempotency": idempotency,
            "reconciliation": reconciliation,
        },
        "relationship_graph": {
            "validation": {
                "passed": relationship_validation.error_count == 0,
                "error_count": relationship_validation.error_count,
                "warning_count": relationship_validation.warning_count,
                "cycles": relationship_validation.cycles_found,
                "invalid_references": relationship_validation.invalid_references,
                "duplicate_edges": relationship_validation.duplicate_edges,
                "prerequisite_dag_valid": relationship_validation.prerequisite_dag_valid,
            },
            "analysis": graph_analysis.model_dump(mode="json"),
        },
        "source_and_provenance_validation": source_validation,
        "source_manifest": source_manifest,
        "review_status": _review_status_summary(artifacts),
        "postgres_validation": postgres,
        "production_claim_allowed": production_claim_allowed,
        "validation_result": "pass" if not validation_errors else "fail",
        "validation_errors": validation_errors,
        "known_limitations": _known_limitations(postgres),
    }


def _source_manifest_status(
    path: str | Path = "data/curated/source_metadata/source_manifest.json",
) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {
            "path": str(source).replace("\\", "/"),
            "available": False,
            "validation_passed": False,
        }
    payload = json.loads(source.read_text(encoding="utf-8"))
    validation = payload.get("validation") or {}
    return {
        "path": str(source).replace("\\", "/"),
        "available": True,
        "schema_version": payload.get("schema_version"),
        "source_count": payload.get("source_count"),
        "file_count": payload.get("file_count"),
        "validation_passed": validation.get("passed") is True,
        "warning_count": validation.get("warning_count", 0),
    }


def _validate_source_and_provenance_references(
    artifacts: StorageArtifacts,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    source_record_ids = {
        *(record.source_record_id for record in artifacts.egp_records),
        *(record.source_record_id for record in artifacts.cefr_descriptors),
    }
    relationship_ids = {relationship.relationship_id for relationship in artifacts.relationships}
    objective_ids = {objective.objective_id for objective in artifacts.learning_objectives}
    skill_ids = set(CANONICAL_GRAMMAR_V1_SKILLS)
    error_mapping_ids = {mapping.mapping_id for mapping in artifacts.error_skill_mappings}

    for evidence in artifacts.skill_evidence:
        if evidence.source_record_id not in source_record_ids:
            issues.append(
                _issue(
                    "missing_skill_source_record",
                    f"Skill evidence references missing source record: {evidence.source_record_id}",
                    evidence_id=evidence.evidence_id,
                ),
            )

    for profile in artifacts.skill_profiles:
        for objective_id in profile.direct_objective_ids + profile.contextual_objective_ids:
            if objective_id not in objective_ids:
                issues.append(
                    _issue(
                        "missing_skill_objective_reference",
                        f"Skill profile references missing objective: {objective_id}",
                        canonical_skill_id=profile.canonical_skill_id,
                    ),
                )

    for relationship in artifacts.relationships:
        if relationship.source_skill_id not in taxonomy_skill_or_group_ids():
            issues.append(
                _issue(
                    "missing_relationship_source_skill",
                    f"Relationship source not found: {relationship.source_skill_id}",
                    relationship_id=relationship.relationship_id,
                ),
            )
        if relationship.target_skill_id not in taxonomy_skill_or_group_ids():
            issues.append(
                _issue(
                    "missing_relationship_target_skill",
                    f"Relationship target not found: {relationship.target_skill_id}",
                    relationship_id=relationship.relationship_id,
                ),
            )
        for evidence in relationship.evidence:
            _validate_evidence_ids(
                source_record_ids=evidence.source_record_ids,
                valid_source_record_ids=source_record_ids,
                valid_relationship_ids=relationship_ids,
                code="missing_relationship_evidence_reference",
                owner_id=relationship.relationship_id,
                issues=issues,
            )

    for criterion in artifacts.assessment_criteria:
        if criterion.canonical_skill_id not in skill_ids:
            issues.append(
                _issue(
                    "missing_assessment_skill",
                    f"Assessment criterion references missing skill: {criterion.canonical_skill_id}",
                    criterion_id=criterion.criterion_id,
                ),
            )
        for evidence in criterion.provenance:
            if evidence.evidence_type == "relationship_context":
                valid_ids = relationship_ids
            else:
                valid_ids = source_record_ids
            for source_record_id in evidence.source_record_ids:
                if source_record_id not in valid_ids:
                    issues.append(
                        _issue(
                            "missing_assessment_evidence_reference",
                            f"Assessment provenance reference not found: {source_record_id}",
                            criterion_id=criterion.criterion_id,
                        ),
                    )

    for mapping in artifacts.error_skill_mappings:
        if mapping.canonical_skill_id not in skill_ids:
            issues.append(
                _issue(
                    "missing_error_mapping_skill",
                    f"Error-skill mapping references missing skill: {mapping.canonical_skill_id}",
                    mapping_id=mapping.mapping_id,
                ),
            )

    for misconception in (
        artifacts.candidate_misconceptions + artifacts.accepted_misconceptions
    ):
        if misconception.canonical_skill_id not in skill_ids:
            issues.append(
                _issue(
                    "missing_misconception_skill",
                    f"Misconception references missing skill: {misconception.canonical_skill_id}",
                    misconception_id=misconception.misconception_id,
                ),
            )
        for link in misconception.evidence_links:
            if link.mapping_id not in error_mapping_ids:
                issues.append(
                    _issue(
                        "missing_misconception_mapping_reference",
                        f"Misconception evidence references missing error mapping: {link.mapping_id}",
                        misconception_id=misconception.misconception_id,
                    ),
                )

    duplicate_rows = _duplicate_logical_rows(artifacts)
    for duplicate in duplicate_rows:
        issues.append(
            _issue(
                "duplicate_logical_row",
                f"Duplicate logical row detected: {duplicate}",
                duplicate_key=duplicate,
            ),
        )

    return {
        "passed": not issues,
        "error_count": len(issues),
        "warning_count": 0,
        "issues": issues,
        "duplicate_logical_rows": duplicate_rows,
    }


def taxonomy_skill_or_group_ids() -> set[str]:
    taxonomy = build_grammar_taxonomy(CANONICAL_GRAMMAR_V1_SKILLS)
    return set(taxonomy.all_node_ids)


def _validate_evidence_ids(
    *,
    source_record_ids: list[str],
    valid_source_record_ids: set[str],
    valid_relationship_ids: set[str],
    code: str,
    owner_id: str,
    issues: list[dict[str, Any]],
) -> None:
    for source_record_id in source_record_ids:
        if (
            source_record_id not in valid_source_record_ids
            and source_record_id not in valid_relationship_ids
        ):
            issues.append(
                _issue(
                    code,
                    f"Evidence reference not found: {source_record_id}",
                    owner_id=owner_id,
                ),
            )


def _duplicate_logical_rows(artifacts: StorageArtifacts) -> list[str]:
    groups = {
        "egp_records": [record.source_record_id for record in artifacts.egp_records],
        "cefr_descriptors": [
            record.source_record_id for record in artifacts.cefr_descriptors
        ],
        "skill_evidence": [item.evidence_id for item in artifacts.skill_evidence],
        "learning_objectives": [
            item.objective_id for item in artifacts.learning_objectives
        ],
        "relationships": [
            item.relationship_id for item in artifacts.relationships
        ],
        "assessment_criteria": [
            item.criterion_id for item in artifacts.assessment_criteria
        ],
        "error_skill_mappings": [
            item.mapping_id for item in artifacts.error_skill_mappings
        ],
        "candidate_misconceptions": [
            item.misconception_id for item in artifacts.candidate_misconceptions
        ],
        "accepted_misconceptions": [
            item.misconception_id for item in artifacts.accepted_misconceptions
        ],
        "skill_misconception_links": [
            item.link_id for item in artifacts.skill_misconception_links
        ],
    }
    duplicates: list[str] = []
    for group_name, keys in groups.items():
        counts = Counter(keys)
        duplicates.extend(
            f"{group_name}:{key}" for key, count in counts.items() if count > 1
        )
    return sorted(duplicates)


def _reconcile_counts(
    *,
    artifacts: StorageArtifacts,
    db_counts: dict[str, int],
) -> dict[str, Any]:
    artifact_counts = artifacts.counts()
    keys = [
        "source_records",
        "skill_source_evidence",
        "learning_objectives",
        "relationships",
        "assessment_criteria",
        "corpus_error_statistics",
        "error_skill_mappings",
        "misconceptions",
        "candidate_misconceptions",
        "accepted_misconceptions",
        "misconception_evidence",
        "skill_misconception_links",
    ]
    db_key_by_artifact_key = {
        "error_skill_mappings": "corpus_error_skill_mappings",
    }
    differences: dict[str, dict[str, int | None]] = {}
    errors: list[str] = []
    for key in keys:
        db_key = db_key_by_artifact_key.get(key, key)
        expected = artifact_counts.get(key)
        actual = db_counts.get(db_key)
        if expected != actual:
            differences[key] = {"artifact": expected, "db": actual}
            errors.append(f"Artifact/DB count mismatch for {key}: {expected} != {actual}")
    return {
        "passed": not differences,
        "differences": differences,
        "errors": errors,
    }


def _review_status_summary(artifacts: StorageArtifacts) -> dict[str, Any]:
    enrichment = artifacts.knowledge_enrichment_report
    error_review = _load_json_if_available(
        "data/reports/corpus_errors/error_mapping_human_review_report.json",
    )
    misconception_review = _load_json_if_available(
        "data/reports/misconceptions/misconception_human_review_report.json",
    )
    return {
        "egp": _load_report_status("data/reports/egp/mapping_report.json"),
        "cefr_alignment": _load_report_status(
            "data/reports/knowledge_alignment/cefr_egp_alignment_report.json",
        ),
        "relationships": _load_report_status(
            "data/reports/relationships/grammar_relationship_report.json",
        ),
        "assessment": _load_report_status(
            "data/reports/assessment/grammar_assessment_report.json",
        ),
        "errors": {
            "normalization_review_queue_count": artifacts.error_normalization_report.get(
                "review_queue_count",
            ),
            "mapping_review_queue_count": error_review.get("total_review_queue"),
            "approved_mappings": error_review.get("approved_mappings"),
            "rejected_mappings": error_review.get("rejected_mappings"),
            "needs_review_mappings": error_review.get("needs_review_mappings"),
            "undecided_mappings": error_review.get("undecided_mappings"),
            "validation_passed": (error_review.get("validation") or {}).get("passed"),
        },
        "misconceptions": {
            "candidate_count": artifacts.counts()["candidate_misconceptions"],
            "accepted_count": artifacts.counts()["accepted_misconceptions"],
            "approved": misconception_review.get("approved"),
            "rejected": misconception_review.get("rejected"),
            "needs_review": misconception_review.get("needs_review"),
            "undecided": misconception_review.get("undecided"),
            "validation_passed": (
                misconception_review.get("validation") or {}
            ).get("passed"),
        },
        "knowledge_enrichment": {
            "pending_misconception_candidates": (
                enrichment.get("counts", {}) or {}
            ).get("pending_misconception_candidates"),
            "accepted_misconceptions": (
                enrichment.get("counts", {}) or {}
            ).get("accepted_misconceptions"),
        },
    }


def _load_json_if_available(path: str) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    return json.loads(source.read_text(encoding="utf-8"))


def _load_report_status(path: str) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {"available": False, "path": path}
    payload = json.loads(source.read_text(encoding="utf-8"))
    validation = payload.get("validation")
    validation_passed = None
    if isinstance(validation, dict):
        if isinstance(validation.get("passed"), bool):
            validation_passed = validation["passed"]
        elif isinstance(validation.get("errors"), int):
            validation_passed = validation["errors"] == 0
    elif isinstance(payload.get("validation_errors"), int):
        validation_passed = payload["validation_errors"] == 0
    return {
        "available": True,
        "path": path,
        "validation_passed": validation_passed,
    }


def _postgres_validation_status(run_postgres_validation: bool | None) -> dict[str, Any]:
    should_run = (
        os.getenv("KNOWLEDGE_CORE_RUN_POSTGRES_VALIDATION", "").strip().lower()
        in {"1", "true", "yes", "on"}
        if run_postgres_validation is None
        else run_postgres_validation
    )
    if not should_run:
        return {
            "status": "not_executed",
            "production_claim_allowed": False,
            "reason": (
                "Live PostgreSQL validation is gated; set "
                "KNOWLEDGE_CORE_RUN_POSTGRES_VALIDATION=1 and provide a reachable "
                "POSTGRES_DATABASE_URL before making a production claim."
            ),
        }
    try:
        import psycopg  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "failed",
            "production_claim_allowed": False,
            "reason": f"psycopg is unavailable: {exc}",
        }
    database_url = AppConfig().postgres_database_url
    try:
        with psycopg.connect(database_url, connect_timeout=5) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "failed",
            "production_claim_allowed": False,
            "reason": f"PostgreSQL validation query failed: {exc}",
        }
    return {
        "status": "passed",
        "production_claim_allowed": True,
        "reason": "Live PostgreSQL connectivity validation succeeded.",
    }


def _count_differences(
    first: dict[str, int],
    second: dict[str, int],
) -> dict[str, dict[str, int]]:
    return {
        key: {"first": first[key], "second": second[key]}
        for key in sorted(set(first) & set(second))
        if first[key] != second[key]
    }


def _issue(code: str, message: str, **context: Any) -> dict[str, Any]:
    return {
        "severity": "error",
        "code": code,
        "message": message,
        **context,
    }


def _known_limitations(postgres: dict[str, Any]) -> list[str]:
    limitations = [
        "Corpus error storage persists aggregate statistics, error-skill mappings, and misconception evidence links; it does not load all normalized error instances into SQLite.",
        "Pending misconception candidates are queryable but are not accepted diagnostic evidence.",
    ]
    if postgres["status"] != "passed":
        limitations.append(
            "Live PostgreSQL validation has not passed, so no production persistence claim is made.",
        )
    return limitations
