import os
from dataclasses import asdict
from time import perf_counter

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import (
    authorize_ops_request,
    authorize_user,
    build_chroma_debug_snapshot,
    personalization_snapshot_payload,
    practice_request_overrides,
    profile_response,
    require_debug_endpoint_enabled,
    set_legacy_endpoint_headers,
    update_profile_response,
)
from app.api.routes import activities, conversations, learners, recommendations
from app.api.schemas import (
    AuthTokenRequestModel,
    AuthTokenResponseModel,
    ChatMemoryResponseModel,
    ChatSessionListResponseModel,
    ChromaDebugResponseModel,
    GeneratePracticeRequestModel,
    GeneratePracticeResponseModel,
    HealthResponseModel,
    InterpretOnboardingRequestModel,
    InterpretOnboardingResponseModel,
    InterpretPracticeRequestModel,
    InterpretPracticeResponseModel,
    MetricsResponseModel,
    ObservabilityDashboardResponseModel,
    PersonalizationSnapshotResponseModel,
    SaveChatMessageRequestModel,
    SaveChatMessageResponseModel,
    ScorePracticeRequestModel,
    ScorePracticeResponseModel,
    UpdateUserProfileRequestModel,
    UserProfileResponseModel,
    WorkflowGraphResponseModel,
)
from app.auth.service import AuthService
from app.bootstrap import build_baseline_pipeline
from app.observability.metrics import metrics_registry
from app.observability.tracing import get_tracer, setup_tracing
from app.schemas import SubmittedAnswer

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

app.include_router(conversations.router)
app.include_router(activities.router)
app.include_router(learners.router)
app.include_router(recommendations.router)


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
        deployment_environment=pipeline.config.deployment_environment,
        generator_backend=pipeline.generator.backend_name,
        repository_backend=pipeline.config.learning_repository_backend,
        vector_store_backend=pipeline.config.vector_store_backend,
        auth_mode=pipeline.config.auth_mode,
        debug_endpoints_enabled=pipeline.config.debug_endpoints_enabled,
        observability_enabled=pipeline.config.observability_enabled,
        otel_enabled=pipeline.config.otel_enabled,
    )


@app.post("/api/auth/dev-token", response_model=AuthTokenResponseModel)
def create_dev_auth_token(payload: AuthTokenRequestModel) -> AuthTokenResponseModel:
    if not pipeline.config.auth_dev_token_enabled:
        raise HTTPException(status_code=404, detail="Dev token endpoint is disabled.")
    return AuthTokenResponseModel(
        access_token=auth_service.issue_token(payload.user_id),
        user_id=payload.user_id,
        expires_in_seconds=pipeline.config.auth_token_ttl_seconds,
    )


@app.get("/api/debug/metrics", response_model=MetricsResponseModel)
def debug_metrics() -> MetricsResponseModel:
    require_debug_endpoint_enabled()
    return MetricsResponseModel(**metrics_registry.snapshot())


@app.get("/api/debug/workflow", response_model=WorkflowGraphResponseModel)
def debug_workflow() -> WorkflowGraphResponseModel:
    require_debug_endpoint_enabled()
    return WorkflowGraphResponseModel(**pipeline.workflow_graph.as_dict())


@app.get("/api/debug/chroma", response_model=ChromaDebugResponseModel)
def debug_chroma() -> ChromaDebugResponseModel:
    require_debug_endpoint_enabled()
    return ChromaDebugResponseModel(**build_chroma_debug_snapshot())


@app.get(
    "/api/ops/observability",
    response_model=ObservabilityDashboardResponseModel,
)
def ops_observability(
    user_id: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> ObservabilityDashboardResponseModel:
    authorize_ops_request(user_id, authorization)
    return ObservabilityDashboardResponseModel(
        status="ok",
        deployment_environment=pipeline.config.deployment_environment,
        service_name=pipeline.config.otel_service_name,
        metrics=MetricsResponseModel(**metrics_registry.snapshot()),
        observability_enabled=pipeline.config.observability_enabled,
        otel_enabled=pipeline.config.otel_enabled,
        otel_exporter_otlp_endpoint=pipeline.config.otel_exporter_otlp_endpoint,
        debug_endpoints_enabled=pipeline.config.debug_endpoints_enabled,
    )


@app.post("/api/practice/generate", response_model=GeneratePracticeResponseModel)
def generate_practice(
    payload: GeneratePracticeRequestModel,
    response: Response,
    authorization: str | None = Header(default=None),
) -> GeneratePracticeResponseModel:
    authorize_user(payload.user_id, authorization)
    set_legacy_endpoint_headers(
        response,
        "Use POST /api/conversations/{conversation_id}/messages for new practice turns "
        "or POST /api/recommendations/{recommendation_id}/accept for continuations.",
    )
    request_overrides = practice_request_overrides(payload)
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


@app.post("/api/practice/score", response_model=ScorePracticeResponseModel)
def score_practice(
    payload: ScorePracticeRequestModel,
    response: Response,
    authorization: str | None = Header(default=None),
) -> ScorePracticeResponseModel:
    authorize_user(payload.user_id, authorization)
    set_legacy_endpoint_headers(
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
    authorize_user(user_id, authorization)
    return update_profile_response(user_id, payload)


@app.get(
    "/api/users/{user_id}/profile",
    response_model=UserProfileResponseModel,
)
def get_user_profile(
    user_id: str,
    authorization: str | None = Header(default=None),
) -> UserProfileResponseModel:
    authorize_user(user_id, authorization)
    return profile_response(user_id)


@app.post(
    "/api/users/{user_id}/onboarding/interpret",
    response_model=InterpretOnboardingResponseModel,
)
def interpret_onboarding_answer(
    user_id: str,
    payload: InterpretOnboardingRequestModel,
    authorization: str | None = Header(default=None),
) -> InterpretOnboardingResponseModel:
    authorize_user(user_id, authorization)
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
    authorize_user(user_id, authorization)
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
    authorize_user(user_id, authorization)
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
    authorize_user(user_id, authorization)
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
    authorize_user(user_id, authorization)
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
    authorize_user(user_id, authorization)
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
    authorize_user(user_id, authorization)
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
    authorize_user(user_id, authorization)
    return PersonalizationSnapshotResponseModel(
        **personalization_snapshot_payload(user_id),
    )
