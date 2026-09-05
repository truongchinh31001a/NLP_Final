from fastapi import APIRouter, Header, HTTPException, Query

from app.api.dependencies import (
    authorize_user,
    conversation_turn_response,
    get_pipeline,
)
from app.api.schemas import (
    ConversationDetailResponseModel,
    ConversationListResponseModel,
    ConversationMessageTurnResponseModel,
    CreateConversationRequestModel,
    SendConversationMessageRequestModel,
)

router = APIRouter()


@router.post("/api/conversations", response_model=ConversationDetailResponseModel)
def create_conversation(
    payload: CreateConversationRequestModel,
    authorization: str | None = Header(default=None),
) -> ConversationDetailResponseModel:
    authorize_user(payload.user_id, authorization)
    pipeline = get_pipeline()
    return ConversationDetailResponseModel(
        **pipeline.create_conversation(payload.user_id),
    )


@router.get("/api/conversations", response_model=ConversationListResponseModel)
def list_conversations(
    user_id: str = Query(min_length=1),
    limit: int = Query(default=20, ge=1, le=50),
    authorization: str | None = Header(default=None),
) -> ConversationListResponseModel:
    authorize_user(user_id, authorization)
    pipeline = get_pipeline()
    return ConversationListResponseModel(
        **pipeline.list_conversations(user_id, limit=limit),
    )


@router.get(
    "/api/conversations/{conversation_id}",
    response_model=ConversationDetailResponseModel,
)
def get_conversation(
    conversation_id: str,
    user_id: str = Query(min_length=1),
    limit: int = Query(default=24, ge=1, le=100),
    authorization: str | None = Header(default=None),
) -> ConversationDetailResponseModel:
    authorize_user(user_id, authorization)
    pipeline = get_pipeline()
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


@router.post(
    "/api/conversations/{conversation_id}/messages",
    response_model=ConversationMessageTurnResponseModel,
)
def send_conversation_message(
    conversation_id: str,
    payload: SendConversationMessageRequestModel,
    authorization: str | None = Header(default=None),
) -> ConversationMessageTurnResponseModel:
    authorize_user(payload.user_id, authorization)
    pipeline = get_pipeline()
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
    return conversation_turn_response(result)
