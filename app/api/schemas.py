from typing import Any, Literal

from pydantic import BaseModel, Field


class GeneratePracticeRequestModel(BaseModel):
    user_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    topic: str | None = None
    difficulty: str | None = None
    exercise_type: str | None = None
    num_questions: int | None = Field(default=None, ge=1, le=20)
    target_subtopic: str | None = None
    content_theme: str | None = None


class GeneratePracticeOptionModel(BaseModel):
    label: str
    text: str
    is_correct: bool


class GeneratePracticeExerciseModel(BaseModel):
    exercise_id: str
    exercise_type: str
    topic: str
    difficulty: str
    skill: str = ""
    subtopic: str | None = None
    error_tag: str | None = None
    question_text: str
    options: list[GeneratePracticeOptionModel]
    correct_answer: str
    explanation: str
    source_chunk_ids: list[str]


class GeneratePracticeResponseModel(BaseModel):
    generation_run_id: str
    request: dict
    plan: dict
    exercises: list[GeneratePracticeExerciseModel]
    recommendation: str
    generator_backend: str
    agent_trace: list[dict] = Field(default_factory=list)


class SubmittedAnswerModel(BaseModel):
    exercise_id: str
    selected_answer: str


class ScorePracticeRequestModel(BaseModel):
    user_id: str = Field(min_length=1)
    generation_run_id: str = Field(min_length=1)
    answers: list[SubmittedAnswerModel] = Field(min_length=1)


class PracticeReviewResponseModel(BaseModel):
    review_code: str
    evaluator: str
    summary: str
    strengths: list[str]
    weaknesses: list[str]
    next_steps: list[str]
    next_practice_prompt: str
    raw_response: str = ""


class ScorePracticeResponseModel(BaseModel):
    topic: str
    score: float
    correct_count: int
    total_questions: int
    weak_topics_detected: list[str]
    recommendation: str
    generation_run_id: str
    session_code: str
    practice_review: PracticeReviewResponseModel | None = None


class UpdateUserProfileRequestModel(BaseModel):
    display_name: str | None = Field(default=None, max_length=80)
    level: str | None = None
    goals: list[str] = Field(default_factory=list)
    preferred_difficulty: str | None = None
    preferred_num_questions: int | None = Field(default=None, ge=1, le=20)
    weak_topics: list[str] = Field(default_factory=list)
    onboarding_completed: bool = True


class InterpretOnboardingRequestModel(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    current_answers: dict[str, Any] = Field(default_factory=dict)
    current_step_key: str | None = None


class InterpretOnboardingResponseModel(BaseModel):
    answers: dict[str, Any]
    assistant_reply: str
    next_question: str | None = None
    next_step_key: str | None = None
    is_complete: bool
    confidence: float
    source: str
    raw_llm_response: str = ""


class InterpretPracticeRequestModel(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class InterpretPracticeResponseModel(BaseModel):
    request: dict[str, Any]
    assistant_reply: str
    needs_clarification: bool
    clarification_question: str | None = None
    confidence: float
    source: str
    raw_llm_response: str = ""


class UserProfileResponseModel(BaseModel):
    user_id: str
    display_name: str
    level: str
    goals: list[str]
    preferred_difficulty: str | None = None
    preferred_num_questions: int | None = None
    onboarding_completed: bool
    weak_topics: dict[str, float]
    topic_accuracy: dict[str, float]
    weak_subtopics: dict[str, float]
    subtopic_accuracy: dict[str, float]
    error_tag_weakness: dict[str, float]


class ChatMessageResponseModel(BaseModel):
    message_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: str | None = None


class SaveChatMessageRequestModel(BaseModel):
    session_id: str | None = None
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    update_memory: bool = True


class ChatMemoryResponseModel(BaseModel):
    session_id: str
    has_history: bool
    memory_summary: str = ""
    extracted_facts: dict[str, Any] = Field(default_factory=dict)
    suggested_next_question: str
    messages: list[ChatMessageResponseModel] = Field(default_factory=list)


class SaveChatMessageResponseModel(BaseModel):
    session_id: str
    message: ChatMessageResponseModel
    memory_summary: str = ""
    extracted_facts: dict[str, Any] = Field(default_factory=dict)
    suggested_next_question: str


class PersonalizationTopicStatModel(BaseModel):
    code: str
    label: str
    topic: str
    attempts_count: int
    correct_count: int
    accuracy: float
    weakness_score: float
    status: str | None = None
    last_practiced_at: str | None = None


class PersonalizationSubtopicStatModel(BaseModel):
    code: str
    label: str
    topic: str
    attempts_count: int
    correct_count: int
    accuracy: float
    mastery_score: float
    weakness_score: float
    status: str | None = None
    last_practiced_at: str | None = None


class PersonalizationErrorStatModel(BaseModel):
    code: str
    label: str
    topic: str
    attempts_count: int
    incorrect_count: int
    error_rate: float
    weakness_score: float
    status: str | None = None
    last_seen_at: str | None = None


class PersonalizationSnapshotResponseModel(BaseModel):
    user_id: str
    display_name: str
    level: str
    goals: list[str]
    preferred_difficulty: str | None = None
    preferred_num_questions: int | None = None
    onboarding_completed: bool
    topic_stats: list[PersonalizationTopicStatModel]
    subtopic_stats: list[PersonalizationSubtopicStatModel]
    error_stats: list[PersonalizationErrorStatModel]
    next_plan: dict


class HealthResponseModel(BaseModel):
    status: str
    generator_backend: str


class ChromaDebugChunkModel(BaseModel):
    chunk_id: str
    topic: str
    subtopic: str | None = None
    level: str
    skill: str | None = None
    source: str | None = None
    content_preview: str


class ChromaDebugResponseModel(BaseModel):
    configured_backend: str
    using_chroma_backend: bool
    collection_name: str
    persist_directory: str
    is_available: bool
    status_message: str
    total_chunks: int
    topic_counts: dict[str, int]
    level_counts: dict[str, int]
    sample_chunks: list[ChromaDebugChunkModel]
    raw_knowledge_path: str
    raw_knowledge_count: int
    ingest_command: str
    error: str | None = None
