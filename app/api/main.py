import os
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.schemas import (
    ChatMemoryResponseModel,
    GeneratePracticeRequestModel,
    GeneratePracticeResponseModel,
    HealthResponseModel,
    InterpretOnboardingRequestModel,
    InterpretOnboardingResponseModel,
    InterpretPracticeRequestModel,
    InterpretPracticeResponseModel,
    PersonalizationSnapshotResponseModel,
    SaveChatMessageRequestModel,
    SaveChatMessageResponseModel,
    ScorePracticeRequestModel,
    ScorePracticeResponseModel,
    UpdateUserProfileRequestModel,
    UserProfileResponseModel,
)
from app.bootstrap import build_baseline_pipeline
from app.schemas import PracticeRequest, SessionResult, SubmittedAnswer

app = FastAPI(
    title="Personalized English Exercise Chatbot API",
    version="0.1.0",
)

pipeline = build_baseline_pipeline()

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


@app.get("/api/health", response_model=HealthResponseModel)
def healthcheck() -> HealthResponseModel:
    return HealthResponseModel(
        status="ok",
        generator_backend=pipeline.generator.backend_name,
    )


@app.post("/api/practice/generate", response_model=GeneratePracticeResponseModel)
def generate_practice(
    payload: GeneratePracticeRequestModel,
) -> GeneratePracticeResponseModel:
    request_overrides = _practice_request_overrides(payload)
    generated = pipeline.create_exercise_set(
        user_id=payload.user_id,
        raw_text=payload.message,
        request_overrides=request_overrides,
    )

    preview_result = SessionResult(
        user_id=payload.user_id,
        topic=generated.plan.topic,
        total_questions=max(len(generated.exercises), 1),
        correct_count=max(len(generated.exercises) - 1, 0),
        score=max(len(generated.exercises) - 1, 0)
        / max(len(generated.exercises), 1),
    )
    preview_result.recommendation = pipeline.recommendation.recommend(preview_result)

    return GeneratePracticeResponseModel(
        generation_run_id=generated.generation_run_id,
        request=asdict(generated.request),
        plan=asdict(generated.plan),
        exercises=[asdict(exercise) for exercise in generated.exercises],
        recommendation=preview_result.recommendation,
        generator_backend=pipeline.generator.backend_name,
        agent_trace=generated.agent_trace,
    )


@app.post("/api/practice/score", response_model=ScorePracticeResponseModel)
def score_practice(payload: ScorePracticeRequestModel) -> ScorePracticeResponseModel:
    try:
        result = pipeline.score_submission(
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
) -> UserProfileResponseModel:
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
) -> InterpretOnboardingResponseModel:
    _ = user_id
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
) -> InterpretPracticeResponseModel:
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
def get_chat_resume(user_id: str) -> ChatMemoryResponseModel:
    return ChatMemoryResponseModel(
        **pipeline.repository.get_chat_resume(user_id),
    )


@app.post(
    "/api/users/{user_id}/chat/messages",
    response_model=SaveChatMessageResponseModel,
)
def save_chat_message(
    user_id: str,
    payload: SaveChatMessageRequestModel,
) -> SaveChatMessageResponseModel:
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
    return SaveChatMessageResponseModel(**saved)


@app.get(
    "/api/users/{user_id}/personalization",
    response_model=PersonalizationSnapshotResponseModel,
)
def get_personalization_snapshot(
    user_id: str,
) -> PersonalizationSnapshotResponseModel:
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
