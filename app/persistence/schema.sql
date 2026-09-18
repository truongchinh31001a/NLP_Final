PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_code TEXT NOT NULL UNIQUE,
    name TEXT,
    skill TEXT NOT NULL DEFAULT 'grammar',
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id TEXT NOT NULL UNIQUE,
    topic_id INTEGER NOT NULL,
    subtopic TEXT,
    level TEXT NOT NULL,
    skill TEXT NOT NULL,
    content TEXT NOT NULL,
    examples_json TEXT,
    common_mistakes_json TEXT,
    source TEXT,
    language TEXT DEFAULT 'english',
    metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);

CREATE TABLE IF NOT EXISTS seed_exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_code TEXT NOT NULL UNIQUE,
    topic_id INTEGER NOT NULL,
    subtopic TEXT,
    learner_level TEXT,
    difficulty TEXT,
    skill TEXT NOT NULL,
    exercise_type TEXT NOT NULL,
    question_text TEXT NOT NULL,
    correct_answer TEXT NOT NULL,
    explanation TEXT,
    error_tag TEXT,
    source TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);

CREATE TABLE IF NOT EXISTS seed_exercise_options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_id INTEGER NOT NULL,
    option_label TEXT NOT NULL,
    option_text TEXT NOT NULL,
    is_correct INTEGER NOT NULL,
    FOREIGN KEY (exercise_id) REFERENCES seed_exercises(id)
);

CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_code TEXT NOT NULL UNIQUE,
    topic_id INTEGER NOT NULL,
    parent_skill_code TEXT,
    name TEXT NOT NULL,
    skill_type TEXT NOT NULL DEFAULT 'grammar',
    cefr TEXT,
    description TEXT,
    prerequisites_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);

CREATE TABLE IF NOT EXISTS skill_dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prerequisite_skill_id INTEGER NOT NULL,
    dependent_skill_id INTEGER NOT NULL,
    relation_type TEXT NOT NULL DEFAULT 'prerequisite',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (prerequisite_skill_id, dependent_skill_id, relation_type),
    FOREIGN KEY (prerequisite_skill_id) REFERENCES skills(id),
    FOREIGN KEY (dependent_skill_id) REFERENCES skills(id)
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_code TEXT NOT NULL UNIQUE,
    name TEXT,
    email TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    level TEXT NOT NULL,
    goals_json TEXT NOT NULL DEFAULT '[]',
    preferred_difficulty TEXT,
    preferred_num_questions INTEGER,
    onboarding_completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS generation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generation_run_id TEXT NOT NULL UNIQUE,
    activity_id INTEGER,
    user_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    exercise_type TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    num_questions INTEGER NOT NULL,
    raw_request_text TEXT NOT NULL,
    prompt_snapshot TEXT,
    retrieved_chunk_ids_json TEXT NOT NULL DEFAULT '[]',
    agent_trace_json TEXT NOT NULL DEFAULT '[]',
    generator_backend TEXT,
    model_name TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (activity_id) REFERENCES learning_activities(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);

CREATE TABLE IF NOT EXISTS practice_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_code TEXT NOT NULL UNIQUE,
    activity_id INTEGER,
    user_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    generation_run_id INTEGER,
    difficulty TEXT NOT NULL,
    total_questions INTEGER NOT NULL,
    correct_count INTEGER NOT NULL,
    accuracy REAL NOT NULL,
    recommendation_text TEXT,
    started_at TEXT,
    ended_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (activity_id) REFERENCES learning_activities(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (topic_id) REFERENCES topics(id),
    FOREIGN KEY (generation_run_id) REFERENCES generation_runs(id)
);

CREATE TABLE IF NOT EXISTS session_exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_exercise_code TEXT NOT NULL UNIQUE,
    client_exercise_id TEXT NOT NULL,
    generation_run_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    exercise_type TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    skill TEXT NOT NULL DEFAULT 'grammar',
    subtopic TEXT,
    error_tag TEXT,
    question_text TEXT NOT NULL,
    correct_answer TEXT NOT NULL,
    explanation TEXT,
    source_chunk_ids_json TEXT NOT NULL DEFAULT '[]',
    display_order INTEGER,
    FOREIGN KEY (generation_run_id) REFERENCES generation_runs(id),
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);

CREATE TABLE IF NOT EXISTS session_exercise_options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_exercise_id INTEGER NOT NULL,
    option_label TEXT NOT NULL,
    option_text TEXT NOT NULL,
    is_correct INTEGER NOT NULL,
    FOREIGN KEY (session_exercise_id) REFERENCES session_exercises(id)
);

CREATE TABLE IF NOT EXISTS user_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    session_exercise_id INTEGER NOT NULL,
    selected_answer TEXT,
    is_correct INTEGER NOT NULL,
    error_tag TEXT,
    answer_time_ms INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES practice_sessions(id),
    FOREIGN KEY (session_exercise_id) REFERENCES session_exercises(id)
);

CREATE TABLE IF NOT EXISTS answer_diagnoses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_answer_id INTEGER NOT NULL UNIQUE,
    session_id INTEGER NOT NULL,
    session_exercise_id INTEGER NOT NULL,
    error_type TEXT NOT NULL,
    skill_code TEXT NOT NULL,
    topic_code TEXT NOT NULL,
    subtopic TEXT,
    subtype TEXT,
    severity REAL NOT NULL DEFAULT 0,
    mastery_impact REAL NOT NULL DEFAULT 0,
    explanation TEXT,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_answer_id) REFERENCES user_answers(id),
    FOREIGN KEY (session_id) REFERENCES practice_sessions(id),
    FOREIGN KEY (session_exercise_id) REFERENCES session_exercises(id)
);

CREATE TABLE IF NOT EXISTS practice_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_code TEXT NOT NULL UNIQUE,
    user_id INTEGER NOT NULL,
    session_id INTEGER NOT NULL UNIQUE,
    evaluator TEXT NOT NULL,
    summary_text TEXT NOT NULL,
    strengths_json TEXT NOT NULL DEFAULT '[]',
    weaknesses_json TEXT NOT NULL DEFAULT '[]',
    next_steps_json TEXT NOT NULL DEFAULT '[]',
    next_practice_prompt TEXT,
    raw_response TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (session_id) REFERENCES practice_sessions(id)
);

CREATE TABLE IF NOT EXISTS user_topic_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    attempts_count INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    accuracy REAL NOT NULL DEFAULT 0,
    weakness_score REAL NOT NULL DEFAULT 0,
    status TEXT,
    last_practiced_at TEXT,
    UNIQUE (user_id, topic_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);

CREATE TABLE IF NOT EXISTS user_skill_mastery (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    skill_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    mastery_probability REAL NOT NULL DEFAULT 0.35,
    attempts_count INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    incorrect_count INTEGER NOT NULL DEFAULT 0,
    confidence REAL NOT NULL DEFAULT 0,
    difficulty_history_json TEXT NOT NULL DEFAULT '[]',
    error_frequency_json TEXT NOT NULL DEFAULT '{}',
    status TEXT,
    last_practiced_at TEXT,
    next_review_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, skill_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (skill_id) REFERENCES skills(id),
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);

CREATE TABLE IF NOT EXISTS user_skill_mastery_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    skill_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    session_id INTEGER,
    session_exercise_id INTEGER,
    is_correct INTEGER NOT NULL,
    prior_mastery REAL NOT NULL,
    posterior_mastery REAL NOT NULL,
    difficulty TEXT,
    error_tag TEXT,
    observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (skill_id) REFERENCES skills(id),
    FOREIGN KEY (topic_id) REFERENCES topics(id),
    FOREIGN KEY (session_id) REFERENCES practice_sessions(id),
    FOREIGN KEY (session_exercise_id) REFERENCES session_exercises(id)
);

CREATE TABLE IF NOT EXISTS user_subtopic_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    subtopic TEXT NOT NULL,
    attempts_count INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    accuracy REAL NOT NULL DEFAULT 0,
    mastery_score REAL NOT NULL DEFAULT 0,
    weakness_score REAL NOT NULL DEFAULT 0,
    status TEXT,
    last_practiced_at TEXT,
    UNIQUE (user_id, topic_id, subtopic),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);

CREATE TABLE IF NOT EXISTS user_error_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    error_tag TEXT NOT NULL,
    attempts_count INTEGER NOT NULL DEFAULT 0,
    incorrect_count INTEGER NOT NULL DEFAULT 0,
    error_rate REAL NOT NULL DEFAULT 0,
    weakness_score REAL NOT NULL DEFAULT 0,
    status TEXT,
    last_seen_at TEXT,
    UNIQUE (user_id, topic_id, error_tag),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_code TEXT NOT NULL UNIQUE,
    user_id INTEGER NOT NULL,
    active_activity_id INTEGER,
    pending_clarification_json TEXT,
    title TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_updated
ON chat_sessions (user_id, updated_at);

CREATE TABLE IF NOT EXISTS learning_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_code TEXT NOT NULL UNIQUE,
    conversation_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    parent_activity_id TEXT,
    activity_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'CREATED',
    target_skills_json TEXT NOT NULL DEFAULT '[]',
    difficulty TEXT,
    config_json TEXT NOT NULL DEFAULT '{}',
    generation_run_id INTEGER,
    practice_session_id INTEGER,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    submitted_at TEXT,
    completed_at TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES chat_sessions(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (generation_run_id) REFERENCES generation_runs(id),
    FOREIGN KEY (practice_session_id) REFERENCES practice_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_learning_activities_user_conversation_updated
ON learning_activities (user_id, conversation_id, updated_at);

CREATE TABLE IF NOT EXISTS learning_activity_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL,
    event_code TEXT,
    event_type TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT,
    reason TEXT,
    status TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (activity_id) REFERENCES learning_activities(id)
);

CREATE INDEX IF NOT EXISTS idx_learning_activity_events_activity_created
ON learning_activity_events (activity_id, created_at);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_code TEXT NOT NULL UNIQUE,
    session_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created
ON chat_messages (session_id, created_at);

CREATE TABLE IF NOT EXISTS chat_memory_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    summary_text TEXT NOT NULL DEFAULT '',
    facts_json TEXT NOT NULL DEFAULT '{}',
    last_session_id INTEGER,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (last_session_id) REFERENCES chat_sessions(id)
);

CREATE TABLE IF NOT EXISTS evaluation_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_code TEXT NOT NULL UNIQUE,
    generation_run_id INTEGER,
    session_exercise_id INTEGER,
    evaluator TEXT,
    fluency INTEGER,
    relevance INTEGER,
    answerability INTEGER,
    difficulty_appropriateness INTEGER,
    distractor_quality INTEGER,
    personalization_usefulness INTEGER,
    comment TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (generation_run_id) REFERENCES generation_runs(id),
    FOREIGN KEY (session_exercise_id) REFERENCES session_exercises(id)
);

-- Knowledge Core Storage V1
-- Local development uses SQLite. Columns ending in _json intentionally use
-- TEXT so the schema remains straightforward to port to PostgreSQL JSONB.

CREATE TABLE IF NOT EXISTS knowledge_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_name TEXT NOT NULL UNIQUE,
    description TEXT,
    taxonomy_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    activated_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS knowledge_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL UNIQUE,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_version TEXT,
    source_year INTEGER,
    source_url TEXT,
    license_note TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_source_id INTEGER NOT NULL,
    document_key TEXT NOT NULL,
    title TEXT NOT NULL,
    file_name TEXT,
    file_hash TEXT,
    language TEXT,
    publication_year INTEGER,
    page_count INTEGER,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (knowledge_source_id, document_key),
    FOREIGN KEY (knowledge_source_id) REFERENCES knowledge_sources(id)
);

CREATE TABLE IF NOT EXISTS source_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_source_id INTEGER NOT NULL,
    source_document_id INTEGER,
    external_record_id TEXT NOT NULL,
    record_type TEXT NOT NULL,
    cefr_level TEXT,
    raw_text TEXT,
    normalized_text TEXT,
    page_number INTEGER,
    row_number INTEGER,
    sheet_name TEXT,
    raw_payload_json TEXT NOT NULL DEFAULT '{}',
    record_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (knowledge_source_id, external_record_id, record_type),
    FOREIGN KEY (knowledge_source_id) REFERENCES knowledge_sources(id),
    FOREIGN KEY (source_document_id) REFERENCES source_documents(id)
);

CREATE TABLE IF NOT EXISTS knowledge_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_version_id INTEGER NOT NULL,
    canonical_id TEXT NOT NULL,
    node_type TEXT NOT NULL,
    domain TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    parent_node_id INTEGER,
    is_atomic INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (knowledge_version_id, canonical_id),
    FOREIGN KEY (knowledge_version_id) REFERENCES knowledge_versions(id),
    FOREIGN KEY (parent_node_id) REFERENCES knowledge_nodes(id)
);

CREATE TABLE IF NOT EXISTS skill_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_node_id INTEGER NOT NULL UNIQUE,
    cefr_min_level TEXT,
    cefr_primary_level TEXT,
    evidence_status TEXT NOT NULL,
    alignment_confidence REAL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (knowledge_node_id) REFERENCES knowledge_nodes(id)
);

CREATE TABLE IF NOT EXISTS skill_source_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evidence_key TEXT NOT NULL,
    knowledge_node_id INTEGER NOT NULL,
    source_record_id INTEGER NOT NULL,
    evidence_type TEXT NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL,
    review_status TEXT NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (
        knowledge_node_id,
        source_record_id,
        evidence_type,
        status
    ),
    UNIQUE (knowledge_node_id, evidence_key),
    FOREIGN KEY (knowledge_node_id) REFERENCES knowledge_nodes(id),
    FOREIGN KEY (source_record_id) REFERENCES source_records(id)
);

CREATE TABLE IF NOT EXISTS learning_objectives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_version_id INTEGER NOT NULL,
    objective_key TEXT NOT NULL,
    cefr_level TEXT,
    domain TEXT NOT NULL,
    scale_name TEXT,
    objective_text TEXT NOT NULL,
    source_record_id INTEGER,
    status TEXT NOT NULL,
    confidence REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (knowledge_version_id, objective_key),
    FOREIGN KEY (knowledge_version_id) REFERENCES knowledge_versions(id),
    FOREIGN KEY (source_record_id) REFERENCES source_records(id)
);

CREATE TABLE IF NOT EXISTS skill_learning_objectives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_node_id INTEGER NOT NULL,
    learning_objective_id INTEGER NOT NULL,
    alignment_type TEXT NOT NULL,
    confidence REAL NOT NULL,
    reason TEXT,
    review_status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (
        knowledge_node_id,
        learning_objective_id,
        alignment_type
    ),
    FOREIGN KEY (knowledge_node_id) REFERENCES knowledge_nodes(id),
    FOREIGN KEY (learning_objective_id) REFERENCES learning_objectives(id)
);

CREATE TABLE IF NOT EXISTS skill_cefr_alignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_node_id INTEGER NOT NULL UNIQUE,
    inferred_min_level TEXT,
    inferred_primary_level TEXT,
    confidence REAL NOT NULL,
    status TEXT NOT NULL,
    review_status TEXT NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (knowledge_node_id) REFERENCES knowledge_nodes(id)
);

CREATE TABLE IF NOT EXISTS skill_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_version_id INTEGER NOT NULL,
    relationship_key TEXT NOT NULL,
    source_node_id INTEGER NOT NULL,
    target_node_id INTEGER NOT NULL,
    relation_type TEXT NOT NULL,
    dependency_strength TEXT NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL,
    review_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    bidirectional INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (
        knowledge_version_id,
        source_node_id,
        target_node_id,
        relation_type
    ),
    CHECK (source_node_id != target_node_id),
    FOREIGN KEY (knowledge_version_id) REFERENCES knowledge_versions(id),
    FOREIGN KEY (source_node_id) REFERENCES knowledge_nodes(id),
    FOREIGN KEY (target_node_id) REFERENCES knowledge_nodes(id)
);

CREATE TABLE IF NOT EXISTS relationship_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    relationship_id INTEGER NOT NULL,
    source_record_id INTEGER,
    external_reference_id TEXT,
    evidence_type TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (
        relationship_id,
        source_record_id,
        external_reference_id,
        evidence_type,
        note
    ),
    FOREIGN KEY (relationship_id) REFERENCES skill_relationships(id),
    FOREIGN KEY (source_record_id) REFERENCES source_records(id)
);

CREATE TABLE IF NOT EXISTS assessment_criteria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_version_id INTEGER NOT NULL,
    criterion_key TEXT NOT NULL,
    knowledge_node_id INTEGER NOT NULL,
    criterion_type TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    observable_behavior TEXT NOT NULL,
    cefr_level TEXT,
    recommended_threshold REAL,
    recommended_min_items INTEGER,
    threshold_source TEXT,
    confidence REAL NOT NULL,
    status TEXT NOT NULL,
    review_status TEXT NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (knowledge_version_id, criterion_key),
    FOREIGN KEY (knowledge_version_id) REFERENCES knowledge_versions(id),
    FOREIGN KEY (knowledge_node_id) REFERENCES knowledge_nodes(id)
);

CREATE TABLE IF NOT EXISTS assessment_evidence_requirements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_criterion_id INTEGER NOT NULL,
    requirement_text TEXT NOT NULL,
    position INTEGER NOT NULL,
    UNIQUE (assessment_criterion_id, position, requirement_text),
    FOREIGN KEY (assessment_criterion_id) REFERENCES assessment_criteria(id)
);

CREATE TABLE IF NOT EXISTS assessment_failure_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_criterion_id INTEGER NOT NULL,
    signal_text TEXT NOT NULL,
    position INTEGER NOT NULL,
    UNIQUE (assessment_criterion_id, position, signal_text),
    FOREIGN KEY (assessment_criterion_id) REFERENCES assessment_criteria(id)
);

CREATE TABLE IF NOT EXISTS assessment_task_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_criterion_id INTEGER NOT NULL,
    task_type TEXT NOT NULL,
    UNIQUE (assessment_criterion_id, task_type),
    FOREIGN KEY (assessment_criterion_id) REFERENCES assessment_criteria(id)
);

CREATE TABLE IF NOT EXISTS assessment_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_criterion_id INTEGER NOT NULL,
    source_record_id INTEGER,
    external_reference_id TEXT,
    evidence_type TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (
        assessment_criterion_id,
        source_record_id,
        external_reference_id,
        evidence_type,
        note
    ),
    FOREIGN KEY (assessment_criterion_id) REFERENCES assessment_criteria(id),
    FOREIGN KEY (source_record_id) REFERENCES source_records(id)
);

CREATE TABLE IF NOT EXISTS corpus_error_statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_version_id INTEGER NOT NULL,
    statistic_key TEXT NOT NULL,
    knowledge_source_id INTEGER,
    knowledge_node_id INTEGER,
    statistic_type TEXT NOT NULL,
    normalized_category TEXT,
    normalized_subtype TEXT,
    mapping_status TEXT,
    source_label TEXT,
    count INTEGER NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (knowledge_version_id, statistic_key),
    FOREIGN KEY (knowledge_version_id) REFERENCES knowledge_versions(id),
    FOREIGN KEY (knowledge_source_id) REFERENCES knowledge_sources(id),
    FOREIGN KEY (knowledge_node_id) REFERENCES knowledge_nodes(id)
);

CREATE TABLE IF NOT EXISTS corpus_error_skill_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_version_id INTEGER NOT NULL,
    mapping_key TEXT NOT NULL,
    knowledge_source_id INTEGER NOT NULL,
    knowledge_node_id INTEGER NOT NULL,
    normalized_error_id TEXT NOT NULL,
    error_instance_id TEXT NOT NULL,
    external_source_record_id TEXT NOT NULL,
    source_key TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence REAL NOT NULL,
    review_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    provenance_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (knowledge_version_id, mapping_key),
    FOREIGN KEY (knowledge_version_id) REFERENCES knowledge_versions(id),
    FOREIGN KEY (knowledge_source_id) REFERENCES knowledge_sources(id),
    FOREIGN KEY (knowledge_node_id) REFERENCES knowledge_nodes(id)
);

CREATE TABLE IF NOT EXISTS misconceptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_version_id INTEGER NOT NULL,
    misconception_key TEXT NOT NULL,
    knowledge_node_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    error_category TEXT NOT NULL,
    error_subtype TEXT,
    expected_pattern TEXT NOT NULL,
    observed_pattern TEXT NOT NULL,
    diagnostic_rule TEXT NOT NULL,
    source_evidence_count INTEGER NOT NULL,
    frequency REAL NOT NULL,
    frequency_scope TEXT NOT NULL,
    severity TEXT NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL,
    review_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    provenance_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (knowledge_version_id, misconception_key),
    FOREIGN KEY (knowledge_version_id) REFERENCES knowledge_versions(id),
    FOREIGN KEY (knowledge_node_id) REFERENCES knowledge_nodes(id)
);

CREATE TABLE IF NOT EXISTS misconception_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    misconception_id INTEGER NOT NULL,
    error_skill_mapping_id INTEGER,
    knowledge_source_id INTEGER NOT NULL,
    normalized_error_id TEXT NOT NULL,
    error_instance_id TEXT NOT NULL,
    external_source_record_id TEXT NOT NULL,
    source_key TEXT NOT NULL,
    source_label TEXT,
    proficiency_label TEXT,
    task_id TEXT,
    split TEXT,
    mapping_confidence REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (misconception_id, error_instance_id, normalized_error_id),
    FOREIGN KEY (misconception_id) REFERENCES misconceptions(id),
    FOREIGN KEY (error_skill_mapping_id) REFERENCES corpus_error_skill_mappings(id),
    FOREIGN KEY (knowledge_source_id) REFERENCES knowledge_sources(id)
);

CREATE TABLE IF NOT EXISTS skill_misconception_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_version_id INTEGER NOT NULL,
    link_key TEXT NOT NULL,
    misconception_id INTEGER NOT NULL,
    knowledge_node_id INTEGER NOT NULL,
    evidence_status TEXT NOT NULL,
    source_evidence_count INTEGER NOT NULL,
    confidence REAL NOT NULL,
    review_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (knowledge_version_id, link_key),
    FOREIGN KEY (knowledge_version_id) REFERENCES knowledge_versions(id),
    FOREIGN KEY (misconception_id) REFERENCES misconceptions(id),
    FOREIGN KEY (knowledge_node_id) REFERENCES knowledge_nodes(id)
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

CREATE INDEX IF NOT EXISTS idx_corpus_error_stats_version_type
ON corpus_error_statistics (knowledge_version_id, statistic_type);

CREATE INDEX IF NOT EXISTS idx_corpus_error_skill_mappings_node
ON corpus_error_skill_mappings (knowledge_node_id);

CREATE INDEX IF NOT EXISTS idx_corpus_error_skill_mappings_source
ON corpus_error_skill_mappings (knowledge_source_id, source_key);

CREATE INDEX IF NOT EXISTS idx_misconceptions_node
ON misconceptions (knowledge_node_id);

CREATE INDEX IF NOT EXISTS idx_misconception_evidence_misconception
ON misconception_evidence (misconception_id);

CREATE INDEX IF NOT EXISTS idx_skill_misconception_links_node
ON skill_misconception_links (knowledge_node_id);

CREATE VIEW IF NOT EXISTS v_atomic_skills AS
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
    AND n.is_atomic = 1
    AND n.is_active = 1;

CREATE VIEW IF NOT EXISTS v_skill_prerequisites AS
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

CREATE VIEW IF NOT EXISTS v_skill_assessment_summary AS
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

CREATE VIEW IF NOT EXISTS v_skill_misconceptions AS
SELECT
    n.canonical_id AS skill_id,
    m.misconception_key AS misconception_id,
    m.name,
    m.error_category,
    m.error_subtype,
    m.source_evidence_count,
    m.frequency,
    m.severity,
    m.confidence,
    m.status,
    m.review_status
FROM misconceptions m
JOIN knowledge_versions kv
    ON kv.id = m.knowledge_version_id
JOIN knowledge_nodes n
    ON n.id = m.knowledge_node_id
WHERE kv.status = 'active';

CREATE VIEW IF NOT EXISTS v_corpus_error_statistics AS
SELECT
    ces.statistic_key,
    ces.statistic_type,
    ks.source_key,
    n.canonical_id AS skill_id,
    ces.normalized_category,
    ces.normalized_subtype,
    ces.mapping_status,
    ces.source_label,
    ces.count
FROM corpus_error_statistics ces
JOIN knowledge_versions kv
    ON kv.id = ces.knowledge_version_id
LEFT JOIN knowledge_sources ks
    ON ks.id = ces.knowledge_source_id
LEFT JOIN knowledge_nodes n
    ON n.id = ces.knowledge_node_id
WHERE kv.status = 'active';
