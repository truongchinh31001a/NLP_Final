from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Sequence, TypeVar

from pydantic import BaseModel

from knowledge_core.alignment.models import (
    CanonicalSkillEvidenceProfile,
    SkillCEFRAlignment,
)
from knowledge_core.assessment.builder import AssessmentInputArtifacts
from knowledge_core.assessment.models import (
    AssessmentCriterion,
    AssessmentValidationResult,
    GrammarAssessmentConfig,
    SkillAssessmentProfile,
    now_utc,
)
from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILLS
from knowledge_core.relationships.models import SkillRelationship
from knowledge_core.relationships.taxonomy import build_grammar_taxonomy
from knowledge_core.sources.cefr.models import CEFRDescriptorRecord
from knowledge_core.sources.egp.models import RawEGPRecord


ASSESSMENT_CRITERIA_JSONL = "grammar_assessment_criteria.jsonl"
ASSESSMENT_CRITERIA_PARQUET = "grammar_assessment_criteria.parquet"
ASSESSMENT_PROFILES_JSONL = "grammar_assessment_profiles.jsonl"
ASSESSMENT_REVIEW_CSV = "grammar_assessment_criteria_review.csv"
ASSESSMENT_REPORT_JSON = "grammar_assessment_report.json"

ModelT = TypeVar("ModelT", bound=BaseModel)


class AssessmentOutputError(RuntimeError):
    """Raised when assessment artifacts cannot be read or written."""


def load_assessment_inputs(
    config: GrammarAssessmentConfig,
) -> AssessmentInputArtifacts:
    return AssessmentInputArtifacts(
        skill_profiles=load_jsonl_models(
            config.inputs.skill_evidence_profiles,
            CanonicalSkillEvidenceProfile,
        ),
        skill_alignments=load_jsonl_models(
            config.inputs.cefr_egp_alignment,
            SkillCEFRAlignment,
        ),
        relationships=load_jsonl_models(
            config.inputs.relationships,
            SkillRelationship,
        ),
        cefr_descriptors=load_jsonl_models(
            config.inputs.cefr_descriptors,
            CEFRDescriptorRecord,
        ),
        egp_records=load_jsonl_models(
            config.inputs.egp_records,
            RawEGPRecord,
        ),
    )


def load_jsonl_models(path: str | Path, model_cls: type[ModelT]) -> list[ModelT]:
    source_path = Path(path)
    if not source_path.exists():
        raise AssessmentOutputError(f"Input artifact not found: {source_path}")
    records: list[ModelT] = []
    with source_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AssessmentOutputError(
                    f"Invalid JSONL in {source_path} line {line_number}: {exc}",
                ) from exc
            records.append(model_cls.model_validate(payload))
    return records


def write_assessment_outputs(
    *,
    criteria: Sequence[AssessmentCriterion],
    profiles: Sequence[SkillAssessmentProfile],
    config: GrammarAssessmentConfig,
) -> dict[str, Path]:
    output_dir = Path(config.outputs.assessment_dir)
    return {
        "criteria_jsonl": write_jsonl(criteria, output_dir / ASSESSMENT_CRITERIA_JSONL),
        "criteria_parquet": write_parquet(
            criteria,
            output_dir / ASSESSMENT_CRITERIA_PARQUET,
        ),
        "profiles_jsonl": write_jsonl(profiles, output_dir / ASSESSMENT_PROFILES_JSONL),
    }


def write_review_csv(
    criteria: Sequence[AssessmentCriterion],
    config: GrammarAssessmentConfig,
) -> Path:
    path = Path(config.outputs.review_dir) / ASSESSMENT_REVIEW_CSV
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "criterion_id",
        "canonical_skill_id",
        "criterion_type",
        "observable_behavior",
        "evidence_requirements",
        "task_types",
        "failure_signals",
        "cefr_level",
        "recommended_threshold",
        "recommended_min_items",
        "confidence",
        "reason",
        "provenance_types",
        "status",
        "review_status",
        "reviewer_decision",
        "reviewer_note",
    ]
    rows = [_review_row(criterion) for criterion in criteria]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_assessment_report(
    report: dict[str, Any],
    config: GrammarAssessmentConfig,
) -> Path:
    path = Path(config.outputs.reports_dir) / ASSESSMENT_REPORT_JSON
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return path


def build_assessment_report(
    *,
    criteria: Sequence[AssessmentCriterion],
    profiles: Sequence[SkillAssessmentProfile],
    validation: AssessmentValidationResult,
    config: GrammarAssessmentConfig,
) -> dict[str, Any]:
    canonical_skill_ids = tuple(CANONICAL_GRAMMAR_V1_SKILLS)
    taxonomy = build_grammar_taxonomy(canonical_skill_ids)
    criteria_by_type = Counter(criterion.criterion_type for criterion in criteria)
    criteria_by_level = Counter(criterion.cefr_level or "none" for criterion in criteria)
    task_type_distribution = Counter(
        task_type
        for criterion in criteria
        for task_type in criterion.acceptable_task_types
    )
    criteria_by_skill: dict[str, list[AssessmentCriterion]] = {}
    for criterion in criteria:
        criteria_by_skill.setdefault(criterion.canonical_skill_id, []).append(criterion)

    skills_without_cefr_context = [
        skill_id
        for skill_id in canonical_skill_ids
        if not any(
            criterion.cefr_level and criterion.cefr_context_descriptor_ids
            for criterion in criteria_by_skill.get(skill_id, [])
        )
    ]
    review_required = [
        criterion
        for criterion in criteria
        if criterion.status != "accepted" or criterion.review_status != "approved"
    ]
    skills_with_criteria = len(
        {
            criterion.canonical_skill_id
            for criterion in criteria
            if criterion.canonical_skill_id in set(canonical_skill_ids)
        },
    )
    criteria_with_cefr_context = sum(
        1
        for criterion in criteria
        if criterion.cefr_level and criterion.cefr_context_descriptor_ids
    )
    definition_of_done_satisfied = (
        validation.error_count == 0
        and validation.taxonomy_unchanged
        and skills_with_criteria == len(canonical_skill_ids)
        and len(criteria) > 0
        and all(criterion.provenance for criterion in criteria)
    )
    return {
        "run_at": now_utc().isoformat(),
        "total_canonical_skills": len(canonical_skill_ids),
        "skills_with_assessment_criteria": skills_with_criteria,
        "total_criteria": len(criteria),
        "criteria_by_type": dict(sorted(criteria_by_type.items())),
        "criteria_by_cefr_level": dict(sorted(criteria_by_level.items())),
        "average_criteria_per_skill": round(
            len(criteria) / len(canonical_skill_ids),
            2,
        ),
        "task_type_distribution": dict(sorted(task_type_distribution.items())),
        "skills_without_cefr_context": skills_without_cefr_context,
        "cefr_context_coverage": {
            "skills_with_cefr_context": (
                len(canonical_skill_ids) - len(skills_without_cefr_context)
            ),
            "criteria_with_cefr_context": criteria_with_cefr_context,
            "criteria_without_cefr_context": len(criteria) - criteria_with_cefr_context,
        },
        "criteria_requiring_review": [
            _criterion_sample(criterion)
            for criterion in review_required
        ],
        "criteria_requiring_review_count": len(review_required),
        "invalid_references": validation.invalid_references,
        "duplicate_criteria": validation.duplicate_criteria,
        "validation_errors": validation.error_count,
        "validation_warnings": validation.warning_count,
        "validation_issues": [
            issue.model_dump(mode="json")
            for issue in validation.issues
        ],
        "taxonomy": {
            "root_id": taxonomy.root_id,
            "atomic_skills": len(taxonomy.atomic_skill_ids),
            "group_nodes": len(taxonomy.group_node_ids),
            "taxonomy_hash": taxonomy.taxonomy_hash,
        },
        "taxonomy_unchanged": validation.taxonomy_unchanged,
        "inputs": {
            "skill_evidence_profiles": config.inputs.skill_evidence_profiles,
            "cefr_egp_alignment": config.inputs.cefr_egp_alignment,
            "relationships": config.inputs.relationships,
            "cefr_descriptors": config.inputs.cefr_descriptors,
            "egp_records": config.inputs.egp_records,
        },
        "outputs": {
            "assessment_dir": config.outputs.assessment_dir,
            "review_dir": config.outputs.review_dir,
            "reports_dir": config.outputs.reports_dir,
        },
        "definition_of_done_satisfied": definition_of_done_satisfied,
        "profiles": [
            profile.model_dump(mode="json")
            for profile in profiles
        ],
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
        raise AssessmentOutputError(
            "pyarrow is required to write assessment Parquet output",
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


def _review_row(criterion: AssessmentCriterion) -> dict[str, Any]:
    provenance_types = sorted(
        {evidence.evidence_type for evidence in criterion.provenance},
    )
    return {
        "criterion_id": criterion.criterion_id,
        "canonical_skill_id": criterion.canonical_skill_id,
        "criterion_type": criterion.criterion_type,
        "observable_behavior": criterion.observable_behavior,
        "evidence_requirements": ";".join(criterion.evidence_requirements),
        "task_types": ";".join(criterion.acceptable_task_types),
        "failure_signals": ";".join(criterion.failure_signals),
        "cefr_level": criterion.cefr_level or "",
        "recommended_threshold": criterion.recommended_threshold,
        "recommended_min_items": criterion.recommended_min_items,
        "confidence": criterion.confidence,
        "reason": criterion.reason,
        "provenance_types": ";".join(provenance_types),
        "status": criterion.status,
        "review_status": criterion.review_status,
        "reviewer_decision": "",
        "reviewer_note": "",
    }


def _criterion_sample(criterion: AssessmentCriterion) -> dict[str, Any]:
    return {
        "criterion_id": criterion.criterion_id,
        "canonical_skill_id": criterion.canonical_skill_id,
        "criterion_type": criterion.criterion_type,
        "confidence": criterion.confidence,
        "status": criterion.status,
        "review_status": criterion.review_status,
        "reason": criterion.reason,
    }
