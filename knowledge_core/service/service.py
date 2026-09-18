from __future__ import annotations

from collections.abc import Collection, Iterable

from knowledge_core.repository.base import VersionSelector
from knowledge_core.repository.models import (
    KnowledgeNodeReadModel,
    LearningObjectiveReadModel,
    MisconceptionReadModel,
    RelationshipReadModel,
    SkillProfileReadModel,
)
from knowledge_core.repository.session import KnowledgeRepositorySession
from knowledge_core.service.models import AssessmentProfile, DiagnosticContext, SkillContext


class KnowledgeService:
    """Read-only application facade over KnowledgeRepository.

    The service composes persisted knowledge into consumer-friendly views. It
    deliberately does not estimate mastery, select adaptive activities,
    generate content, or call external/LLM services.
    """

    def __init__(self, repositories: KnowledgeRepositorySession) -> None:
        self.repositories = repositories

    def get_skill(
        self,
        skill_id: str,
        version: VersionSelector = None,
    ) -> KnowledgeNodeReadModel:
        return self.repositories.nodes.get_by_canonical_id(skill_id, version)

    def get_skill_context(
        self,
        skill_id: str,
        version: VersionSelector = None,
    ) -> SkillContext:
        resolved = self.repositories.versions.resolve_version(version)
        snapshot = self.repositories.queries.get_skill_snapshot(skill_id, resolved)
        prerequisite_nodes = self._nodes_for_prerequisite_path(skill_id, resolved)
        return SkillContext(
            snapshot=snapshot,
            ancestors=tuple(self.repositories.nodes.list_ancestors(skill_id, resolved)),
            transitive_prerequisites=tuple(prerequisite_nodes[:-1]),
        )

    def get_prerequisites(
        self,
        skill_id: str,
        *,
        transitive: bool = False,
        version: VersionSelector = None,
    ) -> tuple[KnowledgeNodeReadModel, ...]:
        resolved = self.repositories.versions.resolve_version(version)
        if transitive:
            return tuple(self._nodes_for_prerequisite_path(skill_id, resolved)[:-1])
        relationships = self.repositories.relationships.list_direct_prerequisites(
            skill_id,
            resolved,
        )
        return tuple(
            self.repositories.nodes.get_by_canonical_id(item.source_skill_id, resolved)
            for item in relationships
        )

    def get_learning_path(
        self,
        skill_id: str,
        version: VersionSelector = None,
    ) -> tuple[KnowledgeNodeReadModel, ...]:
        """Return prerequisite skills in dependency order, followed by the target."""
        resolved = self.repositories.versions.resolve_version(version)
        return tuple(self._nodes_for_prerequisite_path(skill_id, resolved))

    def is_unlocked(
        self,
        skill_id: str,
        mastered_skill_ids: Collection[str],
        version: VersionSelector = None,
    ) -> bool:
        required = {
            item.canonical_id
            for item in self.get_prerequisites(skill_id, version=version)
        }
        return required.issubset(set(mastered_skill_ids))

    def get_unlocked_skills(
        self,
        mastered_skill_ids: Collection[str],
        version: VersionSelector = None,
    ) -> tuple[KnowledgeNodeReadModel, ...]:
        resolved = self.repositories.versions.resolve_version(version)
        mastered = set(mastered_skill_ids)
        return tuple(
            skill
            for skill in self.repositories.nodes.list_atomic_skills(resolved)
            if skill.canonical_id not in mastered
            and self.is_unlocked(skill.canonical_id, mastered, resolved)
        )

    def get_learning_objectives(
        self,
        skill_id: str,
        version: VersionSelector = None,
    ) -> tuple[LearningObjectiveReadModel, ...]:
        return tuple(self.repositories.objectives.list_for_skill(skill_id, version=version))

    def get_cefr_profile(
        self,
        skill_id: str,
        version: VersionSelector = None,
    ) -> SkillProfileReadModel:
        return self.repositories.nodes.get_skill_profile(skill_id, version)

    def get_assessment_profile(
        self,
        skill_id: str,
        version: VersionSelector = None,
    ) -> AssessmentProfile:
        criteria = tuple(self.repositories.assessments.list_for_skill(skill_id, version=version))
        return AssessmentProfile(
            skill_id=skill_id,
            criteria=criteria,
            task_types=_unique_text(item.task_types for item in criteria),
            evidence_requirements=_unique_text(
                item.evidence_requirements for item in criteria
            ),
            failure_signals=_unique_text(item.failure_signals for item in criteria),
        )

    def get_misconceptions(
        self,
        skill_id: str,
        version: VersionSelector = None,
    ) -> tuple[MisconceptionReadModel, ...]:
        return tuple(self.repositories.misconceptions.list_for_skill(skill_id, version=version))

    def get_diagnostic_signals(
        self,
        skill_id: str,
        version: VersionSelector = None,
    ) -> DiagnosticContext:
        resolved = self.repositories.versions.resolve_version(version)
        assessment = self.get_assessment_profile(skill_id, resolved)
        return DiagnosticContext(
            skill_id=skill_id,
            failure_signals=assessment.failure_signals,
            misconceptions=self.get_misconceptions(skill_id, resolved),
            error_statistics=tuple(
                self.repositories.corpus_errors.list_statistics(
                    skill_id=skill_id,
                    version=resolved,
                    limit=1000,
                )
            ),
            error_skill_mappings=tuple(
                self.repositories.corpus_errors.list_skill_mappings(
                    skill_id=skill_id,
                    version=resolved,
                    limit=1000,
                )
            ),
        )

    def get_related_learning_targets(
        self,
        skill_id: str,
        version: VersionSelector = None,
    ) -> tuple[RelationshipReadModel, ...]:
        return tuple(self.repositories.relationships.list_related(skill_id, version=version))

    def _nodes_for_prerequisite_path(
        self,
        skill_id: str,
        version: VersionSelector,
    ) -> list[KnowledgeNodeReadModel]:
        relationships = self.repositories.relationships.list_transitive_prerequisites(
            skill_id,
            version,
        )
        prerequisites_by_target: dict[str, list[str]] = {}
        for relationship in relationships:
            prerequisites_by_target.setdefault(relationship.target_skill_id, []).append(
                relationship.source_skill_id,
            )

        ordered_ids: list[str] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(current_id: str) -> None:
            if current_id in visited:
                return
            if current_id in visiting:
                raise ValueError(f"Prerequisite cycle detected at {current_id}")
            visiting.add(current_id)
            for prerequisite_id in sorted(prerequisites_by_target.get(current_id, ())):
                visit(prerequisite_id)
            visiting.remove(current_id)
            visited.add(current_id)
            ordered_ids.append(current_id)

        visit(skill_id)
        return [
            self.repositories.nodes.get_by_canonical_id(item_id, version)
            for item_id in ordered_ids
        ]


def _unique_text(groups: Iterable[tuple[str, ...]]) -> tuple[str, ...]:
    return tuple(sorted({value for group in groups for value in group}))
