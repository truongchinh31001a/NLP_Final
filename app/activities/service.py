import uuid
from typing import Any

from app.persistence.repository import LearningRepository
from app.schemas import (
    LearningActivity,
    LearningActivityStatus,
    LearningActivityType,
)


class ActivityService:
    """Canonical lifecycle facade for learning activities."""

    def __init__(self, repository: LearningRepository) -> None:
        self.repository = repository

    def create_activity(
        self,
        *,
        user_id: str,
        conversation_id: str | None = None,
        activity_type: LearningActivityType = LearningActivityType.PRACTICE,
        parent_activity_id: str | None = None,
        target_skills: list[str] | None = None,
        difficulty: str | None = None,
        config: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LearningActivity:
        resolved_conversation_id = self._ensure_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
        )
        return self.repository.create_learning_activity(
            LearningActivity(
                activity_id=f"activity_{uuid.uuid4().hex}",
                conversation_id=resolved_conversation_id,
                learner_id=user_id,
                type=activity_type,
                parent_activity_id=parent_activity_id,
                target_skills=target_skills or [],
                difficulty=difficulty,
                config=config or {},
                metadata=metadata or {},
            )
        )

    def get_activity(self, *, user_id: str, activity_id: str) -> LearningActivity:
        activity = self.repository.get_learning_activity(user_id, activity_id)
        if activity is None:
            raise LookupError(f"Learning activity not found: {activity_id}")
        return activity

    def start_generation(
        self,
        *,
        user_id: str,
        activity_id: str,
    ) -> LearningActivity:
        return self._transition(
            user_id=user_id,
            activity_id=activity_id,
            status=LearningActivityStatus.GENERATING,
        )

    def mark_ready(
        self,
        *,
        user_id: str,
        activity_id: str,
        generation_run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LearningActivity:
        activity = self._merge_metadata(
            user_id=user_id,
            activity_id=activity_id,
            metadata=metadata,
        )
        if generation_run_id and activity.generation_run_id != generation_run_id:
            activity = self.repository.attach_generated_exercise_set_to_activity(
                user_id,
                activity_id,
                generation_run_id,
            )
        if activity.status == LearningActivityStatus.READY:
            return activity
        return self._transition(
            user_id=user_id,
            activity_id=activity_id,
            status=LearningActivityStatus.READY,
        )

    def start_activity(
        self,
        *,
        user_id: str,
        activity_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> LearningActivity:
        self._merge_metadata(
            user_id=user_id,
            activity_id=activity_id,
            metadata=metadata,
        )
        return self._transition(
            user_id=user_id,
            activity_id=activity_id,
            status=LearningActivityStatus.IN_PROGRESS,
        )

    def submit_activity(
        self,
        *,
        user_id: str,
        activity_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> LearningActivity:
        self._merge_metadata(
            user_id=user_id,
            activity_id=activity_id,
            metadata=metadata,
        )
        return self._transition(
            user_id=user_id,
            activity_id=activity_id,
            status=LearningActivityStatus.SUBMITTED,
        )

    def grade_activity(
        self,
        *,
        user_id: str,
        activity_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> LearningActivity:
        self._merge_metadata(
            user_id=user_id,
            activity_id=activity_id,
            metadata=metadata,
        )
        return self._transition(
            user_id=user_id,
            activity_id=activity_id,
            status=LearningActivityStatus.GRADED,
        )

    def complete_activity(
        self,
        *,
        user_id: str,
        activity_id: str,
        session_code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LearningActivity:
        self._merge_metadata(
            user_id=user_id,
            activity_id=activity_id,
            metadata=metadata,
        )
        if session_code:
            activity = self.get_activity(user_id=user_id, activity_id=activity_id)
            if activity.session_code == session_code:
                return activity
            return self.repository.attach_session_result_to_activity(
                user_id,
                activity_id,
                session_code,
            )
        return self._transition(
            user_id=user_id,
            activity_id=activity_id,
            status=LearningActivityStatus.COMPLETED,
        )

    def fail_activity(
        self,
        *,
        user_id: str,
        activity_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> LearningActivity:
        self._merge_metadata(
            user_id=user_id,
            activity_id=activity_id,
            metadata=metadata,
        )
        return self._transition(
            user_id=user_id,
            activity_id=activity_id,
            status=LearningActivityStatus.FAILED,
        )

    def _transition(
        self,
        *,
        user_id: str,
        activity_id: str,
        status: LearningActivityStatus,
    ) -> LearningActivity:
        activity = self.get_activity(user_id=user_id, activity_id=activity_id)
        if activity.status == status:
            return activity
        return self.repository.update_learning_activity_status(
            user_id,
            activity_id,
            status,
        )

    def _merge_metadata(
        self,
        *,
        user_id: str,
        activity_id: str,
        metadata: dict[str, Any] | None,
    ) -> LearningActivity:
        if metadata:
            return self.repository.update_learning_activity_metadata(
                user_id,
                activity_id,
                metadata,
            )
        return self.get_activity(user_id=user_id, activity_id=activity_id)

    def _ensure_conversation(
        self,
        *,
        user_id: str,
        conversation_id: str | None,
    ) -> str:
        resume = self.repository.get_chat_resume(
            user_id,
            session_id=conversation_id,
        )
        return str(resume["session_id"])
