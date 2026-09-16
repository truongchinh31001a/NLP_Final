from app.activities.practice_service import (
    PracticeActivityGeneration,
    PracticeActivityService,
    PracticeActivitySubmission,
)
from app.schemas import SubmittedAnswer


class PracticeService(PracticeActivityService):
    """Canonical practice facade kept compatible with the legacy pipeline."""

    def generate(self, **kwargs) -> PracticeActivityGeneration:
        return self.create_practice_activity(**kwargs)

    def submit(
        self,
        *,
        user_id: str,
        activity_id: str,
        answers: list[SubmittedAnswer],
    ) -> PracticeActivitySubmission:
        return self.submit_practice_activity(
            user_id=user_id,
            activity_id=activity_id,
            answers=answers,
        )


__all__ = [
    "PracticeActivityGeneration",
    "PracticeActivityService",
    "PracticeActivitySubmission",
    "PracticeService",
]
