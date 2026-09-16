from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence, TypeVar

from pydantic import BaseModel

from knowledge_core.alignment.models import (
    CanonicalSkillEvidenceProfile,
    SkillCEFRAlignment,
)
from knowledge_core.relationships.models import (
    GrammarRelationshipConfig,
    RelationshipGraphAnalysis,
    RelationshipValidationResult,
    SkillRelationship,
    now_utc,
)
from knowledge_core.relationships.taxonomy import GrammarTaxonomy


RELATIONSHIPS_JSONL = "grammar_relationships.jsonl"
RELATIONSHIPS_PARQUET = "grammar_relationships.parquet"
RELATIONSHIP_REVIEW_CSV = "grammar_relationship_review.csv"
RELATIONSHIP_REPORT_JSON = "grammar_relationship_report.json"
RELATIONSHIP_GRAPH_JSON = "grammar_relationship_graph.json"

ModelT = TypeVar("ModelT", bound=BaseModel)


class RelationshipOutputError(RuntimeError):
    """Raised when relationship artifacts cannot be read or written."""


@dataclass(slots=True)
class RelationshipInputArtifacts:
    skill_profiles: list[CanonicalSkillEvidenceProfile]
    skill_alignments: list[SkillCEFRAlignment]


def load_relationship_inputs(
    config: GrammarRelationshipConfig,
) -> RelationshipInputArtifacts:
    return RelationshipInputArtifacts(
        skill_profiles=load_jsonl_models(
            config.inputs.skill_evidence_profiles,
            CanonicalSkillEvidenceProfile,
        ),
        skill_alignments=load_jsonl_models(
            config.inputs.cefr_egp_alignment,
            SkillCEFRAlignment,
        ),
    )


def load_jsonl_models(path: str | Path, model_cls: type[ModelT]) -> list[ModelT]:
    source_path = Path(path)
    if not source_path.exists():
        raise RelationshipOutputError(f"Input artifact not found: {source_path}")
    records: list[ModelT] = []
    with source_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RelationshipOutputError(
                    f"Invalid JSONL in {source_path} line {line_number}: {exc}",
                ) from exc
            records.append(model_cls.model_validate(payload))
    return records


def write_relationship_outputs(
    relationships: Sequence[SkillRelationship],
    config: GrammarRelationshipConfig,
) -> dict[str, Path]:
    output_dir = Path(config.outputs.relationships_dir)
    return {
        "relationships_jsonl": write_jsonl(
            relationships,
            output_dir / RELATIONSHIPS_JSONL,
        ),
        "relationships_parquet": write_parquet(
            relationships,
            output_dir / RELATIONSHIPS_PARQUET,
        ),
    }


def write_review_csv(
    relationships: Sequence[SkillRelationship],
    config: GrammarRelationshipConfig,
) -> Path:
    path = Path(config.outputs.review_dir) / RELATIONSHIP_REVIEW_CSV
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [_review_row(relationship) for relationship in relationships]
    fieldnames = [
        "relationship_id",
        "source_skill_id",
        "target_skill_id",
        "relation_type",
        "dependency_strength",
        "confidence",
        "reason",
        "evidence_types",
        "source_record_ids",
        "status",
        "review_status",
        "reviewer_decision",
        "reviewer_note",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_relationship_report(
    report: dict[str, Any],
    config: GrammarRelationshipConfig,
) -> Path:
    path = Path(config.outputs.reports_dir) / RELATIONSHIP_REPORT_JSON
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return path


def write_graph_export(
    graph_payload: dict[str, Any],
    config: GrammarRelationshipConfig,
) -> Path:
    path = Path(config.outputs.reports_dir) / RELATIONSHIP_GRAPH_JSON
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(graph_payload, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return path


def build_relationship_report(
    *,
    relationships: Sequence[SkillRelationship],
    taxonomy: GrammarTaxonomy,
    analysis: RelationshipGraphAnalysis,
    validation: RelationshipValidationResult,
    config: GrammarRelationshipConfig,
) -> dict[str, Any]:
    by_type = Counter(relationship.relation_type for relationship in relationships)
    confidence_bands = Counter(_confidence_band(relationship.confidence) for relationship in relationships)
    review_required = [
        relationship
        for relationship in relationships
        if relationship.review_status != "approved" or relationship.status != "accepted"
    ]
    atomic_nodes_in_any_relationship = {
        node
        for relationship in relationships
        for node in [relationship.source_skill_id, relationship.target_skill_id]
        if node in taxonomy.atomic_skill_ids
    }
    atomic_non_structural_nodes = {
        node
        for relationship in relationships
        if relationship.relation_type != "parent_of"
        for node in [relationship.source_skill_id, relationship.target_skill_id]
        if node in taxonomy.atomic_skill_ids
    }
    return {
        "run_at": now_utc().isoformat(),
        "total_relationships": len(relationships),
        "relationships_by_type": dict(sorted(by_type.items())),
        "hard_prerequisite_count": sum(
            1 for relationship in relationships if relationship.dependency_strength == "hard"
        ),
        "soft_prerequisite_count": sum(
            1 for relationship in relationships if relationship.dependency_strength == "soft"
        ),
        "bidirectional_relationship_count": sum(
            1 for relationship in relationships if relationship.bidirectional
        ),
        "canonical_skills_covered": len(atomic_nodes_in_any_relationship),
        "canonical_skills_with_non_structural_relationships": len(
            atomic_non_structural_nodes,
        ),
        "total_canonical_atomic_skills": len(taxonomy.atomic_skill_ids),
        "isolated_skills": analysis.isolated_skills,
        "root_prerequisite_skills": analysis.root_prerequisite_skills,
        "terminal_skills": analysis.terminal_skills,
        "prerequisite_dag_valid": validation.prerequisite_dag_valid,
        "cycles_found": validation.cycles_found,
        "duplicate_edges": validation.duplicate_edges,
        "invalid_references": validation.invalid_references,
        "validation_errors": validation.error_count,
        "validation_warnings": validation.warning_count,
        "max_prerequisite_depth": analysis.max_prerequisite_depth,
        "longest_prerequisite_path": analysis.longest_prerequisite_path,
        "relationships_requiring_review": [
            _relationship_sample(relationship) for relationship in review_required
        ],
        "relationships_requiring_review_count": len(review_required),
        "relationships_by_confidence_band": dict(sorted(confidence_bands.items())),
        "connected_components": analysis.connected_components,
        "node_summaries": {
            skill_id: summary.model_dump(mode="json")
            for skill_id, summary in analysis.node_summaries.items()
        },
        "taxonomy": {
            "root_id": taxonomy.root_id,
            "atomic_skills": len(taxonomy.atomic_skill_ids),
            "group_nodes": len(taxonomy.group_node_ids),
            "taxonomy_hash": taxonomy.taxonomy_hash,
        },
        "inputs": {
            "skill_evidence_profiles": config.inputs.skill_evidence_profiles,
            "cefr_egp_alignment": config.inputs.cefr_egp_alignment,
        },
        "taxonomy_unchanged": validation.error_count == 0,
    }


def build_graph_export(
    *,
    relationships: Sequence[SkillRelationship],
    taxonomy: GrammarTaxonomy,
    analysis: RelationshipGraphAnalysis,
) -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": node_id,
                "kind": "atomic_skill"
                if node_id in taxonomy.atomic_skill_ids
                else "taxonomy_group",
            }
            for node_id in sorted(taxonomy.all_node_ids)
        ],
        "edges": [
            {
                "id": relationship.relationship_id,
                "source": relationship.source_skill_id,
                "target": relationship.target_skill_id,
                "relation_type": relationship.relation_type,
                "dependency_strength": relationship.dependency_strength,
                "bidirectional": relationship.bidirectional,
                "confidence": relationship.confidence,
                "status": relationship.status,
            }
            for relationship in relationships
        ],
        "analysis": analysis.model_dump(mode="json"),
    }


def write_jsonl(records: Sequence[BaseModel], destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(
                json.dumps(
                    record.model_dump(mode="json"),
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )
            handle.write("\n")
    return path


def write_parquet(records: Sequence[BaseModel], destination: str | Path) -> Path:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RelationshipOutputError(
            "pyarrow is required to write relationship Parquet output",
        ) from exc

    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [_flatten_for_parquet(record) for record in records]
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path)
    return path


def _flatten_for_parquet(record: BaseModel) -> dict[str, Any]:
    payload = record.model_dump(mode="json")
    return {
        key: _parquet_value(value)
        for key, value in payload.items()
    }


def _parquet_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _review_row(relationship: SkillRelationship) -> dict[str, Any]:
    evidence_types = sorted({evidence.evidence_type for evidence in relationship.evidence})
    source_record_ids = sorted(
        {
            source_record_id
            for evidence in relationship.evidence
            for source_record_id in evidence.source_record_ids
        },
    )
    return {
        "relationship_id": relationship.relationship_id,
        "source_skill_id": relationship.source_skill_id,
        "target_skill_id": relationship.target_skill_id,
        "relation_type": relationship.relation_type,
        "dependency_strength": relationship.dependency_strength,
        "confidence": relationship.confidence,
        "reason": relationship.reason,
        "evidence_types": ";".join(evidence_types),
        "source_record_ids": ";".join(source_record_ids),
        "status": relationship.status,
        "review_status": relationship.review_status,
        "reviewer_decision": "",
        "reviewer_note": "",
    }


def _relationship_sample(relationship: SkillRelationship) -> dict[str, Any]:
    return {
        "relationship_id": relationship.relationship_id,
        "source_skill_id": relationship.source_skill_id,
        "target_skill_id": relationship.target_skill_id,
        "relation_type": relationship.relation_type,
        "dependency_strength": relationship.dependency_strength,
        "confidence": relationship.confidence,
        "status": relationship.status,
        "review_status": relationship.review_status,
        "reason": relationship.reason,
    }


def _confidence_band(confidence: float) -> str:
    if confidence >= 0.95:
        return "0.95-1.00"
    if confidence >= 0.85:
        return "0.85-0.94"
    if confidence >= 0.70:
        return "0.70-0.84"
    if confidence >= 0.60:
        return "0.60-0.69"
    return "<0.60"
