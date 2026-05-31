from pydantic import BaseModel, Field


class GeneratePracticeRequestModel(BaseModel):
    user_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


class GeneratePracticeOptionModel(BaseModel):
    label: str
    text: str
    is_correct: bool


class GeneratePracticeExerciseModel(BaseModel):
    exercise_id: str
    exercise_type: str
    topic: str
    difficulty: str
    question_text: str
    options: list[GeneratePracticeOptionModel]
    correct_answer: str
    explanation: str
    source_chunk_ids: list[str]


class GeneratePracticeResponseModel(BaseModel):
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
    topic: str = Field(min_length=1)
    answers: list[SubmittedAnswerModel] = Field(min_length=1)


class ScorePracticeResponseModel(BaseModel):
    topic: str
    score: float
    correct_count: int
    total_questions: int
    weak_topics_detected: list[str]
    recommendation: str


class HealthResponseModel(BaseModel):
    status: str
    generator_backend: str
