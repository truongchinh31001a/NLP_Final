from app.personalization.service import PersonalizationService
from app.schemas import LearnerProfile, PracticePlan, PracticeRequest


class PracticePlanner:
    """Practice-facing wrapper around personalization planning."""

    def __init__(self, personalization: PersonalizationService) -> None:
        self.personalization = personalization

    def build_plan(
        self,
        request: PracticeRequest,
        profile: LearnerProfile,
    ) -> PracticePlan:
        return self.personalization.build_plan(request, profile)


__all__ = ["PracticePlanner"]
