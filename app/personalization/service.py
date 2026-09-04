from typing import Any

from app.config import AppConfig
from app.conversation.schemas import ConversationRoute
from app.learner.skill_graph import DEFAULT_SKILL_GRAPH, SkillGraph
from app.onboarding.service import OnboardingInterpreter
from app.persistence.repository import LearningRepository
from app.schemas import (
    ConversationTurnContext,
    LearnerProfile,
    PracticePlan,
    PracticeRequest,
    SessionResult,
)
from app.tutor.service import TutorCapabilityResult


class PersonalizationService:
    def __init__(
        self,
        config: AppConfig,
        skill_graph: SkillGraph | None = None,
    ) -> None:
        self.config = config
        self.skill_graph = skill_graph or DEFAULT_SKILL_GRAPH

    def build_plan(self, request: PracticeRequest, profile: LearnerProfile) -> PracticePlan:
        topic = request.topic or self._pick_default_topic(profile)
        weak_skill = self._pick_weak_skill(profile, topic=topic)
        target_subtopic = request.target_subtopic or self._pick_weak_detail(
            profile.weak_subtopics,
            topic,
        ) or (
            self.skill_graph.subtopic_from_skill_id(weak_skill.skill_id)
            if weak_skill is not None
            else None
        )
        target_error_tag = self._pick_weak_detail(profile.error_tag_weakness, topic)
        target_skill_id = self.skill_graph.skill_id_for(
            topic=topic,
            skill_type=self._skill_for_topic(topic),
            subtopic=target_subtopic,
        )
        difficulty = (
            request.difficulty
            or profile.preferred_difficulty
            or self._adaptive_difficulty_from_skill(profile, target_skill_id)
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
            target_skill_id=target_skill_id,
            content_theme=request.content_theme,
            learner_summary=learner_summary,
        )

    def update_profile(self, profile: LearnerProfile, result: SessionResult) -> LearnerProfile:
        topic_accuracy = result.correct_count / max(result.total_questions, 1)
        previous_accuracy = profile.topic_accuracy.get(result.topic)
        smoothed_accuracy = (
            topic_accuracy
            if previous_accuracy is None
            else (previous_accuracy * 0.7) + (topic_accuracy * 0.3)
        )
        profile.topic_accuracy[result.topic] = smoothed_accuracy
        profile.weak_topics[result.topic] = 1.0 - smoothed_accuracy
        return profile

    def _pick_default_topic(self, profile: LearnerProfile) -> str:
        weak_skill = self._pick_weak_skill(profile)
        if weak_skill is not None:
            return weak_skill.topic
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

    def _adaptive_difficulty_from_skill(
        self,
        profile: LearnerProfile,
        target_skill_id: str | None,
    ) -> str | None:
        if not target_skill_id:
            return None
        mastery = profile.skill_mastery.get(target_skill_id)
        if mastery is None:
            return None
        if mastery < 0.45:
            return "easy"
        if mastery < 0.75:
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
        target_skill_id = self.skill_graph.skill_id_for(
            topic=topic,
            skill_type=self._skill_for_topic(topic),
            subtopic=target_subtopic,
        )
        if target_skill_id:
            mastery = profile.skill_mastery.get(target_skill_id)
            if mastery is not None:
                readiness = self.skill_graph.prerequisite_readiness(
                    target_skill_id,
                    profile.skill_mastery,
                )
                parts.append(f"target_skill={target_skill_id}")
                parts.append(f"skill_mastery={mastery:.2f}")
                parts.append(f"prerequisite_readiness={readiness:.2f}")
        if profile.goals:
            parts.append(f"goals={', '.join(profile.goals)}")
        if profile.preferred_num_questions:
            parts.append(f"preferred_num_questions={profile.preferred_num_questions}")
        return "; ".join(parts)

    def _pick_weak_skill(
        self,
        profile: LearnerProfile,
        topic: str | None = None,
    ):
        if not profile.skill_mastery:
            return None
        return self.skill_graph.weakest_ready_skill(
            profile.skill_mastery,
            topic=topic,
        )

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

    def _skill_for_topic(self, topic: str) -> str:
        if "vocabulary" in topic:
            return "vocabulary"
        return "grammar"


class ProgressiveProfileService:
    """Extracts learner facts from normal chat without gating the conversation."""

    def __init__(
        self,
        repository: LearningRepository,
        onboarding: OnboardingInterpreter,
    ) -> None:
        self.repository = repository
        self.onboarding = onboarding

    def enrich(
        self,
        *,
        user_id: str,
        message: str,
        conversation_id: str,
    ) -> dict[str, Any]:
        extracted_facts = self.onboarding.extract_progressive_profile_facts(message)
        extracted_facts["last_user_request"] = message[:500]
        if not extracted_facts:
            return {}

        self.repository.merge_chat_memory_facts(
            user_id,
            extracted_facts,
            session_id=conversation_id,
        )
        return extracted_facts


class ProgressService:
    """Conversation capability for reading learner progress and weak areas."""

    def __init__(self, repository: LearningRepository) -> None:
        self.repository = repository

    def summarize(
        self,
        *,
        user_id: str,
        route: ConversationRoute,
        context: ConversationTurnContext,
    ) -> TutorCapabilityResult:
        snapshot = self.repository.get_personalization_snapshot(user_id)
        metric = str(route.slots.get("metric") or "weak_areas")
        if metric == "lowest_skill":
            reply, metadata = self._lowest_skill_reply(snapshot)
        else:
            reply, metadata = self._weak_areas_reply(snapshot)
        return TutorCapabilityResult(
            assistant_reply=reply,
            ui_action="progress.open",
            metadata={
                "metric": metric,
                "conversation_id": context.conversation_id,
                **metadata,
            },
        )

    def _lowest_skill_reply(
        self,
        snapshot: dict,
    ) -> tuple[str, dict]:
        skills = snapshot.get("skill_mastery")
        if isinstance(skills, list) and skills:
            skill_items = [item for item in skills if isinstance(item, dict)]
            if not skill_items:
                return self._no_skill_data_reply()
            weakest = max(
                skill_items,
                key=lambda item: float(item.get("weakness_score") or 0.0),
            )
            label = str(weakest.get("label") or weakest.get("code") or "ky nang nay")
            mastery = float(weakest.get("mastery_probability") or 0.0)
            reply = (
                f"Ky nang thap nhat hien tai la {label} "
                f"(mastery khoang {mastery:.0%}). Nen luyen lai nhom nay truoc."
            )
            return reply, {"lowest_skill": weakest}

        return self._no_skill_data_reply()

    def _no_skill_data_reply(self) -> tuple[str, dict]:
        return (
            "Minh chua co du lieu mastery theo skill. Hay lam mot bai practice "
            "de minh bat dau do diem manh/yeu cho ban.",
            {"lowest_skill": None},
        )

    def _weak_areas_reply(
        self,
        snapshot: dict,
    ) -> tuple[str, dict]:
        candidates = []
        for key in ("subtopic_stats", "error_stats", "topic_stats"):
            values = snapshot.get(key)
            if isinstance(values, list):
                candidates.extend(
                    item
                    for item in values
                    if isinstance(item, dict)
                    and float(item.get("weakness_score") or 0.0) > 0
                )

        candidates.sort(
            key=lambda item: float(item.get("weakness_score") or 0.0),
            reverse=True,
        )
        if not candidates:
            return (
                "Minh chua thay diem yeu ro rang. Lam them mot bai ngan se giup "
                "minh cap nhat tien do chinh xac hon.",
                {"weak_areas": []},
            )

        top = candidates[:3]
        labels = ", ".join(
            str(item.get("label") or item.get("code") or "unknown")
            for item in top
        )
        reply = (
            f"Hien tai ban nen uu tien: {labels}. "
            "Minh co the tao bai tiep theo bam vao nhom nay."
        )
        return reply, {"weak_areas": top}


class ProfileUpdateService:
    """Applies preference/profile updates extracted from conversation turns."""

    def __init__(
        self,
        config: AppConfig,
        repository: LearningRepository,
    ) -> None:
        self.config = config
        self.repository = repository

    def apply(
        self,
        *,
        user_id: str,
        route: ConversationRoute,
        message: str,
    ) -> TutorCapabilityResult:
        profile = self.repository.get_profile(user_id)
        changes: list[str] = []

        preferred_num_questions = route.slots.get("preferred_num_questions")
        if isinstance(preferred_num_questions, int):
            profile.preferred_num_questions = preferred_num_questions
            changes.append(f"{preferred_num_questions} cau moi bai")

        preferred_difficulty = route.slots.get("preferred_difficulty")
        if isinstance(preferred_difficulty, str):
            profile.preferred_difficulty = preferred_difficulty
            changes.append(f"do kho {preferred_difficulty}")
        elif route.slots.get("difficulty_delta") in {"harder", "easier"}:
            profile.preferred_difficulty = self._shift_difficulty(
                profile,
                str(route.slots["difficulty_delta"]),
            )
            changes.append(f"do kho {profile.preferred_difficulty}")

        for goal in self._extract_goals(route, message):
            if goal not in profile.goals:
                profile.goals.append(goal)
                changes.append(f"muc tieu {goal}")

        for topic in self._extract_weak_topics(route, message):
            profile.topic_accuracy.setdefault(topic, 0.25)
            profile.weak_topics[topic] = max(profile.weak_topics.get(topic, 0.0), 0.75)
            changes.append(f"diem yeu {topic.replace('_', ' ')}")

        if changes:
            self.repository.save_profile(profile)

        change_text = ", ".join(changes) if changes else "thong tin uu tien moi"
        return TutorCapabilityResult(
            assistant_reply=f"Minh da cap nhat ho so hoc: {change_text}.",
            ui_action="profile.update",
            metadata={
                "changes": changes,
                "preferred_difficulty": profile.preferred_difficulty,
                "preferred_num_questions": profile.preferred_num_questions,
                "goals": list(profile.goals),
                "weak_topics": dict(profile.weak_topics),
            },
        )

    def _extract_goals(
        self,
        route: ConversationRoute,
        message: str,
    ) -> list[str]:
        raw_goals = route.slots.get("goals")
        goals: list[str] = []
        if isinstance(raw_goals, list):
            goals.extend(str(item).strip() for item in raw_goals if str(item).strip())

        normalized = message.lower()
        keyword_goals = {
            "ielts": "ielts",
            "toeic": "toeic",
            "giao tiep": "communication",
            "communication": "communication",
            "speaking": "speaking",
            "writing": "writing",
            "du lich": "travel",
            "travel": "travel",
        }
        for marker, goal in keyword_goals.items():
            if marker in normalized and goal not in goals:
                goals.append(goal)
        return goals

    def _extract_weak_topics(
        self,
        route: ConversationRoute,
        message: str,
    ) -> list[str]:
        raw_topics = route.slots.get("weak_topics")
        topics: list[str] = []
        if isinstance(raw_topics, list):
            topics.extend(self._normalize_topic(item) for item in raw_topics)

        normalized = message.lower()
        topic_markers = {
            "passive": "passive_voice",
            "bi dong": "passive_voice",
            "relative": "relative_clause",
            "quan he": "relative_clause",
            "conditional": "conditional_sentence",
            "dieu kien": "conditional_sentence",
            "reported": "reported_speech",
            "gian tiep": "reported_speech",
            "preposition": "prepositions",
            "gioi tu": "prepositions",
            "vocabulary": "vocabulary",
            "tu vung": "vocabulary",
            "tense": "tenses",
            "thi": "tenses",
        }
        weakness_markers = ("yeu", "sai", "kem", "kho", "weak", "bad at")
        if any(marker in normalized for marker in weakness_markers):
            for marker, topic in topic_markers.items():
                if marker in normalized and topic not in topics:
                    topics.append(topic)
        return [topic for topic in topics if topic]

    def _normalize_topic(self, value: object) -> str:
        return str(value).strip().lower().replace(" ", "_").replace("-", "_")

    def _shift_difficulty(self, profile: LearnerProfile, direction: str) -> str:
        levels = ["easy", "medium", "hard"]
        current = profile.preferred_difficulty or self.config.default_difficulty
        index = levels.index(current) if current in levels else 0
        if direction == "harder":
            return levels[min(index + 1, len(levels) - 1)]
        return levels[max(index - 1, 0)]
