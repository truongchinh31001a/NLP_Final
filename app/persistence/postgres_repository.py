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
    ) -> str:
        session_code = result.session_code or f"pg-session-{uuid.uuid4().hex[:12]}"
        result.session_code = session_code
        with self._connect() as connection:
            self._ensure_user(connection, result.user_id)
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
                    generation_run_id,
                    result_json,
                    selected_answers_json,
                    answer_diagnoses_json
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_code)
                DO UPDATE SET
                    result_json = EXCLUDED.result_json,
                    selected_answers_json = EXCLUDED.selected_answers_json,
                    answer_diagnoses_json = EXCLUDED.answer_diagnoses_json,
                    updated_at = now()
                """,
                (
                    session_code,
                    result.user_id,
                    generation_run_id,
                    Jsonb(asdict(result)),
                    Jsonb(selected_answers or {}),
                    Jsonb([asdict(item) for item in answer_diagnoses or []]),
                ),
            )
        return session_code

    def save_generated_exercise_set(
        self,
        generated: GeneratedExerciseSet,
        generator_backend: str,
    ) -> str:
        generation_run_id = generated.generation_run_id or f"pg-gen-{uuid.uuid4().hex[:12]}"
        generated.generation_run_id = generation_run_id
        with self._connect() as connection:
            self._ensure_user(connection, generated.request.user_id)
            connection.execute(
                """
                INSERT INTO tutor_generated_runs (
                    generation_run_id,
                    user_code,
                    generator_backend,
                    payload_json
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (generation_run_id)
                DO UPDATE SET
                    generator_backend = EXCLUDED.generator_backend,
                    payload_json = EXCLUDED.payload_json,
                    updated_at = now()
                """,
                (
                    generation_run_id,
                    generated.request.user_id,
                    generator_backend,
                    Jsonb(asdict(generated)),
                ),
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

    def get_chat_resume(self, user_id: str, limit: int = 24) -> dict[str, Any]:
        with self._connect() as connection:
            self._ensure_user(connection, user_id)
            session_id = self._get_or_create_chat_session(connection, user_id)
            memory = self._get_chat_memory(connection, user_id)
            messages = connection.execute(
                """
                SELECT message_id, role, content, created_at::text AS created_at
                FROM tutor_chat_messages
                WHERE session_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (session_id, limit),
            ).fetchall()
        ordered_messages = list(reversed(messages))
        return {
            "session_id": session_id,
            "has_history": bool(ordered_messages or memory),
            "memory_summary": self._build_memory_summary(memory),
            "extracted_facts": memory,
            "suggested_next_question": self._suggest_next_question(memory),
            "messages": ordered_messages,
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
        normalized_role = "assistant" if role == "bot" else role
        message_id = f"pg-msg-{uuid.uuid4().hex[:12]}"
        with self._connect() as connection:
            self._ensure_user(connection, user_id)
            active_session_id = session_id or self._get_or_create_chat_session(
                connection,
                user_id,
            )
            connection.execute(
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
                """,
                (
                    active_session_id,
                    user_id,
                    message_id,
                    normalized_role,
                    content,
                    Jsonb(metadata or {}),
                ),
            )
            memory = self._get_chat_memory(connection, user_id)
            if update_memory and normalized_role == "user":
                memory = self._updated_chat_memory(memory, content)
                self._save_chat_memory(connection, user_id, memory)
        message = {
            "message_id": message_id,
            "role": normalized_role,
            "content": content,
            "created_at": None,
        }
        return {
            "session_id": active_session_id,
            "message": message,
            "memory_summary": self._build_memory_summary(memory),
            "extracted_facts": memory,
            "suggested_next_question": self._suggest_next_question(memory),
        }

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
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
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

        session_id = f"pg-chat-{uuid.uuid4().hex[:12]}"
        connection.execute(
            """
            INSERT INTO tutor_chat_sessions (session_id, user_code)
            VALUES (%s, %s)
            """,
            (session_id, user_id),
        )
        return session_id

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
