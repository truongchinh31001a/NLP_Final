from fastapi import APIRouter, Header, HTTPException, Query

from app.api.dependencies import (
    activity_submit_response,
    authorize_user,
    get_activity_or_404,
    get_pipeline,
    learning_activity_payload,
    writing_activity_submit_response,
)
from app.api.schemas import (
    ActivityReviewResponseModel,
    ActivitySubmitResponseModel,
    LearningActivityResponseModel,
    SubmitActivityRequestModel,
)
from app.conversation.schemas import ConversationRoute
from app.schemas import ConversationIntent, LearningActivityType, SubmittedAnswer

router = APIRouter()


@router.post(
    "/api/activities/{activity_id}/submit",
    response_model=ActivitySubmitResponseModel,
)
def submit_activity(
    activity_id: str,
    payload: SubmitActivityRequestModel,
    authorization: str | None = Header(default=None),
) -> ActivitySubmitResponseModel:
    authorize_user(payload.user_id, authorization)
    pipeline = get_pipeline()
    try:
        activity = pipeline.repository.get_learning_activity(
            payload.user_id,
            activity_id,
        )
        if activity is None:
            raise LookupError(f"Learning activity not found: {activity_id}")
        if activity.type == LearningActivityType.WRITING:
            if not payload.writing_text or not payload.writing_text.strip():
                raise ValueError("writing_text is required for writing activities.")
            writing_submission = pipeline.submit_writing_activity(
                user_id=payload.user_id,
                activity_id=activity_id,
                writing_text=payload.writing_text,
            )
            return writing_activity_submit_response(writing_submission)
        if not payload.answers:
            raise ValueError("answers are required for practice and reading activities.")
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
    return activity_submit_response(submission)


@router.get(
    "/api/activities/{activity_id}",
    response_model=LearningActivityResponseModel,
)
def get_activity(
    activity_id: str,
    user_id: str = Query(min_length=1),
    authorization: str | None = Header(default=None),
) -> LearningActivityResponseModel:
    authorize_user(user_id, authorization)
    activity = get_activity_or_404(user_id, activity_id)
    return LearningActivityResponseModel(
        **learning_activity_payload(activity),
    )


@router.get(
    "/api/activities/{activity_id}/review",
    response_model=ActivityReviewResponseModel,
)
def get_activity_review(
    activity_id: str,
    user_id: str = Query(min_length=1),
    question_number: int | None = Query(default=None, ge=1),
    authorization: str | None = Header(default=None),
) -> ActivityReviewResponseModel:
    authorize_user(user_id, authorization)
    pipeline = get_pipeline()
    activity = get_activity_or_404(user_id, activity_id)
    route = ConversationRoute(
        intent=ConversationIntent.REVIEW,
        confidence=1.0,
        source="api",
        reason="Canonical activity review endpoint.",
        slots={
            "activity_id": activity_id,
            **({"question_number": question_number} if question_number else {}),
        },
    )
    context = pipeline.build_conversation_turn_context(
        user_id=user_id,
        conversation_id=activity.conversation_id,
    )
    if pipeline.conversation_service.review_service is None:
        raise HTTPException(status_code=503, detail="Review service is unavailable.")
    result = pipeline.conversation_service.review_service.review(
        route=route,
        context=context,
    )
    return ActivityReviewResponseModel(
        learner_id=user_id,
        activity_id=activity.activity_id,
        conversation_id=activity.conversation_id,
        assistant_reply=result.assistant_reply,
        activity=learning_activity_payload(activity),
        metadata=result.metadata,
        ui_action=result.ui_action,
    )
