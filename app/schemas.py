from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ConversationIntent(str, Enum):
    PRACTICE = "PRACTICE"
    EXPLAIN = "EXPLAIN"
    REVIEW = "REVIEW"
    PROGRESS = "PROGRESS"
    PROFILE_UPDATE = "PROFILE_UPDATE"
    GENERAL = "GENERAL"


class LearningActivityType(str, Enum):
    PRACTICE = "PRACTICE"
    REVIEW = "REVIEW"
    CALIBRATION = "CALIBRATION"
    QUIZ = "QUIZ"
    READING = "READING"
    CONVERSATION_EXERCISE = "CONVERSATION_EXERCISE"


class LearningActivityStatus(str, Enum):
    CREATED = "CREATED"
    GENERATING = "GENERATING"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    GRADED = "GRADED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(slots=True)
class PracticeRequest:
    user_id: str
    raw_text: str
    processing_text: str = ""
    detected_language: str = "en"
    topic: str | None = None
    difficulty: str | None = None
    exercise_type: str | None = None
    num_questions: int | None = None
    target_subtopic: str | None = None
    content_theme: str | None = None


@dataclass(slots=True)
class PracticePlan:
    user_id: str
    topic: str
    difficulty: str
    exercise_type: str
    num_questions: int
    focus_reason: str
    target_subtopic: str | None = None
    target_error_tag: str | None = None
    target_skill_id: str | None = None
    content_theme: str | None = None
    learner_summary: str = ""


@dataclass(slots=True)
class LearnerProfile:
    user_id: str
    display_name: str = ""
    level: str = "beginner"
    goals: list[str] = field(default_factory=list)
    preferred_difficulty: str | None = None
    preferred_num_questions: int | None = None
    onboarding_completed: bool = False
    weak_topics: dict[str, float] = field(default_factory=dict)
    topic_accuracy: dict[str, float] = field(default_factory=dict)
    weak_subtopics: dict[str, float] = field(default_factory=dict)
    subtopic_accuracy: dict[str, float] = field(default_factory=dict)
    error_tag_weakness: dict[str, float] = field(default_factory=dict)
    skill_mastery: dict[str, float] = field(default_factory=dict)
    skill_confidence: dict[str, float] = field(default_factory=dict)
    skill_attempts: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class PendingClarification:
    pending_intent: ConversationIntent
    missing_fields: list[str] = field(default_factory=list)
    collected_slots: dict[str, Any] = field(default_factory=dict)
    question: str = ""


@dataclass(slots=True)
class LearningActivity:
    activity_id: str
    conversation_id: str
    learner_id: str
    type: LearningActivityType
    status: LearningActivityStatus = LearningActivityStatus.CREATED
    target_skills: list[str] = field(default_factory=list)
    difficulty: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    submitted_at: str | None = None
    completed_at: str | None = None
    updated_at: str | None = None
    generation_run_id: str | None = None
    session_code: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ConversationTurnContext:
    conversation_id: str
    learner_id: str
    profile: LearnerProfile
    recent_messages: list[dict[str, Any]] = field(default_factory=list)
    memory_summary: str = ""
    active_intent: ConversationIntent | None = None
    pending_clarification: PendingClarification | None = None
    active_activity: LearningActivity | None = None
    recent_context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SkillMasterySnapshot:
    code: str
    label: str
    topic: str
    skill_type: str
    cefr: str | None
    mastery_probability: float
    confidence: float
    attempts_count: int
    correct_count: int
    incorrect_count: int
    weakness_score: float
    status: str | None = None
    last_practiced_at: str | None = None
    next_review_at: str | None = None
    prerequisites: list[str] = field(default_factory=list)


@dataclass(slots=True)
class KnowledgeChunk:
    chunk_id: str
    topic: str
    level: str
    content: str
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExerciseOption:
    label: str
    text: str
    is_correct: bool = False


@dataclass(slots=True)
class ExerciseItem:
    exercise_id: str
    exercise_type: str
    topic: str
    difficulty: str
    question_text: str
    options: list[ExerciseOption] = field(default_factory=list)
    correct_answer: str = ""
    explanation: str = ""
    source_chunk_ids: list[str] = field(default_factory=list)
    skill: str = ""
    subtopic: str | None = None
    error_tag: str | None = None


@dataclass(slots=True)
class GeneratedExerciseSet:
    request: PracticeRequest
    plan: PracticePlan
    retrieved_chunks: list[KnowledgeChunk]
    exercises: list[ExerciseItem]
    activity_id: str | None = None
    generation_run_id: str = ""
    prompt_snapshot: str = ""
    agent_trace: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class SubmittedAnswer:
    exercise_id: str
    selected_answer: str


@dataclass(slots=True)
class AnswerDiagnosis:
    exercise_id: str
    is_correct: bool
    error_type: str
    skill_id: str
    topic: str
    subtopic: str | None = None
    subtype: str | None = None
    severity: float = 0.0
    mastery_impact: float = 0.0
    explanation: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PracticeReview:
    review_code: str
    evaluator: str
    summary: str
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    next_practice_prompt: str = ""
    raw_response: str = ""


@dataclass(slots=True)
class ActivityRecommendation:
    recommendation_id: str
    user_id: str
    topic: str
    difficulty: str
    exercise_type: str
    num_questions: int
    reason: str
    skill: str | None = None
    subtopic: str | None = None
    source_activity_id: str | None = None
    conversation_id: str | None = None
    prompt: str = ""


@dataclass(slots=True)
class SessionResult:
    user_id: str
    topic: str
    score: float
    correct_count: int
    total_questions: int
    weak_topics_detected: list[str] = field(default_factory=list)
    recommendation: str = ""
    activity_id: str | None = None
    generation_run_id: str = ""
    session_code: str = ""
    answer_diagnoses: list[AnswerDiagnosis] = field(default_factory=list)
    practice_review: PracticeReview | None = None
