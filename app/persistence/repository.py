from dataclasses import dataclass, field
from typing import Protocol

from app.schemas import LearnerProfile, SessionResult


class LearningRepository(Protocol):
    def get_profile(self, user_id: str) -> LearnerProfile:
        ...

    def save_profile(self, profile: LearnerProfile) -> None:
        ...

    def save_session_result(self, result: SessionResult) -> None:
        ...


@dataclass
class InMemoryLearningRepository:
    profiles: dict[str, LearnerProfile] = field(default_factory=dict)
    session_results: list[SessionResult] = field(default_factory=list)

    def get_profile(self, user_id: str) -> LearnerProfile:
        return self.profiles.setdefault(user_id, LearnerProfile(user_id=user_id))

    def save_profile(self, profile: LearnerProfile) -> None:
        self.profiles[profile.user_id] = profile

    def save_session_result(self, result: SessionResult) -> None:
        self.session_results.append(result)
