from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence, TypeVar

from pydantic import BaseModel

from knowledge_core.alignment.cefr_alignment import KnowledgeAlignmentDataset
from knowledge_core.alignment.models import (
    AlignmentValidationResult,
    CanonicalSkillEvidenceProfile,
    KnowledgeAlignmentConfig,
    SkillCEFRAlignment,
    SkillSourceEvidence,
    now_utc,
)
from knowledge_core.mapping.egp.models import EGPCanonicalMapping
from knowledge_core.sources.cefr.models import (
    CEFRDescriptorRecord,
    CEFRLearningObjectiveCandidate,
)
from knowledge_core.sources.egp.models import RawEGPRecord


GRAMMAR_SKILL_EVIDENCE_JSONL = "grammar_skill_evidence.jsonl"
GRAMMAR_SKILL_EVIDENCE_PARQUET = "grammar_skill_evidence.parquet"
CEFR_EGP_ALIGNMENT_JSONL = "cefr_egp_alignment.jsonl"
CEFR_EGP_ALIGNMENT_PARQUET = "cefr_egp_alignment.parquet"
SKILL_SOURCE_EVIDENCE_JSONL = "skill_source_evidence.jsonl"
SKILL_SOURCE_EVIDENCE_PARQUET = "skill_source_evidence.parquet"
REVIEW_CSV = "cefr_egp_alignment_review.csv"
ALIGNMENT_REPORT = "cefr_egp_alignment_report.json"

ModelT = TypeVar("ModelT", bound=BaseModel)


class KnowledgeAlignmentOutputError(RuntimeError):
    """Raised when knowledge alignment output cannot be written."""


@dataclass(slots=True)
class AlignmentInputArtifacts:
    egp_records: list[RawEGPRecord]
    egp_mappings: list[EGPCanonicalMapping]
    cefr_descriptors: list[CEFRDescriptorRecord]
    cefr_objectives: list[CEFRLearningObjectiveCandidate]


def load_input_artifacts(config: KnowledgeAlignmentConfig) -> AlignmentInputArtifacts:
    return AlignmentInputArtifacts(
        egp_records=load_jsonl_models(config.inputs.egp_records, RawEGPRecord),
        egp_mappings=load_jsonl_models(config.inputs.egp_mappings, EGPCanonicalMapping),
        cefr_descriptors=load_jsonl_models(
            config.inputs.cefr_descriptors,
            CEFRDescriptorRecord,
        ),
        cefr_objectives=load_jsonl_models(
            config.inputs.cefr_objectives,
            CEFRLearningObjectiveCandidate,
        ),
    )


def load_jsonl_models(path: str | Path, model_cls: type[ModelT]) -> list[ModelT]:
    source_path = Path(path)
    if not source_path.exists():
        raise KnowledgeAlignmentOutputError(f"Input artifact not found: {source_path}")
    records: list[ModelT] = []
    with source_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise KnowledgeAlignmentOutputError(
                    f"Invalid JSONL in {source_path} line {line_number}: {exc}",
                ) from exc
            records.append(model_cls.model_validate(payload))
    return records


def write_alignment_outputs(
    dataset: KnowledgeAlignmentDataset,
    config: KnowledgeAlignmentConfig,
) -> dict[str, Path]:
    interim_dir = Path(config.outputs.interim_dir)
    return {
        "grammar_skill_evidence_jsonl": write_jsonl(
            dataset.profiles,
            interim_dir / GRAMMAR_SKILL_EVIDENCE_JSONL,
        ),
        "grammar_skill_evidence_parquet": write_parquet(
            dataset.profiles,
            interim_dir / GRAMMAR_SKILL_EVIDENCE_PARQUET,
        ),
        "cefr_egp_alignment_jsonl": write_jsonl(
            dataset.alignments,
            interim_dir / CEFR_EGP_ALIGNMENT_JSONL,
        ),
        "cefr_egp_alignment_parquet": write_parquet(
            dataset.alignments,
            interim_dir / CEFR_EGP_ALIGNMENT_PARQUET,
        ),
        "skill_source_evidence_jsonl": write_jsonl(
            dataset.source_evidence,
            interim_dir / SKILL_SOURCE_EVIDENCE_JSONL,
        ),
        "skill_source_evidence_parquet": write_parquet(
            dataset.source_evidence,
            interim_dir / SKILL_SOURCE_EVIDENCE_PARQUET,
        ),
    }


def write_review_csv(
    profiles: Sequence[CanonicalSkillEvidenceProfile],
    config: KnowledgeAlignmentConfig,
) -> Path:
    path = Path(config.outputs.review_dir) / REVIEW_CSV
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [_review_row(profile) for profile in profiles]
    fieldnames = [
        "canonical_skill_id",
        "egp_levels",
        "egp_evidence_count",
        "proposed_min_cefr",
        "proposed_primary_cefr",
        "direct_objectives",
        "contextual_objectives",
        "grammatical_accuracy_context",
        "alignment_status",
        "confidence",
        "reason",
        "reviewer_decision",
        "reviewer_note",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_alignment_report(
    report: dict[str, Any],
    config: KnowledgeAlignmentConfig,
) -> Path:
    path = Path(config.outputs.reports_dir) / ALIGNMENT_REPORT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return path


def build_artifact_inspection_report(
    *,
    canonical_skills: Sequence[str],
    artifacts: AlignmentInputArtifacts,
    config: KnowledgeAlignmentConfig,
) -> dict[str, Any]:
    return {
        "run_at": now_utc().isoformat(),
        "canonical_taxonomy": {
            "source": "knowledge_core.mapping.egp.canonical.CANONICAL_GRAMMAR_V1_SKILLS",
            "skills": len(canonical_skills),
            "hash": canonical_taxonomy_hash(canonical_skills),
            "skill_ids": list(canonical_skills),
        },
        "inputs": {
            "egp_records": {
                "path": config.inputs.egp_records,
                "records": len(artifacts.egp_records),
                "cefr_levels": _counter_dict(
                    record.cefr_level for record in artifacts.egp_records
                ),
            },
            "egp_mappings": {
                "path": config.inputs.egp_mappings,
                "records": len(artifacts.egp_mappings),
                "status_counts": _counter_dict(
                    mapping.status for mapping in artifacts.egp_mappings
                ),
            },
            "cefr_descriptors": {
                "path": config.inputs.cefr_descriptors,
                "records": len(artifacts.cefr_descriptors),
                "scale_counts": _counter_dict(
                    record.scale_name for record in artifacts.cefr_descriptors
                ),
            },
            "cefr_objectives": {
                "path": config.inputs.cefr_objectives,
                "records": len(artifacts.cefr_objectives),
                "domain_counts": _counter_dict(
                    objective.domain for objective in artifacts.cefr_objectives
                ),
            },
        },
    }


def build_alignment_report(
    *,
    canonical_skills: Sequence[str],
    dataset: KnowledgeAlignmentDataset,
    validation: AlignmentValidationResult,
    artifact_inspection: dict[str, Any],
) -> dict[str, Any]:
    profiles = dataset.profiles
    alignments = dataset.alignments
    skills_with_direct_objectives = [
        profile.canonical_skill_id
        for profile in profiles
        if profile.direct_objective_ids
    ]
    skills_with_contextual_objectives = [
        profile.canonical_skill_id
        for profile in profiles
        if profile.contextual_objective_ids
    ]
    curated_only = [
        profile.canonical_skill_id
        for profile in profiles
        if profile.evidence_status == "curated_only"
    ]
    without_cefr = [
        profile.canonical_skill_id
        for profile in profiles
        if profile.cefr_primary_level is None
    ]
    requiring_review = [
        alignment.canonical_skill_id
        for alignment in alignments
        if alignment.review_status != "accepted"
    ]
    conflicting = [
        profile.canonical_skill_id
        for profile in profiles
        if profile.provenance.get("conflicting_level_evidence")
    ]
    return {
        "run_at": now_utc().isoformat(),
        "total_canonical_skills": len(canonical_skills),
        "skills_with_egp_evidence": sum(
            1 for profile in profiles if profile.egp_evidence_count > 0
        ),
        "skills_with_cefr_alignment": sum(
            1 for profile in profiles if profile.cefr_primary_level is not None
        ),
        "skills_with_direct_objectives": len(skills_with_direct_objectives),
        "skills_with_contextual_objectives": len(skills_with_contextual_objectives),
        "skills_curated_only": len(curated_only),
        "skills_without_cefr_alignment": len(without_cefr),
        "distribution_by_primary_cefr_level": _counter_dict(
            profile.cefr_primary_level or "none" for profile in profiles
        ),
        "distribution_by_alignment_status": _counter_dict(
            profile.evidence_status for profile in profiles
        ),
        "skills_with_conflicting_level_evidence": conflicting,
        "skills_requiring_review": requiring_review,
        "top_10_strongest_alignments": [
            _alignment_sample(alignment)
            for alignment in sorted(
                alignments,
                key=lambda item: (-item.confidence, item.canonical_skill_id),
            )[:10]
        ],
        "all_ambiguous_alignments": [
            _alignment_sample(alignment)
            for alignment in alignments
            if alignment.status == "ambiguous"
        ],
        "all_curated_only_skills": curated_only,
        "objective_alignment": {
            "skills_with_direct_objectives": skills_with_direct_objectives,
            "skills_with_contextual_objectives": skills_with_contextual_objectives,
            "direct_objective_links": sum(
                len(profile.direct_objective_ids) for profile in profiles
            ),
            "contextual_objective_links": sum(
                len(profile.contextual_objective_ids) for profile in profiles
            ),
        },
        "source_evidence": {
            "total": len(dataset.source_evidence),
            "by_type": _counter_dict(
                evidence.evidence_type for evidence in dataset.source_evidence
            ),
        },
        "egp_ambiguous_source_mappings": {
            "skills": sorted(dataset.egp_bundle.ambiguous_by_skill),
            "records": sorted(
                {
                    mapping.source_record_id
                    for mappings in dataset.egp_bundle.ambiguous_by_skill.values()
                    for mapping in mappings
                },
            ),
        },
        "validation": {
            "errors": validation.error_count,
            "warnings": validation.warning_count,
            "issues": [issue.model_dump(mode="json") for issue in validation.issues],
        },
        "artifact_inspection": artifact_inspection,
        "canonical_taxonomy_unchanged": validation.error_count == 0,
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
        raise KnowledgeAlignmentOutputError(
            "pyarrow is required to write knowledge alignment Parquet output",
        ) from exc

    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [_flatten_for_parquet(record) for record in records]
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path)
    return path


def canonical_taxonomy_hash(canonical_skills: Sequence[str]) -> str:
    raw = "\n".join(canonical_skills)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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


def _review_row(profile: CanonicalSkillEvidenceProfile) -> dict[str, Any]:
    return {
        "canonical_skill_id": profile.canonical_skill_id,
        "egp_levels": ";".join(profile.egp_levels),
        "egp_evidence_count": profile.egp_evidence_count,
        "proposed_min_cefr": profile.cefr_min_level or "",
        "proposed_primary_cefr": profile.cefr_primary_level or "",
        "direct_objectives": ";".join(profile.direct_objective_ids),
        "contextual_objectives": ";".join(profile.contextual_objective_ids),
        "grammatical_accuracy_context": ";".join(profile.grammatical_accuracy_context),
        "alignment_status": profile.evidence_status,
        "confidence": profile.alignment_confidence,
        "reason": profile.notes,
        "reviewer_decision": "",
        "reviewer_note": "",
    }


def _counter_dict(values: Any) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _alignment_sample(alignment: SkillCEFRAlignment) -> dict[str, Any]:
    return {
        "canonical_skill_id": alignment.canonical_skill_id,
        "inferred_min_level": alignment.inferred_min_level,
        "inferred_primary_level": alignment.inferred_primary_level,
        "confidence": alignment.confidence,
        "status": alignment.status,
        "review_status": alignment.review_status,
        "egp_levels": alignment.egp_levels,
        "objective_ids": alignment.objective_ids,
        "grammatical_accuracy_descriptor_ids": alignment.grammatical_accuracy_descriptor_ids,
        "reason": alignment.reason,
    }

