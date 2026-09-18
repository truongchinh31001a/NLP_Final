from __future__ import annotations

from collections import Counter

from knowledge_core.repository.assessment_repository import AssessmentRepository
from knowledge_core.repository.base import BaseKnowledgeRepository, VersionSelector
from knowledge_core.repository.corpus_error_repository import CorpusErrorRepository
from knowledge_core.repository.knowledge_node_repository import KnowledgeNodeRepository
from knowledge_core.repository.models import SkillSnapshotReadModel
from knowledge_core.repository.misconception_repository import MisconceptionRepository
from knowledge_core.repository.objective_repository import LearningObjectiveRepository
from knowledge_core.repository.relationship_repository import RelationshipRepository
from knowledge_core.repository.source_evidence_repository import SourceEvidenceRepository


class KnowledgeQueryRepository(BaseKnowledgeRepository):
    def __init__(
        self,
        *,
        nodes: KnowledgeNodeRepository,
        evidence: SourceEvidenceRepository,
        objectives: LearningObjectiveRepository,
        relationships: RelationshipRepository,
        assessments: AssessmentRepository,
        misconceptions: MisconceptionRepository,
        corpus_errors: CorpusErrorRepository,
    ) -> None:
        super().__init__(nodes.connection)
        self.nodes = nodes
        self.evidence = evidence
        self.objectives = objectives
        self.relationships = relationships
        self.assessments = assessments
        self.misconceptions = misconceptions
        self.corpus_errors = corpus_errors

    def get_skill_snapshot(
        self,
        skill_id: str,
        version: VersionSelector = None,
    ) -> SkillSnapshotReadModel:
        resolved = self.resolve_version(version)
        skill = self.nodes.get_by_canonical_id(skill_id, resolved)
        profile = self.nodes.get_skill_profile(skill_id, resolved)
        direct_prerequisites = self.relationships.list_direct_prerequisites(
            skill_id,
            resolved,
        )
        related_relationships = self.relationships.list_related(skill_id, version=resolved)
        learning_objectives = self.objectives.list_for_skill(skill_id, version=resolved)
        assessment_criteria = self.assessments.list_for_skill(skill_id, version=resolved)
        source_evidence = self.evidence.list_skill_evidence(skill_id, version=resolved)
        misconceptions = self.misconceptions.list_for_skill(
            skill_id,
            version=resolved,
        )
        error_mappings = self.corpus_errors.list_skill_mappings(
            skill_id=skill_id,
            version=resolved,
            limit=1000,
        )

        return SkillSnapshotReadModel(
            skill=skill,
            profile=profile,
            direct_prerequisites=tuple(direct_prerequisites),
            related_relationships=tuple(related_relationships),
            learning_objectives=tuple(learning_objectives),
            assessment_criteria=tuple(assessment_criteria),
            source_evidence_summary={
                "total": len(source_evidence),
                "by_source": dict(Counter(item.source_key for item in source_evidence)),
                "by_evidence_type": dict(
                    Counter(item.evidence_type for item in source_evidence),
                ),
                "by_review_status": dict(
                    Counter(item.review_status for item in source_evidence),
                ),
            },
            misconceptions=tuple(misconceptions),
            corpus_error_summary={
                "skill_mapping_count": len(error_mappings),
                "by_source": dict(Counter(item.source_key for item in error_mappings)),
                "by_status": dict(Counter(item.status for item in error_mappings)),
                "by_review_status": dict(
                    Counter(item.review_status for item in error_mappings),
                ),
            },
        )
