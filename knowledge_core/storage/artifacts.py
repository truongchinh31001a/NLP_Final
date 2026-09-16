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

    def counts(self) -> dict[str, int]:
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
