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
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);

CREATE TABLE IF NOT EXISTS practice_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_code TEXT NOT NULL UNIQUE,
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
    title TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_updated
ON chat_sessions (user_id, updated_at);

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
