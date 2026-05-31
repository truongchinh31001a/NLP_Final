from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PracticeRequest:
    user_id: str
    raw_text: str
    topic: str | None = None
    difficulty: str | None = None
    exercise_type: str | None = None
    num_questions: int | None = None


@dataclass(slots=True)
class PracticePlan:
    user_id: str
    topic: str
    difficulty: str
    exercise_type: str
    num_questions: int
    focus_reason: str


@dataclass(slots=True)
class LearnerProfile:
    user_id: str
    level: str = "beginner"
    goals: list[str] = field(default_factory=list)
    preferred_difficulty: str | None = None
    weak_topics: dict[str, float] = field(default_factory=dict)
    topic_accuracy: dict[str, float] = field(default_factory=dict)


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


@dataclass(slots=True)
class GeneratedExerciseSet:
    request: PracticeRequest
    plan: PracticePlan
    retrieved_chunks: list[KnowledgeChunk]
    exercises: list[ExerciseItem]
    prompt_snapshot: str = ""


@dataclass(slots=True)
class SessionResult:
    user_id: str
    topic: str
    score: float
    correct_count: int
    total_questions: int
    weak_topics_detected: list[str] = field(default_factory=list)
    recommendation: str = ""
