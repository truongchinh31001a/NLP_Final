from fastapi import APIRouter, Header, HTTPException, Query

from app.api.dependencies import (
    authorize_user,
    get_pipeline,
    list_of_dicts,
    personalization_snapshot_payload,
    profile_response,
    recommendation_list_response,
    update_profile_response,
)
from app.api.schemas import (
    LearnerMasteryResponseModel,
    LearnerProgressResponseModel,
    PersonalizationSnapshotResponseModel,
    RecommendationListResponseModel,
    UpdateUserProfileRequestModel,
    UserProfileResponseModel,
)
from app.conversation.schemas import ConversationRoute
from app.schemas import ConversationIntent

router = APIRouter()


@router.get(
    "/api/learners/{learner_id}/profile",
    response_model=UserProfileResponseModel,
)
def get_learner_profile(
    learner_id: str,
    authorization: str | None = Header(default=None),
) -> UserProfileResponseModel:
    authorize_user(learner_id, authorization)
    return profile_response(learner_id)


@router.patch(
    "/api/learners/{learner_id}/profile",
    response_model=UserProfileResponseModel,
)
def update_learner_profile(
    learner_id: str,
    payload: UpdateUserProfileRequestModel,
    authorization: str | None = Header(default=None),
) -> UserProfileResponseModel:
    authorize_user(learner_id, authorization)
    return update_profile_response(learner_id, payload)


@router.get(
    "/api/learners/{learner_id}/mastery",
    response_model=LearnerMasteryResponseModel,
)
def get_learner_mastery(
    learner_id: str,
    limit: int = Query(default=5, ge=1, le=20),
    authorization: str | None = Header(default=None),
) -> LearnerMasteryResponseModel:
    authorize_user(learner_id, authorization)
    pipeline = get_pipeline()
    snapshot = pipeline.repository.get_personalization_snapshot(learner_id)
    skill_mastery = list_of_dicts(snapshot.get("skill_mastery"))
    weak_skills = sorted(
        skill_mastery,
        key=lambda item: float(item.get("weakness_score") or 0.0),
        reverse=True,
    )[:limit]
    return LearnerMasteryResponseModel(
        learner_id=learner_id,
        skill_mastery=skill_mastery,
        weak_skills=weak_skills,
        topic_stats=list_of_dicts(snapshot.get("topic_stats")),
        subtopic_stats=list_of_dicts(snapshot.get("subtopic_stats")),
        error_stats=list_of_dicts(snapshot.get("error_stats")),
    )


@router.get(
    "/api/learners/{learner_id}/progress",
    response_model=LearnerProgressResponseModel,
)
def get_learner_progress(
    learner_id: str,
    metric: str = Query(default="weak_areas"),
    conversation_id: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> LearnerProgressResponseModel:
    authorize_user(learner_id, authorization)
    pipeline = get_pipeline()
    context = pipeline.build_conversation_turn_context(
        user_id=learner_id,
        conversation_id=conversation_id,
    )
    route = ConversationRoute(
        intent=ConversationIntent.PROGRESS,
        confidence=1.0,
        source="api",
        reason="Canonical learner progress endpoint.",
        slots={"metric": metric},
    )
    if pipeline.conversation_service.progress_service is None:
        raise HTTPException(status_code=503, detail="Progress service is unavailable.")
    progress = pipeline.conversation_service.progress_service.summarize(
        user_id=learner_id,
        route=route,
        context=context,
    )
    return LearnerProgressResponseModel(
        learner_id=learner_id,
        conversation_id=conversation_id,
        metric=metric,
        summary=progress.assistant_reply,
        weak_areas=list_of_dicts(progress.metadata.get("weak_areas")),
        lowest_skill=(
            progress.metadata.get("lowest_skill")
            if isinstance(progress.metadata.get("lowest_skill"), dict)
            else None
        ),
        snapshot=PersonalizationSnapshotResponseModel(
            **personalization_snapshot_payload(learner_id),
        ),
        ui_action=progress.ui_action,
    )


@router.get(
    "/api/learners/{learner_id}/recommendations",
    response_model=RecommendationListResponseModel,
)
def list_learner_recommendations(
    learner_id: str,
    limit: int = Query(default=5, ge=1, le=20),
    authorization: str | None = Header(default=None),
) -> RecommendationListResponseModel:
    authorize_user(learner_id, authorization)
    return recommendation_list_response(learner_id, limit)
