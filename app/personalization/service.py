from app.config import AppConfig
from app.schemas import LearnerProfile, PracticePlan, PracticeRequest, SessionResult


class PersonalizationService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def build_plan(self, request: PracticeRequest, profile: LearnerProfile) -> PracticePlan:
        topic = request.topic or self._pick_default_topic(profile)
        target_subtopic = request.target_subtopic or self._pick_weak_detail(
            profile.weak_subtopics,
            topic,
        )
        target_error_tag = self._pick_weak_detail(profile.error_tag_weakness, topic)
        difficulty = (
            request.difficulty
            or profile.preferred_difficulty
            or self._adaptive_difficulty(profile, topic)
            or self._difficulty_from_level(profile.level)
        )
        exercise_type = request.exercise_type or self._default_exercise_type(topic)
        num_questions = (
            request.num_questions
            or profile.preferred_num_questions
            or self.config.default_num_questions
        )

        learner_summary = self._build_learner_summary(
            profile=profile,
            topic=topic,
            target_subtopic=target_subtopic,
            target_error_tag=target_error_tag,
            content_theme=request.content_theme,
        )
        focus_reason = self._focus_reason(
            request,
            profile,
            topic,
            difficulty,
            target_subtopic,
            target_error_tag,
        )
        return PracticePlan(
            user_id=request.user_id,
            topic=topic,
            difficulty=difficulty,
            exercise_type=exercise_type,
            num_questions=num_questions,
            focus_reason=focus_reason,
            target_subtopic=target_subtopic,
            target_error_tag=target_error_tag,
            content_theme=request.content_theme,
            learner_summary=learner_summary,
        )

    def update_profile(self, profile: LearnerProfile, result: SessionResult) -> LearnerProfile:
        topic_accuracy = result.correct_count / max(result.total_questions, 1)
        profile.topic_accuracy[result.topic] = topic_accuracy
        profile.weak_topics[result.topic] = 1.0 - topic_accuracy
        return profile

    def _pick_default_topic(self, profile: LearnerProfile) -> str:
        if profile.weak_subtopics:
            weak_subtopic_key = max(profile.weak_subtopics, key=profile.weak_subtopics.get)
            return self._topic_from_stat_key(weak_subtopic_key)
        if profile.error_tag_weakness:
            weak_error_key = max(
                profile.error_tag_weakness,
                key=profile.error_tag_weakness.get,
            )
            return self._topic_from_stat_key(weak_error_key)
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
        target_subtopic: str | None,
        target_error_tag: str | None,
    ) -> str:
        if request.topic and request.difficulty:
            return "Followed the learner's explicit topic and difficulty request."
        if request.topic and request.content_theme and request.target_subtopic:
            return (
                f"Followed the learner's explicit `{topic}` request, focusing on "
                f"`{request.target_subtopic}` with `{request.content_theme}`-themed contexts."
            )
        if request.topic and request.content_theme:
            return (
                f"Followed the learner's explicit `{topic}` request with "
                f"`{request.content_theme}`-themed contexts."
            )
        if request.topic and request.target_subtopic:
            return (
                f"Followed the learner's explicit `{topic}` request, focusing on "
                f"`{request.target_subtopic}`."
            )
        if request.topic:
            return (
                f"Followed the learner's explicit `{topic}` request and used "
                f"`{difficulty}` difficulty from profile/adaptation."
            )
        if target_subtopic and target_error_tag:
            return (
                f"Targeted weak subtopic `{target_subtopic}` and frequent error "
                f"`{target_error_tag}` at `{difficulty}` difficulty."
            )
        if target_subtopic:
            return f"Focused on weak subtopic `{target_subtopic}` at `{difficulty}` difficulty."
        if target_error_tag:
            return f"Focused on frequent error `{target_error_tag}` at `{difficulty}` difficulty."
        if topic in profile.weak_topics:
            return f"Focused on weak topic `{topic}` with `{difficulty}` difficulty."
        return f"Used profile level `{profile.level}` to build a default practice plan."

    def _pick_weak_detail(
        self,
        stats: dict[str, float],
        topic: str,
    ) -> str | None:
        matching_stats = {
            key: value
            for key, value in stats.items()
            if self._topic_from_stat_key(key) == topic
            and self._detail_is_compatible(
                topic,
                self._detail_from_stat_key(key),
            )
        }
        if not matching_stats:
            return None
        stat_key = max(matching_stats, key=matching_stats.get)
        return self._detail_from_stat_key(stat_key)

    def _adaptive_difficulty(
        self,
        profile: LearnerProfile,
        topic: str,
    ) -> str | None:
        accuracy = profile.topic_accuracy.get(topic)
        if accuracy is None:
            return None
        if accuracy < 0.6:
            return "easy"
        if accuracy < 0.85:
            return "medium"
        return "hard"

    def _build_learner_summary(
        self,
        profile: LearnerProfile,
        topic: str,
        target_subtopic: str | None,
        target_error_tag: str | None,
        content_theme: str | None,
    ) -> str:
        topic_accuracy = profile.topic_accuracy.get(topic)
        parts = [f"learner_level={profile.level}", f"topic={topic}"]
        if content_theme:
            parts.append(f"preferred_content_theme={content_theme}")
        if topic_accuracy is not None:
            parts.append(f"topic_accuracy={topic_accuracy:.2f}")
        if target_subtopic:
            subtopic_key = self._stat_key(topic, target_subtopic)
            weakness = profile.weak_subtopics.get(subtopic_key)
            if weakness is not None:
                parts.append(f"weak_subtopic={target_subtopic}:{weakness:.2f}")
        if target_error_tag:
            error_key = self._stat_key(topic, target_error_tag)
            weakness = profile.error_tag_weakness.get(error_key)
            if weakness is not None:
                parts.append(f"frequent_error={target_error_tag}:{weakness:.2f}")
        if profile.goals:
            parts.append(f"goals={', '.join(profile.goals)}")
        if profile.preferred_num_questions:
            parts.append(f"preferred_num_questions={profile.preferred_num_questions}")
        return "; ".join(parts)

    def _stat_key(self, topic: str, detail: str) -> str:
        return f"{topic}:{detail}"

    def _topic_from_stat_key(self, stat_key: str) -> str:
        return stat_key.split(":", maxsplit=1)[0]

    def _detail_from_stat_key(self, stat_key: str) -> str:
        if ":" not in stat_key:
            return stat_key
        return stat_key.split(":", maxsplit=1)[1]

    def _detail_is_compatible(self, topic: str, detail: str) -> bool:
        normalized = detail.strip().lower()
        if not normalized or normalized in {"auto", "general", "none"}:
            return False
        if "vocabulary" in topic:
            return any(
                marker in normalized
                for marker in [
                    "vocabulary",
                    "word",
                    "meaning",
                    "context",
                    "daily",
                    "basic",
                    "travel",
                    "airport",
                    "hotel",
                    "transport",
                    "learning",
                    "adjective",
                    "antonym",
                ]
            )
        return "vocabulary" not in normalized
