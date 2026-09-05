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
  "intent": "PRACTICE|READING|WRITING|EXPLAIN|REVIEW|PROGRESS|PROFILE_UPDATE|GENERAL",
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
    "missing_slots": [],
    "referenced_activity_id": null,
    "needs_clarification": false,
    "clarification_question": null
  }
}
```

`pending_clarification` is stored on the chat session as well as assistant
metadata, so a short follow-up after a reload can still resume the previous
intent. For review turns, `referenced_activity_id` points to the activity used
by the resolver; generic phrases like "cau 1 sai" prefer the latest submitted
or completed activity over a newer activity that has not been submitted.

## Canonical Activity Endpoints

```text
GET  /api/activities/{activity_id}?user_id={user_id}
GET  /api/activities/{activity_id}/review?user_id={user_id}
POST /api/activities/{activity_id}/submit
POST /api/recommendations/{recommendation_id}/accept
```

`GET /api/activities/{activity_id}` returns the activity envelope with
`learner_id`, `conversation_id`, lifecycle status, metadata, generated
request/plan/exercises when available, result when submitted, and `ui_action`.

`GET /api/activities/{activity_id}/review` is the query-style review endpoint
for clients that already know the activity id. Normal learner turns can still
ask review questions through `POST /api/conversations/{conversation_id}/messages`.

Practice submission should call `POST /api/activities/{activity_id}/submit`.
Accepted recommendations create a new practice activity directly from structured
recommendation fields and should not be reparsed as a generic text prompt.

## Canonical Learner Endpoints

```text
GET   /api/learners/{learner_id}/profile
PATCH /api/learners/{learner_id}/profile
GET   /api/learners/{learner_id}/mastery
GET   /api/learners/{learner_id}/progress
GET   /api/learners/{learner_id}/recommendations
```

`/api/learners/{learner_id}/mastery` exposes skill mastery, weak skills,
confidence, attempts, and review scheduling. `/api/learners/{learner_id}/progress`
returns the same progress summary used by the conversation capability plus the
personalization snapshot for dashboards.

`GET /api/recommendations?user_id={user_id}` remains available, but new clients
should prefer `GET /api/learners/{learner_id}/recommendations`.

## Compatibility Endpoints

```text
POST /api/practice/generate
POST /api/practice/score
GET   /api/users/{user_id}/profile
PATCH /api/users/{user_id}/profile
GET   /api/users/{user_id}/personalization
```

These endpoints remain for compatibility. The legacy practice endpoints set
deprecation headers and wrap the canonical activity path when possible:

- `POST /api/practice/generate` creates a practice `LearningActivity` and
  returns both `activity_id` and `generation_run_id`.
- `POST /api/practice/score` accepts `generation_run_id`, resolves the linked
  `activity_id` when available, then submits the activity through the canonical
  flow.

New frontend code should prefer conversation/activity endpoints.

## Expected UI Actions

```text
PRACTICE       -> practice.start
LISTENING      -> listening.start  (planned)
SPEAKING       -> speaking.start   (planned)
EXPLAIN        -> explain.respond
REVIEW         -> review.open
PROGRESS       -> progress.open
PROFILE_UPDATE -> profile.update
GENERAL        -> conversation.reply
clarification  -> clarification.ask
submission     -> practice.result
listening submit -> listening.result (planned)
speaking submit  -> speaking.result  (planned)
recommendation -> practice.start
```

## Planned Audio Activity Contract

Listening and speaking are planned activity types, not runtime-enabled in this
phase. Phase 21 selects a browser-first audio path: browser Web Speech API for
speaking transcript capture, browser SpeechSynthesis for listening playback, and
manual transcript entry as the required fallback.

Future listening and speaking creation should still start from
`POST /api/conversations/{conversation_id}/messages`, return a normal
`LearningActivity` envelope, and submit through
`POST /api/activities/{activity_id}/submit`. Listening submissions send selected
answers. Speaking submissions send transcript-first attempt data such as
`transcript`, `stt_confidence`, `duration_ms`, and `attempt_number`. Raw audio is
not part of the default submit payload and must not be persisted without an
explicit artifact policy.

The detailed metadata and frontend contract lives in
`docs/audio_activity_design.md`.

## Smoke Path

1. Create a conversation.
2. Send a practice request through the conversation message endpoint.
3. Confirm the response has `intent=PRACTICE`, `ui_action=practice.start`, and
   an `activity.activity_id`.
4. Read the activity through `GET /api/activities/{activity_id}`.
5. Submit answers through `POST /api/activities/{activity_id}/submit`.
6. Ask a review question in the same conversation or call
   `GET /api/activities/{activity_id}/review`.
7. Ask a progress question in the same conversation or call
   `GET /api/learners/{learner_id}/progress`.
8. Create a new conversation and confirm learner profile/mastery persists.
