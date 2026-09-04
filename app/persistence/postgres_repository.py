import uuid
from contextlib import contextmanager
from dataclasses import asdict, fields
from typing import Any, Iterator

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.config import AppConfig
from app.learner.knowledge_tracing import BayesianKnowledgeTracer
from app.learner.skill_graph import DEFAULT_SKILL_GRAPH
from app.schemas import (
    AnswerDiagnosis,
    ExerciseItem,
    ExerciseOption,
    GeneratedExerciseSet,
    KnowledgeChunk,
    LearnerProfile,
    LearningActivity,
    LearningActivityStatus,
    LearningActivityType,
    PracticePlan,
    PracticeRequest,
    PracticeReview,
    SessionResult,
)


class PostgreSQLLearningRepository:
    """PostgreSQL-backed repository using JSONB documents for P2 runtime.

    The normalized SQLite repository remains useful for local demos and tests.
    This backend gives production deployments a multi-user PostgreSQL storage
    path without forcing a large migration of every SQLite reporting query.
    """

    def __init__(self, config: AppConfig) -> None:
        self.database_url = config.postgres_database_url
        self.knowledge_tracer = BayesianKnowledgeTracer()
        self.skill_graph = DEFAULT_SKILL_GRAPH
        self._init_db()

    def get_profile(self, user_id: str) -> LearnerProfile:
        with self._connect() as connection:
            payload = self._ensure_user(connection, user_id)
            return self._profile_from_payload(user_id, payload)

    def save_profile(self, profile: LearnerProfile) -> None:
        with self._connect() as connection:
            self._upsert_profile(connection, profile)

    def create_learning_activity(self, activity: LearningActivity) -> LearningActivity:
        with self._connect() as connection:
            self._ensure_user(connection, activity.learner_id)
            if not self._chat_session_exists(
                connection,
                activity.learner_id,
                activity.conversation_id,
            ):
                raise LookupError("Chat session not found.")
            activity.activity_id = activity.activity_id or f"pg-activity-{uuid.uuid4().hex[:12]}"
            activity.created_at = activity.created_at or self._now_text(connection)
            activity.updated_at = self._now_text(connection)
            connection.execute(
                """
                INSERT INTO tutor_learning_activities (
                    activity_id,
                    user_code,
                    conversation_id,
                    status,
                    generation_run_id,
                    session_code,
                    activity_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    activity.activity_id,
                    activity.learner_id,
                    activity.conversation_id,
                    self._activity_status_value(activity.status),
                    activity.generation_run_id,
                    activity.session_code,
                    Jsonb(asdict(activity)),
                ),
            )
            self._record_activity_event(
                connection,
                activity.activity_id,
                "CREATED",
                activity.status,
            )
            self._sync_active_activity(
                connection,
                activity.conversation_id,
                activity.activity_id,
                activity.status,
            )
            row = self._get_activity_row(connection, activity.learner_id, activity.activity_id)

        return self._activity_from_payload(row["activity_json"])

    def get_learning_activity(
        self,
        user_id: str,
        activity_id: str,
    ) -> LearningActivity | None:
        with self._connect() as connection:
            row = self._get_activity_row(connection, user_id, activity_id)
        if row is None:
            return None
        return self._activity_from_payload(row["activity_json"])

    def update_learning_activity_status(
        self,
        user_id: str,
        activity_id: str,
        status: LearningActivityStatus,
    ) -> LearningActivity:
        with self._connect() as connection:
            row = self._get_activity_row(connection, user_id, activity_id)
            if row is None:
                raise LookupError(f"Learning activity not found: {activity_id}")
            activity = self._activity_from_payload(row["activity_json"])
            now = self._now_text(connection)
            activity.status = status
            activity.updated_at = now
            if status == LearningActivityStatus.IN_PROGRESS and activity.started_at is None:
                activity.started_at = now
            if status == LearningActivityStatus.SUBMITTED and activity.submitted_at is None:
                activity.submitted_at = now
            if self._is_terminal_activity_status(status) and activity.completed_at is None:
                activity.completed_at = now
            self._save_activity_payload(connection, activity)
            self._record_activity_event(
                connection,
                activity.activity_id,
                "STATUS_CHANGED",
                status,
            )
            self._sync_active_activity(
                connection,
                activity.conversation_id,
                activity.activity_id,
                status,
            )

        return activity

    def attach_generated_exercise_set_to_activity(
        self,
        user_id: str,
        activity_id: str,
        generation_run_id: str,
    ) -> LearningActivity:
        with self._connect() as connection:
            activity = self._require_learning_activity(
                connection,
                user_id,
                activity_id,
            )
            generated_row = connection.execute(
                """
                SELECT payload_json
                FROM tutor_generated_runs
                WHERE user_code = %s AND generation_run_id = %s
                """,
                (user_id, generation_run_id),
            ).fetchone()
            if generated_row is None:
                raise LookupError(f"Generation run not found: {generation_run_id}")
            generated = self._generated_from_payload(generated_row["payload_json"])
            generated.activity_id = activity.activity_id
            activity.generation_run_id = generation_run_id
            activity.updated_at = self._now_text(connection)
            connection.execute(
                """
                UPDATE tutor_generated_runs
                SET activity_id = %s, payload_json = %s, updated_at = now()
                WHERE user_code = %s AND generation_run_id = %s
                """,
                (
                    activity.activity_id,
                    Jsonb(asdict(generated)),
                    user_id,
                    generation_run_id,
                ),
            )
            self._save_activity_payload(connection, activity)
            self._record_activity_event(
                connection,
                activity.activity_id,
                "GENERATED_SET_ATTACHED",
                activity.status,
                {"generation_run_id": generation_run_id},
            )

        return activity

    def attach_session_result_to_activity(
        self,
        user_id: str,
        activity_id: str,
        session_code: str,
    ) -> LearningActivity:
        with self._connect() as connection:
            activity = self._require_learning_activity(
                connection,
                user_id,
                activity_id,
            )
            session_row = connection.execute(
                """
                SELECT result_json
                FROM tutor_practice_sessions
                WHERE user_code = %s AND session_code = %s
                """,
                (user_id, session_code),
            ).fetchone()
            if session_row is None:
                raise LookupError(f"Practice session not found: {session_code}")
            result_json = self._dict(session_row["result_json"])
            result_json["activity_id"] = activity.activity_id
            now = self._now_text(connection)
            activity.session_code = session_code
            activity.status = LearningActivityStatus.COMPLETED
            activity.submitted_at = activity.submitted_at or now
            activity.completed_at = activity.completed_at or now
            activity.updated_at = now
            connection.execute(
                """
                UPDATE tutor_practice_sessions
                SET activity_id = %s, result_json = %s, updated_at = now()
                WHERE user_code = %s AND session_code = %s
                """,
                (
                    activity.activity_id,
                    Jsonb(result_json),
                    user_id,
                    session_code,
                ),
            )
            self._save_activity_payload(connection, activity)
            self._record_activity_event(
                connection,
                activity.activity_id,
                "SESSION_RESULT_ATTACHED",
                activity.status,
                {"session_code": session_code},
            )
            self._sync_active_activity(
                connection,
                activity.conversation_id,
                activity.activity_id,
                activity.status,
            )

        return activity

    def get_latest_learning_activity(
        self,
        user_id: str,
        conversation_id: str,
        statuses: list[LearningActivityStatus] | None = None,
    ) -> LearningActivity | None:
        with self._connect() as connection:
            self._ensure_user(connection, user_id)
            if not self._chat_session_exists(connection, user_id, conversation_id):
                raise LookupError("Chat session not found.")
            status_values = [status.value for status in statuses or []]
            if status_values:
                row = connection.execute(
                    """
                    SELECT activity_json
                    FROM tutor_learning_activities
                    WHERE user_code = %s
                        AND conversation_id = %s
                        AND status = ANY(%s)
                    ORDER BY updated_at DESC, created_at DESC
                    LIMIT 1
                    """,
                    (user_id, conversation_id, status_values),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT activity_json
                    FROM tutor_learning_activities
                    WHERE user_code = %s AND conversation_id = %s
                    ORDER BY updated_at DESC, created_at DESC
                    LIMIT 1
                    """,
                    (user_id, conversation_id),
                ).fetchone()
        if row is None:
            return None
        return self._activity_from_payload(row["activity_json"])

    def get_generated_exercise_set(
        self,
        user_id: str,
        generation_run_id: str,
    ) -> GeneratedExerciseSet | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM tutor_generated_runs
                WHERE user_code = %s AND generation_run_id = %s
                """,
                (user_id, generation_run_id),
            ).fetchone()
        if row is None:
            return None
        return self._generated_from_payload(row["payload_json"])

    def save_session_result(
        self,
        result: SessionResult,
        generation_run_id: str | None = None,
        selected_answers: dict[str, str] | None = None,
        answer_diagnoses: list[AnswerDiagnosis] | None = None,
        activity_id: str | None = None,
    ) -> str:
        session_code = result.session_code or f"pg-session-{uuid.uuid4().hex[:12]}"
        result.session_code = session_code
        with self._connect() as connection:
            self._ensure_user(connection, result.user_id)
            activity_id = activity_id or result.activity_id
            activity = None
            if activity_id is None and generation_run_id:
                generation_row = connection.execute(
                    """
                    SELECT activity_id
                    FROM tutor_generated_runs
                    WHERE user_code = %s AND generation_run_id = %s
                    """,
                    (result.user_id, generation_run_id),
                ).fetchone()
                if generation_row is not None:
                    activity_id = generation_row["activity_id"]
            if activity_id:
                activity = self._require_learning_activity(
                    connection,
                    result.user_id,
                    activity_id,
                )
                result.activity_id = activity_id
            if generation_run_id and selected_answers is not None:
                self._update_skill_mastery_from_answers(
                    connection=connection,
                    user_id=result.user_id,
                    generation_run_id=generation_run_id,
                    selected_answers=selected_answers,
                    answer_diagnoses=answer_diagnoses,
                )
            connection.execute(
                """
                INSERT INTO tutor_practice_sessions (
                    session_code,
                    user_code,
                    activity_id,
                    generation_run_id,
                    result_json,
                    selected_answers_json,
                    answer_diagnoses_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_code)
                DO UPDATE SET
                    activity_id = EXCLUDED.activity_id,
                    result_json = EXCLUDED.result_json,
                    selected_answers_json = EXCLUDED.selected_answers_json,
                    answer_diagnoses_json = EXCLUDED.answer_diagnoses_json,
                    updated_at = now()
                """,
                (
                    session_code,
                    result.user_id,
                    activity_id,
                    generation_run_id,
                    Jsonb(asdict(result)),
                    Jsonb(selected_answers or {}),
                    Jsonb([asdict(item) for item in answer_diagnoses or []]),
                ),
            )
            if activity_id:
                now = self._now_text(connection)
                activity.session_code = session_code
                activity.status = LearningActivityStatus.COMPLETED
                activity.submitted_at = activity.submitted_at or now
                activity.completed_at = activity.completed_at or now
                activity.updated_at = now
                self._save_activity_payload(connection, activity)
                self._record_activity_event(
                    connection,
                    activity.activity_id,
                    "SESSION_RESULT_ATTACHED",
                    activity.status,
                    {"session_code": session_code},
                )
                self._sync_active_activity(
                    connection,
                    activity.conversation_id,
                    activity.activity_id,
                    activity.status,
                )
        return session_code

    def get_session_result(
        self,
        user_id: str,
        session_code: str,
    ) -> SessionResult | None:
        with self._connect() as connection:
            self._ensure_user(connection, user_id)
            row = connection.execute(
                """
                SELECT
                    ps.result_json,
                    ps.answer_diagnoses_json,
                    pr.review_json
                FROM tutor_practice_sessions ps
                LEFT JOIN tutor_practice_reviews pr
                    ON pr.session_code = ps.session_code
                    AND pr.user_code = ps.user_code
                WHERE ps.user_code = %s AND ps.session_code = %s
                """,
                (user_id, session_code),
            ).fetchone()
        if row is None:
            return None

        result = self._session_result_from_payload(
            user_id,
            self._dict(row["result_json"]),
        )
        diagnoses_payload = row.get("answer_diagnoses_json")
        if isinstance(diagnoses_payload, list):
            result.answer_diagnoses = [
                self._diagnosis_from_payload(item)
                for item in diagnoses_payload
                if isinstance(item, dict)
            ]
        review_payload = row.get("review_json")
        if isinstance(review_payload, dict):
            result.practice_review = self._practice_review_from_payload(
                review_payload,
            )
        return result

    def save_generated_exercise_set(
        self,
        generated: GeneratedExerciseSet,
        generator_backend: str,
    ) -> str:
        generation_run_id = generated.generation_run_id or f"pg-gen-{uuid.uuid4().hex[:12]}"
        generated.generation_run_id = generation_run_id
        with self._connect() as connection:
            self._ensure_user(connection, generated.request.user_id)
            activity = None
            if generated.activity_id:
                activity = self._require_learning_activity(
                    connection,
                    generated.request.user_id,
                    generated.activity_id,
                )
            connection.execute(
                """
                INSERT INTO tutor_generated_runs (
                    generation_run_id,
                    user_code,
                    activity_id,
                    generator_backend,
                    payload_json
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (generation_run_id)
                DO UPDATE SET
                    activity_id = EXCLUDED.activity_id,
                    generator_backend = EXCLUDED.generator_backend,
                    payload_json = EXCLUDED.payload_json,
                    updated_at = now()
                """,
                (
                    generation_run_id,
                    generated.request.user_id,
                    generated.activity_id,
                    generator_backend,
                    Jsonb(asdict(generated)),
                ),
            )
            if generated.activity_id:
                activity.generation_run_id = generation_run_id
                activity.updated_at = self._now_text(connection)
                self._save_activity_payload(connection, activity)
                self._record_activity_event(
                    connection,
                    activity.activity_id,
                    "GENERATED_SET_ATTACHED",
                    activity.status,
                    {"generation_run_id": generation_run_id},
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
                    "label": self._label(topic),
                    "topic": topic,
                    "attempts_count": 0,
                    "correct_count": 0,
                    "accuracy": accuracy,
                    "weakness_score": profile.weak_topics.get(topic, 1.0 - accuracy),
                    "status": "postgres_jsonb",
                    "last_practiced_at": None,
                }
                for topic, accuracy in profile.topic_accuracy.items()
            ],
            "subtopic_stats": [
                {
                    "code": stat_key,
                    "label": self._label(stat_key.split(":", maxsplit=1)[-1]),
                    "topic": stat_key.split(":", maxsplit=1)[0],
                    "attempts_count": 0,
                    "correct_count": 0,
                    "accuracy": profile.subtopic_accuracy.get(stat_key, 0.0),
                    "mastery_score": 1.0 - weakness,
                    "weakness_score": weakness,
                    "status": "postgres_jsonb",
                    "last_practiced_at": None,
                }
                for stat_key, weakness in profile.weak_subtopics.items()
            ],
            "error_stats": [
                {
                    "code": stat_key,
                    "label": self._label(stat_key.split(":", maxsplit=1)[-1]),
                    "topic": stat_key.split(":", maxsplit=1)[0],
                    "attempts_count": 0,
                    "incorrect_count": 0,
                    "error_rate": weakness,
                    "weakness_score": weakness,
                    "status": "postgres_jsonb",
                    "last_seen_at": None,
                }
                for stat_key, weakness in profile.error_tag_weakness.items()
            ],
            "skill_mastery": [
                self._skill_mastery_row(profile, skill_id, mastery)
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
        with self._connect() as connection:
            self._ensure_user(connection, user_id)
            active_session_id = (
                session_id
                if session_id
                else self._get_or_create_chat_session(connection, user_id)
            )
            if session_id and not self._chat_session_exists(
                connection,
                user_id,
                session_id,
            ):
                raise LookupError("Chat session not found.")
            memory = self._get_chat_memory(connection, user_id)
            messages = connection.execute(
                """
                SELECT
                    message_id,
                    role,
                    content,
                    metadata_json,
                    created_at::text AS created_at
                FROM tutor_chat_messages
                WHERE session_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (active_session_id, limit),
            ).fetchall()
        ordered_messages = [
            {
                "message_id": row["message_id"],
                "role": row["role"],
                "content": row["content"],
                "metadata": self._dict(row.get("metadata_json")),
                "created_at": row["created_at"],
            }
            for row in reversed(messages)
        ]
        return {
            "session_id": active_session_id,
            "has_history": bool(ordered_messages or memory),
            "memory_summary": self._build_memory_summary(memory),
            "extracted_facts": memory,
            "suggested_next_question": self._suggest_next_question(memory),
            "messages": ordered_messages,
        }

    def list_chat_sessions(self, user_id: str, limit: int = 20) -> dict[str, Any]:
        with self._connect() as connection:
            self._ensure_user(connection, user_id)
            rows = connection.execute(
                """
                SELECT
                    s.session_id,
                    s.title,
                    s.created_at::text AS created_at,
                    s.updated_at::text AS updated_at,
                    COUNT(m.id)::int AS message_count,
                    (
                        SELECT lm.content
                        FROM tutor_chat_messages lm
                        WHERE lm.session_id = s.session_id
                        ORDER BY lm.created_at DESC, lm.id DESC
                        LIMIT 1
                    ) AS preview
                FROM tutor_chat_sessions s
                LEFT JOIN tutor_chat_messages m ON m.session_id = s.session_id
                WHERE s.user_code = %s
                GROUP BY s.session_id, s.title, s.created_at, s.updated_at
                ORDER BY s.updated_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            ).fetchall()

        return {
            "sessions": [self._chat_session_summary_from_row(row) for row in rows],
        }

    def create_chat_session(self, user_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            self._ensure_user(connection, user_id)
            session_id = self._create_chat_session(connection, user_id)
            memory = self._get_chat_memory(connection, user_id)

        return {
            "session_id": session_id,
            "has_history": bool(memory),
            "memory_summary": self._build_memory_summary(memory),
            "extracted_facts": memory,
            "suggested_next_question": self._suggest_next_question(memory),
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

        message_id = f"pg-msg-{uuid.uuid4().hex[:12]}"
        with self._connect() as connection:
            self._ensure_user(connection, user_id)
            active_session_id = (
                session_id
                if session_id
                else self._get_or_create_chat_session(connection, user_id)
            )
            if session_id and not self._chat_session_exists(
                connection,
                user_id,
                session_id,
            ):
                raise LookupError("Chat session not found.")
            message_row = connection.execute(
                """
                INSERT INTO tutor_chat_messages (
                    session_id,
                    user_code,
                    message_id,
                    role,
                    content,
                    metadata_json
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING created_at::text AS created_at
                """,
                (
                    active_session_id,
                    user_id,
                    message_id,
                    normalized_role,
                    cleaned_content,
                    Jsonb(metadata or {}),
                ),
            ).fetchone()
            connection.execute(
                """
                UPDATE tutor_chat_sessions
                SET
                    title = COALESCE(title, %s),
                    updated_at = now()
                WHERE session_id = %s AND user_code = %s
                """,
                (
                    self._make_chat_title(cleaned_content)
                    if normalized_role == "user"
                    else None,
                    active_session_id,
                    user_id,
                ),
            )
            memory = self._get_chat_memory(connection, user_id)
            if update_memory and normalized_role == "user":
                memory = self._updated_chat_memory(memory, cleaned_content)
                self._save_chat_memory(connection, user_id, memory)
        message = {
            "message_id": message_id,
            "role": normalized_role,
            "content": cleaned_content,
            "metadata": metadata or {},
            "created_at": message_row["created_at"] if message_row else None,
        }
        return {
            "session_id": active_session_id,
            "message": message,
            "memory_summary": self._build_memory_summary(memory),
            "extracted_facts": memory,
            "suggested_next_question": self._suggest_next_question(memory),
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

        with self._connect() as connection:
            self._ensure_user(connection, user_id)
            active_session_id = (
                session_id
                if session_id
                else self._get_or_create_chat_session(connection, user_id)
            )
            if session_id and not self._chat_session_exists(
                connection,
                user_id,
                session_id,
            ):
                raise LookupError("Chat session not found.")
            current_memory = self._get_chat_memory(connection, user_id)
            merged_memory = self._merge_chat_facts(current_memory, cleaned_facts)
            self._save_chat_memory(connection, user_id, merged_memory)
            self._sync_profile_from_chat_facts(
                connection,
                user_id,
                merged_memory,
            )

        return self.get_chat_resume(user_id, session_id=active_session_id)

    def save_practice_review(
        self,
        user_id: str,
        session_code: str,
        review: PracticeReview,
    ) -> str:
        with self._connect() as connection:
            self._ensure_user(connection, user_id)
            connection.execute(
                """
                INSERT INTO tutor_practice_reviews (
                    review_code,
                    session_code,
                    user_code,
                    review_json
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (review_code)
                DO UPDATE SET review_json = EXCLUDED.review_json, updated_at = now()
                """,
                (
                    review.review_code,
                    session_code,
                    user_id,
                    Jsonb(asdict(review)),
                ),
            )
        return review.review_code

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tutor_users (
                    user_code TEXT PRIMARY KEY,
                    profile_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tutor_generated_runs (
                    generation_run_id TEXT PRIMARY KEY,
                    user_code TEXT NOT NULL REFERENCES tutor_users(user_code)
                        ON DELETE CASCADE,
                    activity_id TEXT,
                    generator_backend TEXT NOT NULL,
                    payload_json JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tutor_practice_sessions (
                    session_code TEXT PRIMARY KEY,
                    user_code TEXT NOT NULL REFERENCES tutor_users(user_code)
                        ON DELETE CASCADE,
                    activity_id TEXT,
                    generation_run_id TEXT,
                    result_json JSONB NOT NULL,
                    selected_answers_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                    answer_diagnoses_json JSONB NOT NULL DEFAULT '[]'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tutor_chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_code TEXT NOT NULL REFERENCES tutor_users(user_code)
                        ON DELETE CASCADE,
                    active_activity_id TEXT,
                    title TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            connection.execute(
                """
                ALTER TABLE tutor_chat_sessions
                ADD COLUMN IF NOT EXISTS title TEXT
                """
            )
            connection.execute(
                """
                ALTER TABLE tutor_chat_sessions
                ADD COLUMN IF NOT EXISTS active_activity_id TEXT
                """
            )
            connection.execute(
                """
                ALTER TABLE tutor_generated_runs
                ADD COLUMN IF NOT EXISTS activity_id TEXT
                """
            )
            connection.execute(
                """
                ALTER TABLE tutor_practice_sessions
                ADD COLUMN IF NOT EXISTS activity_id TEXT
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tutor_learning_activities (
                    activity_id TEXT PRIMARY KEY,
                    user_code TEXT NOT NULL REFERENCES tutor_users(user_code)
                        ON DELETE CASCADE,
                    conversation_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    generation_run_id TEXT,
                    session_code TEXT,
                    activity_json JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tutor_learning_activity_events (
                    id BIGSERIAL PRIMARY KEY,
                    activity_id TEXT NOT NULL REFERENCES tutor_learning_activities(activity_id)
                        ON DELETE CASCADE,
                    event_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tutor_chat_messages (
                    id BIGSERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES tutor_chat_sessions(session_id)
                        ON DELETE CASCADE,
                    user_code TEXT NOT NULL REFERENCES tutor_users(user_code)
                        ON DELETE CASCADE,
                    message_id TEXT NOT NULL UNIQUE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tutor_chat_memory (
                    user_code TEXT PRIMARY KEY REFERENCES tutor_users(user_code)
                        ON DELETE CASCADE,
                    facts_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tutor_practice_reviews (
                    review_code TEXT PRIMARY KEY,
                    session_code TEXT NOT NULL,
                    user_code TEXT NOT NULL REFERENCES tutor_users(user_code)
                        ON DELETE CASCADE,
                    review_json JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tutor_generated_runs_user
                ON tutor_generated_runs(user_code)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tutor_sessions_user
                ON tutor_practice_sessions(user_code)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tutor_learning_activities_user_conversation
                ON tutor_learning_activities(user_code, conversation_id, updated_at)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tutor_chat_sessions_user_updated
                ON tutor_chat_sessions(user_code, updated_at)
                """
            )

    @contextmanager
    def _connect(self) -> Iterator[Connection]:
        connection = psycopg.connect(self.database_url, row_factory=dict_row)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _ensure_user(self, connection: Connection, user_id: str) -> dict[str, Any]:
        row = connection.execute(
            "SELECT profile_json FROM tutor_users WHERE user_code = %s",
            (user_id,),
        ).fetchone()
        if row is not None:
            return self._dict(row["profile_json"])

        profile = LearnerProfile(user_id=user_id, display_name=user_id)
        payload = asdict(profile)
        connection.execute(
            """
            INSERT INTO tutor_users (user_code, profile_json)
            VALUES (%s, %s)
            ON CONFLICT (user_code) DO NOTHING
            """,
            (user_id, Jsonb(payload)),
        )
        return payload

    def _upsert_profile(self, connection: Connection, profile: LearnerProfile) -> None:
        connection.execute(
            """
            INSERT INTO tutor_users (user_code, profile_json)
            VALUES (%s, %s)
            ON CONFLICT (user_code)
            DO UPDATE SET profile_json = EXCLUDED.profile_json, updated_at = now()
            """,
            (profile.user_id, Jsonb(asdict(profile))),
        )

    def _get_or_create_chat_session(
        self,
        connection: Connection,
        user_id: str,
    ) -> str:
        row = connection.execute(
            """
            SELECT session_id
            FROM tutor_chat_sessions
            WHERE user_code = %s
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        if row is not None:
            return str(row["session_id"])

        return self._create_chat_session(connection, user_id)

    def _chat_session_exists(
        self,
        connection: Connection,
        user_id: str,
        session_id: str,
    ) -> bool:
        row = connection.execute(
            """
            SELECT 1
            FROM tutor_chat_sessions
            WHERE user_code = %s AND session_id = %s
            """,
            (user_id, session_id),
        ).fetchone()
        return row is not None

    def _create_chat_session(
        self,
        connection: Connection,
        user_id: str,
    ) -> str:
        session_id = f"pg-chat-{uuid.uuid4().hex[:12]}"
        connection.execute(
            """
            INSERT INTO tutor_chat_sessions (session_id, user_code)
            VALUES (%s, %s)
            """,
            (session_id, user_id),
        )
        return session_id

    def _get_activity_row(
        self,
        connection: Connection,
        user_id: str,
        activity_id: str,
    ) -> dict[str, Any] | None:
        return connection.execute(
            """
            SELECT activity_json
            FROM tutor_learning_activities
            WHERE user_code = %s AND activity_id = %s
            """,
            (user_id, activity_id),
        ).fetchone()

    def _require_learning_activity(
        self,
        connection: Connection,
        user_id: str,
        activity_id: str,
    ) -> LearningActivity:
        row = self._get_activity_row(connection, user_id, activity_id)
        if row is None:
            raise LookupError(f"Learning activity not found: {activity_id}")
        return self._activity_from_payload(row["activity_json"])

    def _save_activity_payload(
        self,
        connection: Connection,
        activity: LearningActivity,
    ) -> None:
        connection.execute(
            """
            UPDATE tutor_learning_activities
            SET
                status = %s,
                generation_run_id = %s,
                session_code = %s,
                activity_json = %s,
                updated_at = now()
            WHERE user_code = %s AND activity_id = %s
            """,
            (
                self._activity_status_value(activity.status),
                activity.generation_run_id,
                activity.session_code,
                Jsonb(asdict(activity)),
                activity.learner_id,
                activity.activity_id,
            ),
        )

    def _record_activity_event(
        self,
        connection: Connection,
        activity_id: str,
        event_type: str,
        status: LearningActivityStatus,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO tutor_learning_activity_events (
                activity_id,
                event_type,
                status,
                metadata_json
            )
            VALUES (%s, %s, %s, %s)
            """,
            (
                activity_id,
                event_type,
                self._activity_status_value(status),
                Jsonb(metadata or {}),
            ),
        )

    def _sync_active_activity(
        self,
        connection: Connection,
        conversation_id: str,
        activity_id: str,
        status: LearningActivityStatus,
    ) -> None:
        if self._is_terminal_activity_status(status):
            connection.execute(
                """
                UPDATE tutor_chat_sessions
                SET active_activity_id = NULL, updated_at = now()
                WHERE session_id = %s AND active_activity_id = %s
                """,
                (conversation_id, activity_id),
            )
            return
        connection.execute(
            """
            UPDATE tutor_chat_sessions
            SET active_activity_id = %s, updated_at = now()
            WHERE session_id = %s
            """,
            (activity_id, conversation_id),
        )

    def _activity_from_payload(self, payload: dict[str, Any]) -> LearningActivity:
        safe_payload = self._dataclass_payload(LearningActivity, payload)
        safe_payload["type"] = self._activity_type_from_value(safe_payload.get("type"))
        safe_payload["status"] = self._status_from_value(safe_payload.get("status"))
        return LearningActivity(**safe_payload)

    def _session_result_from_payload(
        self,
        user_id: str,
        payload: dict[str, Any],
    ) -> SessionResult:
        safe_payload = self._dataclass_payload(SessionResult, payload)
        safe_payload["user_id"] = user_id
        safe_payload["answer_diagnoses"] = [
            self._diagnosis_from_payload(item)
            for item in payload.get("answer_diagnoses", [])
            if isinstance(item, dict)
        ]
        review_payload = payload.get("practice_review")
        safe_payload["practice_review"] = (
            self._practice_review_from_payload(review_payload)
            if isinstance(review_payload, dict)
            else None
        )
        return SessionResult(**safe_payload)

    def _diagnosis_from_payload(self, payload: dict[str, Any]) -> AnswerDiagnosis:
        return AnswerDiagnosis(**self._dataclass_payload(AnswerDiagnosis, payload))

    def _practice_review_from_payload(self, payload: dict[str, Any]) -> PracticeReview:
        return PracticeReview(**self._dataclass_payload(PracticeReview, payload))

    def _activity_status_value(self, status: LearningActivityStatus | str) -> str:
        if isinstance(status, LearningActivityStatus):
            return status.value
        return str(status)

    def _activity_type_from_value(self, value: object) -> LearningActivityType:
        try:
            return LearningActivityType(str(value))
        except ValueError:
            return LearningActivityType.PRACTICE

    def _status_from_value(self, value: object) -> LearningActivityStatus:
        try:
            return LearningActivityStatus(str(value))
        except ValueError:
            return LearningActivityStatus.CREATED

    def _is_terminal_activity_status(self, status: LearningActivityStatus) -> bool:
        return status in {
            LearningActivityStatus.COMPLETED,
            LearningActivityStatus.FAILED,
            LearningActivityStatus.CANCELLED,
        }

    def _now_text(self, connection: Connection) -> str:
        row = connection.execute("SELECT now()::text AS now_text").fetchone()
        return str(row["now_text"])

    def _chat_session_summary_from_row(self, row: dict[str, Any]) -> dict[str, Any]:
        title = str(row.get("title") or self._make_chat_title(row.get("preview") or ""))
        return {
            "session_id": row["session_id"],
            "title": title or "Phien chat moi",
            "preview": row.get("preview") or "",
            "message_count": int(row.get("message_count") or 0),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    def _make_chat_title(self, content: str) -> str:
        normalized = " ".join(content.split())
        if len(normalized) <= 64:
            return normalized
        return f"{normalized[:61]}..."

    def _get_chat_memory(
        self,
        connection: Connection,
        user_id: str,
    ) -> dict[str, Any]:
        row = connection.execute(
            "SELECT facts_json FROM tutor_chat_memory WHERE user_code = %s",
            (user_id,),
        ).fetchone()
        if row is None:
            return {}
        return self._dict(row["facts_json"])

    def _save_chat_memory(
        self,
        connection: Connection,
        user_id: str,
        facts: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO tutor_chat_memory (user_code, facts_json)
            VALUES (%s, %s)
            ON CONFLICT (user_code)
            DO UPDATE SET facts_json = EXCLUDED.facts_json, updated_at = now()
            """,
            (user_id, Jsonb(facts)),
        )

    def _updated_chat_memory(
        self,
        facts: dict[str, Any],
        content: str,
    ) -> dict[str, Any]:
        updated = dict(facts)
        updated["last_user_request"] = content
        if any(keyword in content.lower() for keyword in ["anime", "manga", "otaku"]):
            updated["preferred_content_theme"] = "anime"
            content_themes = updated.get("content_themes", [])
            themes = content_themes if isinstance(content_themes, list) else []
            if "anime" not in themes:
                updated["content_themes"] = [*themes, "anime"]
        return updated

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
        connection: Connection,
        user_id: str,
        facts: dict[str, Any],
    ) -> None:
        profile = self._profile_from_payload(
            user_id,
            self._ensure_user(connection, user_id),
        )
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
            self._upsert_profile(connection, profile)

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
        *,
        connection: Connection,
        user_id: str,
        generation_run_id: str,
        selected_answers: dict[str, str],
        answer_diagnoses: list[AnswerDiagnosis] | None,
    ) -> None:
        row = connection.execute(
            """
            SELECT payload_json
            FROM tutor_generated_runs
            WHERE user_code = %s AND generation_run_id = %s
            """,
            (user_id, generation_run_id),
        ).fetchone()
        if row is None:
            return

        generated = self._generated_from_payload(row["payload_json"])
        profile = self._profile_from_payload(
            user_id,
            self._ensure_user(connection, user_id),
        )
        diagnosis_by_exercise = {
            diagnosis.exercise_id: diagnosis for diagnosis in answer_diagnoses or []
        }

        for exercise in generated.exercises:
            diagnosis = diagnosis_by_exercise.get(exercise.exercise_id)
            is_correct = (
                diagnosis.is_correct
                if diagnosis is not None
                else self._answers_match(
                    selected_answers.get(exercise.exercise_id),
                    exercise.correct_answer,
                )
            )
            skill_id = self.skill_graph.skill_id_for(
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

        self._upsert_profile(connection, profile)

    def _profile_from_payload(
        self,
        user_id: str,
        payload: dict[str, Any],
    ) -> LearnerProfile:
        safe_payload = self._dataclass_payload(LearnerProfile, payload)
        safe_payload["user_id"] = user_id
        return LearnerProfile(**safe_payload)

    def _generated_from_payload(self, payload: dict[str, Any]) -> GeneratedExerciseSet:
        return GeneratedExerciseSet(
            request=PracticeRequest(**payload["request"]),
            plan=PracticePlan(**payload["plan"]),
            retrieved_chunks=[
                KnowledgeChunk(**chunk)
                for chunk in payload.get("retrieved_chunks", [])
            ],
            exercises=[
                self._exercise_from_payload(exercise)
                for exercise in payload.get("exercises", [])
            ],
            activity_id=payload.get("activity_id"),
            generation_run_id=str(payload.get("generation_run_id", "")),
            prompt_snapshot=str(payload.get("prompt_snapshot", "")),
            agent_trace=list(payload.get("agent_trace", [])),
        )

    def _exercise_from_payload(self, payload: dict[str, Any]) -> ExerciseItem:
        exercise_payload = dict(payload)
        exercise_payload["options"] = [
            ExerciseOption(**option)
            for option in exercise_payload.get("options", [])
        ]
        return ExerciseItem(**self._dataclass_payload(ExerciseItem, exercise_payload))

    def _skill_mastery_row(
        self,
        profile: LearnerProfile,
        skill_id: str,
        mastery: float,
    ) -> dict[str, Any]:
        node = self.skill_graph.get(skill_id)
        attempts = profile.skill_attempts.get(skill_id, 0)
        return {
            "code": skill_id,
            "label": node.label,
            "topic": node.topic,
            "skill_type": node.skill_type,
            "cefr": node.cefr,
            "mastery_probability": mastery,
            "confidence": profile.skill_confidence.get(skill_id, 0.0),
            "attempts_count": attempts,
            "correct_count": 0,
            "incorrect_count": 0,
            "weakness_score": 1.0 - mastery,
            "status": self._status_from_mastery(mastery),
            "last_practiced_at": None,
            "next_review_at": None,
            "prerequisites": list(node.prerequisites),
        }

    def _answers_match(self, selected_answer: str | None, correct_answer: str) -> bool:
        return str(selected_answer or "").strip().lower() == str(correct_answer).strip().lower()

    def _build_memory_summary(self, facts: dict[str, Any]) -> str:
        if not facts:
            return ""
        return "; ".join(f"{key}={value}" for key, value in facts.items())

    def _suggest_next_question(self, facts: dict[str, Any]) -> str:
        if facts.get("last_user_request"):
            return "Minh da tai lai doan chat gan day. Ban muon tiep tuc tu noi dung cu khong?"
        return "Ban muon luyen chu de nao hom nay?"

    def _status_from_mastery(self, mastery: float) -> str:
        if mastery < 0.4:
            return "weak"
        if mastery < 0.65:
            return "learning"
        if mastery < 0.85:
            return "review"
        return "mastered"

    def _label(self, value: str) -> str:
        return value.replace("_", " ").replace(".", " ").title()

    def _dict(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _dataclass_payload(self, dataclass_type: type, payload: dict[str, Any]) -> dict[str, Any]:
        allowed = {field.name for field in fields(dataclass_type)}
        return {
            key: value
            for key, value in payload.items()
            if key in allowed
        }
