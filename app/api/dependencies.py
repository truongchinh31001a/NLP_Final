from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Response

from app.activities.literacy_service import WritingActivitySubmission
from app.activities.practice_service import PracticeActivitySubmission
from app.api.schemas import (
    ActivitySubmitResponseModel,
    ConversationMessageTurnResponseModel,
    ConversationRouteResponseModel,
    RecommendationListResponseModel,
    UpdateUserProfileRequestModel,
    UserProfileResponseModel,
)
from app.auth.service import AuthContext
from app.conversation.schemas import ConversationRoute, ConversationTurnResult
from app.retrieval.knowledge_loader import load_knowledge_chunk_records
from app.schemas import (
    ActivityRecommendation,
    LearningActivityType,
    PendingClarification,
    PracticeRequest,
)


def get_pipeline():
    from app.api import main as api_main

    return api_main.pipeline


def get_auth_service():
    from app.api import main as api_main

    return api_main.auth_service


def profile_response(user_id: str) -> UserProfileResponseModel:
    pipeline = get_pipeline()
    return UserProfileResponseModel(**asdict(pipeline.repository.get_profile(user_id)))


def update_profile_response(
    user_id: str,
    payload: UpdateUserProfileRequestModel,
) -> UserProfileResponseModel:
    pipeline = get_pipeline()
    profile = pipeline.repository.get_profile(user_id)

    if payload.display_name is not None:
        profile.display_name = payload.display_name.strip() or user_id
    if payload.level is not None:
        profile.level = normalize_level(payload.level)
    if payload.goals:
        profile.goals = clean_list(payload.goals)
    if payload.preferred_difficulty is not None:
        profile.preferred_difficulty = normalize_difficulty(
            payload.preferred_difficulty
        )
    if payload.preferred_num_questions is not None:
        profile.preferred_num_questions = payload.preferred_num_questions

    for topic in clean_list(payload.weak_topics):
        topic_code = normalize_topic(topic)
        profile.topic_accuracy.setdefault(topic_code, 0.25)
        profile.weak_topics[topic_code] = max(
            profile.weak_topics.get(topic_code, 0.0),
            0.75,
        )

    profile.onboarding_completed = payload.onboarding_completed
    pipeline.repository.save_profile(profile)
    return profile_response(user_id)


def recommendation_list_response(
    user_id: str,
    limit: int,
) -> RecommendationListResponseModel:
    pipeline = get_pipeline()
    return RecommendationListResponseModel(
        recommendations=[
            recommendation_payload(recommendation)
            for recommendation in pipeline.list_recommendations(
                user_id=user_id,
                limit=limit,
            )
        ],
    )


def get_activity_or_404(
    user_id: str,
    activity_id: str,
):
    pipeline = get_pipeline()
    activity = pipeline.repository.get_learning_activity(user_id, activity_id)
    if activity is None:
        raise HTTPException(
            status_code=404,
            detail=f"Learning activity not found: {activity_id}",
        )
    return activity


def learning_activity_payload(activity) -> dict:
    pipeline = get_pipeline()
    payload = {
        **asdict(activity),
        "request": None,
        "plan": None,
        "exercises": [],
        "result": None,
        "recommendation": "",
        "next_activity_suggestion": None,
        "ui_action": activity_open_ui_action(activity.type),
    }

    generated = None
    if activity.generation_run_id:
        generated = pipeline.repository.get_generated_exercise_set(
            activity.learner_id,
            activity.generation_run_id,
        )
        if generated is not None:
            payload.update(
                {
                    "request": asdict(generated.request),
                    "plan": asdict(generated.plan),
                    "exercises": [
                        asdict(exercise) for exercise in generated.exercises
                    ],
                }
            )

    result = None
    if activity.session_code:
        result = pipeline.repository.get_session_result(
            activity.learner_id,
            activity.session_code,
        )
        if result is not None:
            payload["result"] = asdict(result)
            payload["recommendation"] = result.recommendation

    if generated is not None and result is not None:
        try:
            payload["next_activity_suggestion"] = recommendation_payload(
                pipeline.recommendation.recommendation_for_activity(
                    user_id=activity.learner_id,
                    repository=pipeline.repository,
                    activity=activity,
                )
            )
        except LookupError:
            payload["next_activity_suggestion"] = None

    return payload


def activity_open_ui_action(activity_type: LearningActivityType | str) -> str:
    if activity_type == LearningActivityType.READING:
        return "reading.open"
    if activity_type == LearningActivityType.WRITING:
        return "writing.open"
    if activity_type == LearningActivityType.PRACTICE:
        return "practice.open"
    return "activity.open"


def personalization_snapshot_payload(user_id: str) -> dict:
    pipeline = get_pipeline()
    snapshot = pipeline.repository.get_personalization_snapshot(user_id)
    profile = pipeline.repository.get_profile(user_id)
    next_plan = pipeline.personalization.build_plan(
        PracticeRequest(
            user_id=user_id,
            raw_text="continue personalized practice",
            processing_text="continue personalized practice",
            detected_language="en",
        ),
        profile,
    )
    return {
        **snapshot,
        "next_plan": asdict(next_plan),
    }


def list_of_dicts(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def clean_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        normalized = " ".join(value.strip().split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            cleaned.append(normalized)
    return cleaned


def authorize_user(
    user_id: str,
    authorization: str | None,
) -> AuthContext:
    try:
        return get_auth_service().authorize(user_id, authorization)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def authorize_ops_request(
    user_id: str | None,
    authorization: str | None,
) -> None:
    auth_service = get_auth_service()
    if not auth_service.requires_authentication:
        return
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="user_id is required when auth is enabled.",
        )
    authorize_user(user_id, authorization)


def require_debug_endpoint_enabled() -> None:
    pipeline = get_pipeline()
    if not pipeline.config.debug_endpoints_enabled:
        raise HTTPException(status_code=404, detail="Debug endpoints are disabled.")


def conversation_turn_response(
    result: ConversationTurnResult,
) -> ConversationMessageTurnResponseModel:
    return ConversationMessageTurnResponseModel(
        conversation_id=result.conversation_id,
        message=result.message,
        intent=result.intent,
        assistant_reply=result.assistant_reply,
        pending_clarification=pending_clarification_payload(
            result.pending_clarification,
        ),
        activity=result.activity,
        ui_action=result.ui_action,
        assistant_message=result.assistant_message,
        route=conversation_route_response(result.route),
    )


def practice_generation_activity_payload(
    practice_activity,
) -> dict:
    generated = practice_activity.generated
    return {
        **asdict(practice_activity.activity),
        "request": asdict(generated.request),
        "plan": asdict(generated.plan),
        "exercises": [asdict(exercise) for exercise in generated.exercises],
        "recommendation": practice_activity.recommendation,
        "next_activity_suggestion": None,
    }


def recommendation_payload(recommendation: ActivityRecommendation) -> dict:
    return asdict(recommendation)


def activity_submit_response(
    submission: PracticeActivitySubmission,
) -> ActivitySubmitResponseModel:
    result_payload = asdict(submission.result)
    exercises = [asdict(exercise) for exercise in submission.generated.exercises]
    activity_payload = {
        **asdict(submission.activity),
        "request": asdict(submission.generated.request),
        "plan": asdict(submission.generated.plan),
        "exercises": exercises,
        "result": result_payload,
        "recommendation": submission.result.recommendation,
        "next_activity_suggestion": submission.next_activity_suggestion,
    }
    return ActivitySubmitResponseModel(
        activity=activity_payload,
        result=result_payload,
        exercises=exercises,
        answers=[
            {"exercise_id": exercise_id, "selected_answer": selected_answer}
            for exercise_id, selected_answer in submission.selected_answers.items()
        ],
        next_activity_suggestion=submission.next_activity_suggestion,
        ui_action=(
            "reading.result"
            if submission.activity.type == LearningActivityType.READING
            else "practice.result"
        ),
    )


def writing_activity_submit_response(
    submission: WritingActivitySubmission,
) -> ActivitySubmitResponseModel:
    result_payload = asdict(submission.result)
    activity_payload = {
        **asdict(submission.activity),
        "request": None,
        "plan": None,
        "exercises": [],
        "result": result_payload,
        "recommendation": submission.result.recommendation,
        "next_activity_suggestion": submission.next_activity_suggestion,
    }
    return ActivitySubmitResponseModel(
        activity=activity_payload,
        result=result_payload,
        exercises=[],
        answers=[],
        next_activity_suggestion=submission.next_activity_suggestion,
        ui_action="writing.result",
    )


def pending_clarification_payload(
    clarification: PendingClarification | None,
) -> dict | None:
    if clarification is None:
        return None
    return {
        "pending_intent": clarification.pending_intent,
        "missing_fields": clarification.missing_fields,
        "collected_slots": clarification.collected_slots,
        "question": clarification.question,
    }


def conversation_route_response(
    route: ConversationRoute | None,
) -> ConversationRouteResponseModel | None:
    if route is None:
        return None
    return ConversationRouteResponseModel(
        intent=route.intent,
        confidence=route.confidence,
        source=route.source,
        reason=route.reason,
        slots=route.slots,
        missing_slots=(
            route.pending_clarification.missing_fields
            if route.pending_clarification is not None
            else []
        ),
        referenced_activity_id=(
            str(route.slots["activity_id"]) if route.slots.get("activity_id") else None
        ),
        needs_clarification=route.needs_clarification,
        clarification_question=route.clarification_question,
    )


def set_legacy_endpoint_headers(response: Response, message: str) -> None:
    response.headers["Deprecation"] = "true"
    response.headers["Warning"] = f'299 - "{message}"'


def build_chroma_debug_snapshot() -> dict:
    pipeline = get_pipeline()
    config = pipeline.config
    persist_directory = str(Path(config.chroma_persist_directory))
    raw_knowledge_path = str(Path(config.knowledge_chunks_path))
    ingest_command = (
        "python scripts/ingest_knowledge_chunks.py "
        f"--persist-dir {persist_directory} "
        f"--collection {config.chroma_collection_name}"
    )
    raw_knowledge_count = safe_raw_knowledge_count(config.knowledge_chunks_path)
    base_snapshot = {
        "configured_backend": config.vector_store_backend,
        "retrieval_mode": config.retrieval_mode,
        "embedding_backend": config.embedding_backend,
        "reranker_enabled": config.reranker_enabled,
        "using_chroma_backend": config.vector_store_backend.lower() == "chroma",
        "collection_name": config.chroma_collection_name,
        "persist_directory": persist_directory,
        "raw_knowledge_path": raw_knowledge_path,
        "raw_knowledge_count": raw_knowledge_count,
        "ingest_command": ingest_command,
        "topic_counts": {},
        "level_counts": {},
        "sample_chunks": [],
        "total_chunks": 0,
    }

    if config.vector_store_backend.lower() != "chroma":
        return {
            **base_snapshot,
            "is_available": True,
            "status_message": (
                f"Vector backend is {config.vector_store_backend}; "
                "Chroma collection debug is not applicable."
            ),
            "error": None,
        }

    try:
        from langchain_chroma import Chroma

        from app.retrieval.embeddings import build_embedding_model

        vector_store = Chroma(
            collection_name=config.chroma_collection_name,
            embedding_function=build_embedding_model(config),
            persist_directory=persist_directory,
        )
        payload = vector_store.get(include=["metadatas", "documents"])
    except Exception as exc:  # pragma: no cover - defensive debug endpoint
        return {
            **base_snapshot,
            "is_available": False,
            "status_message": "Khong doc duoc Chroma collection.",
            "error": str(exc),
        }

    ids = payload.get("ids") or []
    metadatas = payload.get("metadatas") or []
    documents = payload.get("documents") or []
    topic_counts = Counter(
        str(metadata.get("topic") or metadata.get("topic_code") or "unknown")
        for metadata in metadatas
        if isinstance(metadata, dict)
    )
    level_counts = Counter(
        str(metadata.get("level") or "unknown")
        for metadata in metadatas
        if isinstance(metadata, dict)
    )
    sample_chunks = [
        chroma_debug_chunk(
            chunk_id=str(chunk_id),
            metadata=metadata if isinstance(metadata, dict) else {},
            document=str(document or ""),
        )
        for chunk_id, metadata, document in list(zip(ids, metadatas, documents))[:8]
    ]

    is_available = bool(ids)
    status_message = (
        "Chroma collection da co du lieu."
        if is_available
        else "Chroma collection dang rong. Hay chay ingest command truoc khi demo."
    )
    return {
        **base_snapshot,
        "is_available": is_available,
        "status_message": status_message,
        "total_chunks": len(ids),
        "topic_counts": dict(sorted(topic_counts.items())),
        "level_counts": dict(sorted(level_counts.items())),
        "sample_chunks": sample_chunks,
        "error": None,
    }


def safe_raw_knowledge_count(path: str) -> int:
    try:
        return len(load_knowledge_chunk_records(path))
    except Exception:
        return 0


def chroma_debug_chunk(
    *,
    chunk_id: str,
    metadata: dict,
    document: str,
) -> dict:
    preview = " ".join(document.split())
    return {
        "chunk_id": str(metadata.get("chunk_id") or chunk_id),
        "topic": str(metadata.get("topic") or metadata.get("topic_code") or "unknown"),
        "subtopic": (
            str(metadata.get("subtopic"))
            if metadata.get("subtopic") is not None
            else None
        ),
        "level": str(metadata.get("level") or "unknown"),
        "skill": (
            str(metadata.get("skill"))
            if metadata.get("skill") is not None
            else None
        ),
        "source": (
            str(metadata.get("source"))
            if metadata.get("source") is not None
            else None
        ),
        "content_preview": preview[:220],
    }


def normalize_level(level: str) -> str:
    normalized = level.strip().lower()
    if normalized in {"beginner", "intermediate", "advanced"}:
        return normalized
    return "beginner"


def normalize_difficulty(difficulty: str) -> str:
    normalized = difficulty.strip().lower()
    if normalized in {"easy", "medium", "hard"}:
        return normalized
    return "easy"


def normalize_topic(topic: str) -> str:
    normalized = topic.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "passive": "passive_voice",
        "cau_bi_dong": "passive_voice",
        "bi_dong": "passive_voice",
        "relative": "relative_clause",
        "menh_de_quan_he": "relative_clause",
        "conditional": "conditional_sentence",
        "cau_dieu_kien": "conditional_sentence",
        "reported": "reported_speech",
        "reported_speech": "reported_speech",
        "cau_gian_tiep": "reported_speech",
        "gian_tiep": "reported_speech",
        "preposition": "prepositions",
        "prepositions": "prepositions",
        "gioi_tu": "prepositions",
        "travel": "travel_vocabulary",
        "tu_vung_du_lich": "travel_vocabulary",
        "tu_vung": "vocabulary",
    }
    return aliases.get(normalized, normalized)


def practice_request_overrides(
    payload,
) -> PracticeRequest | None:
    if not any(
        [
            payload.topic,
            payload.difficulty,
            payload.exercise_type,
            payload.num_questions,
            payload.target_subtopic,
            payload.content_theme,
        ]
    ):
        return None
    return PracticeRequest(
        user_id=payload.user_id,
        raw_text=payload.message,
        processing_text="",
        detected_language="en",
        topic=payload.topic,
        difficulty=payload.difficulty,
        exercise_type=payload.exercise_type,
        num_questions=payload.num_questions,
        target_subtopic=payload.target_subtopic,
        content_theme=payload.content_theme,
    )
