import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from app.learner.knowledge_tracing import BayesianKnowledgeTracer
from app.learner.skill_graph import DEFAULT_SKILL_GRAPH
from app.schemas import (
    AnswerDiagnosis,
    GeneratedExerciseSet,
    LearnerProfile,
    LearningActivity,
    LearningActivityStatus,
    PracticeReview,
    SessionResult,
)


class LearningRepository(Protocol):
    def get_profile(self, user_id: str) -> LearnerProfile:
        ...

    def save_profile(self, profile: LearnerProfile) -> None:
        ...

    def create_learning_activity(self, activity: LearningActivity) -> LearningActivity:
        ...

    def get_learning_activity(
        self,
        user_id: str,
        activity_id: str,
    ) -> LearningActivity | None:
        ...

    def update_learning_activity_status(
        self,
        user_id: str,
        activity_id: str,
        status: LearningActivityStatus,
    ) -> LearningActivity:
        ...

    def attach_generated_exercise_set_to_activity(
        self,
        user_id: str,
        activity_id: str,
        generation_run_id: str,
    ) -> LearningActivity:
        ...

    def attach_session_result_to_activity(
        self,
        user_id: str,
        activity_id: str,
        session_code: str,
    ) -> LearningActivity:
        ...

    def get_latest_learning_activity(
        self,
        user_id: str,
        conversation_id: str,
        statuses: list[LearningActivityStatus] | None = None,
    ) -> LearningActivity | None:
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
        activity_id: str | None = None,
    ) -> str:
        ...

    def get_session_result(
        self,
        user_id: str,
        session_code: str,
    ) -> SessionResult | None:
        ...

    def save_generated_exercise_set(
        self,
        generated: GeneratedExerciseSet,
        generator_backend: str,
    ) -> str:
        ...

    def get_personalization_snapshot(self, user_id: str) -> dict[str, Any]:
        ...

    def get_chat_resume(
        self,
        user_id: str,
        limit: int = 24,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        ...

    def list_chat_sessions(self, user_id: str, limit: int = 20) -> dict[str, Any]:
        ...

    def create_chat_session(self, user_id: str) -> dict[str, Any]:
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

    def merge_chat_memory_facts(
        self,
        user_id: str,
        facts: dict[str, Any],
        session_id: str | None = None,
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
    chat_session_meta: dict[str, dict[str, Any]] = field(default_factory=dict)
    chat_session_order: dict[str, int] = field(default_factory=dict)
    chat_messages: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    chat_memory: dict[str, dict[str, Any]] = field(default_factory=dict)
    learning_activities: dict[str, LearningActivity] = field(default_factory=dict)
    activity_events: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    active_activity_by_chat_session: dict[str, str] = field(default_factory=dict)
    practice_reviews: dict[str, PracticeReview] = field(default_factory=dict)
    knowledge_tracer: BayesianKnowledgeTracer = field(
        default_factory=BayesianKnowledgeTracer
    )

    def get_profile(self, user_id: str) -> LearnerProfile:
        return self.profiles.setdefault(user_id, LearnerProfile(user_id=user_id))

    def save_profile(self, profile: LearnerProfile) -> None:
        self.profiles[profile.user_id] = profile

    def create_learning_activity(self, activity: LearningActivity) -> LearningActivity:
        self._ensure_activity_conversation_owner(
            activity.learner_id,
            activity.conversation_id,
        )
        now = self._now()
        if not activity.activity_id:
            activity.activity_id = f"inmemory-activity-{uuid.uuid4().hex[:12]}"
        activity.created_at = activity.created_at or now
        activity.updated_at = now
        self.learning_activities[activity.activity_id] = activity
        self._sync_active_activity(activity)
        self._record_activity_event(activity, "CREATED")
        return activity

    def get_learning_activity(
        self,
        user_id: str,
        activity_id: str,
    ) -> LearningActivity | None:
        activity = self.learning_activities.get(activity_id)
        if activity is None or activity.learner_id != user_id:
            return None
        return activity

    def update_learning_activity_status(
        self,
        user_id: str,
        activity_id: str,
        status: LearningActivityStatus,
    ) -> LearningActivity:
        activity = self._require_learning_activity(user_id, activity_id)
        now = self._now()
        activity.status = status
        activity.updated_at = now
        if status == LearningActivityStatus.IN_PROGRESS and activity.started_at is None:
            activity.started_at = now
        if status == LearningActivityStatus.SUBMITTED and activity.submitted_at is None:
            activity.submitted_at = now
        if self._is_terminal_activity_status(status) and activity.completed_at is None:
            activity.completed_at = now
        self._sync_active_activity(activity)
        self._record_activity_event(activity, "STATUS_CHANGED")
        return activity

    def attach_generated_exercise_set_to_activity(
        self,
        user_id: str,
        activity_id: str,
        generation_run_id: str,
    ) -> LearningActivity:
        activity = self._require_learning_activity(user_id, activity_id)
        if generation_run_id not in self.generated_sets:
            raise LookupError(f"Generation run not found: {generation_run_id}")
        generated = self.generated_sets[generation_run_id]
        if generated.request.user_id != user_id:
            raise LookupError(f"Generation run not found: {generation_run_id}")
        activity.generation_run_id = generation_run_id
        activity.updated_at = self._now()
        generated.activity_id = activity.activity_id
        self._record_activity_event(
            activity,
            "GENERATED_SET_ATTACHED",
            {"generation_run_id": generation_run_id},
        )
        return activity

    def attach_session_result_to_activity(
        self,
        user_id: str,
        activity_id: str,
        session_code: str,
    ) -> LearningActivity:
        activity = self._require_learning_activity(user_id, activity_id)
        session_result = next(
            (
                result
                for result in self.session_results
                if result.session_code == session_code and result.user_id == user_id
            ),
            None,
        )
        if session_result is None:
            raise LookupError(f"Practice session not found: {session_code}")
        now = self._now()
        activity.session_code = session_code
        activity.status = LearningActivityStatus.COMPLETED
        activity.submitted_at = activity.submitted_at or now
        activity.completed_at = activity.completed_at or now
        activity.updated_at = now
        session_result.activity_id = activity.activity_id
        self._sync_active_activity(activity)
        self._record_activity_event(
            activity,
            "SESSION_RESULT_ATTACHED",
            {"session_code": session_code},
        )
        return activity

    def get_latest_learning_activity(
        self,
        user_id: str,
        conversation_id: str,
        statuses: list[LearningActivityStatus] | None = None,
    ) -> LearningActivity | None:
        self._ensure_activity_conversation_owner(user_id, conversation_id)
        status_values = {status.value for status in statuses or []}
        activities = [
            activity
            for activity in self.learning_activities.values()
            if activity.learner_id == user_id
            and activity.conversation_id == conversation_id
            and (not status_values or activity.status.value in status_values)
        ]
        activities.sort(
            key=lambda activity: activity.updated_at or activity.created_at or "",
            reverse=True,
        )
        return activities[0] if activities else None

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
        activity_id: str | None = None,
    ) -> str:
        _ = answer_diagnoses
        activity_id = (
            activity_id
            or result.activity_id
            or self._activity_id_for_generation_run(generation_run_id)
        )
        if activity_id:
            result.activity_id = activity_id
        result.session_code = result.session_code or f"inmemory-session-{len(self.session_results) + 1}"
        self.session_results.append(result)
        if generation_run_id and selected_answers is not None:
            self._update_skill_mastery_from_answers(
                result.user_id,
                generation_run_id,
                selected_answers,
            )
        if activity_id:
            self.attach_session_result_to_activity(
                result.user_id,
                activity_id,
                result.session_code,
            )
        return result.session_code

    def get_session_result(
        self,
        user_id: str,
        session_code: str,
    ) -> SessionResult | None:
        for result in self.session_results:
            if result.user_id == user_id and result.session_code == session_code:
                return result
        return None

    def save_generated_exercise_set(
        self,
        generated: GeneratedExerciseSet,
        generator_backend: str,
    ) -> str:
        generation_run_id = f"inmemory-{len(self.generated_sets) + 1}"
        generated.generation_run_id = generation_run_id
        self.generated_sets[generation_run_id] = generated
        if generated.activity_id:
            self.attach_generated_exercise_set_to_activity(
                generated.request.user_id,
                generated.activity_id,
                generation_run_id,
            )
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

    def get_chat_resume(
        self,
        user_id: str,
        limit: int = 24,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        if session_id:
            meta = self.chat_session_meta.get(session_id)
            if meta is None or meta.get("user_id") != user_id:
                raise LookupError("Chat session not found.")
            active_session_id = session_id
        else:
            active_session_id = self._get_or_create_chat_session(user_id)
        messages = self.chat_messages.get(active_session_id, [])[-limit:]
        facts = self.chat_memory.get(user_id, {})
        return {
            "session_id": active_session_id,
            "has_history": bool(messages or facts),
            "memory_summary": self._build_memory_summary(facts),
            "extracted_facts": facts,
            "suggested_next_question": self._suggest_next_question(facts),
            "messages": messages,
        }

    def list_chat_sessions(self, user_id: str, limit: int = 20) -> dict[str, Any]:
        session_ids = [
            session_id
            for session_id, meta in self.chat_session_meta.items()
            if meta.get("user_id") == user_id
        ]
        latest_session_id = self.chat_session_ids.get(user_id)
        if latest_session_id:
            self._ensure_chat_session_meta(user_id, latest_session_id)
            if latest_session_id not in session_ids:
                session_ids.append(latest_session_id)

        sessions = [
            self._chat_session_summary(session_id)
            for session_id in session_ids
        ]
        sessions.sort(
            key=lambda item: (
                item["updated_at"] or "",
                self.chat_session_order.get(str(item["session_id"]), 0),
            ),
            reverse=True,
        )
        return {"sessions": sessions[:limit]}

    def create_chat_session(self, user_id: str) -> dict[str, Any]:
        session_id = f"inmemory-chat-{uuid.uuid4().hex[:12]}"
        self._ensure_chat_session_meta(user_id, session_id)
        self.chat_session_ids[user_id] = session_id
        facts = self.chat_memory.get(user_id, {})
        return {
            "session_id": session_id,
            "has_history": bool(facts),
            "memory_summary": self._build_memory_summary(facts),
            "extracted_facts": facts,
            "suggested_next_question": self._suggest_next_question(facts),
            "messages": [],
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
        normalized_role = "assistant" if role == "bot" else role.strip().lower()
        if normalized_role not in {"user", "assistant"}:
            raise ValueError("Chat message role must be `user` or `assistant`.")

        cleaned_content = content.strip()
        if not cleaned_content:
            raise ValueError("Chat message content cannot be empty.")

        active_session_id = session_id or self._get_or_create_chat_session(user_id)
        meta = self.chat_session_meta.get(active_session_id)
        if meta is not None and meta.get("user_id") != user_id:
            raise LookupError("Chat session not found.")
        self._ensure_chat_session_meta(user_id, active_session_id)
        self.chat_session_ids[user_id] = active_session_id
        created_at = self._now()
        message = {
            "message_id": f"inmemory-msg-{len(self.chat_messages.get(active_session_id, [])) + 1}",
            "role": normalized_role,
            "content": cleaned_content,
            "metadata": metadata or {},
            "created_at": created_at,
        }
        self.chat_messages.setdefault(active_session_id, []).append(message)
        session_meta = self.chat_session_meta[active_session_id]
        if normalized_role == "user" and not session_meta.get("title"):
            session_meta["title"] = self._make_chat_title(cleaned_content)
        session_meta["updated_at"] = created_at

        facts = self.chat_memory.setdefault(user_id, {})
        if update_memory and message["role"] == "user":
            facts["last_user_request"] = cleaned_content
            content_theme = self._extract_content_theme(cleaned_content)
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

    def merge_chat_memory_facts(
        self,
        user_id: str,
        facts: dict[str, Any],
        session_id: str | None = None,
    ) -> dict[str, Any]:
        cleaned_facts = {
            key: value
            for key, value in facts.items()
            if value not in (None, "", [])
        }
        if not cleaned_facts:
            return self.get_chat_resume(user_id, session_id=session_id)

        if session_id is not None:
            meta = self.chat_session_meta.get(session_id)
            if meta is None or meta.get("user_id") != user_id:
                raise LookupError("Chat session not found.")

        current_facts = self.chat_memory.setdefault(user_id, {})
        merged_facts = self._merge_chat_facts(current_facts, cleaned_facts)
        self.chat_memory[user_id] = merged_facts
        self._sync_profile_from_chat_facts(user_id, merged_facts)
        return self.get_chat_resume(user_id, session_id=session_id)

    def save_practice_review(
        self,
        user_id: str,
        session_code: str,
        review: PracticeReview,
    ) -> str:
        self.practice_reviews[session_code] = review
        return review.review_code

    def _require_learning_activity(
        self,
        user_id: str,
        activity_id: str,
    ) -> LearningActivity:
        activity = self.get_learning_activity(user_id, activity_id)
        if activity is None:
            raise LookupError(f"Learning activity not found: {activity_id}")
        return activity

    def _ensure_activity_conversation_owner(
        self,
        user_id: str,
        conversation_id: str,
    ) -> None:
        meta = self.chat_session_meta.get(conversation_id)
        if meta is None or meta.get("user_id") != user_id:
            raise LookupError("Chat session not found.")

    def _sync_active_activity(self, activity: LearningActivity) -> None:
        if self._is_terminal_activity_status(activity.status):
            if (
                self.active_activity_by_chat_session.get(activity.conversation_id)
                == activity.activity_id
            ):
                self.active_activity_by_chat_session.pop(activity.conversation_id, None)
            return
        self.active_activity_by_chat_session[activity.conversation_id] = (
            activity.activity_id
        )

    def _record_activity_event(
        self,
        activity: LearningActivity,
        event_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.activity_events.setdefault(activity.activity_id, []).append(
            {
                "event_type": event_type,
                "status": activity.status.value,
                "created_at": self._now(),
                "metadata": metadata or {},
            }
        )

    def _activity_id_for_generation_run(
        self,
        generation_run_id: str | None,
    ) -> str | None:
        if not generation_run_id:
            return None
        generated = self.generated_sets.get(generation_run_id)
        return generated.activity_id if generated is not None else None

    def _is_terminal_activity_status(self, status: LearningActivityStatus) -> bool:
        return status in {
            LearningActivityStatus.COMPLETED,
            LearningActivityStatus.FAILED,
            LearningActivityStatus.CANCELLED,
        }

    def _get_or_create_chat_session(self, user_id: str) -> str:
        session_id = self.chat_session_ids.get(user_id)
        if session_id:
            self._ensure_chat_session_meta(user_id, session_id)
            return session_id
        return str(self.create_chat_session(user_id)["session_id"])

    def _ensure_chat_session_meta(self, user_id: str, session_id: str) -> None:
        now = self._now()
        self.chat_session_meta.setdefault(
            session_id,
            {
                "user_id": user_id,
                "title": "",
                "created_at": now,
                "updated_at": now,
            },
        )
        self.chat_session_order.setdefault(session_id, len(self.chat_session_order) + 1)

    def _chat_session_summary(self, session_id: str) -> dict[str, Any]:
        meta = self.chat_session_meta[session_id]
        messages = self.chat_messages.get(session_id, [])
        last_message = next(
            (message for message in reversed(messages) if message.get("content")),
            None,
        )
        title = str(meta.get("title") or "")
        if not title:
            first_user_message = next(
                (
                    message
                    for message in messages
                    if message.get("role") == "user" and message.get("content")
                ),
                None,
            )
            title = self._make_chat_title(
                str((first_user_message or last_message or {}).get("content") or "")
            )
        return {
            "session_id": session_id,
            "title": title or "Phien chat moi",
            "preview": str((last_message or {}).get("content") or ""),
            "message_count": len(messages),
            "created_at": str(meta.get("created_at") or ""),
            "updated_at": str(meta.get("updated_at") or ""),
        }

    def _make_chat_title(self, content: str) -> str:
        normalized = " ".join(content.split())
        if len(normalized) <= 64:
            return normalized
        return f"{normalized[:61]}..."

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

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

    def _merge_chat_facts(
        self,
        current_facts: dict[str, Any],
        extracted_facts: dict[str, Any],
    ) -> dict[str, Any]:
        merged = dict(current_facts)
        list_keys = {"content_themes", "goals", "weak_topics", "recent_topics"}
        for key, value in extracted_facts.items():
            if value in (None, "", []):
                continue
            if key in list_keys:
                existing = merged.get(key, [])
                existing_values = existing if isinstance(existing, list) else []
                incoming_values = value if isinstance(value, list) else [value]
                merged[key] = self._merge_unique_strings(
                    existing_values,
                    incoming_values,
                )
                continue
            merged[key] = value
        return merged

    def _sync_profile_from_chat_facts(
        self,
        user_id: str,
        facts: dict[str, Any],
    ) -> None:
        profile = self.get_profile(user_id)
        changed = False

        display_name = facts.get("display_name")
        if isinstance(display_name, str) and display_name.strip():
            profile.display_name = display_name.strip()
            changed = True

        level = facts.get("level")
        if isinstance(level, str) and level in {"beginner", "intermediate", "advanced"}:
            profile.level = level
            changed = True

        preferred_difficulty = facts.get("preferred_difficulty")
        if isinstance(preferred_difficulty, str) and preferred_difficulty in {
            "easy",
            "medium",
            "hard",
        }:
            profile.preferred_difficulty = preferred_difficulty
            changed = True

        preferred_num_questions = facts.get("preferred_num_questions")
        if isinstance(preferred_num_questions, int):
            profile.preferred_num_questions = preferred_num_questions
            changed = True

        goals = self._merge_unique_strings(
            profile.goals,
            self._as_string_list(facts.get("goals")),
        )
        if goals != profile.goals:
            profile.goals = goals
            changed = True

        for topic in self._as_string_list(facts.get("weak_topics")):
            profile.topic_accuracy.setdefault(topic, 0.25)
            profile.weak_topics[topic] = max(profile.weak_topics.get(topic, 0.0), 0.75)
            changed = True

        if changed:
            self.save_profile(profile)

    def _merge_unique_strings(
        self,
        existing_values: list[Any],
        incoming_values: list[Any],
    ) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for value in [*existing_values, *incoming_values]:
            normalized = str(value).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
        return merged

    def _as_string_list(self, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, tuple):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()] if str(value).strip() else []

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
