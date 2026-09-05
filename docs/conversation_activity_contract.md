# Conversation And Activity Contract

This document is the current contract after the chat-flow refactor. The old
`docs/chat_flow_phase0_contract.md` is still useful as historical baseline, but
new work should use the canonical conversation/activity endpoints here.

## Canonical Identity Rules

- `conversation_id` identifies a chat thread and its short-term context.
- `activity_id` identifies a learning activity. Practice submission, review,
  and recommendation continuation should use this as the primary business id.
- `generation_run_id` identifies the generated exercise snapshot/run. Keep it
  for trace, debug, observability, and legacy compatibility responses.
- `session_code` identifies a stored practice result/review report.

## Canonical Conversation Endpoints

```text
POST /api/conversations
GET  /api/conversations?user_id={user_id}
GET  /api/conversations/{conversation_id}?user_id={user_id}
POST /api/conversations/{conversation_id}/messages
```

`POST /api/conversations/{conversation_id}/messages` is the default entry point
for learner turns. The backend persists the user message, enriches profile
facts, routes intent, runs the matching capability, persists the assistant
message, and returns a canonical turn payload.

Response fields:

```json
{
  "conversation_id": "chat_session_id",
  "message": {},
  "intent": "PRACTICE|EXPLAIN|REVIEW|PROGRESS|PROFILE_UPDATE|GENERAL",
  "assistant_reply": "text",
  "pending_clarification": null,
  "activity": null,
  "ui_action": "conversation.reply",
  "assistant_message": {},
  "route": {
    "intent": "GENERAL",
    "confidence": 0.82,
    "source": "rule-based",
    "reason": "why this route matched",
    "slots": {},
    "needs_clarification": false,
    "clarification_question": null
  }
}
```

## Canonical Activity Endpoints

```text
POST /api/activities/{activity_id}/submit
GET  /api/recommendations?user_id={user_id}
POST /api/recommendations/{recommendation_id}/accept
```

Practice submission should call `POST /api/activities/{activity_id}/submit`.
Accepted recommendations create a new practice activity directly from structured
recommendation fields and should not be reparsed as a generic text prompt.

## Compatibility Endpoints

```text
POST /api/practice/generate
POST /api/practice/score
```

These endpoints remain for compatibility. They set deprecation headers and wrap
the canonical activity path when possible:

- `POST /api/practice/generate` creates a practice `LearningActivity` and
  returns both `activity_id` and `generation_run_id`.
- `POST /api/practice/score` accepts `generation_run_id`, resolves the linked
  `activity_id` when available, then submits the activity through the canonical
  flow.

New frontend code should prefer conversation/activity endpoints.

## Expected UI Actions

```text
PRACTICE       -> practice.start
EXPLAIN        -> explain.respond
REVIEW         -> review.open
PROGRESS       -> progress.open
PROFILE_UPDATE -> profile.update
GENERAL        -> conversation.reply
clarification  -> clarification.ask
submission     -> practice.result
recommendation -> practice.start
```

## Smoke Path

1. Create a conversation.
2. Send a practice request through the conversation message endpoint.
3. Confirm the response has `intent=PRACTICE`, `ui_action=practice.start`, and
   an `activity.activity_id`.
4. Submit answers through `POST /api/activities/{activity_id}/submit`.
5. Ask a review question in the same conversation.
6. Ask a progress question in the same conversation.
7. Create a new conversation and confirm learner profile/mastery persists.
