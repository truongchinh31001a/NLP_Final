from __future__ import annotations

from dataclasses import dataclass

from knowledge_core.repository.models import (
    AssessmentCriterionReadModel,
    CorpusErrorStatisticReadModel,
    ErrorSkillMappingReadModel,
    KnowledgeNodeReadModel,
    MisconceptionReadModel,
    SkillSnapshotReadModel,
)


@dataclass(frozen=True, slots=True)
class AssessmentProfile:
    skill_id: str
    criteria: tuple[AssessmentCriterionReadModel, ...]
    task_types: tuple[str, ...]
    evidence_requirements: tuple[str, ...]
    failure_signals: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DiagnosticContext:
    skill_id: str
    failure_signals: tuple[str, ...]
    misconceptions: tuple[MisconceptionReadModel, ...]
    error_statistics: tuple[CorpusErrorStatisticReadModel, ...]
    error_skill_mappings: tuple[ErrorSkillMappingReadModel, ...]


@dataclass(frozen=True, slots=True)
class SkillContext:
    snapshot: SkillSnapshotReadModel
    ancestors: tuple[KnowledgeNodeReadModel, ...]
    transitive_prerequisites: tuple[KnowledgeNodeReadModel, ...]
