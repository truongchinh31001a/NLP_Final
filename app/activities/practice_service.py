import uuid
from dataclasses import asdict, dataclass
from typing import Any

from app.agent.learning_agent import LearningAgent
from app.config import AppConfig
from app.persistence.repository import LearningRepository
from app.schemas import (
    GeneratedExerciseSet,
    LearningActivity,
    LearningActivityStatus,
    LearningActivityType,
    PracticeRequest,
    SessionResult,
    SubmittedAnswer,
)


@dataclass(slots=True)
class PracticeActivityGeneration:
    activity: LearningActivity
    generated: GeneratedExerciseSet
    recommendation: str = ""


@dataclass(slots=True)
class PracticeActivitySubmission:
    activity: LearningActivity
    result: SessionResult
    generated: GeneratedExerciseSet
    selected_answers: dict[str, str]
    next_activity_suggestion: dict[str, Any] | None = None


class PracticeActivityService:
    def __init__(
        self,
        config: AppConfig,
        repository: LearningRepository,
        agent: LearningAgent,
    ) -> None:
        self.config = config
        self.repository = repository
        self.agent = agent

    def create_practice_activity(
        self,
        *,
        user_id: str,
        raw_text: str,
        conversation_id: str | None = None,
        request_overrides: PracticeRequest | None = None,
        skip_request_parser: bool = False,
    ) -> PracticeActivityGeneration:
        resolved_conversation_id = self._ensure_conversation(
            user_id,
            conversation_id,
        )
        activity = self.repository.create_learning_activity(
            LearningActivity(
                activity_id=f"activity_{uuid.uuid4().hex}",
                conversation_id=resolved_conversation_id,
                learner_id=user_id,
                type=LearningActivityType.PRACTICE,
                target_skills=self._target_skills(request_overrides),
                difficulty=(
                    request_overrides.difficulty
                    if request_overrides is not None
                    else None
                ),
                metadata={
                    "raw_text": raw_text,
                    "request": (
                        asdict(request_overrides)
                        if request_overrides is not None
                        else None
                    ),
                },
            ),
        )
        self.repository.update_learning_activity_status(
            user_id,
            activity.activity_id,
            LearningActivityStatus.GENERATING,
        )

        try:
            generated = self.agent.create_exercise_set(
                user_id=user_id,
                raw_text=raw_text,
                request_overrides=request_overrides,
                activity_id=activity.activity_id,
                skip_request_parser=skip_request_parser,
            )
        except Exception:
            self.repository.update_learning_activity_status(
                user_id,
                activity.activity_id,
                LearningActivityStatus.FAILED,
            )
            raise

        activity = self.repository.update_learning_activity_status(
            user_id,
            activity.activity_id,
            LearningActivityStatus.READY,
        )
        return PracticeActivityGeneration(
            activity=activity,
            generated=generated,
            recommendation="",
        )

    def submit_practice_activity(
        self,
        *,
        user_id: str,
        activity_id: str,
        answers: list[SubmittedAnswer],
    ) -> PracticeActivitySubmission:
        activity = self._require_practice_activity(user_id, activity_id)
        if not activity.generation_run_id:
            raise LookupError("Practice activity has no generated exercise set.")

        if activity.status == LearningActivityStatus.READY:
            activity = self.repository.update_learning_activity_status(
                user_id,
                activity_id,
                LearningActivityStatus.IN_PROGRESS,
            )

        result = self.agent.score_submission(
            user_id=user_id,
            generation_run_id=activity.generation_run_id,
            answers=answers,
        )
        activity = self.repository.get_learning_activity(user_id, activity_id)
        if activity is None:
            raise LookupError(f"Learning activity not found: {activity_id}")
        generated = self.repository.get_generated_exercise_set(
            user_id,
            activity.generation_run_id or result.generation_run_id,
        )
        if generated is None:
            raise LookupError(
                f"Generation run not found: {activity.generation_run_id}",
            )
        return PracticeActivitySubmission(
            activity=activity,
            result=result,
            generated=generated,
            selected_answers={
                answer.exercise_id: answer.selected_answer for answer in answers
            },
            next_activity_suggestion=self._next_activity_suggestion(
                result,
                generated,
                {answer.exercise_id: answer.selected_answer for answer in answers},
            ),
        )

    def _ensure_conversation(
        self,
        user_id: str,
        conversation_id: str | None,
    ) -> str:
        resume = self.repository.get_chat_resume(
            user_id,
            session_id=conversation_id,
        )
        return str(resume["session_id"])

    def _require_practice_activity(
        self,
        user_id: str,
        activity_id: str,
    ) -> LearningActivity:
        activity = self.repository.get_learning_activity(user_id, activity_id)
        if activity is None:
            raise LookupError(f"Learning activity not found: {activity_id}")
        if activity.type != LearningActivityType.PRACTICE:
            raise ValueError("Learning activity is not a practice activity.")
        if activity.status in {
            LearningActivityStatus.CANCELLED,
            LearningActivityStatus.FAILED,
        }:
            raise ValueError(
                f"Cannot submit a {activity.status.value.lower()} activity.",
            )
        return activity

    def _target_skills(
        self,
        request: PracticeRequest | None,
    ) -> list[str]:
        if request is None:
            return []
        return [
            value
            for value in [
                request.topic,
                request.target_subtopic,
                request.exercise_type,
            ]
            if value
        ]

    def _next_activity_suggestion(
        self,
        result: SessionResult,
        generated: GeneratedExerciseSet,
        selected_answers: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        profile = self.repository.get_profile(result.user_id)
        recommendation = self.agent.recommendation.build_next_activity_recommendation(
            result=result,
            profile=profile,
            generated=generated,
            selected_answers=selected_answers,
            source_activity_id=result.activity_id or generated.activity_id,
            conversation_id=self._conversation_id_for_result(result, generated),
        )
        return asdict(recommendation)

    def _conversation_id_for_result(
        self,
        result: SessionResult,
        generated: GeneratedExerciseSet,
    ) -> str | None:
        activity_id = result.activity_id or generated.activity_id
        if not activity_id:
            return None
        activity = self.repository.get_learning_activity(result.user_id, activity_id)
        return activity.conversation_id if activity is not None else None
