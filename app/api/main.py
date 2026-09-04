import os
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.schemas import (
    AcceptRecommendationRequestModel,
    ActivitySubmitResponseModel,
    AuthTokenRequestModel,
    AuthTokenResponseModel,
    ChatMemoryResponseModel,
    ConversationDetailResponseModel,
    ConversationListResponseModel,
    ConversationMessageTurnResponseModel,
    ConversationRouteResponseModel,
    ChatSessionListResponseModel,
    ChromaDebugResponseModel,
    CreateConversationRequestModel,
    GeneratePracticeRequestModel,
    GeneratePracticeResponseModel,
    HealthResponseModel,
    InterpretOnboardingRequestModel,
    InterpretOnboardingResponseModel,
    InterpretPracticeRequestModel,
    InterpretPracticeResponseModel,
    MetricsResponseModel,
    PersonalizationSnapshotResponseModel,
    RecommendationAcceptResponseModel,
    RecommendationListResponseModel,
    SaveChatMessageRequestModel,
    SaveChatMessageResponseModel,
    ScorePracticeRequestModel,
    ScorePracticeResponseModel,
    SendConversationMessageRequestModel,
    SubmitActivityRequestModel,
    UpdateUserProfileRequestModel,
    UserProfileResponseModel,
    WorkflowGraphResponseModel,
)
from app.auth.service import AuthContext, AuthService
from app.activities.practice_service import PracticeActivitySubmission
from app.bootstrap import build_baseline_pipeline
from app.conversation.schemas import ConversationRoute, ConversationTurnResult
from app.observability.metrics import metrics_registry
from app.observability.tracing import get_tracer, setup_tracing
from app.retrieval.knowledge_loader import load_knowledge_chunk_records
from app.schemas import (
    ActivityRecommendation,
    PendingClarification,
    PracticeRequest,
    SubmittedAnswer,
)

app = FastAPI(
    title="Personalized English Exercise Chatbot API",
    version="0.1.0",
)

pipeline = build_baseline_pipeline()
auth_service = AuthService(pipeline.config)
setup_tracing(pipeline.config)
tracer = get_tracer(__name__)

allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def observe_http_request(request: Request, call_next):
    started_at = perf_counter()
    status_code = 500
    with tracer.start_as_current_span("http.request") as span:
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            route = request.scope.get("route")
            route_path = getattr(route, "path", request.url.path)
            span.set_attribute("http.request.method", request.method)
            span.set_attribute("http.route", route_path)
            span.set_attribute("http.response.status_code", status_code)
            if pipeline.config.observability_enabled:
                labels = {
                    "method": request.method,
                    "path": route_path,
                    "status": status_code,
                }
                metrics_registry.increment("http_requests_total", labels)
                metrics_registry.observe(
                    "http_request_duration_ms",
                    (perf_counter() - started_at) * 1000,
                    labels,
                )


@app.get("/api/health", response_model=HealthResponseModel)
def healthcheck() -> HealthResponseModel:
    return HealthResponseModel(
        status="ok",
        generator_backend=pipeline.generator.backend_name,
        repository_backend=pipeline.config.learning_repository_backend,
        vector_store_backend=pipeline.config.vector_store_backend,
        auth_mode=pipeline.config.auth_mode,
        observability_enabled=pipeline.config.observability_enabled,
        otel_enabled=pipeline.config.otel_enabled,
    )


@app.post("/api/auth/dev-token", response_model=AuthTokenResponseModel)
def create_dev_auth_token(payload: AuthTokenRequestModel) -> AuthTokenResponseModel:
    return AuthTokenResponseModel(
        access_token=auth_service.issue_token(payload.user_id),
        user_id=payload.user_id,
        expires_in_seconds=pipeline.config.auth_token_ttl_seconds,
    )


@app.get("/api/debug/metrics", response_model=MetricsResponseModel)
def debug_metrics() -> MetricsResponseModel:
    return MetricsResponseModel(**metrics_registry.snapshot())


@app.get("/api/debug/workflow", response_model=WorkflowGraphResponseModel)
def debug_workflow() -> WorkflowGraphResponseModel:
    return WorkflowGraphResponseModel(**pipeline.workflow_graph.as_dict())


@app.get("/api/debug/chroma", response_model=ChromaDebugResponseModel)
def debug_chroma() -> ChromaDebugResponseModel:
    return ChromaDebugResponseModel(**_build_chroma_debug_snapshot())


@app.post("/api/conversations", response_model=ConversationDetailResponseModel)
def create_conversation(
    payload: CreateConversationRequestModel,
    authorization: str | None = Header(default=None),
) -> ConversationDetailResponseModel:
    _authorize_user(payload.user_id, authorization)
    return ConversationDetailResponseModel(
        **pipeline.create_conversation(payload.user_id),
    )


@app.get("/api/conversations", response_model=ConversationListResponseModel)
def list_conversations(
    user_id: str = Query(min_length=1),
    limit: int = Query(default=20, ge=1, le=50),
    authorization: str | None = Header(default=None),
) -> ConversationListResponseModel:
    _authorize_user(user_id, authorization)
    return ConversationListResponseModel(
        **pipeline.list_conversations(user_id, limit=limit),
    )


@app.get(
    "/api/conversations/{conversation_id}",
    response_model=ConversationDetailResponseModel,
)
def get_conversation(
    conversation_id: str,
    user_id: str = Query(min_length=1),
    limit: int = Query(default=24, ge=1, le=100),
    authorization: str | None = Header(default=None),
) -> ConversationDetailResponseModel:
    _authorize_user(user_id, authorization)
    try:
        return ConversationDetailResponseModel(
            **pipeline.get_conversation(
                user_id,
                conversation_id,
                limit=limit,
            ),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/api/conversations/{conversation_id}/messages",
    response_model=ConversationMessageTurnResponseModel,
)
def send_conversation_message(
    conversation_id: str,
    payload: SendConversationMessageRequestModel,
    authorization: str | None = Header(default=None),
) -> ConversationMessageTurnResponseModel:
    _authorize_user(payload.user_id, authorization)
    try:
        result = pipeline.handle_conversation_message(
            user_id=payload.user_id,
            conversation_id=conversation_id,
            message=payload.message,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _conversation_turn_response(result)


@app.get("/api/recommendations", response_model=RecommendationListResponseModel)
def list_recommendations(
    user_id: str = Query(min_length=1),
    limit: int = Query(default=5, ge=1, le=20),
    authorization: str | None = Header(default=None),
) -> RecommendationListResponseModel:
    _authorize_user(user_id, authorization)
    return RecommendationListResponseModel(
        recommendations=[
            _recommendation_payload(recommendation)
            for recommendation in pipeline.list_recommendations(
                user_id=user_id,
                limit=limit,
            )
        ],
    )


@app.post(
    "/api/recommendations/{recommendation_id}/accept",
    response_model=RecommendationAcceptResponseModel,
)
def accept_recommendation(
    recommendation_id: str,
    payload: AcceptRecommendationRequestModel,
    authorization: str | None = Header(default=None),
) -> RecommendationAcceptResponseModel:
    _authorize_user(payload.user_id, authorization)
    try:
        recommendation, generated = pipeline.accept_recommendation(
            user_id=payload.user_id,
            recommendation_id=recommendation_id,
            conversation_id=payload.conversation_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RecommendationAcceptResponseModel(
        recommendation=_recommendation_payload(recommendation),
        activity=_practice_generation_activity_payload(generated),
        ui_action="practice.start",
    )


@app.post("/api/practice/generate", response_model=GeneratePracticeResponseModel)
def generate_practice(
    payload: GeneratePracticeRequestModel,
    response: Response,
    authorization: str | None = Header(default=None),
) -> GeneratePracticeResponseModel:
    _authorize_user(payload.user_id, authorization)
    _set_legacy_endpoint_headers(
        response,
        "Use POST /api/conversations/{conversation_id}/messages for new practice turns "
        "or POST /api/recommendations/{recommendation_id}/accept for continuations.",
    )
    request_overrides = _practice_request_overrides(payload)
    try:
        practice_activity = pipeline.create_practice_activity(
            user_id=payload.user_id,
            raw_text=payload.message,
            conversation_id=payload.conversation_id,
            request_overrides=request_overrides,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    generated = practice_activity.generated

    return GeneratePracticeResponseModel(
        activity_id=practice_activity.activity.activity_id,
        generation_run_id=generated.generation_run_id,
        request=asdict(generated.request),
        plan=asdict(generated.plan),
        exercises=[asdict(exercise) for exercise in generated.exercises],
        recommendation=practice_activity.recommendation,
        generator_backend=pipeline.generator.backend_name,
        agent_trace=generated.agent_trace,
    )


@app.post(
    "/api/activities/{activity_id}/submit",
    response_model=ActivitySubmitResponseModel,
)
def submit_activity(
    activity_id: str,
    payload: SubmitActivityRequestModel,
    authorization: str | None = Header(default=None),
) -> ActivitySubmitResponseModel:
    _authorize_user(payload.user_id, authorization)
    try:
        submission = pipeline.submit_practice_activity(
            user_id=payload.user_id,
            activity_id=activity_id,
            answers=[
                SubmittedAnswer(
                    exercise_id=answer.exercise_id,
                    selected_answer=answer.selected_answer,
                )
                for answer in payload.answers
            ],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _activity_submit_response(submission)


@app.post("/api/practice/score", response_model=ScorePracticeResponseModel)
def score_practice(
    payload: ScorePracticeRequestModel,
    response: Response,
    authorization: str | None = Header(default=None),
) -> ScorePracticeResponseModel:
    _authorize_user(payload.user_id, authorization)
    _set_legacy_endpoint_headers(
        response,
        "Use POST /api/activities/{activity_id}/submit. This endpoint resolves "
        "activity_id from generation_run_id when compatibility data exists.",
    )
    try:
        result = pipeline.score_legacy_submission(
            user_id=payload.user_id,
            generation_run_id=payload.generation_run_id,
            answers=[
                SubmittedAnswer(
                    exercise_id=answer.exercise_id,
                    selected_answer=answer.selected_answer,
                )
                for answer in payload.answers
            ],
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    return ScorePracticeResponseModel(**asdict(result))


@app.patch(
    "/api/users/{user_id}/profile",
    response_model=UserProfileResponseModel,
)
def update_user_profile(
    user_id: str,
    payload: UpdateUserProfileRequestModel,
    authorization: str | None = Header(default=None),
) -> UserProfileResponseModel:
    _authorize_user(user_id, authorization)
    profile = pipeline.repository.get_profile(user_id)

    if payload.display_name is not None:
        profile.display_name = payload.display_name.strip() or user_id
    if payload.level is not None:
        profile.level = _normalize_level(payload.level)
    if payload.goals:
        profile.goals = _clean_list(payload.goals)
    if payload.preferred_difficulty is not None:
        profile.preferred_difficulty = _normalize_difficulty(
            payload.preferred_difficulty
        )
    if payload.preferred_num_questions is not None:
        profile.preferred_num_questions = payload.preferred_num_questions

    for topic in _clean_list(payload.weak_topics):
        topic_code = _normalize_topic(topic)
        profile.topic_accuracy.setdefault(topic_code, 0.25)
        profile.weak_topics[topic_code] = max(
            profile.weak_topics.get(topic_code, 0.0),
            0.75,
        )

    profile.onboarding_completed = payload.onboarding_completed
    pipeline.repository.save_profile(profile)
    saved_profile = pipeline.repository.get_profile(user_id)
    return UserProfileResponseModel(**asdict(saved_profile))


@app.post(
    "/api/users/{user_id}/onboarding/interpret",
    response_model=InterpretOnboardingResponseModel,
)
def interpret_onboarding_answer(
    user_id: str,
    payload: InterpretOnboardingRequestModel,
    authorization: str | None = Header(default=None),
) -> InterpretOnboardingResponseModel:
    _authorize_user(user_id, authorization)
    interpretation = pipeline.interpret_onboarding_answer(
        message=payload.message,
        current_answers=payload.current_answers,
        current_step_key=payload.current_step_key,
    )
    return InterpretOnboardingResponseModel(**asdict(interpretation))


@app.post(
    "/api/users/{user_id}/practice/interpret",
    response_model=InterpretPracticeResponseModel,
)
def interpret_practice_request(
    user_id: str,
    payload: InterpretPracticeRequestModel,
    authorization: str | None = Header(default=None),
) -> InterpretPracticeResponseModel:
    _authorize_user(user_id, authorization)
    interpretation = pipeline.interpret_practice_request(
        user_id=user_id,
        message=payload.message,
    )
    return InterpretPracticeResponseModel(
        request=asdict(interpretation.request),
        assistant_reply=interpretation.assistant_reply,
        needs_clarification=interpretation.needs_clarification,
        clarification_question=interpretation.clarification_question,
        confidence=interpretation.confidence,
        source=interpretation.source,
        raw_llm_response=interpretation.raw_llm_response,
    )


@app.get(
    "/api/users/{user_id}/chat/resume",
    response_model=ChatMemoryResponseModel,
)
def get_chat_resume(
    user_id: str,
    authorization: str | None = Header(default=None),
) -> ChatMemoryResponseModel:
    _authorize_user(user_id, authorization)
    return ChatMemoryResponseModel(
        **pipeline.repository.get_chat_resume(user_id),
    )


@app.get(
    "/api/users/{user_id}/chat/sessions",
    response_model=ChatSessionListResponseModel,
)
def list_chat_sessions(
    user_id: str,
    authorization: str | None = Header(default=None),
) -> ChatSessionListResponseModel:
    _authorize_user(user_id, authorization)
    return ChatSessionListResponseModel(
        **pipeline.repository.list_chat_sessions(user_id),
    )


@app.post(
    "/api/users/{user_id}/chat/sessions",
    response_model=ChatMemoryResponseModel,
)
def create_chat_session(
    user_id: str,
    authorization: str | None = Header(default=None),
) -> ChatMemoryResponseModel:
    _authorize_user(user_id, authorization)
    return ChatMemoryResponseModel(
        **pipeline.repository.create_chat_session(user_id),
    )


@app.get(
    "/api/users/{user_id}/chat/sessions/{session_id}",
    response_model=ChatMemoryResponseModel,
)
def get_chat_session(
    user_id: str,
    session_id: str,
    authorization: str | None = Header(default=None),
) -> ChatMemoryResponseModel:
    _authorize_user(user_id, authorization)
    try:
        return ChatMemoryResponseModel(
            **pipeline.repository.get_chat_resume(
                user_id,
                session_id=session_id,
            ),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/api/users/{user_id}/chat/messages",
    response_model=SaveChatMessageResponseModel,
)
def save_chat_message(
    user_id: str,
    payload: SaveChatMessageRequestModel,
    authorization: str | None = Header(default=None),
) -> SaveChatMessageResponseModel:
    _authorize_user(user_id, authorization)
    try:
        saved = pipeline.repository.save_chat_message(
            user_id=user_id,
            role=payload.role,
            content=payload.content,
            session_id=payload.session_id,
            metadata=payload.metadata,
            update_memory=payload.update_memory,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SaveChatMessageResponseModel(**saved)


@app.get(
    "/api/users/{user_id}/personalization",
    response_model=PersonalizationSnapshotResponseModel,
)
def get_personalization_snapshot(
    user_id: str,
    authorization: str | None = Header(default=None),
) -> PersonalizationSnapshotResponseModel:
    _authorize_user(user_id, authorization)
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
    return PersonalizationSnapshotResponseModel(
        **snapshot,
        next_plan=asdict(next_plan),
    )


def _clean_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        normalized = " ".join(value.strip().split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            cleaned.append(normalized)
    return cleaned


def _authorize_user(
    user_id: str,
    authorization: str | None,
) -> AuthContext:
    try:
        return auth_service.authorize(user_id, authorization)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _conversation_turn_response(
    result: ConversationTurnResult,
) -> ConversationMessageTurnResponseModel:
    return ConversationMessageTurnResponseModel(
        conversation_id=result.conversation_id,
        message=result.message,
        intent=result.intent,
        assistant_reply=result.assistant_reply,
        pending_clarification=_pending_clarification_payload(
            result.pending_clarification,
        ),
        activity=result.activity,
        ui_action=result.ui_action,
        assistant_message=result.assistant_message,
        route=_conversation_route_response(result.route),
    )


def _practice_generation_activity_payload(
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


def _recommendation_payload(recommendation: ActivityRecommendation) -> dict:
    return asdict(recommendation)


def _activity_submit_response(
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
        ui_action="practice.result",
    )


def _pending_clarification_payload(
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


def _conversation_route_response(
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
        needs_clarification=route.needs_clarification,
        clarification_question=route.clarification_question,
    )


def _set_legacy_endpoint_headers(response: Response, message: str) -> None:
    response.headers["Deprecation"] = "true"
    response.headers["Warning"] = f'299 - "{message}"'


def _build_chroma_debug_snapshot() -> dict:
    config = pipeline.config
    persist_directory = str(Path(config.chroma_persist_directory))
    raw_knowledge_path = str(Path(config.knowledge_chunks_path))
    ingest_command = (
        "python scripts/ingest_knowledge_chunks.py "
        f"--persist-dir {persist_directory} "
        f"--collection {config.chroma_collection_name}"
    )
    raw_knowledge_count = _safe_raw_knowledge_count(config.knowledge_chunks_path)
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
        _chroma_debug_chunk(
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


def _safe_raw_knowledge_count(path: str) -> int:
    try:
        return len(load_knowledge_chunk_records(path))
    except Exception:
        return 0


def _chroma_debug_chunk(
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


def _normalize_level(level: str) -> str:
    normalized = level.strip().lower()
    if normalized in {"beginner", "intermediate", "advanced"}:
        return normalized
    return "beginner"


def _normalize_difficulty(difficulty: str) -> str:
    normalized = difficulty.strip().lower()
    if normalized in {"easy", "medium", "hard"}:
        return normalized
    return "easy"


def _normalize_topic(topic: str) -> str:
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


def _practice_request_overrides(
    payload: GeneratePracticeRequestModel,
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
