from dataclasses import dataclass, field
from typing import Any

from app.schemas import ConversationIntent, PendingClarification, PracticeRequest


@dataclass(slots=True)
class ConversationRoute:
    intent: ConversationIntent
    confidence: float
    source: str
    reason: str
    requires_context: bool = False
    target_activity_id: str | None = None
    slots: dict[str, Any] = field(default_factory=dict)
    missing_slots: list[str] = field(default_factory=list)
    next_action: str = ""
    needs_clarification: bool = False
    clarification_question: str | None = None
    pending_clarification: PendingClarification | None = None
    assistant_reply: str = ""
    practice_request: PracticeRequest | None = None

    def __post_init__(self) -> None:
        if self.slots is None:
            self.slots = {}

        if self.pending_clarification is not None and not self.missing_slots:
            self.missing_slots = list(self.pending_clarification.missing_fields)

        if self.target_activity_id is None:
            activity_id = self.slots.get("activity_id")
            if activity_id not in (None, ""):
                self.target_activity_id = str(activity_id)

        if not self.next_action:
            self.next_action = self._default_next_action()

        if not self.requires_context:
            self.requires_context = self.intent in {
                ConversationIntent.PRACTICE,
                ConversationIntent.READING,
                ConversationIntent.WRITING,
                ConversationIntent.EXPLAIN,
                ConversationIntent.REVIEW,
                ConversationIntent.PROGRESS,
                ConversationIntent.PROFILE_UPDATE,
            }

    def _default_next_action(self) -> str:
        if self.needs_clarification:
            return "clarification.ask"
        actions = {
            ConversationIntent.PRACTICE: "practice.interpret",
            ConversationIntent.READING: "reading.start",
            ConversationIntent.WRITING: "writing.start",
            ConversationIntent.EXPLAIN: "explain.respond",
            ConversationIntent.REVIEW: "review.open",
            ConversationIntent.PROGRESS: "progress.open",
            ConversationIntent.PROFILE_UPDATE: "profile.update",
            ConversationIntent.GENERAL: "conversation.reply",
        }
        return actions[self.intent]


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
