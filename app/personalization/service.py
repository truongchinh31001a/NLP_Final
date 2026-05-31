from app.config import AppConfig
from app.schemas import LearnerProfile, PracticePlan, PracticeRequest, SessionResult


class PersonalizationService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def build_plan(self, request: PracticeRequest, profile: LearnerProfile) -> PracticePlan:
        topic = request.topic or self._pick_default_topic(profile)
        difficulty = (
            request.difficulty
            or profile.preferred_difficulty
            or self._difficulty_from_level(profile.level)
        )
        exercise_type = request.exercise_type or self._default_exercise_type(topic)
        num_questions = request.num_questions or self.config.default_num_questions

        focus_reason = self._focus_reason(request, profile, topic, difficulty)
        return PracticePlan(
            user_id=request.user_id,
            topic=topic,
            difficulty=difficulty,
            exercise_type=exercise_type,
            num_questions=num_questions,
            focus_reason=focus_reason,
        )

    def update_profile(self, profile: LearnerProfile, result: SessionResult) -> LearnerProfile:
        topic_accuracy = result.correct_count / max(result.total_questions, 1)
        profile.topic_accuracy[result.topic] = topic_accuracy
        profile.weak_topics[result.topic] = 1.0 - topic_accuracy
        return profile

    def _pick_default_topic(self, profile: LearnerProfile) -> str:
        if profile.weak_topics:
            return max(profile.weak_topics, key=profile.weak_topics.get)
        return "grammar"

    def _difficulty_from_level(self, level: str) -> str:
        mapping = {
            "beginner": "easy",
            "intermediate": "medium",
            "advanced": "hard",
        }
        return mapping.get(level, self.config.default_difficulty)

    def _default_exercise_type(self, topic: str) -> str:
        if "vocabulary" in topic:
            return "vocabulary_mcq"
        return "grammar_mcq"

    def _focus_reason(
        self,
        request: PracticeRequest,
        profile: LearnerProfile,
        topic: str,
        difficulty: str,
    ) -> str:
        if request.topic and request.difficulty:
            return "Followed the learner's explicit request."
        if topic in profile.weak_topics:
            return f"Focused on weak topic `{topic}` with `{difficulty}` difficulty."
        return f"Used profile level `{profile.level}` to build a default practice plan."
