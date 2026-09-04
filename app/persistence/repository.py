from dataclasses import dataclass, field
from typing import Any, Protocol

from app.learner.knowledge_tracing import BayesianKnowledgeTracer
from app.learner.skill_graph import DEFAULT_SKILL_GRAPH
from app.schemas import (
    AnswerDiagnosis,
    GeneratedExerciseSet,
    LearnerProfile,
    PracticeReview,
    SessionResult,
)


class LearningRepository(Protocol):
    def get_profile(self, user_id: str) -> LearnerProfile:
        ...

    def save_profile(self, profile: LearnerProfile) -> None:
        ...

    def get_generated_exercise_set(
        self,
        user_id: str,
        generation_run_id: str,
    ) -> GeneratedExerciseSet | None:
        ...

    def save_session_result(
        self,
        result: SessionResult,
        generation_run_id: str | None = None,
        selected_answers: dict[str, str] | None = None,
        answer_diagnoses: list[AnswerDiagnosis] | None = None,
    ) -> str:
        ...

    def save_generated_exercise_set(
        self,
        generated: GeneratedExerciseSet,
        generator_backend: str,
    ) -> str:
        ...

    def get_personalization_snapshot(self, user_id: str) -> dict[str, Any]:
        ...

    def get_chat_resume(self, user_id: str, limit: int = 24) -> dict[str, Any]:
        ...

    def save_chat_message(
        self,
        user_id: str,
        role: str,
        content: str,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        update_memory: bool = True,
    ) -> dict[str, Any]:
        ...

    def save_practice_review(
        self,
        user_id: str,
        session_code: str,
        review: PracticeReview,
    ) -> str:
        ...


@dataclass
class InMemoryLearningRepository:
    profiles: dict[str, LearnerProfile] = field(default_factory=dict)
    session_results: list[SessionResult] = field(default_factory=list)
    generated_sets: dict[str, GeneratedExerciseSet] = field(default_factory=dict)
    chat_session_ids: dict[str, str] = field(default_factory=dict)
    chat_messages: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    chat_memory: dict[str, dict[str, Any]] = field(default_factory=dict)
    practice_reviews: dict[str, PracticeReview] = field(default_factory=dict)
    knowledge_tracer: BayesianKnowledgeTracer = field(
        default_factory=BayesianKnowledgeTracer
    )

    def get_profile(self, user_id: str) -> LearnerProfile:
        return self.profiles.setdefault(user_id, LearnerProfile(user_id=user_id))

    def save_profile(self, profile: LearnerProfile) -> None:
        self.profiles[profile.user_id] = profile

    def get_generated_exercise_set(
        self,
        user_id: str,
        generation_run_id: str,
    ) -> GeneratedExerciseSet | None:
        generated = self.generated_sets.get(generation_run_id)
        if generated is None or generated.request.user_id != user_id:
            return None
        return generated

    def save_session_result(
        self,
        result: SessionResult,
        generation_run_id: str | None = None,
        selected_answers: dict[str, str] | None = None,
        answer_diagnoses: list[AnswerDiagnosis] | None = None,
    ) -> str:
        _ = answer_diagnoses
        self.session_results.append(result)
        if generation_run_id and selected_answers is not None:
            self._update_skill_mastery_from_answers(
                result.user_id,
                generation_run_id,
                selected_answers,
            )
        return f"inmemory-session-{len(self.session_results)}"

    def save_generated_exercise_set(
        self,
        generated: GeneratedExerciseSet,
        generator_backend: str,
    ) -> str:
        generation_run_id = f"inmemory-{len(self.generated_sets) + 1}"
        generated.generation_run_id = generation_run_id
        self.generated_sets[generation_run_id] = generated
        return generation_run_id

    def get_personalization_snapshot(self, user_id: str) -> dict[str, Any]:
        profile = self.get_profile(user_id)
        return {
            "user_id": user_id,
            "display_name": profile.display_name or user_id,
            "level": profile.level,
            "goals": profile.goals,
            "preferred_difficulty": profile.preferred_difficulty,
            "preferred_num_questions": profile.preferred_num_questions,
            "onboarding_completed": profile.onboarding_completed,
            "topic_stats": [
                {
                    "code": topic,
                    "label": topic.replace("_", " ").title(),
                    "topic": topic,
                    "attempts_count": 0,
                    "correct_count": 0,
                    "accuracy": accuracy,
                    "weakness_score": profile.weak_topics.get(topic, 1.0 - accuracy),
                    "status": "in_memory",
                    "last_practiced_at": None,
                }
                for topic, accuracy in profile.topic_accuracy.items()
            ],
            "subtopic_stats": [
                {
                    "code": stat_key,
                    "label": stat_key.split(":", maxsplit=1)[-1].replace("_", " ").title(),
                    "topic": stat_key.split(":", maxsplit=1)[0],
                    "attempts_count": 0,
                    "correct_count": 0,
                    "accuracy": profile.subtopic_accuracy.get(stat_key, 0.0),
                    "mastery_score": 1.0 - weakness,
                    "weakness_score": weakness,
                    "status": "in_memory",
                    "last_practiced_at": None,
                }
                for stat_key, weakness in profile.weak_subtopics.items()
            ],
            "error_stats": [
                {
                    "code": stat_key,
                    "label": stat_key.split(":", maxsplit=1)[-1].replace("_", " ").title(),
                    "topic": stat_key.split(":", maxsplit=1)[0],
                    "attempts_count": 0,
                    "incorrect_count": 0,
                    "error_rate": weakness,
                    "weakness_score": weakness,
                    "status": "in_memory",
                    "last_seen_at": None,
                }
                for stat_key, weakness in profile.error_tag_weakness.items()
            ],
            "skill_mastery": [
                {
                    "code": skill_id,
                    "label": DEFAULT_SKILL_GRAPH.get(skill_id).label,
                    "topic": DEFAULT_SKILL_GRAPH.get(skill_id).topic,
                    "skill_type": DEFAULT_SKILL_GRAPH.get(skill_id).skill_type,
                    "cefr": DEFAULT_SKILL_GRAPH.get(skill_id).cefr,
                    "mastery_probability": mastery,
                    "confidence": profile.skill_confidence.get(skill_id, 0.0),
                    "attempts_count": profile.skill_attempts.get(skill_id, 0),
                    "correct_count": 0,
                    "incorrect_count": 0,
                    "weakness_score": 1.0 - mastery,
                    "status": self._status_from_mastery(mastery),
                    "last_practiced_at": None,
                    "next_review_at": None,
                    "prerequisites": list(
                        DEFAULT_SKILL_GRAPH.get(skill_id).prerequisites
                    ),
                }
                for skill_id, mastery in sorted(
                    profile.skill_mastery.items(),
                    key=lambda item: item[1],
                )
            ],
        }

    def get_chat_resume(self, user_id: str, limit: int = 24) -> dict[str, Any]:
        session_id = self.chat_session_ids.setdefault(
            user_id,
            f"inmemory-chat-{user_id}",
        )
        messages = self.chat_messages.get(session_id, [])[-limit:]
        facts = self.chat_memory.get(user_id, {})
        return {
            "session_id": session_id,
            "has_history": bool(messages or facts),
            "memory_summary": self._build_memory_summary(facts),
            "extracted_facts": facts,
            "suggested_next_question": self._suggest_next_question(facts),
            "messages": messages,
        }

    def save_chat_message(
        self,
        user_id: str,
        role: str,
        content: str,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        update_memory: bool = True,
    ) -> dict[str, Any]:
        active_session_id = session_id or self.chat_session_ids.setdefault(
            user_id,
            f"inmemory-chat-{user_id}",
        )
        self.chat_session_ids[user_id] = active_session_id
        message = {
            "message_id": f"inmemory-msg-{len(self.chat_messages.get(active_session_id, [])) + 1}",
            "role": "assistant" if role == "bot" else role,
            "content": content,
            "created_at": None,
        }
        self.chat_messages.setdefault(active_session_id, []).append(message)

        facts = self.chat_memory.setdefault(user_id, {})
        if update_memory and message["role"] == "user":
            facts["last_user_request"] = content
            content_theme = self._extract_content_theme(content)
            if content_theme:
                facts["preferred_content_theme"] = content_theme
                content_themes = facts.get("content_themes", [])
                existing = content_themes if isinstance(content_themes, list) else []
                if content_theme not in existing:
                    facts["content_themes"] = [*existing, content_theme]
        return {
            "session_id": active_session_id,
            "message": message,
            "memory_summary": self._build_memory_summary(facts),
            "extracted_facts": facts,
            "suggested_next_question": self._suggest_next_question(facts),
        }

    def save_practice_review(
        self,
        user_id: str,
        session_code: str,
        review: PracticeReview,
    ) -> str:
        self.practice_reviews[session_code] = review
        return review.review_code

    def _build_memory_summary(self, facts: dict[str, Any]) -> str:
        if not facts:
            return ""
        return "; ".join(f"{key}={value}" for key, value in facts.items())

    def _suggest_next_question(self, facts: dict[str, Any]) -> str:
        if facts.get("last_user_request"):
            return "Minh da tai lai doan chat gan day. Ban muon tiep tuc tu noi dung cu khong?"
        return "Ban muon luyen chu de nao hom nay?"

    def _extract_content_theme(self, content: str) -> str | None:
        normalized = content.lower()
        if any(keyword in normalized for keyword in ["anime", "manga", "otaku"]):
            return "anime"
        return None

    def _update_skill_mastery_from_answers(
        self,
        user_id: str,
        generation_run_id: str,
        selected_answers: dict[str, str],
    ) -> None:
        generated = self.generated_sets.get(generation_run_id)
        if generated is None:
            return

        profile = self.get_profile(user_id)
        for exercise in generated.exercises:
            selected_answer = selected_answers.get(exercise.exercise_id)
            is_correct = str(selected_answer or "").strip().lower() == str(
                exercise.correct_answer
            ).strip().lower()
            skill_id = DEFAULT_SKILL_GRAPH.skill_id_for(
                topic=exercise.topic,
                skill_type=exercise.skill,
                subtopic=exercise.subtopic,
            )
            prior = profile.skill_mastery.get(skill_id)
            posterior = self.knowledge_tracer.update(prior, is_correct)
            attempts = profile.skill_attempts.get(skill_id, 0) + 1
            profile.skill_mastery[skill_id] = posterior
            profile.skill_attempts[skill_id] = attempts
            profile.skill_confidence[skill_id] = min(attempts / 8, 1.0)
        self.save_profile(profile)

    def _status_from_mastery(self, mastery: float) -> str:
        if mastery < 0.4:
            return "weak"
        if mastery < 0.65:
            return "learning"
        if mastery < 0.85:
            return "review"
        return "mastered"
