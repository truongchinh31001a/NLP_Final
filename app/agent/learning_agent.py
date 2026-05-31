from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

from app.config import AppConfig
from app.generation.service import ExerciseGenerationService
from app.generation.validator import ExerciseValidator
from app.intent.parser import IntentParser
from app.persistence.repository import LearningRepository
from app.personalization.service import PersonalizationService
from app.recommendation.service import RecommendationService
from app.retrieval.service import RetrievalService
from app.schemas import GeneratedExerciseSet, PracticeRequest, SessionResult

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
        self.max_generation_attempts = max_generation_attempts

    def create_exercise_set(self, user_id: str, raw_text: str) -> GeneratedExerciseSet:
        trace: list[AgentStep] = []

        request = self._run_tool(
            trace,
            "parse_learning_request",
            lambda: self.parser.parse(user_id=user_id, raw_text=raw_text),
            "Parsed the learner request into structured practice fields.",
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

        if exercises is None:
            if last_error is not None:
                raise last_error
            raise RuntimeError("Learning agent could not generate exercises.")

        trace.append(
            AgentStep(
                tool="finalize_response",
                status="ok",
                detail="Prepared the validated exercise set for the learner.",
                metadata={
                    "topic": plan.topic,
                    "difficulty": plan.difficulty,
                    "num_questions": len(exercises),
                },
            )
        )

        return GeneratedExerciseSet(
            request=request,
            plan=plan,
            retrieved_chunks=chunks,
            exercises=exercises,
            agent_trace=[self._step_to_dict(step) for step in trace],
        )

    def score_submission(
        self,
        user_id: str,
        topic: str,
        total_questions: int,
        correct_count: int,
    ) -> SessionResult:
        trace: list[AgentStep] = []
        score = correct_count / max(total_questions, 1)
        result = SessionResult(
            user_id=user_id,
            topic=topic,
            score=score,
            correct_count=correct_count,
            total_questions=total_questions,
            weak_topics_detected=[topic] if score < 0.8 else [],
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
        self._run_tool(
            trace,
            "save_session_result",
            lambda: self.repository.save_session_result(result),
            "Persisted the practice session result.",
            {"user_id": user_id, "topic": topic},
        )

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
