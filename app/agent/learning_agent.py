from dataclasses import dataclass, field
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any, Callable, TypeVar

from app.config import AppConfig
from app.generation.service import ExerciseGenerationService
from app.generation.validator import ExerciseValidator
from app.intent.parser import IntentParser
from app.language.translation import BilingualTextNormalizer
from app.persistence.repository import LearningRepository
from app.personalization.service import PersonalizationService
from app.recommendation.service import RecommendationService
from app.retrieval.service import RetrievalService
from app.review.service import PracticeReviewService
from app.schemas import (
    ExerciseItem,
    GeneratedExerciseSet,
    KnowledgeChunk,
    PracticePlan,
    PracticeRequest,
    SessionResult,
    SubmittedAnswer,
)

T = TypeVar("T")


@dataclass(slots=True)
class AgentStep:
    tool: str
    status: str
    detail: str
    metadata: dict[str, Any] = field(default_factory=dict)


class LearningAgent:
    """A bounded agent that can plan and call approved learning tools."""

    def __init__(
        self,
        config: AppConfig,
        repository: LearningRepository,
        parser: IntentParser,
        personalization: PersonalizationService,
        retrieval: RetrievalService,
        generator: ExerciseGenerationService,
        validator: ExerciseValidator,
        recommendation: RecommendationService,
        review: PracticeReviewService,
        max_generation_attempts: int = 2,
    ) -> None:
        self.config = config
        self.repository = repository
        self.parser = parser
        self.personalization = personalization
        self.retrieval = retrieval
        self.generator = generator
        self.validator = validator
        self.recommendation = recommendation
        self.review = review
        self.max_generation_attempts = max_generation_attempts
        self.text_normalizer = BilingualTextNormalizer()

    def create_exercise_set(
        self,
        user_id: str,
        raw_text: str,
        request_overrides: PracticeRequest | None = None,
    ) -> GeneratedExerciseSet:
        trace: list[AgentStep] = []

        request = self._run_tool(
            trace,
            "parse_learning_request",
            lambda: self.parser.parse(user_id=user_id, raw_text=raw_text),
            "Parsed the learner request into structured practice fields.",
        )
        if request_overrides is not None:
            request = self._merge_request_overrides(request, request_overrides)
            trace.append(
                AgentStep(
                    tool="apply_interpreted_practice_intent",
                    status="ok",
                    detail="Applied structured intent fields from the practice interpreter.",
                    metadata={
                        "topic": request.topic,
                        "difficulty": request.difficulty,
                        "exercise_type": request.exercise_type,
                        "num_questions": request.num_questions,
                        "target_subtopic": request.target_subtopic,
                        "content_theme": request.content_theme,
                    },
                )
            )
        trace.append(
            AgentStep(
                tool="normalize_user_language",
                status="ok",
                detail="Normalized bilingual learner text for downstream processing.",
                metadata={
                    "detected_language": request.detected_language,
                    "processing_text": request.processing_text,
                },
            )
        )
        profile = self._run_tool(
            trace,
            "get_user_profile",
            lambda: self.repository.get_profile(user_id),
            "Loaded the learner profile and learning history.",
            {"user_id": user_id},
        )
        plan = self._run_tool(
            trace,
            "build_practice_plan",
            lambda: self.personalization.build_plan(request, profile),
            "Built a personalized practice plan from the request and profile.",
        )
        chunks = self._run_tool(
            trace,
            "retrieve_knowledge",
            lambda: self.retrieval.retrieve(plan, profile.level),
            "Retrieved knowledge chunks for grounded exercise generation.",
            {"topic": plan.topic, "learner_level": profile.level},
        )

        exercises = None
        last_error: Exception | None = None
        for attempt in range(1, self.max_generation_attempts + 1):
            try:
                generated = self._run_tool(
                    trace,
                    "generate_exercises",
                    lambda: self.generator.generate(plan, chunks),
                    "Generated candidate exercises from the plan and retrieved context.",
                    {"attempt": attempt},
                )
                self._run_tool(
                    trace,
                    "validate_exercises",
                    lambda: self.validator.validate(
                        generated,
                        expected_count=plan.num_questions,
                    ),
                    "Validated exercise count, options, answer key, and explanations.",
                    {"attempt": attempt},
                )
                exercises = generated
                break
            except Exception as exc:
                last_error = exc
                trace.append(
                    AgentStep(
                        tool="reflection",
                        status="retry" if attempt < self.max_generation_attempts else "failed",
                        detail=f"Generation attempt {attempt} did not pass validation: {exc}",
                        metadata={"attempt": attempt},
                    )
                )
                if isinstance(exc, FutureTimeoutError):
                    break

        if exercises is None:
            try:
                generated = self._run_tool(
                    trace,
                    "generate_seed_bank_fallback",
                    lambda: self._require_seed_bank_fallback(plan, chunks),
                    "Generated fallback exercises from the curated seed bank.",
                    {"reason": str(last_error) if last_error else "generation failed"},
                )
                self._run_tool(
                    trace,
                    "validate_seed_bank_fallback",
                    lambda: self.validator.validate(
                        generated,
                        expected_count=plan.num_questions,
                    ),
                    "Validated fallback exercise count, options, answer key, and explanations.",
                )
                exercises = generated
            except Exception as exc:
                trace.append(
                    AgentStep(
                        tool="reflection",
                        status="failed",
                        detail=f"Seed-bank fallback did not pass validation: {exc}",
                    )
                )
                if last_error is not None:
                    raise last_error
                raise RuntimeError("Learning agent could not generate exercises.") from exc

        generated_set = GeneratedExerciseSet(
            request=request,
            plan=plan,
            retrieved_chunks=chunks,
            exercises=exercises,
            agent_trace=[self._step_to_dict(step) for step in trace],
        )

        generation_run_id = self._run_tool(
            trace,
            "save_generated_exercise_set",
            lambda: self.repository.save_generated_exercise_set(
                generated_set,
                self.generator.backend_name,
            ),
            "Persisted the generation run and generated exercise snapshots.",
            {"topic": plan.topic, "num_questions": len(exercises)},
        )

        trace.append(
            AgentStep(
                tool="finalize_response",
                status="ok",
                detail="Prepared the validated exercise set for the learner.",
                metadata={
                    "topic": plan.topic,
                    "difficulty": plan.difficulty,
                    "num_questions": len(exercises),
                    "generation_run_id": generation_run_id,
                },
            )
        )

        generated_set.agent_trace = [self._step_to_dict(step) for step in trace]
        return generated_set

    def score_submission(
        self,
        user_id: str,
        generation_run_id: str,
        answers: list[SubmittedAnswer],
    ) -> SessionResult:
        trace: list[AgentStep] = []
        generated = self._run_tool(
            trace,
            "load_generated_exercise_set",
            lambda: self.repository.get_generated_exercise_set(
                user_id,
                generation_run_id,
            ),
            "Loaded the persisted generated exercise snapshot.",
            {"generation_run_id": generation_run_id},
        )
        if generated is None:
            raise LookupError(f"Generation run not found: {generation_run_id}")

        answer_lookup = {
            answer.exercise_id: answer.selected_answer for answer in answers
        }
        correct_count = sum(
            1
            for exercise in generated.exercises
            if self._answers_match(
                answer_lookup.get(exercise.exercise_id),
                exercise.correct_answer,
            )
        )
        topic = generated.plan.topic
        total_questions = len(generated.exercises)
        score = correct_count / max(total_questions, 1)
        result = SessionResult(
            user_id=user_id,
            topic=topic,
            score=score,
            correct_count=correct_count,
            total_questions=total_questions,
            weak_topics_detected=[topic] if score < 0.8 else [],
            generation_run_id=generation_run_id,
        )

        result.recommendation = self._run_tool(
            trace,
            "recommend_next_practice",
            lambda: self.recommendation.recommend(result),
            "Recommended the next practice action from the scoring result.",
        )
        profile = self._run_tool(
            trace,
            "get_user_profile",
            lambda: self.repository.get_profile(user_id),
            "Loaded the learner profile before updating memory.",
            {"user_id": user_id},
        )
        updated_profile = self._run_tool(
            trace,
            "analyze_errors_and_update_profile",
            lambda: self.personalization.update_profile(profile, result),
            "Updated topic accuracy and weak topic scores.",
            {"topic": topic, "score": score},
        )
        self._run_tool(
            trace,
            "save_user_profile",
            lambda: self.repository.save_profile(updated_profile),
            "Persisted the updated learner profile.",
            {"user_id": user_id},
        )
        session_code = self._run_tool(
            trace,
            "save_session_result",
            lambda: self.repository.save_session_result(
                result,
                generation_run_id=generation_run_id,
                selected_answers=answer_lookup,
            ),
            "Persisted the practice session result.",
            {"user_id": user_id, "topic": topic, "generation_run_id": generation_run_id},
        )
        result.session_code = session_code

        practice_review = self._run_tool(
            trace,
            "review_practice_session",
            lambda: self.review.review(
                result=result,
                generated=generated,
                selected_answers=answer_lookup,
            ),
            "Reviewed the completed session for strengths, weaknesses, and next steps.",
            {"session_code": session_code, "score": score},
        )
        self._run_tool(
            trace,
            "save_practice_review",
            lambda: self.repository.save_practice_review(
                user_id=user_id,
                session_code=session_code,
                review=practice_review,
            ),
            "Persisted the practice review for later personalization.",
            {
                "session_code": session_code,
                "evaluator": practice_review.evaluator,
            },
        )
        result.practice_review = practice_review

        return result

    def _run_tool(
        self,
        trace: list[AgentStep],
        tool: str,
        action: Callable[[], T],
        detail: str,
        metadata: dict[str, Any] | None = None,
    ) -> T:
        try:
            output = action()
        except Exception as exc:
            trace.append(
                AgentStep(
                    tool=tool,
                    status="error",
                    detail=str(exc),
                    metadata=metadata or {},
                )
            )
            raise

        trace.append(
            AgentStep(
                tool=tool,
                status="ok",
                detail=detail,
                metadata=metadata or {},
            )
        )
        return output

    def _step_to_dict(self, step: AgentStep) -> dict[str, Any]:
        return {
            "tool": step.tool,
            "status": step.status,
            "detail": step.detail,
            "metadata": step.metadata,
        }

    def _require_seed_bank_fallback(
        self,
        plan: PracticePlan,
        chunks: list[KnowledgeChunk],
    ) -> list[ExerciseItem]:
        exercises = self.generator.generate_from_seed_bank(plan, chunks)
        if exercises is None:
            raise RuntimeError("No seed-bank fallback exercises are available for this plan.")
        return exercises

    def _merge_request_overrides(
        self,
        request: PracticeRequest,
        overrides: PracticeRequest,
    ) -> PracticeRequest:
        return PracticeRequest(
            user_id=request.user_id,
            raw_text=request.raw_text,
            processing_text=request.processing_text,
            detected_language=request.detected_language,
            topic=overrides.topic or request.topic,
            difficulty=overrides.difficulty or request.difficulty,
            exercise_type=overrides.exercise_type or request.exercise_type,
            num_questions=overrides.num_questions or request.num_questions,
            target_subtopic=overrides.target_subtopic or request.target_subtopic,
            content_theme=overrides.content_theme or request.content_theme,
        )

    def _answers_match(self, selected_answer: str | None, correct_answer: str) -> bool:
        return self.text_normalizer.answers_match(selected_answer, correct_answer)
