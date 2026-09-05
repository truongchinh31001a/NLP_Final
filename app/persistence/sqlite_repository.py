import json
import re
import sqlite3
import unicodedata
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from app.config import AppConfig
from app.learner.knowledge_tracing import BayesianKnowledgeTracer
from app.learner.skill_graph import DEFAULT_SKILL_GRAPH, SkillNode
from app.learner.spaced_repetition import next_review_at
from app.language.translation import BilingualTextNormalizer
from app.schemas import (
    AnswerDiagnosis,
    ConversationIntent,
    ExerciseItem,
    ExerciseOption,
    GeneratedExerciseSet,
    LearnerProfile,
    LearningActivity,
    LearningActivityStatus,
    LearningActivityType,
    PendingClarification,
    PracticePlan,
    PracticeReview,
    PracticeRequest,
    SessionResult,
)


class SQLiteLearningRepository:
    def __init__(self, config: AppConfig) -> None:
        self.db_path = Path(config.sqlite_db_path)
        self.schema_path = Path(__file__).with_name("schema.sql")
        self.text_normalizer = BilingualTextNormalizer()
        self.skill_graph = DEFAULT_SKILL_GRAPH
        self.knowledge_tracer = BayesianKnowledgeTracer()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get_profile(self, user_id: str) -> LearnerProfile:
        with self._connect() as connection:
            db_user_id = self._ensure_user(connection, user_id)
            row = connection.execute(
                """
                SELECT
                    u.name,
                    p.level,
                    p.goals_json,
                    p.preferred_difficulty,
                    p.preferred_num_questions,
                    p.onboarding_completed
                FROM user_profiles p
                JOIN users u ON u.id = p.user_id
                WHERE p.user_id = ?
                """,
                (db_user_id,),
            ).fetchone()

            if row is None:
                connection.execute(
                    """
                    INSERT INTO user_profiles (user_id, level, goals_json)
                    VALUES (?, ?, ?)
                    """,
                    (db_user_id, "beginner", "[]"),
                )
                row = connection.execute(
                    """
                    SELECT
                        u.name,
                        p.level,
                        p.goals_json,
                        p.preferred_difficulty,
                        p.preferred_num_questions,
                        p.onboarding_completed
                    FROM user_profiles p
                    JOIN users u ON u.id = p.user_id
                    WHERE p.user_id = ?
                    """,
                    (db_user_id,),
                ).fetchone()

            topic_rows = connection.execute(
                """
                SELECT t.topic_code, s.accuracy, s.weakness_score
                FROM user_topic_stats s
                JOIN topics t ON t.id = s.topic_id
                WHERE s.user_id = ?
                """,
                (db_user_id,),
            ).fetchall()
            subtopic_rows = connection.execute(
                """
                SELECT
                    t.topic_code,
                    s.subtopic,
                    s.accuracy,
                    s.weakness_score
                FROM user_subtopic_stats s
                JOIN topics t ON t.id = s.topic_id
                WHERE s.user_id = ?
                """,
                (db_user_id,),
            ).fetchall()
            error_rows = connection.execute(
                """
                SELECT
                    t.topic_code,
                    s.error_tag,
                    s.weakness_score
                FROM user_error_stats s
                JOIN topics t ON t.id = s.topic_id
                WHERE s.user_id = ?
                """,
                (db_user_id,),
            ).fetchall()
            skill_rows = connection.execute(
                """
                SELECT
                    sk.skill_code,
                    m.mastery_probability,
                    m.confidence,
                    m.attempts_count
                FROM user_skill_mastery m
                JOIN skills sk ON sk.id = m.skill_id
                WHERE m.user_id = ?
                """,
                (db_user_id,),
            ).fetchall()

        goals = json.loads(row["goals_json"] or "[]")
        return LearnerProfile(
            user_id=user_id,
            display_name=self._sanitize_display_name(row["name"], user_id),
            level=row["level"],
            goals=goals,
            preferred_difficulty=row["preferred_difficulty"],
            preferred_num_questions=row["preferred_num_questions"],
            onboarding_completed=bool(row["onboarding_completed"]),
            topic_accuracy={
                topic_row["topic_code"]: float(topic_row["accuracy"])
                for topic_row in topic_rows
            },
            weak_topics={
                topic_row["topic_code"]: float(topic_row["weakness_score"])
                for topic_row in topic_rows
            },
            subtopic_accuracy={
                self._stat_key(
                    subtopic_row["topic_code"],
                    subtopic_row["subtopic"],
                ): float(subtopic_row["accuracy"])
                for subtopic_row in subtopic_rows
            },
            weak_subtopics={
                self._stat_key(
                    subtopic_row["topic_code"],
                    subtopic_row["subtopic"],
                ): float(subtopic_row["weakness_score"])
                for subtopic_row in subtopic_rows
            },
            error_tag_weakness={
                self._stat_key(
                    error_row["topic_code"],
                    error_row["error_tag"],
                ): float(error_row["weakness_score"])
                for error_row in error_rows
            },
            skill_mastery={
                skill_row["skill_code"]: float(skill_row["mastery_probability"])
                for skill_row in skill_rows
            },
            skill_confidence={
                skill_row["skill_code"]: float(skill_row["confidence"])
                for skill_row in skill_rows
            },
            skill_attempts={
                skill_row["skill_code"]: int(skill_row["attempts_count"])
                for skill_row in skill_rows
            },
        )

    def get_personalization_snapshot(self, user_id: str) -> dict[str, object]:
        profile = self.get_profile(user_id)
        with self._connect() as connection:
            db_user_id = self._ensure_user(connection, user_id)
            topic_rows = connection.execute(
                """
                SELECT
                    t.topic_code,
                    s.attempts_count,
                    s.correct_count,
                    s.accuracy,
                    s.weakness_score,
                    s.status,
                    s.last_practiced_at
                FROM user_topic_stats s
                JOIN topics t ON t.id = s.topic_id
                WHERE s.user_id = ?
                ORDER BY s.weakness_score DESC, s.last_practiced_at DESC
                """,
                (db_user_id,),
            ).fetchall()
            subtopic_rows = connection.execute(
                """
                SELECT
                    t.topic_code,
                    s.subtopic,
                    s.attempts_count,
                    s.correct_count,
                    s.accuracy,
                    s.mastery_score,
                    s.weakness_score,
                    s.status,
                    s.last_practiced_at
                FROM user_subtopic_stats s
                JOIN topics t ON t.id = s.topic_id
                WHERE s.user_id = ?
                ORDER BY s.weakness_score DESC, s.last_practiced_at DESC
                """,
                (db_user_id,),
            ).fetchall()
            error_rows = connection.execute(
                """
                SELECT
                    t.topic_code,
                    s.error_tag,
                    s.attempts_count,
                    s.incorrect_count,
                    s.error_rate,
                    s.weakness_score,
                    s.status,
                    s.last_seen_at
                FROM user_error_stats s
                JOIN topics t ON t.id = s.topic_id
                WHERE s.user_id = ?
                ORDER BY s.weakness_score DESC, s.last_seen_at DESC
                """,
                (db_user_id,),
            ).fetchall()
            skill_rows = connection.execute(
                """
                SELECT
                    sk.skill_code,
                    sk.name,
                    sk.skill_type,
                    sk.cefr,
                    sk.prerequisites_json,
                    t.topic_code,
                    m.mastery_probability,
                    m.confidence,
                    m.attempts_count,
                    m.correct_count,
                    m.incorrect_count,
                    m.status,
                    m.last_practiced_at,
                    m.next_review_at
                FROM user_skill_mastery m
                JOIN skills sk ON sk.id = m.skill_id
                JOIN topics t ON t.id = m.topic_id
                WHERE m.user_id = ?
                ORDER BY m.mastery_probability ASC, m.next_review_at ASC
                """,
                (db_user_id,),
            ).fetchall()

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
                    "code": row["topic_code"],
                    "label": self._label_from_code(row["topic_code"]),
                    "topic": row["topic_code"],
                    "attempts_count": int(row["attempts_count"]),
                    "correct_count": int(row["correct_count"]),
                    "accuracy": float(row["accuracy"]),
                    "weakness_score": float(row["weakness_score"]),
                    "status": row["status"],
                    "last_practiced_at": row["last_practiced_at"],
                }
                for row in topic_rows
            ],
            "subtopic_stats": [
                {
                    "code": self._stat_key(row["topic_code"], row["subtopic"]),
                    "label": self._label_from_code(row["subtopic"]),
                    "topic": row["topic_code"],
                    "attempts_count": int(row["attempts_count"]),
                    "correct_count": int(row["correct_count"]),
                    "accuracy": float(row["accuracy"]),
                    "mastery_score": float(row["mastery_score"]),
                    "weakness_score": float(row["weakness_score"]),
                    "status": row["status"],
                    "last_practiced_at": row["last_practiced_at"],
                }
                for row in subtopic_rows
            ],
            "error_stats": [
                {
                    "code": self._stat_key(row["topic_code"], row["error_tag"]),
                    "label": self._label_from_code(row["error_tag"]),
                    "topic": row["topic_code"],
                    "attempts_count": int(row["attempts_count"]),
                    "incorrect_count": int(row["incorrect_count"]),
                    "error_rate": float(row["error_rate"]),
                    "weakness_score": float(row["weakness_score"]),
                    "status": row["status"],
                    "last_seen_at": row["last_seen_at"],
                }
                for row in error_rows
            ],
            "skill_mastery": [
                {
                    "code": row["skill_code"],
                    "label": row["name"],
                    "topic": row["topic_code"],
                    "skill_type": row["skill_type"],
                    "cefr": row["cefr"],
                    "mastery_probability": float(row["mastery_probability"]),
                    "confidence": float(row["confidence"]),
                    "attempts_count": int(row["attempts_count"]),
                    "correct_count": int(row["correct_count"]),
                    "incorrect_count": int(row["incorrect_count"]),
                    "weakness_score": 1.0 - float(row["mastery_probability"]),
                    "status": row["status"],
                    "last_practiced_at": row["last_practiced_at"],
                    "next_review_at": row["next_review_at"],
                    "prerequisites": json.loads(row["prerequisites_json"] or "[]"),
                }
                for row in skill_rows
            ],
        }

    def get_chat_resume(
        self,
        user_id: str,
        limit: int = 24,
        session_id: str | None = None,
    ) -> dict[str, object]:
        with self._connect() as connection:
            db_user_id = self._ensure_user(connection, user_id)
            session = (
                self._get_chat_session_by_code(connection, db_user_id, session_id)
                if session_id
                else self._get_or_create_active_chat_session(connection, db_user_id)
            )
            if session is None:
                raise LookupError("Chat session not found.")
            memory_row = self._get_chat_memory_row(connection, db_user_id)
            message_rows = connection.execute(
                """
                SELECT message_code, role, content, metadata_json, created_at
                FROM chat_messages
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(session["id"]), limit),
            ).fetchall()

        facts = (
            json.loads(memory_row["facts_json"] or "{}")
            if memory_row is not None
            else {}
        )
        summary = memory_row["summary_text"] if memory_row is not None else ""
        messages = [
            {
                "message_id": row["message_code"],
                "role": row["role"],
                "content": row["content"],
                "metadata": self._json_object(row["metadata_json"]),
                "created_at": row["created_at"],
            }
            for row in reversed(message_rows)
        ]
        return {
            "session_id": session["session_code"],
            "has_history": bool(messages or summary),
            "memory_summary": summary,
            "extracted_facts": facts,
            "suggested_next_question": self._build_suggested_next_question(
                facts,
                messages,
            ),
            "messages": messages,
            "pending_clarification": self._clarification_payload(
                self._clarification_from_payload(
                    self._json_object(session["pending_clarification_json"]),
                ),
            ),
        }

    def list_chat_sessions(self, user_id: str, limit: int = 20) -> dict[str, object]:
        with self._connect() as connection:
            db_user_id = self._ensure_user(connection, user_id)
            rows = connection.execute(
                """
                SELECT
                    s.session_code,
                    s.title,
                    s.created_at,
                    s.updated_at,
                    COUNT(m.id) AS message_count,
                    (
                        SELECT lm.content
                        FROM chat_messages lm
                        WHERE lm.session_id = s.id
                        ORDER BY lm.created_at DESC, lm.id DESC
                        LIMIT 1
                    ) AS preview
                FROM chat_sessions s
                LEFT JOIN chat_messages m ON m.session_id = s.id
                WHERE s.user_id = ?
                GROUP BY s.id
                ORDER BY s.updated_at DESC, s.id DESC
                LIMIT ?
                """,
                (db_user_id, limit),
            ).fetchall()

        return {
            "sessions": [self._chat_session_summary_from_row(row) for row in rows],
        }

    def create_chat_session(self, user_id: str) -> dict[str, object]:
        with self._connect() as connection:
            db_user_id = self._ensure_user(connection, user_id)
            session = self._create_chat_session(connection, db_user_id)
            memory_row = self._get_chat_memory_row(connection, db_user_id)

        facts = (
            json.loads(memory_row["facts_json"] or "{}")
            if memory_row is not None
            else {}
        )
        summary = memory_row["summary_text"] if memory_row is not None else ""
        return {
            "session_id": session["session_code"],
            "has_history": bool(summary),
            "memory_summary": summary,
            "extracted_facts": facts,
            "suggested_next_question": self._build_suggested_next_question(
                facts,
                [],
            ),
            "messages": [],
            "pending_clarification": None,
        }

    def save_chat_message(
        self,
        user_id: str,
        role: str,
        content: str,
        session_id: str | None = None,
        metadata: dict[str, object] | None = None,
        update_memory: bool = True,
    ) -> dict[str, object]:
        normalized_role = "assistant" if role == "bot" else role.strip().lower()
        if normalized_role not in {"user", "assistant"}:
            raise ValueError("Chat message role must be `user` or `assistant`.")

        cleaned_content = content.strip()
        if not cleaned_content:
            raise ValueError("Chat message content cannot be empty.")

        with self._connect() as connection:
            db_user_id = self._ensure_user(connection, user_id)
            session = (
                self._get_chat_session_by_code(connection, db_user_id, session_id)
                if session_id
                else self._get_or_create_active_chat_session(connection, db_user_id)
            )
            if session is None:
                raise LookupError("Chat session not found.")
            message_code = f"msg_{uuid.uuid4().hex}"
            metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
            connection.execute(
                """
                INSERT INTO chat_messages (
                    message_code,
                    session_id,
                    role,
                    content,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    message_code,
                    int(session["id"]),
                    normalized_role,
                    cleaned_content,
                    metadata_json,
                ),
            )
            connection.execute(
                """
                UPDATE chat_sessions
                SET
                    title = COALESCE(title, ?),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    self._make_chat_title(cleaned_content)
                    if normalized_role == "user"
                    else None,
                    int(session["id"]),
                ),
            )
            message_row = connection.execute(
                """
                SELECT message_code, role, content, metadata_json, created_at
                FROM chat_messages
                WHERE message_code = ?
                """,
                (message_code,),
            ).fetchone()

            memory_row = self._get_chat_memory_row(connection, db_user_id)
            facts = (
                json.loads(memory_row["facts_json"] or "{}")
                if memory_row is not None
                else {}
            )
            summary = memory_row["summary_text"] if memory_row is not None else ""
            if update_memory and normalized_role == "user":
                facts, summary = self._update_chat_memory_from_message(
                    connection=connection,
                    user_id=db_user_id,
                    session_id=int(session["id"]),
                    content=cleaned_content,
                )

        return {
            "session_id": session["session_code"],
            "message": {
                "message_id": message_row["message_code"],
                "role": message_row["role"],
                "content": message_row["content"],
                "metadata": self._json_object(message_row["metadata_json"]),
                "created_at": message_row["created_at"],
            },
            "memory_summary": summary,
            "extracted_facts": facts,
            "suggested_next_question": self._build_suggested_next_question(
                facts,
                [],
            ),
        }

    def merge_chat_memory_facts(
        self,
        user_id: str,
        facts: dict[str, object],
        session_id: str | None = None,
    ) -> dict[str, object]:
        cleaned_facts = {
            key: value
            for key, value in facts.items()
            if value not in (None, "", [])
        }
        if not cleaned_facts:
            return self.get_chat_resume(user_id, session_id=session_id)

        with self._connect() as connection:
            db_user_id = self._ensure_user(connection, user_id)
            session = (
                self._get_chat_session_by_code(connection, db_user_id, session_id)
                if session_id
                else self._get_or_create_active_chat_session(connection, db_user_id)
            )
            if session is None:
                raise LookupError("Chat session not found.")
            memory_row = self._get_chat_memory_row(connection, db_user_id)
            current_facts = (
                json.loads(memory_row["facts_json"] or "{}")
                if memory_row is not None
                else {}
            )
            merged_facts = self._merge_chat_facts(current_facts, cleaned_facts)
            summary = self._build_chat_memory_summary(merged_facts)
            connection.execute(
                """
                INSERT INTO chat_memory_summaries (
                    user_id,
                    summary_text,
                    facts_json,
                    last_session_id,
                    updated_at
                )
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    summary_text = excluded.summary_text,
                    facts_json = excluded.facts_json,
                    last_session_id = excluded.last_session_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    db_user_id,
                    summary,
                    json.dumps(merged_facts, ensure_ascii=False),
                    int(session["id"]),
                ),
            )
            self._sync_profile_from_chat_facts(
                connection,
                db_user_id,
                merged_facts,
            )
            resolved_session_id = str(session["session_code"])

        return self.get_chat_resume(user_id, session_id=resolved_session_id)

    def save_profile(self, profile: LearnerProfile) -> None:
        with self._connect() as connection:
            db_user_id = self._ensure_user(connection, profile.user_id)
            if profile.display_name:
                connection.execute(
                    """
                    UPDATE users
                    SET name = ?
                    WHERE id = ?
                    """,
                    (profile.display_name, db_user_id),
                )
            connection.execute(
                """
                INSERT INTO user_profiles (
                    user_id,
                    level,
                    goals_json,
                    preferred_difficulty,
                    preferred_num_questions,
                    onboarding_completed,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    level = excluded.level,
                    goals_json = excluded.goals_json,
                    preferred_difficulty = excluded.preferred_difficulty,
                    preferred_num_questions = excluded.preferred_num_questions,
                    onboarding_completed = excluded.onboarding_completed,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    db_user_id,
                    profile.level,
                    json.dumps(profile.goals, ensure_ascii=False),
                    profile.preferred_difficulty,
                    profile.preferred_num_questions,
                    int(profile.onboarding_completed),
                ),
            )

            for topic_code, accuracy in profile.topic_accuracy.items():
                topic_id = self._ensure_topic(connection, topic_code)
                weakness_score = profile.weak_topics.get(topic_code, 1.0 - accuracy)
                connection.execute(
                    """
                    INSERT INTO user_topic_stats (
                        user_id,
                        topic_id,
                        accuracy,
                        weakness_score,
                        status,
                        last_practiced_at
                    )
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id, topic_id) DO UPDATE SET
                        accuracy = excluded.accuracy,
                        weakness_score = excluded.weakness_score,
                        status = excluded.status,
                        last_practiced_at = CURRENT_TIMESTAMP
                    """,
                    (
                        db_user_id,
                        topic_id,
                        accuracy,
                        weakness_score,
                        self._status_from_accuracy(accuracy),
                    ),
                )

            for skill_code, mastery_probability in profile.skill_mastery.items():
                node = self.skill_graph.get(skill_code)
                skill_id = self._ensure_skill(connection, node)
                topic_id = self._ensure_topic(connection, node.topic)
                confidence = profile.skill_confidence.get(skill_code, 0.0)
                attempts_count = profile.skill_attempts.get(skill_code, 0)
                connection.execute(
                    """
                    INSERT INTO user_skill_mastery (
                        user_id,
                        skill_id,
                        topic_id,
                        mastery_probability,
                        attempts_count,
                        confidence,
                        status,
                        next_review_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id, skill_id) DO UPDATE SET
                        topic_id = excluded.topic_id,
                        mastery_probability = excluded.mastery_probability,
                        attempts_count = excluded.attempts_count,
                        confidence = excluded.confidence,
                        status = excluded.status,
                        next_review_at = COALESCE(
                            user_skill_mastery.next_review_at,
                            excluded.next_review_at
                        ),
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        db_user_id,
                        skill_id,
                        topic_id,
                        mastery_probability,
                        attempts_count,
                        confidence,
                        self._status_from_mastery(mastery_probability),
                        next_review_at(mastery_probability, confidence),
                    ),
                )

    def create_learning_activity(self, activity: LearningActivity) -> LearningActivity:
        with self._connect() as connection:
            db_user_id = self._ensure_user(connection, activity.learner_id)
            conversation = self._get_chat_session_by_code(
                connection,
                db_user_id,
                activity.conversation_id,
            )
            if conversation is None:
                raise LookupError("Chat session not found.")

            activity_code = activity.activity_id or f"activity_{uuid.uuid4().hex}"
            cursor = connection.execute(
                """
                INSERT INTO learning_activities (
                    activity_code,
                    conversation_id,
                    user_id,
                    activity_type,
                    status,
                    target_skills_json,
                    difficulty,
                    metadata_json,
                    created_at,
                    started_at,
                    submitted_at,
                    completed_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    activity_code,
                    int(conversation["id"]),
                    db_user_id,
                    self._activity_type_value(activity.type),
                    self._activity_status_value(activity.status),
                    json.dumps(activity.target_skills, ensure_ascii=False),
                    activity.difficulty,
                    json.dumps(activity.metadata, ensure_ascii=False),
                    activity.created_at,
                    activity.started_at,
                    activity.submitted_at,
                    activity.completed_at,
                ),
            )
            db_activity_id = int(cursor.lastrowid)
            self._sync_active_activity(connection, int(conversation["id"]), db_activity_id, activity.status)
            self._record_activity_event(
                connection,
                db_activity_id,
                "CREATED",
                activity.status,
            )
            row = self._get_activity_row_by_db_id(connection, db_user_id, db_activity_id)

        return self._activity_from_row(row)

    def get_learning_activity(
        self,
        user_id: str,
        activity_id: str,
    ) -> LearningActivity | None:
        with self._connect() as connection:
            db_user_id = self._ensure_user(connection, user_id)
            row = self._get_activity_row_by_code(
                connection,
                db_user_id,
                activity_id,
            )
        return self._activity_from_row(row) if row is not None else None

    def update_learning_activity_status(
        self,
        user_id: str,
        activity_id: str,
        status: LearningActivityStatus,
    ) -> LearningActivity:
        with self._connect() as connection:
            db_user_id = self._ensure_user(connection, user_id)
            row = self._get_activity_row_by_code(connection, db_user_id, activity_id)
            if row is None:
                raise LookupError(f"Learning activity not found: {activity_id}")

            started_sql = (
                "COALESCE(started_at, CURRENT_TIMESTAMP)"
                if status == LearningActivityStatus.IN_PROGRESS
                else "started_at"
            )
            submitted_sql = (
                "COALESCE(submitted_at, CURRENT_TIMESTAMP)"
                if status == LearningActivityStatus.SUBMITTED
                else "submitted_at"
            )
            completed_sql = (
                "COALESCE(completed_at, CURRENT_TIMESTAMP)"
                if self._is_terminal_activity_status(status)
                else "completed_at"
            )
            connection.execute(
                f"""
                UPDATE learning_activities
                SET
                    status = ?,
                    started_at = {started_sql},
                    submitted_at = {submitted_sql},
                    completed_at = {completed_sql},
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status.value, int(row["id"])),
            )
            self._sync_active_activity(
                connection,
                int(row["conversation_db_id"]),
                int(row["id"]),
                status,
            )
            self._record_activity_event(
                connection,
                int(row["id"]),
                "STATUS_CHANGED",
                status,
            )
            updated = self._get_activity_row_by_db_id(connection, db_user_id, int(row["id"]))

        return self._activity_from_row(updated)

    def update_learning_activity_metadata(
        self,
        user_id: str,
        activity_id: str,
        metadata: dict[str, Any],
    ) -> LearningActivity:
        with self._connect() as connection:
            db_user_id = self._ensure_user(connection, user_id)
            row = self._get_activity_row_by_code(connection, db_user_id, activity_id)
            if row is None:
                raise LookupError(f"Learning activity not found: {activity_id}")
            current_metadata = self._json_object(row["metadata_json"])
            current_metadata.update(metadata)
            connection.execute(
                """
                UPDATE learning_activities
                SET metadata_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    json.dumps(current_metadata, ensure_ascii=False),
                    int(row["id"]),
                ),
            )
            self._record_activity_event(
                connection,
                int(row["id"]),
                "METADATA_UPDATED",
                self._status_from_value(row["status"]),
                {"metadata_keys": sorted(metadata.keys())},
            )
            updated = self._get_activity_row_by_db_id(
                connection,
                db_user_id,
                int(row["id"]),
            )

        return self._activity_from_row(updated)

    def attach_generated_exercise_set_to_activity(
        self,
        user_id: str,
        activity_id: str,
        generation_run_id: str,
    ) -> LearningActivity:
        with self._connect() as connection:
            db_user_id = self._ensure_user(connection, user_id)
            activity_row = self._get_activity_row_by_code(
                connection,
                db_user_id,
                activity_id,
            )
            if activity_row is None:
                raise LookupError(f"Learning activity not found: {activity_id}")
            generation_row = self._get_generation_run_by_public_id(
                connection,
                db_user_id,
                generation_run_id,
            )
            if generation_row is None:
                raise LookupError(f"Generation run not found: {generation_run_id}")

            connection.execute(
                """
                UPDATE learning_activities
                SET generation_run_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (int(generation_row["id"]), int(activity_row["id"])),
            )
            connection.execute(
                """
                UPDATE generation_runs
                SET activity_id = ?
                WHERE id = ?
                """,
                (int(activity_row["id"]), int(generation_row["id"])),
            )
            self._record_activity_event(
                connection,
                int(activity_row["id"]),
                "GENERATED_SET_ATTACHED",
                self._status_from_value(activity_row["status"]),
                {"generation_run_id": generation_run_id},
            )
            row = self._get_activity_row_by_db_id(
                connection,
                db_user_id,
                int(activity_row["id"]),
            )

        return self._activity_from_row(row)

    def attach_session_result_to_activity(
        self,
        user_id: str,
        activity_id: str,
        session_code: str,
    ) -> LearningActivity:
        with self._connect() as connection:
            db_user_id = self._ensure_user(connection, user_id)
            activity_row = self._get_activity_row_by_code(
                connection,
                db_user_id,
                activity_id,
            )
            if activity_row is None:
                raise LookupError(f"Learning activity not found: {activity_id}")
            session_row = connection.execute(
                """
                SELECT id
                FROM practice_sessions
                WHERE session_code = ? AND user_id = ?
                """,
                (session_code, db_user_id),
            ).fetchone()
            if session_row is None:
                raise LookupError(f"Practice session not found: {session_code}")

            connection.execute(
                """
                UPDATE learning_activities
                SET
                    practice_session_id = ?,
                    status = ?,
                    submitted_at = COALESCE(submitted_at, CURRENT_TIMESTAMP),
                    completed_at = COALESCE(completed_at, CURRENT_TIMESTAMP),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    int(session_row["id"]),
                    LearningActivityStatus.COMPLETED.value,
                    int(activity_row["id"]),
                ),
            )
            connection.execute(
                """
                UPDATE practice_sessions
                SET activity_id = ?
                WHERE id = ?
                """,
                (int(activity_row["id"]), int(session_row["id"])),
            )
            self._sync_active_activity(
                connection,
                int(activity_row["conversation_db_id"]),
                int(activity_row["id"]),
                LearningActivityStatus.COMPLETED,
            )
            self._record_activity_event(
                connection,
                int(activity_row["id"]),
                "SESSION_RESULT_ATTACHED",
                LearningActivityStatus.COMPLETED,
                {"session_code": session_code},
            )
            row = self._get_activity_row_by_db_id(
                connection,
                db_user_id,
                int(activity_row["id"]),
            )

        return self._activity_from_row(row)

    def get_latest_learning_activity(
        self,
        user_id: str,
        conversation_id: str,
        statuses: list[LearningActivityStatus] | None = None,
    ) -> LearningActivity | None:
        with self._connect() as connection:
            db_user_id = self._ensure_user(connection, user_id)
            conversation = self._get_chat_session_by_code(
                connection,
                db_user_id,
                conversation_id,
            )
            if conversation is None:
                raise LookupError("Chat session not found.")

            status_values = [status.value for status in statuses or []]
            status_clause = ""
            params: list[object] = [db_user_id, int(conversation["id"])]
            if status_values:
                placeholders = ",".join("?" for _ in status_values)
                status_clause = f"AND la.status IN ({placeholders})"
                params.extend(status_values)
            rows = connection.execute(
                f"""
                SELECT
                    la.*,
                    u.user_code,
                    la.conversation_id AS conversation_db_id,
                    cs.session_code AS conversation_code,
                    gr.generation_run_id AS public_generation_run_id,
                    ps.session_code AS practice_session_code
                FROM learning_activities la
                JOIN users u ON u.id = la.user_id
                JOIN chat_sessions cs ON cs.id = la.conversation_id
                LEFT JOIN generation_runs gr ON gr.id = la.generation_run_id
                LEFT JOIN practice_sessions ps ON ps.id = la.practice_session_id
                WHERE la.user_id = ? AND la.conversation_id = ?
                {status_clause}
                ORDER BY la.updated_at DESC, la.id DESC
                LIMIT 1
                """,
                params,
            ).fetchall()

        return self._activity_from_row(rows[0]) if rows else None

    def get_pending_clarification(
        self,
        user_id: str,
        conversation_id: str,
    ) -> PendingClarification | None:
        with self._connect() as connection:
            db_user_id = self._ensure_user(connection, user_id)
            session = self._get_chat_session_by_code(
                connection,
                db_user_id,
                conversation_id,
            )
            if session is None:
                raise LookupError("Chat session not found.")
            return self._clarification_from_payload(
                self._json_object(session["pending_clarification_json"]),
            )

    def save_pending_clarification(
        self,
        user_id: str,
        conversation_id: str,
        clarification: PendingClarification | None,
    ) -> None:
        with self._connect() as connection:
            db_user_id = self._ensure_user(connection, user_id)
            session = self._get_chat_session_by_code(
                connection,
                db_user_id,
                conversation_id,
            )
            if session is None:
                raise LookupError("Chat session not found.")
            connection.execute(
                """
                UPDATE chat_sessions
                SET
                    pending_clarification_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    json.dumps(
                        self._clarification_payload(clarification),
                        ensure_ascii=False,
                    )
                    if clarification is not None
                    else None,
                    int(session["id"]),
                ),
            )

    def get_generated_exercise_set(
        self,
        user_id: str,
        generation_run_id: str,
    ) -> GeneratedExerciseSet | None:
        with self._connect() as connection:
            run = connection.execute(
                """
                SELECT
                    gr.id,
                    gr.generation_run_id,
                    la.activity_code,
                    gr.exercise_type,
                    gr.difficulty,
                    gr.num_questions,
                    gr.raw_request_text,
                    gr.prompt_snapshot,
                    gr.agent_trace_json,
                    t.topic_code
                FROM generation_runs gr
                JOIN users u ON u.id = gr.user_id
                JOIN topics t ON t.id = gr.topic_id
                LEFT JOIN learning_activities la ON la.id = gr.activity_id
                WHERE gr.generation_run_id = ? AND u.user_code = ?
                """,
                (generation_run_id, user_id),
            ).fetchone()

            if run is None:
                return None

            exercise_rows = connection.execute(
                """
                SELECT
                    id,
                    session_exercise_code,
                    client_exercise_id,
                    exercise_type,
                    difficulty,
                    skill,
                    subtopic,
                    error_tag,
                    question_text,
                    correct_answer,
                    explanation,
                    source_chunk_ids_json
                FROM session_exercises
                WHERE generation_run_id = ?
                ORDER BY display_order, id
                """,
                (int(run["id"]),),
            ).fetchall()

            exercises: list[ExerciseItem] = []
            for exercise_row in exercise_rows:
                option_rows = connection.execute(
                    """
                    SELECT option_label, option_text, is_correct
                    FROM session_exercise_options
                    WHERE session_exercise_id = ?
                    ORDER BY id
                    """,
                    (int(exercise_row["id"]),),
                ).fetchall()
                exercises.append(
                    ExerciseItem(
                        exercise_id=exercise_row["client_exercise_id"]
                        or exercise_row["session_exercise_code"],
                        exercise_type=exercise_row["exercise_type"],
                        topic=run["topic_code"],
                        difficulty=exercise_row["difficulty"],
                        skill=exercise_row["skill"] or self._skill_for_topic(
                            run["topic_code"]
                        ),
                        subtopic=exercise_row["subtopic"],
                        error_tag=exercise_row["error_tag"],
                        question_text=exercise_row["question_text"],
                        options=[
                            ExerciseOption(
                                label=option_row["option_label"],
                                text=option_row["option_text"],
                                is_correct=bool(option_row["is_correct"]),
                            )
                            for option_row in option_rows
                        ],
                        correct_answer=exercise_row["correct_answer"],
                        explanation=exercise_row["explanation"] or "",
                        source_chunk_ids=json.loads(
                            exercise_row["source_chunk_ids_json"] or "[]"
                        ),
                    )
                )

        request = PracticeRequest(
            user_id=user_id,
            raw_text=run["raw_request_text"],
            topic=run["topic_code"],
            difficulty=run["difficulty"],
            exercise_type=run["exercise_type"],
            num_questions=int(run["num_questions"]),
        )
        first_exercise = exercises[0] if exercises else None
        target_subtopic = first_exercise.subtopic if first_exercise else None
        target_error_tag = first_exercise.error_tag if first_exercise else None
        target_skill_id = self.skill_graph.skill_id_for(
            topic=run["topic_code"],
            skill_type=(
                first_exercise.skill
                if first_exercise is not None
                else self._skill_for_topic(run["topic_code"])
            ),
            subtopic=target_subtopic,
        )
        plan = PracticePlan(
            user_id=user_id,
            topic=run["topic_code"],
            difficulty=run["difficulty"],
            exercise_type=run["exercise_type"],
            num_questions=int(run["num_questions"]),
            focus_reason="Loaded from persisted SQLite generation run.",
            target_subtopic=target_subtopic,
            target_error_tag=target_error_tag,
            target_skill_id=target_skill_id,
        )
        return GeneratedExerciseSet(
            request=request,
            plan=plan,
            retrieved_chunks=[],
            exercises=exercises,
            activity_id=run["activity_code"],
            generation_run_id=run["generation_run_id"],
            prompt_snapshot=run["prompt_snapshot"] or "",
            agent_trace=json.loads(run["agent_trace_json"] or "[]"),
        )

    def save_generated_exercise_set(
        self,
        generated: GeneratedExerciseSet,
        generator_backend: str,
    ) -> str:
        generation_run_id = f"gen_{uuid.uuid4().hex}"
        with self._connect() as connection:
            db_user_id = self._ensure_user(connection, generated.request.user_id)
            topic_id = self._ensure_topic(connection, generated.plan.topic)
            retrieved_chunk_ids = [chunk.chunk_id for chunk in generated.retrieved_chunks]
            model_name = generator_backend.split(":", maxsplit=1)[-1]
            activity_row = None
            if generated.activity_id:
                activity_row = self._get_activity_row_by_code(
                    connection,
                    db_user_id,
                    generated.activity_id,
                )
                if activity_row is None:
                    raise LookupError(
                        f"Learning activity not found: {generated.activity_id}"
                    )

            cursor = connection.execute(
                """
                INSERT INTO generation_runs (
                    generation_run_id,
                    activity_id,
                    user_id,
                    topic_id,
                    exercise_type,
                    difficulty,
                    num_questions,
                    raw_request_text,
                    prompt_snapshot,
                    retrieved_chunk_ids_json,
                    agent_trace_json,
                    generator_backend,
                    model_name
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generation_run_id,
                    int(activity_row["id"]) if activity_row is not None else None,
                    db_user_id,
                    topic_id,
                    generated.plan.exercise_type,
                    generated.plan.difficulty,
                    generated.plan.num_questions,
                    generated.request.raw_text,
                    generated.prompt_snapshot,
                    json.dumps(retrieved_chunk_ids, ensure_ascii=False),
                    json.dumps(generated.agent_trace, ensure_ascii=False),
                    generator_backend,
                    model_name,
                ),
            )
            db_generation_run_id = int(cursor.lastrowid)

            for display_order, exercise in enumerate(generated.exercises, start=1):
                exercise_cursor = connection.execute(
                    """
                    INSERT INTO session_exercises (
                        session_exercise_code,
                        client_exercise_id,
                        generation_run_id,
                        topic_id,
                        exercise_type,
                        difficulty,
                        skill,
                        subtopic,
                        error_tag,
                        question_text,
                        correct_answer,
                        explanation,
                        source_chunk_ids_json,
                        display_order
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"{generation_run_id}_q{display_order}",
                        exercise.exercise_id,
                        db_generation_run_id,
                        topic_id,
                        exercise.exercise_type,
                        exercise.difficulty,
                        exercise.skill or self._skill_for_topic(exercise.topic),
                        exercise.subtopic,
                        exercise.error_tag,
                        exercise.question_text,
                        exercise.correct_answer,
                        exercise.explanation,
                        json.dumps(exercise.source_chunk_ids, ensure_ascii=False),
                        display_order,
                    ),
                )
                db_session_exercise_id = int(exercise_cursor.lastrowid)

                for option in exercise.options:
                    connection.execute(
                        """
                        INSERT INTO session_exercise_options (
                            session_exercise_id,
                            option_label,
                            option_text,
                            is_correct
                        )
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            db_session_exercise_id,
                            option.label,
                            option.text,
                            int(option.is_correct),
                        ),
                    )

            if activity_row is not None:
                connection.execute(
                    """
                    UPDATE learning_activities
                    SET generation_run_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (db_generation_run_id, int(activity_row["id"])),
                )
                self._record_activity_event(
                    connection,
                    int(activity_row["id"]),
                    "GENERATED_SET_ATTACHED",
                    self._status_from_value(activity_row["status"]),
                    {"generation_run_id": generation_run_id},
                )

        generated.generation_run_id = generation_run_id
        return generation_run_id

    def save_session_result(
        self,
        result: SessionResult,
        generation_run_id: str | None = None,
        selected_answers: dict[str, str] | None = None,
        answer_diagnoses: list[AnswerDiagnosis] | None = None,
        activity_id: str | None = None,
    ) -> str:
        session_code = f"sess_{uuid.uuid4().hex}"
        with self._connect() as connection:
            db_user_id = self._ensure_user(connection, result.user_id)
            topic_id = self._ensure_topic(connection, result.topic)
            latest_generation_run = (
                self._get_generation_run_by_public_id(
                    connection,
                    user_id=db_user_id,
                    generation_run_id=generation_run_id,
                )
                if generation_run_id
                else self._get_latest_generation_run(
                    connection,
                    user_id=db_user_id,
                    topic_id=topic_id,
                )
            )

            if generation_run_id and latest_generation_run is None:
                raise LookupError(f"Generation run not found: {generation_run_id}")

            generation_run_db_id = (
                int(latest_generation_run["id"])
                if latest_generation_run is not None
                else None
            )
            if latest_generation_run is not None:
                topic_id = int(latest_generation_run["topic_id"])
            difficulty = (
                str(latest_generation_run["difficulty"])
                if latest_generation_run is not None
                else "unknown"
            )
            activity_row = None
            activity_code = activity_id or result.activity_id
            if activity_code is None and latest_generation_run is not None:
                generation_activity_id = latest_generation_run["activity_id"]
                if generation_activity_id is not None:
                    activity_row = self._get_activity_row_by_db_id(
                        connection,
                        db_user_id,
                        int(generation_activity_id),
                    )
                    activity_code = (
                        str(activity_row["activity_code"])
                        if activity_row is not None
                        else None
                    )
            elif activity_code is not None:
                activity_row = self._get_activity_row_by_code(
                    connection,
                    db_user_id,
                    activity_code,
                )
                if activity_row is None:
                    raise LookupError(f"Learning activity not found: {activity_code}")
            result.activity_id = activity_code

            connection.execute(
                """
                INSERT INTO practice_sessions (
                    session_code,
                    activity_id,
                    user_id,
                    topic_id,
                    generation_run_id,
                    difficulty,
                    total_questions,
                    correct_count,
                    accuracy,
                    recommendation_text,
                    started_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    session_code,
                    int(activity_row["id"]) if activity_row is not None else None,
                    db_user_id,
                    topic_id,
                    generation_run_db_id,
                    difficulty,
                    result.total_questions,
                    result.correct_count,
                    result.score,
                    result.recommendation,
                ),
            )
            db_session_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
            result.session_code = session_code

            if selected_answers is not None and generation_run_db_id is not None:
                self._save_user_answers(
                    connection=connection,
                    user_id=db_user_id,
                    session_id=db_session_id,
                    generation_run_db_id=generation_run_db_id,
                    selected_answers=selected_answers,
                    answer_diagnoses=answer_diagnoses,
                )

            existing = connection.execute(
                """
                SELECT attempts_count, correct_count
                FROM user_topic_stats
                WHERE user_id = ? AND topic_id = ?
                """,
                (db_user_id, topic_id),
            ).fetchone()
            attempts_count = result.total_questions
            correct_count = result.correct_count
            if existing is not None:
                attempts_count += int(existing["attempts_count"])
                correct_count += int(existing["correct_count"])

            accuracy = correct_count / max(attempts_count, 1)
            connection.execute(
                """
                INSERT INTO user_topic_stats (
                    user_id,
                    topic_id,
                    attempts_count,
                    correct_count,
                    accuracy,
                    weakness_score,
                    status,
                    last_practiced_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, topic_id) DO UPDATE SET
                    attempts_count = excluded.attempts_count,
                    correct_count = excluded.correct_count,
                    accuracy = excluded.accuracy,
                    weakness_score = excluded.weakness_score,
                    status = excluded.status,
                    last_practiced_at = CURRENT_TIMESTAMP
                """,
                (
                    db_user_id,
                    topic_id,
                    attempts_count,
                    correct_count,
                    accuracy,
                    1.0 - accuracy,
                    self._status_from_accuracy(accuracy),
                ),
            )

            if activity_row is not None:
                connection.execute(
                    """
                    UPDATE learning_activities
                    SET
                        practice_session_id = ?,
                        status = ?,
                        submitted_at = COALESCE(submitted_at, CURRENT_TIMESTAMP),
                        completed_at = COALESCE(completed_at, CURRENT_TIMESTAMP),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        db_session_id,
                        LearningActivityStatus.COMPLETED.value,
                        int(activity_row["id"]),
                    ),
                )
                self._sync_active_activity(
                    connection,
                    int(activity_row["conversation_db_id"]),
                    int(activity_row["id"]),
                    LearningActivityStatus.COMPLETED,
                )
                self._record_activity_event(
                    connection,
                    int(activity_row["id"]),
                    "SESSION_RESULT_ATTACHED",
                    LearningActivityStatus.COMPLETED,
                    {"session_code": session_code},
                )
        return session_code

    def get_session_result(
        self,
        user_id: str,
        session_code: str,
    ) -> SessionResult | None:
        with self._connect() as connection:
            db_user_id = self._ensure_user(connection, user_id)
            session_row = connection.execute(
                """
                SELECT
                    ps.id,
                    ps.session_code,
                    la.activity_code,
                    gr.generation_run_id,
                    t.topic_code,
                    ps.total_questions,
                    ps.correct_count,
                    ps.accuracy,
                    ps.recommendation_text
                FROM practice_sessions ps
                JOIN topics t ON t.id = ps.topic_id
                LEFT JOIN learning_activities la ON la.id = ps.activity_id
                LEFT JOIN generation_runs gr ON gr.id = ps.generation_run_id
                WHERE ps.user_id = ? AND ps.session_code = ?
                """,
                (db_user_id, session_code),
            ).fetchone()
            if session_row is None:
                return None

            diagnosis_rows = connection.execute(
                """
                SELECT
                    COALESCE(se.client_exercise_id, se.session_exercise_code)
                        AS exercise_id,
                    ad.error_type,
                    ad.skill_code,
                    ad.topic_code,
                    ad.subtopic,
                    ad.subtype,
                    ad.severity,
                    ad.mastery_impact,
                    ad.explanation,
                    ad.evidence_json,
                    ua.selected_answer,
                    ua.is_correct
                FROM answer_diagnoses ad
                JOIN user_answers ua ON ua.id = ad.user_answer_id
                JOIN session_exercises se ON se.id = ad.session_exercise_id
                WHERE ad.session_id = ?
                ORDER BY ad.id
                """,
                (int(session_row["id"]),),
            ).fetchall()
            review_row = connection.execute(
                """
                SELECT
                    review_code,
                    evaluator,
                    summary_text,
                    strengths_json,
                    weaknesses_json,
                    next_steps_json,
                    next_practice_prompt,
                    raw_response
                FROM practice_reviews
                WHERE user_id = ? AND session_id = ?
                """,
                (db_user_id, int(session_row["id"])),
            ).fetchone()

        diagnoses = []
        for row in diagnosis_rows:
            evidence = self._json_object(row["evidence_json"])
            if row["selected_answer"] is not None:
                evidence.setdefault("selected_answer", row["selected_answer"])
            diagnoses.append(
                AnswerDiagnosis(
                    exercise_id=row["exercise_id"],
                    is_correct=bool(row["is_correct"]),
                    error_type=row["error_type"],
                    skill_id=row["skill_code"],
                    topic=row["topic_code"],
                    subtopic=row["subtopic"],
                    subtype=row["subtype"],
                    severity=float(row["severity"] or 0.0),
                    mastery_impact=float(row["mastery_impact"] or 0.0),
                    explanation=row["explanation"] or "",
                    evidence=evidence,
                )
            )
        review = None
        if review_row is not None:
            review = PracticeReview(
                review_code=review_row["review_code"],
                evaluator=review_row["evaluator"],
                summary=review_row["summary_text"],
                strengths=[
                    str(item)
                    for item in self._json_value(review_row["strengths_json"], [])
                ],
                weaknesses=[
                    str(item)
                    for item in self._json_value(review_row["weaknesses_json"], [])
                ],
                next_steps=[
                    str(item)
                    for item in self._json_value(review_row["next_steps_json"], [])
                ],
                next_practice_prompt=review_row["next_practice_prompt"] or "",
                raw_response=review_row["raw_response"] or "",
            )
        return SessionResult(
            user_id=user_id,
            topic=session_row["topic_code"],
            score=float(session_row["accuracy"]),
            correct_count=int(session_row["correct_count"]),
            total_questions=int(session_row["total_questions"]),
            weak_topics_detected=(
                [session_row["topic_code"]]
                if float(session_row["accuracy"]) < 0.8
                else []
            ),
            recommendation=session_row["recommendation_text"] or "",
            activity_id=session_row["activity_code"],
            generation_run_id=session_row["generation_run_id"] or "",
            session_code=session_row["session_code"],
            answer_diagnoses=diagnoses,
            practice_review=review,
        )

    def save_practice_review(
        self,
        user_id: str,
        session_code: str,
        review: PracticeReview,
    ) -> str:
        with self._connect() as connection:
            db_user_id = self._ensure_user(connection, user_id)
            session_row = connection.execute(
                """
                SELECT id
                FROM practice_sessions
                WHERE session_code = ? AND user_id = ?
                """,
                (session_code, db_user_id),
            ).fetchone()
            if session_row is None:
                raise LookupError(f"Practice session not found: {session_code}")

            connection.execute(
                """
                INSERT INTO practice_reviews (
                    review_code,
                    user_id,
                    session_id,
                    evaluator,
                    summary_text,
                    strengths_json,
                    weaknesses_json,
                    next_steps_json,
                    next_practice_prompt,
                    raw_response
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    evaluator = excluded.evaluator,
                    summary_text = excluded.summary_text,
                    strengths_json = excluded.strengths_json,
                    weaknesses_json = excluded.weaknesses_json,
                    next_steps_json = excluded.next_steps_json,
                    next_practice_prompt = excluded.next_practice_prompt,
                    raw_response = excluded.raw_response,
                    created_at = CURRENT_TIMESTAMP
                """,
                (
                    review.review_code,
                    db_user_id,
                    int(session_row["id"]),
                    review.evaluator,
                    review.summary,
                    json.dumps(review.strengths, ensure_ascii=False),
                    json.dumps(review.weaknesses, ensure_ascii=False),
                    json.dumps(review.next_steps, ensure_ascii=False),
                    review.next_practice_prompt,
                    review.raw_response,
                ),
            )
        return review.review_code

    def _get_or_create_active_chat_session(
        self,
        connection: sqlite3.Connection,
        user_id: int,
    ) -> sqlite3.Row:
        row = connection.execute(
            """
            SELECT
                id,
                session_code,
                active_activity_id,
                pending_clarification_json,
                title,
                status,
                created_at,
                updated_at
            FROM chat_sessions
            WHERE user_id = ? AND status = 'active'
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        if row is not None:
            return row

        return self._create_chat_session(connection, user_id)

    def _get_chat_session_by_code(
        self,
        connection: sqlite3.Connection,
        user_id: int,
        session_code: str,
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT
                id,
                session_code,
                active_activity_id,
                pending_clarification_json,
                title,
                status,
                created_at,
                updated_at
            FROM chat_sessions
            WHERE user_id = ? AND session_code = ?
            """,
            (user_id, session_code),
        ).fetchone()

    def _create_chat_session(
        self,
        connection: sqlite3.Connection,
        user_id: int,
    ) -> sqlite3.Row:
        new_session_code = f"chat_{uuid.uuid4().hex}"
        cursor = connection.execute(
            """
            INSERT INTO chat_sessions (session_code, user_id)
            VALUES (?, ?)
            """,
            (new_session_code, user_id),
        )
        return connection.execute(
            """
            SELECT
                id,
                session_code,
                active_activity_id,
                pending_clarification_json,
                title,
                status,
                created_at,
                updated_at
            FROM chat_sessions
            WHERE id = ?
            """,
            (int(cursor.lastrowid),),
        ).fetchone()

    def _get_chat_memory_row(
        self,
        connection: sqlite3.Connection,
        user_id: int,
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT summary_text, facts_json, last_session_id, updated_at
            FROM chat_memory_summaries
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    def _update_chat_memory_from_message(
        self,
        connection: sqlite3.Connection,
        user_id: int,
        session_id: int,
        content: str,
    ) -> tuple[dict[str, object], str]:
        memory_row = self._get_chat_memory_row(connection, user_id)
        current_facts = (
            json.loads(memory_row["facts_json"] or "{}")
            if memory_row is not None
            else {}
        )
        extracted_facts = self._extract_chat_facts(content)
        extracted_facts["last_user_request"] = content[:500]
        merged_facts = self._merge_chat_facts(current_facts, extracted_facts)
        summary = self._build_chat_memory_summary(merged_facts)

        connection.execute(
            """
            INSERT INTO chat_memory_summaries (
                user_id,
                summary_text,
                facts_json,
                last_session_id,
                updated_at
            )
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                summary_text = excluded.summary_text,
                facts_json = excluded.facts_json,
                last_session_id = excluded.last_session_id,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                summary,
                json.dumps(merged_facts, ensure_ascii=False),
                session_id,
            ),
        )
        self._sync_profile_from_chat_facts(connection, user_id, merged_facts)
        return merged_facts, summary

    def _extract_chat_facts(self, content: str) -> dict[str, object]:
        normalized = self._normalize_for_matching(content)
        facts: dict[str, object] = {}

        display_name = self._extract_display_name(content)
        if display_name:
            facts["display_name"] = display_name

        level = self._extract_level(normalized)
        if level:
            facts["level"] = level

        difficulty = (
            self._extract_difficulty(normalized)
            if self._has_preference_scope(normalized)
            else None
        )
        if difficulty:
            facts["preferred_difficulty"] = difficulty

        question_count = (
            self._extract_question_count(normalized)
            if self._has_preference_scope(normalized)
            else None
        )
        if question_count:
            facts["preferred_num_questions"] = question_count

        goals = self._extract_goals(normalized)
        if goals:
            facts["goals"] = goals

        content_themes = self._extract_content_themes(normalized)
        if content_themes:
            facts["content_themes"] = content_themes
            facts["preferred_content_theme"] = content_themes[0]

        mentioned_topics = self._extract_topics(normalized)
        if mentioned_topics:
            facts["recent_topics"] = mentioned_topics
            facts["last_topic_requested"] = mentioned_topics[0]

        if self._has_weakness_marker(normalized) and mentioned_topics:
            facts["weak_topics"] = mentioned_topics

        return facts

    def _merge_chat_facts(
        self,
        current_facts: dict[str, object],
        extracted_facts: dict[str, object],
    ) -> dict[str, object]:
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
            else:
                merged[key] = value
        return merged

    def _sync_profile_from_chat_facts(
        self,
        connection: sqlite3.Connection,
        user_id: int,
        facts: dict[str, object],
    ) -> None:
        connection.execute(
            """
            INSERT INTO user_profiles (user_id, level, goals_json)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO NOTHING
            """,
            (user_id, str(facts.get("level") or "beginner"), "[]"),
        )

        if facts.get("display_name"):
            connection.execute(
                """
                UPDATE users
                SET name = ?
                WHERE id = ?
                """,
                (str(facts["display_name"]), user_id),
            )

        profile_row = connection.execute(
            """
            SELECT
                level,
                goals_json,
                preferred_difficulty,
                preferred_num_questions,
                onboarding_completed
            FROM user_profiles
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        existing_goals = json.loads(profile_row["goals_json"] or "[]")
        goals = self._merge_unique_strings(
            existing_goals,
            self._as_string_list(facts.get("goals")),
        )
        connection.execute(
            """
            UPDATE user_profiles
            SET
                level = ?,
                goals_json = ?,
                preferred_difficulty = COALESCE(?, preferred_difficulty),
                preferred_num_questions = COALESCE(?, preferred_num_questions),
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (
                str(facts.get("level") or profile_row["level"] or "beginner"),
                json.dumps(goals, ensure_ascii=False),
                facts.get("preferred_difficulty"),
                facts.get("preferred_num_questions"),
                user_id,
            ),
        )

        for topic_code in self._as_string_list(facts.get("weak_topics")):
            normalized_topic = self._normalize_topic_code(topic_code)
            topic_id = self._ensure_topic(connection, normalized_topic)
            connection.execute(
                """
                INSERT INTO user_topic_stats (
                    user_id,
                    topic_id,
                    attempts_count,
                    correct_count,
                    accuracy,
                    weakness_score,
                    status,
                    last_practiced_at
                )
                VALUES (?, ?, 0, 0, 0.25, 0.75, 'chat_reported', CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, topic_id) DO UPDATE SET
                    weakness_score = MAX(weakness_score, excluded.weakness_score),
                    status = excluded.status,
                    last_practiced_at = CURRENT_TIMESTAMP
                """,
                (user_id, topic_id),
            )

    def _build_chat_memory_summary(self, facts: dict[str, object]) -> str:
        parts: list[str] = []
        if facts.get("display_name"):
            parts.append(f"name={facts['display_name']}")
        if facts.get("level"):
            parts.append(f"level={facts['level']}")
        if facts.get("goals"):
            parts.append(f"goals={', '.join(self._as_string_list(facts.get('goals')))}")
        if facts.get("weak_topics"):
            parts.append(
                "weak_topics="
                + ", ".join(self._as_string_list(facts.get("weak_topics")))
            )
        if facts.get("preferred_difficulty"):
            parts.append(f"preferred_difficulty={facts['preferred_difficulty']}")
        if facts.get("preferred_num_questions"):
            parts.append(f"preferred_num_questions={facts['preferred_num_questions']}")
        if facts.get("preferred_content_theme"):
            parts.append(f"preferred_content_theme={facts['preferred_content_theme']}")
        if facts.get("content_themes"):
            parts.append(
                "content_themes="
                + ", ".join(self._as_string_list(facts.get("content_themes")))
            )
        if facts.get("last_topic_requested"):
            parts.append(f"last_topic={facts['last_topic_requested']}")
        if facts.get("last_user_request"):
            parts.append(f"last_request={facts['last_user_request']}")
        return "; ".join(parts)

    def _build_suggested_next_question(
        self,
        facts: dict[str, object],
        messages: list[dict[str, object]],
    ) -> str:
        if not facts.get("display_name"):
            return "Minh nen goi ban la gi de luu vao bo nho hoc tap?"
        if not facts.get("level"):
            return "Trinh do hien tai cua ban la beginner, intermediate hay advanced?"
        if not facts.get("goals"):
            return "Muc tieu hoc chinh cua ban la gi: giao tiep, thi cu, ngu phap hay tu vung?"
        if not facts.get("weak_topics"):
            return "Ban hay sai nhat phan nao de minh uu tien bai luyen tiep theo?"
        if not facts.get("preferred_num_questions"):
            return "Moi lan luyen ban muon mac dinh bao nhieu cau?"
        if facts.get("last_topic_requested"):
            topic = self._label_from_code(str(facts["last_topic_requested"]))
            return f"Lan truoc ban dang quan tam {topic}. Ban muon luyen tiep chu de nay khong?"
        if messages:
            return "Minh da tai lai doan chat gan day. Ban muon tiep tuc tu noi dung cu hay doi chu de?"
        return "Ban muon luyen chu de nao hom nay?"

    def _extract_display_name(self, content: str) -> str | None:
        normalized = self._normalize_for_matching(content)
        patterns = [
            r"(?:tên tôi là|ten toi la|tôi tên là|toi ten la|mình tên là|minh ten la|mình tên|minh ten|tên mình là|ten minh la|tên em là|ten em la|tên anh là|ten anh la|tên chị là|ten chi la|gọi mình là|goi minh la|gọi tôi là|goi toi la|gọi em là|goi em la|gọi anh là|goi anh la|gọi chị là|goi chi la|gọi là|goi la|mình là|minh la|tôi là|toi la|em là|em la|anh là|anh la|chị là|chi la|call me|my name is|i am|i'm)\s+([^\n,.;!?]{1,40})",
        ]
        for source in [content, normalized]:
            for pattern in patterns:
                match = re.search(pattern, source, re.IGNORECASE)
                if not match:
                    continue
                candidate = self._clean_display_name_candidate(match.group(1))
                candidate_key = self._normalize_for_matching(candidate)
                if candidate and candidate_key not in {
                    "beginner",
                    "intermediate",
                    "advanced",
                    "easy",
                    "medium",
                    "hard",
                    "co ban",
                    "khong biet",
                    "chua biet",
                }:
                    return candidate.title()
        return None

    def _sanitize_display_name(self, raw_name: str | None, fallback: str) -> str:
        if not raw_name:
            return fallback
        return self._extract_display_name(raw_name) or raw_name

    def _clean_display_name_candidate(self, raw_candidate: str) -> str:
        candidate = re.split(r"[,.;!?\n]", raw_candidate, maxsplit=1)[0]
        candidate = " ".join(candidate.strip(" .,!?:;").split())
        candidate = re.sub(
            r"\s+(?:cũng được|cung duoc|được|duoc|đi|di|nhé|nhe|nha|ạ|a|ha|với|voi|thôi|thoi)$",
            "",
            candidate,
            flags=re.IGNORECASE,
        ).strip()
        candidate = re.sub(r"^(?:là|la)\s+", "", candidate, flags=re.IGNORECASE)
        return candidate[:40]

    def _extract_level(self, normalized: str) -> str | None:
        if any(token in normalized for token in ["advanced", "nang cao", "gioi"]):
            return "advanced"
        if any(
            token in normalized
            for token in ["intermediate", "trung cap", "trung binh", "vua"]
        ):
            return "intermediate"
        if any(
            token in normalized
            for token in ["beginner", "moi bat dau", "co ban", "mat goc"]
        ):
            return "beginner"
        return None

    def _extract_difficulty(self, normalized: str) -> str | None:
        if any(token in normalized for token in ["hard", "muc kho", "do kho kho"]):
            return "hard"
        if any(
            token in normalized
            for token in ["medium", "muc vua", "do kho vua", "muc trung binh"]
        ):
            return "medium"
        if any(token in normalized for token in ["easy", "muc de", "do kho de"]):
            return "easy"
        return None

    def _extract_question_count(self, normalized: str) -> int | None:
        match = re.search(
            r"\b(\d{1,2})\s*(?:cau|questions?|items?|bai)\b",
            normalized,
        )
        if not match:
            return None
        return max(1, min(int(match.group(1)), 20))

    def _extract_goals(self, normalized: str) -> list[str]:
        goal_map = {
            "daily_communication": ["giao tiep", "communication", "speaking"],
            "exam_preparation": ["toeic", "ielts", "thi", "kiem tra", "exam"],
            "grammar_foundation": ["ngu phap", "grammar"],
            "topic_vocabulary": ["tu vung", "vocabulary"],
            "travel_english": ["du lich", "travel", "san bay", "khach san"],
            "work_english": ["cong viec", "work", "business"],
            "writing_practice": ["viet", "writing"],
            "listening_practice": ["nghe", "listening"],
        }
        return [
            goal
            for goal, keywords in goal_map.items()
            if any(self._contains_keyword(normalized, keyword) for keyword in keywords)
        ]

    def _extract_content_themes(self, normalized: str) -> list[str]:
        theme_map = {
            "anime": ["anime", "manga", "otaku", "anime character", "episode"],
        }
        return [
            theme
            for theme, keywords in theme_map.items()
            if any(self._contains_keyword(normalized, keyword) for keyword in keywords)
        ]

    def _extract_topics(self, normalized: str) -> list[str]:
        topic_map = {
            "passive_voice": ["passive", "bi dong", "cau bi dong"],
            "relative_clause": ["relative", "quan he", "menh de quan he"],
            "conditional_sentence": ["conditional", "dieu kien", "cau dieu kien"],
            "reported_speech": ["reported", "gian tiep", "tuong thuat"],
            "tenses": ["tense", "thi hien tai", "thi qua khu", "thi tuong lai"],
            "prepositions": ["preposition", "gioi tu"],
            "travel_vocabulary": ["travel", "du lich", "san bay", "khach san"],
            "vocabulary": ["vocabulary", "tu vung"],
            "listening": ["listening", "nghe"],
            "writing": ["writing", "viet"],
        }
        topics: list[str] = []
        for topic_code, keywords in topic_map.items():
            if any(self._contains_keyword(normalized, keyword) for keyword in keywords):
                topics.append(topic_code)
        return topics

    def _contains_keyword(self, normalized: str, keyword: str) -> bool:
        return bool(re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", normalized))

    def _has_weakness_marker(self, normalized: str) -> bool:
        return any(
            marker in normalized
            for marker in [
                "hay sai",
                "thuong sai",
                "yeu",
                "kho",
                "loi",
                "quen",
                "confuse",
                "weak",
                "mistake",
                "struggle",
            ]
        )

    def _has_preference_scope(self, normalized: str) -> bool:
        return any(
            marker in normalized
            for marker in [
                "tu gio",
                "tu bay gio",
                "lan sau",
                "moi lan",
                "mac dinh",
                "uu tien",
                "toi muon",
                "minh muon",
                "i want",
                "prefer",
                "preference",
            ]
        )

    def _normalize_for_matching(self, value: str) -> str:
        normalized = value.replace("\u0111", "d").replace("\u0110", "D")
        normalized = unicodedata.normalize("NFD", normalized)
        normalized = "".join(
            character
            for character in normalized
            if unicodedata.category(character) != "Mn"
        )
        return normalized.lower().strip()

    def _normalize_topic_code(self, topic: str) -> str:
        normalized = self._normalize_for_matching(topic)
        normalized = normalized.replace("-", "_").replace(" ", "_")
        aliases = {
            "passive": "passive_voice",
            "bi_dong": "passive_voice",
            "relative": "relative_clause",
            "quan_he": "relative_clause",
            "conditional": "conditional_sentence",
            "dieu_kien": "conditional_sentence",
            "travel": "travel_vocabulary",
            "du_lich": "travel_vocabulary",
            "tu_vung": "vocabulary",
        }
        return aliases.get(normalized, normalized)

    def _merge_unique_strings(
        self,
        existing_values: list[object],
        incoming_values: list[object],
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
            return [str(item) for item in value if str(item).strip()]
        if isinstance(value, tuple):
            return [str(item) for item in value if str(item).strip()]
        return [str(value)] if str(value).strip() else []

    def _make_chat_title(self, content: str) -> str:
        normalized = " ".join(content.split())
        if len(normalized) <= 64:
            return normalized
        return f"{normalized[:61]}..."

    def _chat_session_summary_from_row(self, row: sqlite3.Row) -> dict[str, object]:
        title = row["title"] or self._make_chat_title(row["preview"] or "")
        return {
            "session_id": row["session_code"],
            "title": title or "Phien chat moi",
            "preview": row["preview"] or "",
            "message_count": int(row["message_count"] or 0),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _init_db(self) -> None:
        schema = self.schema_path.read_text(encoding="utf-8")
        with self._connect() as connection:
            connection.executescript(schema)
            self._ensure_column(
                connection,
                table_name="session_exercises",
                column_name="client_exercise_id",
                column_definition="TEXT",
            )
            self._ensure_column(
                connection,
                table_name="generation_runs",
                column_name="activity_id",
                column_definition="INTEGER",
            )
            self._ensure_column(
                connection,
                table_name="practice_sessions",
                column_name="activity_id",
                column_definition="INTEGER",
            )
            self._ensure_column(
                connection,
                table_name="chat_sessions",
                column_name="active_activity_id",
                column_definition="INTEGER",
            )
            self._ensure_column(
                connection,
                table_name="chat_sessions",
                column_name="pending_clarification_json",
                column_definition="TEXT",
            )
            self._ensure_column(
                connection,
                table_name="session_exercises",
                column_name="skill",
                column_definition="TEXT NOT NULL DEFAULT 'grammar'",
            )
            self._ensure_column(
                connection,
                table_name="session_exercises",
                column_name="subtopic",
                column_definition="TEXT",
            )
            self._ensure_column(
                connection,
                table_name="session_exercises",
                column_name="error_tag",
                column_definition="TEXT",
            )
            self._ensure_column(
                connection,
                table_name="seed_exercises",
                column_name="subtopic",
                column_definition="TEXT",
            )
            self._ensure_column(
                connection,
                table_name="seed_exercises",
                column_name="error_tag",
                column_definition="TEXT",
            )
            self._ensure_column(
                connection,
                table_name="user_profiles",
                column_name="preferred_num_questions",
                column_definition="INTEGER",
            )
            self._ensure_column(
                connection,
                table_name="user_profiles",
                column_name="onboarding_completed",
                column_definition="INTEGER NOT NULL DEFAULT 0",
            )
            self._seed_skill_graph(connection)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _ensure_user(self, connection: sqlite3.Connection, user_code: str) -> int:
        connection.execute(
            """
            INSERT INTO users (user_code)
            VALUES (?)
            ON CONFLICT(user_code) DO NOTHING
            """,
            (user_code,),
        )
        row = connection.execute(
            "SELECT id FROM users WHERE user_code = ?",
            (user_code,),
        ).fetchone()
        return int(row["id"])

    def _ensure_topic(self, connection: sqlite3.Connection, topic_code: str) -> int:
        connection.execute(
            """
            INSERT INTO topics (topic_code, name, skill)
            VALUES (?, ?, ?)
            ON CONFLICT(topic_code) DO NOTHING
            """,
            (
                topic_code,
                topic_code.replace("_", " ").title(),
                self._skill_for_topic(topic_code),
            ),
        )
        row = connection.execute(
            "SELECT id FROM topics WHERE topic_code = ?",
            (topic_code,),
        ).fetchone()
        return int(row["id"])

    def _get_activity_row_by_code(
        self,
        connection: sqlite3.Connection,
        user_id: int,
        activity_code: str,
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT
                la.*,
                u.user_code,
                la.conversation_id AS conversation_db_id,
                cs.session_code AS conversation_code,
                gr.generation_run_id AS public_generation_run_id,
                ps.session_code AS practice_session_code
            FROM learning_activities la
            JOIN users u ON u.id = la.user_id
            JOIN chat_sessions cs ON cs.id = la.conversation_id
            LEFT JOIN generation_runs gr ON gr.id = la.generation_run_id
            LEFT JOIN practice_sessions ps ON ps.id = la.practice_session_id
            WHERE la.user_id = ? AND la.activity_code = ?
            """,
            (user_id, activity_code),
        ).fetchone()

    def _get_activity_row_by_db_id(
        self,
        connection: sqlite3.Connection,
        user_id: int,
        activity_id: int,
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT
                la.*,
                u.user_code,
                la.conversation_id AS conversation_db_id,
                cs.session_code AS conversation_code,
                gr.generation_run_id AS public_generation_run_id,
                ps.session_code AS practice_session_code
            FROM learning_activities la
            JOIN users u ON u.id = la.user_id
            JOIN chat_sessions cs ON cs.id = la.conversation_id
            LEFT JOIN generation_runs gr ON gr.id = la.generation_run_id
            LEFT JOIN practice_sessions ps ON ps.id = la.practice_session_id
            WHERE la.user_id = ? AND la.id = ?
            """,
            (user_id, activity_id),
        ).fetchone()

    def _activity_from_row(self, row: sqlite3.Row | None) -> LearningActivity:
        if row is None:
            raise LookupError("Learning activity not found.")
        return LearningActivity(
            activity_id=row["activity_code"],
            conversation_id=row["conversation_code"],
            learner_id=row["user_code"],
            type=self._activity_type_from_value(row["activity_type"]),
            status=self._status_from_value(row["status"]),
            target_skills=[
                str(item)
                for item in self._json_value(row["target_skills_json"], [])
                if str(item).strip()
            ],
            difficulty=row["difficulty"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            submitted_at=row["submitted_at"],
            completed_at=row["completed_at"],
            updated_at=row["updated_at"],
            generation_run_id=row["public_generation_run_id"],
            session_code=row["practice_session_code"],
            metadata=self._json_object(row["metadata_json"]),
        )

    def _sync_active_activity(
        self,
        connection: sqlite3.Connection,
        conversation_id: int,
        activity_id: int,
        status: LearningActivityStatus,
    ) -> None:
        if self._is_terminal_activity_status(status):
            connection.execute(
                """
                UPDATE chat_sessions
                SET active_activity_id = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND active_activity_id = ?
                """,
                (conversation_id, activity_id),
            )
            return
        connection.execute(
            """
            UPDATE chat_sessions
            SET active_activity_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (activity_id, conversation_id),
        )

    def _record_activity_event(
        self,
        connection: sqlite3.Connection,
        activity_id: int,
        event_type: str,
        status: LearningActivityStatus,
        metadata: dict[str, object] | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO learning_activity_events (
                activity_id,
                event_type,
                status,
                metadata_json
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                activity_id,
                event_type,
                status.value,
                json.dumps(metadata or {}, ensure_ascii=False),
            ),
        )

    def _activity_type_value(self, activity_type: LearningActivityType | str) -> str:
        if isinstance(activity_type, LearningActivityType):
            return activity_type.value
        return str(activity_type)

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

    def _json_value(self, raw_value: str | None, default: object) -> object:
        if not raw_value:
            return default
        try:
            return json.loads(raw_value)
        except json.JSONDecodeError:
            return default

    def _json_object(self, raw_value: str | None) -> dict[str, object]:
        value = self._json_value(raw_value, {})
        return value if isinstance(value, dict) else {}

    def _clarification_payload(
        self,
        clarification: PendingClarification | None,
    ) -> dict[str, object] | None:
        if clarification is None:
            return None
        return {
            "pending_intent": clarification.pending_intent.value,
            "missing_fields": list(clarification.missing_fields),
            "collected_slots": self._json_safe_dict(clarification.collected_slots),
            "question": clarification.question,
        }

    def _clarification_from_payload(
        self,
        payload: object,
    ) -> PendingClarification | None:
        if not isinstance(payload, dict):
            return None
        try:
            pending_intent = ConversationIntent(str(payload.get("pending_intent")))
        except ValueError:
            return None
        missing_fields = payload.get("missing_fields")
        collected_slots = payload.get("collected_slots")
        return PendingClarification(
            pending_intent=pending_intent,
            missing_fields=[
                str(item)
                for item in (missing_fields if isinstance(missing_fields, list) else [])
            ],
            collected_slots=(
                dict(collected_slots) if isinstance(collected_slots, dict) else {}
            ),
            question=str(payload.get("question") or ""),
        )

    def _json_safe_dict(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            str(key): self._json_safe_value(value)
            for key, value in payload.items()
        }

    def _json_safe_value(self, value: object) -> object:
        if hasattr(value, "value"):
            return str(value.value)
        if isinstance(value, dict):
            return self._json_safe_dict(value)
        if isinstance(value, list):
            return [self._json_safe_value(item) for item in value]
        return value

    def _get_latest_generation_run(
        self,
        connection: sqlite3.Connection,
        user_id: int,
        topic_id: int,
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT id, topic_id, difficulty, activity_id
            FROM generation_runs
            WHERE user_id = ? AND topic_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id, topic_id),
        ).fetchone()

    def _get_generation_run_by_public_id(
        self,
        connection: sqlite3.Connection,
        user_id: int,
        generation_run_id: str,
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT id, topic_id, difficulty, activity_id
            FROM generation_runs
            WHERE user_id = ? AND generation_run_id = ?
            """,
            (user_id, generation_run_id),
        ).fetchone()

    def _save_user_answers(
        self,
        connection: sqlite3.Connection,
        user_id: int,
        session_id: int,
        generation_run_db_id: int,
        selected_answers: dict[str, str],
        answer_diagnoses: list[AnswerDiagnosis] | None = None,
    ) -> None:
        diagnosis_by_exercise = {
            diagnosis.exercise_id: diagnosis
            for diagnosis in answer_diagnoses or []
        }
        exercise_rows = connection.execute(
            """
            SELECT
                se.id,
                se.client_exercise_id,
                se.session_exercise_code,
                se.topic_id,
                se.exercise_type,
                se.difficulty,
                se.skill,
                se.subtopic,
                se.error_tag,
                se.correct_answer,
                t.topic_code
            FROM session_exercises se
            JOIN topics t ON t.id = se.topic_id
            WHERE se.generation_run_id = ?
            ORDER BY se.display_order, se.id
            """,
            (generation_run_db_id,),
        ).fetchall()

        for exercise_row in exercise_rows:
            exercise_id = (
                exercise_row["client_exercise_id"]
                or exercise_row["session_exercise_code"]
            )
            selected_answer = selected_answers.get(exercise_id)
            is_correct = self._answers_match(
                selected_answer,
                exercise_row["correct_answer"],
            )
            exercise_error_tag = exercise_row["error_tag"]
            cursor = connection.execute(
                """
                INSERT INTO user_answers (
                    session_id,
                    session_exercise_id,
                    selected_answer,
                    is_correct,
                    error_tag
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    int(exercise_row["id"]),
                    selected_answer,
                    int(is_correct),
                    None if is_correct else exercise_error_tag or "incorrect_answer",
                ),
            )
            user_answer_id = int(cursor.lastrowid)
            diagnosis = diagnosis_by_exercise.get(exercise_id)
            if diagnosis is not None:
                self._save_answer_diagnosis(
                    connection=connection,
                    user_answer_id=user_answer_id,
                    session_id=session_id,
                    session_exercise_id=int(exercise_row["id"]),
                    diagnosis=diagnosis,
                )
            self._update_subtopic_stats(
                connection=connection,
                user_id=user_id,
                topic_id=int(exercise_row["topic_id"]),
                subtopic=exercise_row["subtopic"],
                is_correct=is_correct,
            )
            self._update_error_stats(
                connection=connection,
                user_id=user_id,
                topic_id=int(exercise_row["topic_id"]),
                error_tag=exercise_error_tag,
                is_correct=is_correct,
            )
            self._update_skill_mastery(
                connection=connection,
                user_id=user_id,
                topic_id=int(exercise_row["topic_id"]),
                topic_code=str(exercise_row["topic_code"]),
                skill_type=str(exercise_row["skill"] or ""),
                subtopic=exercise_row["subtopic"],
                difficulty=exercise_row["difficulty"],
                error_tag=exercise_error_tag,
                session_id=session_id,
                session_exercise_id=int(exercise_row["id"]),
                is_correct=is_correct,
            )

    def _update_subtopic_stats(
        self,
        connection: sqlite3.Connection,
        user_id: int,
        topic_id: int,
        subtopic: str | None,
        is_correct: bool,
    ) -> None:
        if not subtopic:
            return

        existing = connection.execute(
            """
            SELECT attempts_count, correct_count
            FROM user_subtopic_stats
            WHERE user_id = ? AND topic_id = ? AND subtopic = ?
            """,
            (user_id, topic_id, subtopic),
        ).fetchone()
        attempts_count = 1
        correct_count = int(is_correct)
        if existing is not None:
            attempts_count += int(existing["attempts_count"])
            correct_count += int(existing["correct_count"])

        accuracy = correct_count / max(attempts_count, 1)
        confidence = min(attempts_count / 5, 1.0)
        mastery_score = accuracy * confidence
        weakness_score = 1.0 - mastery_score

        connection.execute(
            """
            INSERT INTO user_subtopic_stats (
                user_id,
                topic_id,
                subtopic,
                attempts_count,
                correct_count,
                accuracy,
                mastery_score,
                weakness_score,
                status,
                last_practiced_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, topic_id, subtopic) DO UPDATE SET
                attempts_count = excluded.attempts_count,
                correct_count = excluded.correct_count,
                accuracy = excluded.accuracy,
                mastery_score = excluded.mastery_score,
                weakness_score = excluded.weakness_score,
                status = excluded.status,
                last_practiced_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                topic_id,
                subtopic,
                attempts_count,
                correct_count,
                accuracy,
                mastery_score,
                weakness_score,
                self._status_from_accuracy(accuracy),
            ),
        )

    def _save_answer_diagnosis(
        self,
        connection: sqlite3.Connection,
        user_answer_id: int,
        session_id: int,
        session_exercise_id: int,
        diagnosis: AnswerDiagnosis,
    ) -> None:
        connection.execute(
            """
            INSERT INTO answer_diagnoses (
                user_answer_id,
                session_id,
                session_exercise_id,
                error_type,
                skill_code,
                topic_code,
                subtopic,
                subtype,
                severity,
                mastery_impact,
                explanation,
                evidence_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_answer_id) DO UPDATE SET
                error_type = excluded.error_type,
                skill_code = excluded.skill_code,
                topic_code = excluded.topic_code,
                subtopic = excluded.subtopic,
                subtype = excluded.subtype,
                severity = excluded.severity,
                mastery_impact = excluded.mastery_impact,
                explanation = excluded.explanation,
                evidence_json = excluded.evidence_json
            """,
            (
                user_answer_id,
                session_id,
                session_exercise_id,
                diagnosis.error_type,
                diagnosis.skill_id,
                diagnosis.topic,
                diagnosis.subtopic,
                diagnosis.subtype,
                diagnosis.severity,
                diagnosis.mastery_impact,
                diagnosis.explanation,
                json.dumps(diagnosis.evidence, ensure_ascii=False),
            ),
        )

    def _update_error_stats(
        self,
        connection: sqlite3.Connection,
        user_id: int,
        topic_id: int,
        error_tag: str | None,
        is_correct: bool,
    ) -> None:
        if not error_tag:
            return

        existing = connection.execute(
            """
            SELECT attempts_count, incorrect_count
            FROM user_error_stats
            WHERE user_id = ? AND topic_id = ? AND error_tag = ?
            """,
            (user_id, topic_id, error_tag),
        ).fetchone()
        attempts_count = 1
        incorrect_count = 0 if is_correct else 1
        if existing is not None:
            attempts_count += int(existing["attempts_count"])
            incorrect_count += int(existing["incorrect_count"])

        error_rate = incorrect_count / max(attempts_count, 1)
        connection.execute(
            """
            INSERT INTO user_error_stats (
                user_id,
                topic_id,
                error_tag,
                attempts_count,
                incorrect_count,
                error_rate,
                weakness_score,
                status,
                last_seen_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, topic_id, error_tag) DO UPDATE SET
                attempts_count = excluded.attempts_count,
                incorrect_count = excluded.incorrect_count,
                error_rate = excluded.error_rate,
                weakness_score = excluded.weakness_score,
                status = excluded.status,
                last_seen_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                topic_id,
                error_tag,
                attempts_count,
                incorrect_count,
                error_rate,
                error_rate,
                self._status_from_error_rate(error_rate),
            ),
        )

    def _update_skill_mastery(
        self,
        connection: sqlite3.Connection,
        user_id: int,
        topic_id: int,
        topic_code: str,
        skill_type: str,
        subtopic: str | None,
        difficulty: str | None,
        error_tag: str | None,
        session_id: int,
        session_exercise_id: int,
        is_correct: bool,
    ) -> None:
        node = self.skill_graph.resolve(
            topic=topic_code,
            skill_type=skill_type or self._skill_for_topic(topic_code),
            subtopic=subtopic,
        )
        skill_id = self._ensure_skill(connection, node)
        existing = connection.execute(
            """
            SELECT
                mastery_probability,
                attempts_count,
                correct_count,
                incorrect_count,
                difficulty_history_json,
                error_frequency_json
            FROM user_skill_mastery
            WHERE user_id = ? AND skill_id = ?
            """,
            (user_id, skill_id),
        ).fetchone()

        prior_mastery = (
            float(existing["mastery_probability"])
            if existing is not None
            else self.knowledge_tracer.parameters.initial_mastery
        )
        attempts_count = 1
        correct_count = int(is_correct)
        incorrect_count = 0 if is_correct else 1
        difficulty_history: list[str] = []
        error_frequency: dict[str, int] = {}

        if existing is not None:
            attempts_count += int(existing["attempts_count"])
            correct_count += int(existing["correct_count"])
            incorrect_count += int(existing["incorrect_count"])
            difficulty_history = self._json_list(
                existing["difficulty_history_json"],
            )
            error_frequency = self._json_dict(
                existing["error_frequency_json"],
            )

        if difficulty:
            difficulty_history = [*difficulty_history, str(difficulty)][-20:]
        if error_tag and not is_correct:
            error_frequency[error_tag] = int(error_frequency.get(error_tag, 0)) + 1

        repeated_error_count = max(error_frequency.values(), default=0)
        posterior_mastery = self.knowledge_tracer.update(
            prior_mastery,
            is_correct,
            attempts_count=max(attempts_count - 1, 0),
            repeated_error_count=repeated_error_count,
        )
        confidence = min(attempts_count / 8, 1.0)
        connection.execute(
            """
            INSERT INTO user_skill_mastery (
                user_id,
                skill_id,
                topic_id,
                mastery_probability,
                attempts_count,
                correct_count,
                incorrect_count,
                confidence,
                difficulty_history_json,
                error_frequency_json,
                status,
                last_practiced_at,
                next_review_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, skill_id) DO UPDATE SET
                topic_id = excluded.topic_id,
                mastery_probability = excluded.mastery_probability,
                attempts_count = excluded.attempts_count,
                correct_count = excluded.correct_count,
                incorrect_count = excluded.incorrect_count,
                confidence = excluded.confidence,
                difficulty_history_json = excluded.difficulty_history_json,
                error_frequency_json = excluded.error_frequency_json,
                status = excluded.status,
                last_practiced_at = CURRENT_TIMESTAMP,
                next_review_at = excluded.next_review_at,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                skill_id,
                topic_id,
                posterior_mastery,
                attempts_count,
                correct_count,
                incorrect_count,
                confidence,
                json.dumps(difficulty_history, ensure_ascii=False),
                json.dumps(error_frequency, ensure_ascii=False),
                self._status_from_mastery(posterior_mastery),
                next_review_at(posterior_mastery, confidence),
            ),
        )
        connection.execute(
            """
            INSERT INTO user_skill_mastery_history (
                user_id,
                skill_id,
                topic_id,
                session_id,
                session_exercise_id,
                is_correct,
                prior_mastery,
                posterior_mastery,
                difficulty,
                error_tag
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                skill_id,
                topic_id,
                session_id,
                session_exercise_id,
                int(is_correct),
                prior_mastery,
                posterior_mastery,
                difficulty,
                None if is_correct else error_tag,
            ),
        )

    def _ensure_column(
        self,
        connection: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_definition: str,
    ) -> None:
        columns = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name not in columns:
            connection.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
            )

    def _seed_skill_graph(self, connection: sqlite3.Connection) -> None:
        for node in self.skill_graph.nodes.values():
            self._ensure_skill(connection, node)

    def _ensure_skill(
        self,
        connection: sqlite3.Connection,
        node: SkillNode,
    ) -> int:
        topic_id = self._ensure_topic(connection, node.topic)
        connection.execute(
            """
            INSERT INTO skills (
                skill_code,
                topic_id,
                parent_skill_code,
                name,
                skill_type,
                cefr,
                description,
                prerequisites_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(skill_code) DO UPDATE SET
                topic_id = excluded.topic_id,
                parent_skill_code = excluded.parent_skill_code,
                name = excluded.name,
                skill_type = excluded.skill_type,
                cefr = excluded.cefr,
                description = excluded.description,
                prerequisites_json = excluded.prerequisites_json
            """,
            (
                node.skill_id,
                topic_id,
                node.parent_id,
                node.label,
                node.skill_type,
                node.cefr,
                node.description,
                json.dumps(list(node.prerequisites), ensure_ascii=False),
            ),
        )
        row = connection.execute(
            "SELECT id FROM skills WHERE skill_code = ?",
            (node.skill_id,),
        ).fetchone()
        skill_id = int(row["id"])

        for prerequisite_code in node.prerequisites:
            prerequisite_id = self._ensure_skill(
                connection,
                self.skill_graph.get(prerequisite_code),
            )
            connection.execute(
                """
                INSERT INTO skill_dependencies (
                    prerequisite_skill_id,
                    dependent_skill_id,
                    relation_type
                )
                VALUES (?, ?, 'prerequisite')
                ON CONFLICT(prerequisite_skill_id, dependent_skill_id, relation_type)
                DO NOTHING
                """,
                (prerequisite_id, skill_id),
            )

        return skill_id

    def _json_list(self, raw_value: str | None) -> list[str]:
        if not raw_value:
            return []
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError:
            return []
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if str(item).strip()]

    def _json_dict(self, raw_value: str | None) -> dict[str, int]:
        if not raw_value:
            return {}
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError:
            return {}
        if not isinstance(value, dict):
            return {}
        cleaned: dict[str, int] = {}
        for key, count in value.items():
            try:
                cleaned[str(key)] = int(count)
            except (TypeError, ValueError):
                continue
        return cleaned

    def _stat_key(self, topic_code: str, detail_code: str) -> str:
        return f"{topic_code}:{detail_code}"

    def _label_from_code(self, code: str | None) -> str:
        if not code:
            return "Unknown"
        return str(code).replace("_", " ").title()

    def _answers_match(self, selected_answer: str | None, correct_answer: str) -> bool:
        return self.text_normalizer.answers_match(selected_answer, correct_answer)

    def _skill_for_topic(self, topic_code: str) -> str:
        if "vocabulary" in topic_code:
            return "vocabulary"
        return "grammar"

    def _status_from_accuracy(self, accuracy: float) -> str:
        if accuracy < 0.6:
            return "weak"
        if accuracy < 0.8:
            return "needs_practice"
        return "can_increase_difficulty"

    def _status_from_error_rate(self, error_rate: float) -> str:
        if error_rate >= 0.5:
            return "active_error"
        if error_rate >= 0.2:
            return "watch"
        return "improving"

    def _status_from_mastery(self, mastery: float) -> str:
        if mastery < 0.4:
            return "weak"
        if mastery < 0.65:
            return "learning"
        if mastery < 0.85:
            return "review"
        return "mastered"
