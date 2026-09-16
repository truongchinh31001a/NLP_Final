from app.activities.practice_service import PracticeActivityService
from app.agent.learning_agent import LearningAgent
from app.schemas import SessionResult, SubmittedAnswer


class PracticeGrader:
    """Backend grading facade with activity-first and legacy paths."""

    def __init__(
        self,
        *,
        practice_activity_service: PracticeActivityService | None = None,
        agent: LearningAgent | None = None,
    ) -> None:
        self.practice_activity_service = practice_activity_service
        self.agent = agent

    def grade_activity(
        self,
        *,
        user_id: str,
        activity_id: str,
        answers: list[SubmittedAnswer],
    ) -> SessionResult:
        if self.practice_activity_service is None:
            raise RuntimeError("PracticeGrader requires a PracticeActivityService.")
        return self.practice_activity_service.submit_practice_activity(
            user_id=user_id,
            activity_id=activity_id,
            answers=answers,
        ).result

    def grade_generation_run(
        self,
        *,
        user_id: str,
        generation_run_id: str,
        answers: list[SubmittedAnswer],
    ) -> SessionResult:
        if self.agent is None:
            raise RuntimeError("PracticeGrader requires a LearningAgent.")
        return self.agent.score_submission(
            user_id=user_id,
            generation_run_id=generation_run_id,
            answers=answers,
        )


__all__ = ["PracticeGrader"]
