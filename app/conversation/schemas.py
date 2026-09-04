from dataclasses import dataclass, field
from typing import Any

from app.schemas import ConversationIntent, PendingClarification, PracticeRequest


@dataclass(slots=True)
class ConversationRoute:
    intent: ConversationIntent
    confidence: float
    source: str
    reason: str
    slots: dict[str, Any] = field(default_factory=dict)
    needs_clarification: bool = False
    clarification_question: str | None = None
    pending_clarification: PendingClarification | None = None
    assistant_reply: str = ""
    practice_request: PracticeRequest | None = None


@dataclass(slots=True)
class ConversationTurnResult:
    conversation_id: str
    message: dict[str, Any]
    intent: ConversationIntent
    assistant_reply: str
    pending_clarification: PendingClarification | None = None
    activity: dict[str, Any] | None = None
    ui_action: str = "conversation.reply"
    assistant_message: dict[str, Any] | None = None
    route: ConversationRoute | None = None
