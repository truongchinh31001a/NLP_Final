from fastapi import APIRouter, Header, HTTPException, Query

from app.api.dependencies import (
    authorize_user,
    get_pipeline,
    practice_generation_activity_payload,
    recommendation_list_response,
    recommendation_payload,
)
from app.api.schemas import (
    AcceptRecommendationRequestModel,
    RecommendationAcceptResponseModel,
    RecommendationListResponseModel,
)

router = APIRouter()


@router.get("/api/recommendations", response_model=RecommendationListResponseModel)
def list_recommendations(
    user_id: str = Query(min_length=1),
    limit: int = Query(default=5, ge=1, le=20),
    authorization: str | None = Header(default=None),
) -> RecommendationListResponseModel:
    authorize_user(user_id, authorization)
    return recommendation_list_response(user_id, limit)


@router.post(
    "/api/recommendations/{recommendation_id}/accept",
    response_model=RecommendationAcceptResponseModel,
)
def accept_recommendation(
    recommendation_id: str,
    payload: AcceptRecommendationRequestModel,
    authorization: str | None = Header(default=None),
) -> RecommendationAcceptResponseModel:
    authorize_user(payload.user_id, authorization)
    pipeline = get_pipeline()
    try:
        recommendation, generated = pipeline.accept_recommendation(
            user_id=payload.user_id,
            recommendation_id=recommendation_id,
            conversation_id=payload.conversation_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RecommendationAcceptResponseModel(
        recommendation=recommendation_payload(recommendation),
        activity=practice_generation_activity_payload(generated),
        ui_action="practice.start",
    )
