import os
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.schemas import (
    GeneratePracticeRequestModel,
    GeneratePracticeResponseModel,
    HealthResponseModel,
    ScorePracticeRequestModel,
    ScorePracticeResponseModel,
)
from app.bootstrap import build_baseline_pipeline
from app.schemas import GeneratedExerciseSet, SessionResult

app = FastAPI(
    title="Personalized English Exercise Chatbot API",
    version="0.1.0",
)

pipeline = build_baseline_pipeline()
practice_cache: dict[tuple[str, str], GeneratedExerciseSet] = {}

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
    generated = pipeline.create_exercise_set(
        user_id=payload.user_id,
        raw_text=payload.message,
    )

    practice_cache[(payload.user_id, generated.plan.topic)] = generated

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
        request=asdict(generated.request),
        plan=asdict(generated.plan),
        exercises=[asdict(exercise) for exercise in generated.exercises],
        recommendation=preview_result.recommendation,
        generator_backend=pipeline.generator.backend_name,
    )


@app.post("/api/practice/score", response_model=ScorePracticeResponseModel)
def score_practice(payload: ScorePracticeRequestModel) -> ScorePracticeResponseModel:
    cached_set = practice_cache.get((payload.user_id, payload.topic))
    if cached_set is None:
        raise HTTPException(
            status_code=404,
            detail="No generated exercise set found for this user and topic.",
        )

    answer_lookup = {
        answer.exercise_id: answer.selected_answer for answer in payload.answers
    }
    correct_count = sum(
        1
        for exercise in cached_set.exercises
        if answer_lookup.get(exercise.exercise_id) == exercise.correct_answer
    )

    result = pipeline.score_submission(
        user_id=payload.user_id,
        topic=payload.topic,
        total_questions=len(cached_set.exercises),
        correct_count=correct_count,
    )

    return ScorePracticeResponseModel(**asdict(result))
