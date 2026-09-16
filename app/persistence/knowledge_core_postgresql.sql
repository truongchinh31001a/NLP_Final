-- Knowledge Core Storage V1 PostgreSQL companion DDL.
-- The local application migration source remains app/persistence/schema.sql.
-- This file documents the direct PostgreSQL port of the Knowledge Core tables
-- and views; live PostgreSQL execution is not covered by the SQLite test suite.

CREATE TABLE IF NOT EXISTS knowledge_versions (
    id BIGSERIAL PRIMARY KEY,
    version_name TEXT NOT NULL UNIQUE,
    description TEXT,
    taxonomy_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    activated_at TIMESTAMPTZ,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS knowledge_sources (
    id BIGSERIAL PRIMARY KEY,
    source_key TEXT NOT NULL UNIQUE,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_version TEXT,
    source_year INTEGER,
    source_url TEXT,
    license_note TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_documents (
    id BIGSERIAL PRIMARY KEY,
    knowledge_source_id BIGINT NOT NULL REFERENCES knowledge_sources(id),
    document_key TEXT NOT NULL,
    title TEXT NOT NULL,
    file_name TEXT,
    file_hash TEXT,
    language TEXT,
    publication_year INTEGER,
    page_count INTEGER,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (knowledge_source_id, document_key)
);

CREATE TABLE IF NOT EXISTS source_records (
    id BIGSERIAL PRIMARY KEY,
    knowledge_source_id BIGINT NOT NULL REFERENCES knowledge_sources(id),
    source_document_id BIGINT REFERENCES source_documents(id),
    external_record_id TEXT NOT NULL,
    record_type TEXT NOT NULL,
    cefr_level TEXT,
    raw_text TEXT,
    normalized_text TEXT,
    page_number INTEGER,
    row_number INTEGER,
    sheet_name TEXT,
    raw_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    record_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (knowledge_source_id, external_record_id, record_type)
);

CREATE TABLE IF NOT EXISTS knowledge_nodes (
    id BIGSERIAL PRIMARY KEY,
    knowledge_version_id BIGINT NOT NULL REFERENCES knowledge_versions(id),
    canonical_id TEXT NOT NULL,
    node_type TEXT NOT NULL,
    domain TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    parent_node_id BIGINT REFERENCES knowledge_nodes(id),
    is_atomic BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (knowledge_version_id, canonical_id)
);

CREATE TABLE IF NOT EXISTS skill_profiles (
    id BIGSERIAL PRIMARY KEY,
    knowledge_node_id BIGINT NOT NULL UNIQUE REFERENCES knowledge_nodes(id),
    cefr_min_level TEXT,
    cefr_primary_level TEXT,
    evidence_status TEXT NOT NULL,
    alignment_confidence DOUBLE PRECISION,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS skill_source_evidence (
    id BIGSERIAL PRIMARY KEY,
    evidence_key TEXT NOT NULL,
    knowledge_node_id BIGINT NOT NULL REFERENCES knowledge_nodes(id),
    source_record_id BIGINT NOT NULL REFERENCES source_records(id),
    evidence_type TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    status TEXT NOT NULL,
    review_status TEXT NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (knowledge_node_id, source_record_id, evidence_type, status),
    UNIQUE (knowledge_node_id, evidence_key)
);

CREATE TABLE IF NOT EXISTS learning_objectives (
    id BIGSERIAL PRIMARY KEY,
    knowledge_version_id BIGINT NOT NULL REFERENCES knowledge_versions(id),
    objective_key TEXT NOT NULL,
    cefr_level TEXT,
    domain TEXT NOT NULL,
    scale_name TEXT,
    objective_text TEXT NOT NULL,
    source_record_id BIGINT REFERENCES source_records(id),
    status TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (knowledge_version_id, objective_key)
);

CREATE TABLE IF NOT EXISTS skill_learning_objectives (
    id BIGSERIAL PRIMARY KEY,
    knowledge_node_id BIGINT NOT NULL REFERENCES knowledge_nodes(id),
    learning_objective_id BIGINT NOT NULL REFERENCES learning_objectives(id),
    alignment_type TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    reason TEXT,
    review_status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (knowledge_node_id, learning_objective_id, alignment_type)
);

CREATE TABLE IF NOT EXISTS skill_cefr_alignments (
    id BIGSERIAL PRIMARY KEY,
    knowledge_node_id BIGINT NOT NULL UNIQUE REFERENCES knowledge_nodes(id),
    inferred_min_level TEXT,
    inferred_primary_level TEXT,
    confidence DOUBLE PRECISION NOT NULL,
    status TEXT NOT NULL,
    review_status TEXT NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS skill_relationships (
    id BIGSERIAL PRIMARY KEY,
    knowledge_version_id BIGINT NOT NULL REFERENCES knowledge_versions(id),
    relationship_key TEXT NOT NULL,
    source_node_id BIGINT NOT NULL REFERENCES knowledge_nodes(id),
    target_node_id BIGINT NOT NULL REFERENCES knowledge_nodes(id),
    relation_type TEXT NOT NULL,
    dependency_strength TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    status TEXT NOT NULL,
    review_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    bidirectional BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (knowledge_version_id, source_node_id, target_node_id, relation_type),
    CHECK (source_node_id <> target_node_id)
);

CREATE TABLE IF NOT EXISTS relationship_evidence (
    id BIGSERIAL PRIMARY KEY,
    relationship_id BIGINT NOT NULL REFERENCES skill_relationships(id),
    source_record_id BIGINT REFERENCES source_records(id),
    external_reference_id TEXT,
    evidence_type TEXT NOT NULL,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (relationship_id, source_record_id, external_reference_id, evidence_type, note)
);

CREATE TABLE IF NOT EXISTS assessment_criteria (
    id BIGSERIAL PRIMARY KEY,
    knowledge_version_id BIGINT NOT NULL REFERENCES knowledge_versions(id),
    criterion_key TEXT NOT NULL,
    knowledge_node_id BIGINT NOT NULL REFERENCES knowledge_nodes(id),
    criterion_type TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    observable_behavior TEXT NOT NULL,
    cefr_level TEXT,
    recommended_threshold DOUBLE PRECISION,
    recommended_min_items INTEGER,
    threshold_source TEXT,
    confidence DOUBLE PRECISION NOT NULL,
    status TEXT NOT NULL,
    review_status TEXT NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (knowledge_version_id, criterion_key)
);

CREATE TABLE IF NOT EXISTS assessment_evidence_requirements (
    id BIGSERIAL PRIMARY KEY,
    assessment_criterion_id BIGINT NOT NULL REFERENCES assessment_criteria(id),
    requirement_text TEXT NOT NULL,
    position INTEGER NOT NULL,
    UNIQUE (assessment_criterion_id, position, requirement_text)
);

CREATE TABLE IF NOT EXISTS assessment_failure_signals (
    id BIGSERIAL PRIMARY KEY,
    assessment_criterion_id BIGINT NOT NULL REFERENCES assessment_criteria(id),
    signal_text TEXT NOT NULL,
    position INTEGER NOT NULL,
    UNIQUE (assessment_criterion_id, position, signal_text)
);

CREATE TABLE IF NOT EXISTS assessment_task_types (
    id BIGSERIAL PRIMARY KEY,
    assessment_criterion_id BIGINT NOT NULL REFERENCES assessment_criteria(id),
    task_type TEXT NOT NULL,
    UNIQUE (assessment_criterion_id, task_type)
);

CREATE TABLE IF NOT EXISTS assessment_evidence (
    id BIGSERIAL PRIMARY KEY,
    assessment_criterion_id BIGINT NOT NULL REFERENCES assessment_criteria(id),
    source_record_id BIGINT REFERENCES source_records(id),
    external_reference_id TEXT,
    evidence_type TEXT NOT NULL,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (assessment_criterion_id, source_record_id, external_reference_id, evidence_type, note)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_canonical_id
ON knowledge_nodes (canonical_id);

CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_parent_node_id
ON knowledge_nodes (parent_node_id);

CREATE INDEX IF NOT EXISTS idx_source_records_source_type
ON source_records (knowledge_source_id, record_type);

CREATE INDEX IF NOT EXISTS idx_source_records_cefr_level
ON source_records (cefr_level);

CREATE INDEX IF NOT EXISTS idx_skill_source_evidence_node
ON skill_source_evidence (knowledge_node_id);

CREATE INDEX IF NOT EXISTS idx_skill_source_evidence_source_record
ON skill_source_evidence (source_record_id);

CREATE INDEX IF NOT EXISTS idx_skill_learning_objectives_node
ON skill_learning_objectives (knowledge_node_id);

CREATE INDEX IF NOT EXISTS idx_skill_relationships_source_relation
ON skill_relationships (source_node_id, relation_type);

CREATE INDEX IF NOT EXISTS idx_skill_relationships_target_relation
ON skill_relationships (target_node_id, relation_type);

CREATE INDEX IF NOT EXISTS idx_skill_cefr_alignments_primary_level
ON skill_cefr_alignments (inferred_primary_level);

CREATE INDEX IF NOT EXISTS idx_assessment_criteria_node
ON assessment_criteria (knowledge_node_id);

CREATE INDEX IF NOT EXISTS idx_learning_objectives_cefr_level
ON learning_objectives (cefr_level);

CREATE OR REPLACE VIEW v_atomic_skills AS
SELECT
    n.canonical_id,
    n.name,
    n.domain,
    sp.cefr_min_level,
    sp.cefr_primary_level,
    sp.evidence_status
FROM knowledge_nodes n
JOIN knowledge_versions kv
    ON kv.id = n.knowledge_version_id
LEFT JOIN skill_profiles sp
    ON sp.knowledge_node_id = n.id
WHERE
    kv.status = 'active'
    AND n.is_atomic = TRUE
    AND n.is_active = TRUE;

CREATE OR REPLACE VIEW v_skill_prerequisites AS
SELECT
    target_node.canonical_id AS skill_id,
    source_node.canonical_id AS prerequisite_skill_id,
    sr.confidence,
    sr.dependency_strength
FROM skill_relationships sr
JOIN knowledge_versions kv
    ON kv.id = sr.knowledge_version_id
JOIN knowledge_nodes source_node
    ON source_node.id = sr.source_node_id
JOIN knowledge_nodes target_node
    ON target_node.id = sr.target_node_id
WHERE
    kv.status = 'active'
    AND sr.relation_type = 'prerequisite_of';

CREATE OR REPLACE VIEW v_skill_assessment_summary AS
SELECT
    n.canonical_id AS skill_id,
    ac.criterion_key AS criterion_id,
    ac.criterion_type,
    ac.cefr_level,
    ac.recommended_threshold
FROM assessment_criteria ac
JOIN knowledge_versions kv
    ON kv.id = ac.knowledge_version_id
JOIN knowledge_nodes n
    ON n.id = ac.knowledge_node_id
WHERE kv.status = 'active';
