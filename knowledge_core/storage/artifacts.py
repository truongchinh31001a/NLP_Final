from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from knowledge_core.alignment.models import (
    CanonicalSkillEvidenceProfile,
    SkillCEFRAlignment,
    SkillSourceEvidence,
)
from knowledge_core.assessment.models import AssessmentCriterion, SkillAssessmentProfile
from knowledge_core.enrichment.models import SkillMisconceptionLink
from knowledge_core.misconceptions.models import MisconceptionCandidate
from knowledge_core.normalization.corpus_errors.models import ErrorSkillMapping
from knowledge_core.relationships.models import SkillRelationship
from knowledge_core.sources.cefr.models import (
    CEFRDescriptorRecord,
    CEFRLearningObjectiveCandidate,
)
from knowledge_core.sources.egp.models import RawEGPRecord


ModelT = TypeVar("ModelT", bound=BaseModel)


class StorageArtifactError(RuntimeError):
    """Raised when Knowledge Core storage artifacts cannot be loaded."""


@dataclass(frozen=True, slots=True)
class StorageArtifactPaths:
    egp_records: Path = Path("data/interim/english_profile/grammar/egp_records.jsonl")
    cefr_descriptors: Path = Path("data/interim/cefr/cefr_descriptors.jsonl")
    learning_objectives: Path = Path(
        "data/interim/cefr/cefr_learning_objective_candidates.jsonl",
    )
    skill_profiles: Path = Path(
        "data/interim/knowledge_alignment/grammar_skill_evidence.jsonl",
    )
    skill_evidence: Path = Path(
        "data/interim/knowledge_alignment/skill_source_evidence.jsonl",
    )
    skill_alignments: Path = Path(
        "data/interim/knowledge_alignment/cefr_egp_alignment.jsonl",
    )
    relationships: Path = Path("data/curated/relationships/grammar_relationships.jsonl")
    assessment_criteria: Path = Path(
        "data/curated/assessment/grammar_assessment_criteria.jsonl",
    )
    assessment_profiles: Path = Path(
        "data/curated/assessment/grammar_assessment_profiles.jsonl",
    )
    error_normalization_report: Path = Path(
        "data/reports/corpus_errors/error_normalization_report.json",
    )
    error_skill_mappings: Path = Path(
        "data/curated/error_mapping/accepted_error_skill_mappings.jsonl",
    )
    candidate_misconceptions: Path = Path(
        "data/interim/misconceptions/candidate_misconceptions.jsonl",
    )
    accepted_misconceptions: Path = Path(
        "data/curated/misconceptions/accepted_misconceptions.jsonl",
    )
    skill_misconception_links: Path = Path(
        "data/curated/knowledge_enrichment/skill_misconception_links.jsonl",
    )
    misconception_report: Path = Path(
        "data/reports/misconceptions/misconception_report.json",
    )
    knowledge_enrichment_report: Path = Path(
        "data/reports/knowledge_enrichment/knowledge_enrichment_report.json",
    )


@dataclass(slots=True)
class StorageArtifacts:
    egp_records: list[RawEGPRecord]
    cefr_descriptors: list[CEFRDescriptorRecord]
    learning_objectives: list[CEFRLearningObjectiveCandidate]
    skill_profiles: list[CanonicalSkillEvidenceProfile]
    skill_evidence: list[SkillSourceEvidence]
    skill_alignments: list[SkillCEFRAlignment]
    relationships: list[SkillRelationship]
    assessment_criteria: list[AssessmentCriterion]
    assessment_profiles: list[SkillAssessmentProfile]
    error_normalization_report: dict[str, object]
    error_skill_mappings: list[ErrorSkillMapping]
    candidate_misconceptions: list[MisconceptionCandidate]
    accepted_misconceptions: list[MisconceptionCandidate]
    skill_misconception_links: list[SkillMisconceptionLink]
    misconception_report: dict[str, object]
    knowledge_enrichment_report: dict[str, object]

    def counts(self) -> dict[str, int]:
        misconception_records = merged_misconceptions(
            candidates=self.candidate_misconceptions,
            accepted=self.accepted_misconceptions,
        )
        return {
            "egp_records": len(self.egp_records),
            "cefr_descriptors": len(self.cefr_descriptors),
            "source_records": len(self.egp_records) + len(self.cefr_descriptors),
            "learning_objectives": len(self.learning_objectives),
            "skill_profiles": len(self.skill_profiles),
            "skill_source_evidence": len(self.skill_evidence),
            "skill_alignments": len(self.skill_alignments),
            "relationships": len(self.relationships),
            "assessment_criteria": len(self.assessment_criteria),
            "assessment_profiles": len(self.assessment_profiles),
            "normalized_errors": int(
                self.error_normalization_report.get("normalized_error_count", 0) or 0,
            ),
            "source_errors": sum(
                int(value)
                for value in (
                    self.error_normalization_report.get("source_error_counts", {})
                    or {}
                ).values()
            ),
            "error_skill_mappings": len(self.error_skill_mappings),
            "candidate_misconceptions": len(self.candidate_misconceptions),
            "accepted_misconceptions": len(self.accepted_misconceptions),
            "misconceptions": len(misconception_records),
            "misconception_evidence": sum(
                len(misconception.evidence_links)
                for misconception in misconception_records
            ),
            "skill_misconception_links": len(self.skill_misconception_links),
            "corpus_error_statistics": len(corpus_error_statistic_rows(self)),
        }


def load_storage_artifacts(paths: StorageArtifactPaths | None = None) -> StorageArtifacts:
    resolved = paths or StorageArtifactPaths()
    return StorageArtifacts(
        egp_records=load_jsonl_models(resolved.egp_records, RawEGPRecord),
        cefr_descriptors=load_jsonl_models(
            resolved.cefr_descriptors,
            CEFRDescriptorRecord,
        ),
        learning_objectives=load_jsonl_models(
            resolved.learning_objectives,
            CEFRLearningObjectiveCandidate,
        ),
        skill_profiles=load_jsonl_models(
            resolved.skill_profiles,
            CanonicalSkillEvidenceProfile,
        ),
        skill_evidence=load_jsonl_models(resolved.skill_evidence, SkillSourceEvidence),
        skill_alignments=load_jsonl_models(
            resolved.skill_alignments,
            SkillCEFRAlignment,
        ),
        relationships=load_jsonl_models(resolved.relationships, SkillRelationship),
        assessment_criteria=load_jsonl_models(
            resolved.assessment_criteria,
            AssessmentCriterion,
        ),
        assessment_profiles=load_jsonl_models(
            resolved.assessment_profiles,
            SkillAssessmentProfile,
        ),
        error_normalization_report=load_json(resolved.error_normalization_report),
        error_skill_mappings=load_jsonl_models(
            resolved.error_skill_mappings,
            ErrorSkillMapping,
        ),
        candidate_misconceptions=load_jsonl_models(
            resolved.candidate_misconceptions,
            MisconceptionCandidate,
        ),
        accepted_misconceptions=load_jsonl_models(
            resolved.accepted_misconceptions,
            MisconceptionCandidate,
        ),
        skill_misconception_links=load_jsonl_models(
            resolved.skill_misconception_links,
            SkillMisconceptionLink,
        ),
        misconception_report=load_json(resolved.misconception_report),
        knowledge_enrichment_report=load_json(resolved.knowledge_enrichment_report),
    )


def load_jsonl_models(path: str | Path, model_cls: type[ModelT]) -> list[ModelT]:
    source_path = Path(path)
    if not source_path.exists():
        raise StorageArtifactError(f"Input artifact not found: {source_path}")
    records: list[ModelT] = []
    with source_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise StorageArtifactError(
                    f"Invalid JSONL in {source_path} line {line_number}: {exc}",
                ) from exc
            records.append(model_cls.model_validate(payload))
    return records


def load_json(path: str | Path) -> dict[str, object]:
    source_path = Path(path)
    if not source_path.exists():
        raise StorageArtifactError(f"Input artifact not found: {source_path}")
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StorageArtifactError(f"Invalid JSON in {source_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise StorageArtifactError(f"Expected JSON object in {source_path}")
    return payload


def merged_misconceptions(
    *,
    candidates: list[MisconceptionCandidate],
    accepted: list[MisconceptionCandidate],
) -> list[MisconceptionCandidate]:
    by_id = {candidate.misconception_id: candidate for candidate in candidates}
    for misconception in accepted:
        by_id[misconception.misconception_id] = misconception
    return sorted(by_id.values(), key=lambda item: item.misconception_id)


def corpus_error_statistic_rows(artifacts: StorageArtifacts) -> list[dict[str, object]]:
    report = artifacts.error_normalization_report
    rows: list[dict[str, object]] = []

    for source_key, count in sorted(
        (report.get("source_error_counts", {}) or {}).items(),
    ):
        rows.append(
            {
                "statistic_type": "source_error_count",
                "source_key": source_key,
                "count": int(count),
            },
        )

    for status, count in sorted(
        (report.get("normalization_status_counts", {}) or {}).items(),
    ):
        rows.append(
            {
                "statistic_type": "normalization_status_count",
                "mapping_status": status,
                "count": int(count),
            },
        )

    for category, count in sorted(
        (report.get("normalized_category_counts", {}) or {}).items(),
    ):
        rows.append(
            {
                "statistic_type": "normalized_category_count",
                "normalized_category": category,
                "count": int(count),
            },
        )

    for status, count in sorted(
        (report.get("skill_mapping_status_counts", {}) or {}).items(),
    ):
        rows.append(
            {
                "statistic_type": "skill_mapping_status_count",
                "mapping_status": status,
                "count": int(count),
            },
        )

    for skill_id, count in sorted(
        (report.get("skill_mapping_skill_counts", {}) or {}).items(),
    ):
        rows.append(
            {
                "statistic_type": "skill_mapping_skill_count",
                "canonical_skill_id": skill_id,
                "count": int(count),
            },
        )

    for item in report.get("source_label_rule_summary", []) or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "statistic_type": "source_label_rule_count",
                "source_key": item.get("source_key"),
                "source_label": item.get("source_label"),
                "normalized_category": item.get("normalized_category"),
                "normalized_subtype": item.get("normalized_subtype"),
                "mapping_status": item.get("normalization_status"),
                "canonical_skill_ids": item.get("canonical_skill_candidates") or [],
                "reason": item.get("reason"),
                "count": int(item.get("count") or 0),
            },
        )

    return rows
