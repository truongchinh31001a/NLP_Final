from typing import Any

from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.runnables import Runnable

from app.generation.output_models import GeneratedExerciseBatchModel
from app.generation.prompts import build_generation_prompt
from app.schemas import ExerciseItem, ExerciseOption, KnowledgeChunk, PracticePlan


class ExerciseGenerationService:
    def __init__(self, llm_runnable: Runnable[Any, Any], backend_name: str) -> None:
        self.llm_runnable = llm_runnable
        self.backend_name = backend_name
        self.output_parser = PydanticOutputParser(
            pydantic_object=GeneratedExerciseBatchModel
        )
        self.prompt = build_generation_prompt(
            format_instructions=self.output_parser.get_format_instructions()
        )

    def generate(self, plan: PracticePlan, chunks: list[KnowledgeChunk]) -> list[ExerciseItem]:
        source_chunk_ids = [chunk.chunk_id for chunk in chunks]
        chain = self.prompt | self.llm_runnable | StrOutputParser() | self.output_parser

        payload = chain.invoke(
            {
                "topic": plan.topic,
                "difficulty": plan.difficulty,
                "exercise_type": plan.exercise_type,
                "num_questions": plan.num_questions,
                "learner_level": self._infer_level_from_chunks(chunks),
                "retrieved_context": self._format_context(chunks),
            }
        )

        return [
            ExerciseItem(
                exercise_id=exercise.exercise_id,
                exercise_type=plan.exercise_type,
                topic=plan.topic,
                difficulty=plan.difficulty,
                question_text=exercise.question_text,
                options=[
                    ExerciseOption(
                        label=option.label,
                        text=option.text,
                        is_correct=option.is_correct,
                    )
                    for option in exercise.options
                ],
                correct_answer=exercise.correct_answer,
                explanation=exercise.explanation,
                source_chunk_ids=source_chunk_ids,
            )
            for exercise in payload.exercises
        ]

    def _format_context(self, chunks: list[KnowledgeChunk]) -> str:
        if not chunks:
            return "No retrieved context available."

        return "\n".join(
            f"- [{chunk.topic}/{chunk.level}] {chunk.content}" for chunk in chunks
        )

    def _infer_level_from_chunks(self, chunks: list[KnowledgeChunk]) -> str:
        if chunks:
            return chunks[0].level
        return "beginner"
