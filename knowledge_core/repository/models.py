from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class KnowledgeVersionReadModel:
    id: int
    version_name: str
    description: str | None
    taxonomy_hash: str
    status: str
    created_at: str
    activated_at: str | None


@dataclass(frozen=True, slots=True)
class KnowledgeNodeReadModel:
    id: int
    canonical_id: str
    node_type: str
    domain: str
    name: str
    description: str | None
    parent_canonical_id: str | None
    is_atomic: bool
    is_active: bool
    knowledge_version: str


@dataclass(frozen=True, slots=True)
class SkillProfileReadModel:
    canonical_id: str
    cefr_min_level: str | None
    cefr_primary_level: str | None
    evidence_status: str
    alignment_confidence: float | None
    notes: str | None


@dataclass(frozen=True, slots=True)
class SourceRecordReadModel:
    source_record_id: str
    source_key: str
    source_name: str
    source_document_title: str | None
    file_name: str | None
    record_type: str
    cefr_level: str | None
    raw_text: str | None
    normalized_text: str | None
    page_number: int | None
    row_number: int | None
    sheet_name: str | None


@dataclass(frozen=True, slots=True)
class SourceEvidenceReadModel:
    evidence_id: str
    skill_id: str
    source_key: str
    source_record_id: str
    record_type: str
    source_cefr_level: str | None
    evidence_type: str
    confidence: float
    status: str
    review_status: str
    reason: str | None
    source_text: str | None
    page_number: int | None
    row_number: int | None


@dataclass(frozen=True, slots=True)
class LearningObjectiveReadModel:
    objective_key: str
    cefr_level: str | None
    domain: str
    scale_name: str | None
    objective_text: str
    status: str
    alignment_type: str | None = None
    alignment_confidence: float | None = None
    review_status: str | None = None
    skill_id: str | None = None
    source_record_id: str | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class RelationshipReadModel:
    relationship_id: str
    source_skill_id: str
    target_skill_id: str
    relation_type: str
    dependency_strength: str
    confidence: float
    status: str
    review_status: str
    reason: str
    bidirectional: bool
    other_skill_id: str | None = None


@dataclass(frozen=True, slots=True)
class RelationshipEvidenceReadModel:
    relationship_id: str
    evidence_type: str
    source_record_id: str | None
    external_reference_id: str | None
    source_key: str | None
    record_type: str | None
    source_text: str | None
    page_number: int | None
    row_number: int | None
    note: str | None


@dataclass(frozen=True, slots=True)
class AssessmentEvidenceReadModel:
    criterion_key: str
    evidence_type: str
    source_record_id: str | None
    external_reference_id: str | None
    source_key: str | None
    record_type: str | None
    source_text: str | None
    page_number: int | None
    row_number: int | None
    note: str | None


@dataclass(frozen=True, slots=True)
class AssessmentCriterionReadModel:
    criterion_key: str
    canonical_skill_id: str
    criterion_type: str
    name: str
    description: str
    observable_behavior: str
    cefr_level: str | None
    recommended_threshold: float | None
    recommended_min_items: int | None
    threshold_source: str | None
    confidence: float
    status: str
    review_status: str
    evidence_requirements: tuple[str, ...] = field(default_factory=tuple)
    failure_signals: tuple[str, ...] = field(default_factory=tuple)
    task_types: tuple[str, ...] = field(default_factory=tuple)
    evidence: tuple[AssessmentEvidenceReadModel, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class MisconceptionEvidenceReadModel:
    misconception_id: str
    normalized_error_id: str
    error_instance_id: str
    source_record_id: str
    source_key: str
    source_label: str | None
    proficiency_label: str | None
    task_id: str | None
    split: str | None
    mapping_confidence: float
    error_skill_mapping_id: str | None = None


@dataclass(frozen=True, slots=True)
class MisconceptionReadModel:
    misconception_id: str
    canonical_skill_id: str
    name: str
    description: str
    error_category: str
    error_subtype: str | None
    expected_pattern: str
    observed_pattern: str
    diagnostic_rule: str
    source_evidence_count: int
    frequency: float
    frequency_scope: str
    severity: str
    confidence: float
    status: str
    review_status: str
    reason: str
    evidence: tuple[MisconceptionEvidenceReadModel, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class CorpusErrorStatisticReadModel:
    statistic_key: str
    statistic_type: str
    count: int
    source_key: str | None = None
    skill_id: str | None = None
    normalized_category: str | None = None
    normalized_subtype: str | None = None
    mapping_status: str | None = None
    source_label: str | None = None


@dataclass(frozen=True, slots=True)
class ErrorSkillMappingReadModel:
    mapping_id: str
    skill_id: str
    source_key: str
    normalized_error_id: str
    error_instance_id: str
    source_record_id: str
    status: str
    confidence: float
    review_status: str
    reason: str


@dataclass(frozen=True, slots=True)
class SkillSnapshotReadModel:
    skill: KnowledgeNodeReadModel
    profile: SkillProfileReadModel
    direct_prerequisites: tuple[RelationshipReadModel, ...]
    related_relationships: tuple[RelationshipReadModel, ...]
    learning_objectives: tuple[LearningObjectiveReadModel, ...]
    assessment_criteria: tuple[AssessmentCriterionReadModel, ...]
    source_evidence_summary: dict[str, object]
    misconceptions: tuple[MisconceptionReadModel, ...] = field(default_factory=tuple)
    corpus_error_summary: dict[str, object] = field(default_factory=dict)
