from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any

from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.runnables import Runnable

from app.config import AppConfig
from app.generation.output_models import GeneratedExerciseBatchModel
from app.generation.prompts import build_generation_prompt
from app.generation.seed_bank import SeedExercise, SeedExerciseBank
from app.schemas import ExerciseItem, ExerciseOption, KnowledgeChunk, PracticePlan


class ExerciseGenerationService:
    def __init__(
        self,
        config: AppConfig,
        llm_runnable: Runnable[Any, Any],
        backend_name: str,
        seed_bank: SeedExerciseBank | None = None,
    ) -> None:
        self.config = config
        self.llm_runnable = llm_runnable
        self.backend_name = backend_name
        self.seed_bank = seed_bank
        self.output_parser = PydanticOutputParser(
            pydantic_object=GeneratedExerciseBatchModel
        )
        self.prompt = build_generation_prompt(
            format_instructions=self.output_parser.get_format_instructions()
        )

    def generate(self, plan: PracticePlan, chunks: list[KnowledgeChunk]) -> list[ExerciseItem]:
        source_chunk_ids = [chunk.chunk_id for chunk in chunks]
        seed_examples = self._select_seed_examples(plan)

        if self._should_use_seed_fallback(seed_examples, plan.num_questions):
            seed_fallback = self.generate_from_seed_bank(
                plan=plan,
                chunks=chunks,
                seed_examples=seed_examples,
            )
            if seed_fallback is not None:
                return seed_fallback

        chain = self.prompt | self.llm_runnable | StrOutputParser() | self.output_parser

        invoke_payload = {
            "topic": plan.topic,
            "difficulty": plan.difficulty,
            "exercise_type": plan.exercise_type,
            "num_questions": plan.num_questions,
            "learner_level": self._infer_level_from_chunks(chunks),
            "target_subtopic": plan.target_subtopic or "auto",
            "target_error_tag": plan.target_error_tag or "auto",
            "target_skill_id": plan.target_skill_id or "auto",
            "content_theme": plan.content_theme or "none",
            "learner_summary": plan.learner_summary or "No learner history yet.",
            "retrieved_context": self._format_context(chunks),
            "seed_exercise_examples": self._format_seed_examples(seed_examples),
        }
        payload = self._invoke_with_timeout(chain, invoke_payload)

        exercises = [
            ExerciseItem(
                exercise_id=exercise.exercise_id,
                exercise_type=plan.exercise_type,
                topic=plan.topic,
                difficulty=plan.difficulty,
                skill=exercise.skill or self._skill_for_topic(plan.topic),
                subtopic=(
                    exercise.subtopic
                    or plan.target_subtopic
                    or self._infer_subtopic_from_chunks(chunks)
                    or self._infer_subtopic_from_seed(seed_examples)
                    or "general"
                ),
                error_tag=exercise.error_tag
                or plan.target_error_tag
                or self._infer_error_tag_from_seed(seed_examples)
                or "general",
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
        self._reject_exact_seed_duplicates(exercises, seed_examples)
        return exercises

    def generate_from_seed_bank(
        self,
        plan: PracticePlan,
        chunks: list[KnowledgeChunk],
        seed_examples: list[SeedExercise] | None = None,
    ) -> list[ExerciseItem] | None:
        selected_examples = seed_examples
        if selected_examples is None:
            selected_examples = self._select_seed_examples(plan)

        if len(selected_examples) < plan.num_questions:
            return None

        source_chunk_ids = [chunk.chunk_id for chunk in chunks]
        return self._build_from_seed_examples(
            plan=plan,
            source_chunk_ids=source_chunk_ids,
            seed_examples=selected_examples[: plan.num_questions],
        )

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

    def _select_seed_examples(self, plan: PracticePlan) -> list[SeedExercise]:
        if self.seed_bank is None:
            return []
        return self.seed_bank.select_for_plan(
            plan=plan,
            limit=max(plan.num_questions, 3),
        )

    def _format_seed_examples(self, examples: list[SeedExercise]) -> str:
        if self.seed_bank is None:
            return "No seed exercise examples available."
        return self.seed_bank.format_reference_examples(examples, limit=3)

    def _should_use_seed_fallback(
        self,
        seed_examples: list[SeedExercise],
        requested_count: int,
    ) -> bool:
        return (
            len(seed_examples) >= requested_count
            and (
                self.config.seed_first_generation
                or self.backend_name.startswith("langchain-fallback")
            )
        )

    def _invoke_with_timeout(
        self,
        chain: Runnable[dict[str, Any], GeneratedExerciseBatchModel],
        payload: dict[str, Any],
    ) -> GeneratedExerciseBatchModel:
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(chain.invoke, payload)
        try:
            return future.result(
                timeout=self.config.generation_llm_timeout_seconds,
            )
        except TimeoutError as exc:
            future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            raise TimeoutError(
                "LLM generation timed out; falling back to curated seed exercises."
            ) from exc
        finally:
            if future.done():
                executor.shutdown(wait=True)

    def _build_from_seed_examples(
        self,
        plan: PracticePlan,
        source_chunk_ids: list[str],
        seed_examples: list[SeedExercise],
    ) -> list[ExerciseItem]:
        return [
            ExerciseItem(
                exercise_id=seed.exercise_code,
                exercise_type=seed.exercise_type,
                topic=seed.topic_code,
                difficulty=seed.difficulty,
                skill=seed.skill,
                subtopic=seed.subtopic or plan.target_subtopic or "general",
                error_tag=seed.error_tag or plan.target_error_tag or "general",
                question_text=seed.question_text,
                options=[
                    ExerciseOption(
                        label=option.label,
                        text=option.text,
                        is_correct=option.is_correct,
                    )
                    for option in seed.options
                ],
                correct_answer=seed.correct_answer,
                explanation=seed.explanation,
                source_chunk_ids=[*source_chunk_ids, f"seed:{seed.exercise_code}"],
            )
            for seed in seed_examples
        ]

    def _reject_exact_seed_duplicates(
        self,
        exercises: list[ExerciseItem],
        seed_examples: list[SeedExercise],
    ) -> None:
        seed_questions = {
            self._normalize_question(seed.question_text)
            for seed in seed_examples
        }
        for exercise in exercises:
            if self._normalize_question(exercise.question_text) in seed_questions:
                raise ValueError(
                    "Generated exercise duplicates a seed exercise question exactly."
                )

    def _normalize_question(self, question_text: str) -> str:
        return " ".join(question_text.strip().lower().split())

    def _skill_for_topic(self, topic: str) -> str:
        if "vocabulary" in topic:
            return "vocabulary"
        return "grammar"

    def _infer_subtopic_from_chunks(self, chunks: list[KnowledgeChunk]) -> str | None:
        for chunk in chunks:
            subtopic = chunk.metadata.get("subtopic")
            if subtopic:
                return str(subtopic)
        return None

    def _infer_subtopic_from_seed(self, seed_examples: list[SeedExercise]) -> str | None:
        if seed_examples:
            return seed_examples[0].subtopic
        return None

    def _infer_error_tag_from_seed(self, seed_examples: list[SeedExercise]) -> str | None:
        if seed_examples:
            return seed_examples[0].error_tag
        return None
