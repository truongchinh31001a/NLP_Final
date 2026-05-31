from pydantic import BaseModel, Field


class GeneratedOptionModel(BaseModel):
    label: str
    text: str
    is_correct: bool = False


class GeneratedExerciseModel(BaseModel):
    exercise_id: str
    question_text: str
    options: list[GeneratedOptionModel] = Field(default_factory=list)
    correct_answer: str
    explanation: str


class GeneratedExerciseBatchModel(BaseModel):
    exercises: list[GeneratedExerciseModel] = Field(min_length=1)
