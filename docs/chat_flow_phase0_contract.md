# Chat Flow Phase 0 Compatibility Contract

Current contract after the chat-flow refactor is documented in
`docs/conversation_activity_contract.md`. This file remains as the historical
Phase 0 baseline for legacy endpoint compatibility.

Tài liệu này ghi lại contract hiện tại trước khi refactor chat flow. Các phase sau có thể thêm API mới, nhưng không nên làm hỏng các contract legacy này nếu chưa có bước migration frontend rõ ràng.

## Practice Generate

Endpoint:

```text
POST /api/practice/generate
```

Request body:

```json
{
  "user_id": "demo-user",
  "message": "Cho toi 5 cau passive voice",
  "topic": "passive_voice",
  "difficulty": "easy",
  "exercise_type": "grammar_mcq",
  "num_questions": 5,
  "target_subtopic": "past_simple_passive",
  "content_theme": "anime"
}
```

Optional override fields may be omitted. Backend parses `message`, merges overrides, builds a personalized plan, retrieves context, generates/validates exercises, persists a generation run, and returns an exercise set.

Response shape:

```json
{
  "generation_run_id": "gen_or_backend_id",
  "request": {},
  "plan": {},
  "exercises": [],
  "recommendation": "text",
  "generator_backend": "backend-name",
  "agent_trace": []
}
```

Compatibility notes:

- `generation_run_id` is currently required by `/api/practice/score`.
- `recommendation` is currently a text string.
- Frontend maps snake_case response fields to camelCase UI types in `frontend/lib/api.ts`.

## Practice Score

Endpoint:

```text
POST /api/practice/score
```

Request body:

```json
{
  "user_id": "demo-user",
  "generation_run_id": "gen_or_backend_id",
  "answers": [
    {
      "exercise_id": "seed_passive_001",
      "selected_answer": "B"
    }
  ]
}
```

Response shape:

```json
{
  "topic": "passive_voice",
  "score": 1.0,
  "correct_count": 1,
  "total_questions": 1,
  "weak_topics_detected": [],
  "recommendation": "text",
  "generation_run_id": "gen_or_backend_id",
  "session_code": "sess_or_backend_id",
  "answer_diagnoses": [],
  "practice_review": null
}
```

Compatibility notes:

- Backend owns grading for persisted generation runs.
- Current frontend still has local scoring fallback when `generationRunId` is missing or scoring fails; this should be removed in a later phase after activity submit is stable.
- `session_code` identifies the stored practice result/review today, but Phase 5 should introduce `activity_id` as the primary business identity.

## Practice Interpret

Endpoint:

```text
POST /api/users/{user_id}/practice/interpret
```

Request body:

```json
{
  "message": "Luyen tiep 5 cau passive voice"
}
```

Response shape:

```json
{
  "request": {},
  "assistant_reply": "text",
  "needs_clarification": false,
  "clarification_question": null,
  "confidence": 0.9,
  "source": "rule-based",
  "raw_llm_response": ""
}
```

Compatibility notes:

- This endpoint is practice-specific. Phase 3 should put `ConversationRouter` in front of it rather than deleting it.
- Frontend currently has a rule fallback if this endpoint fails; remove that only after conversation routing is backend-owned.

## Onboarding Interpret

Endpoint:

```text
POST /api/users/{user_id}/onboarding/interpret
```

Request body:

```json
{
  "message": "Minh la Phuc, B1, muon luyen IELTS",
  "current_answers": {},
  "current_step_key": "displayName"
}
```

Response shape:

```json
{
  "answers": {},
  "assistant_reply": "text",
  "next_question": "text",
  "next_step_key": "level",
  "is_complete": false,
  "confidence": 0.8,
  "source": "rule-based",
  "raw_llm_response": ""
}
```

Compatibility notes:

- Current UI still supports guided onboarding.
- Phase 7 should reuse the interpreter for progressive profiling instead of treating onboarding as a hard gate.

## Chat Sessions And Messages

Endpoints:

```text
GET  /api/users/{user_id}/chat/resume
GET  /api/users/{user_id}/chat/sessions
POST /api/users/{user_id}/chat/sessions
GET  /api/users/{user_id}/chat/sessions/{session_id}
POST /api/users/{user_id}/chat/messages
```

`POST /api/users/{user_id}/chat/messages` request body:

```json
{
  "session_id": "chat_or_backend_id",
  "role": "user",
  "content": "Cho toi 5 cau passive voice",
  "metadata": {},
  "update_memory": true
}
```

Response shape:

```json
{
  "session_id": "chat_or_backend_id",
  "message": {
    "message_id": "msg_or_backend_id",
    "role": "user",
    "content": "Cho toi 5 cau passive voice",
    "created_at": "timestamp"
  },
  "memory_summary": "text",
  "extracted_facts": {},
  "suggested_next_question": "text"
}
```

Compatibility notes:

- Chat session state already exists separately from generated practice runs.
- Current memory extraction is lightweight and stores facts such as `last_user_request` and content theme hints.
- Phase 4 can map existing chat sessions to the new conversation concept before introducing new frontend behavior.

## Learner Profile And Personalization

Endpoints:

```text
PATCH /api/users/{user_id}/profile
GET   /api/users/{user_id}/personalization
```

Compatibility notes:

- Learner profile, topic stats, subtopic stats, error stats and skill mastery are long-term learner state.
- New Chat should not reset this state.
- Phase 7 should stop using `onboarding_completed` as a strict blocker for practice when a user request is already sufficient.

## Phase 0 Verification

Commands:

```bash
python -m unittest discover tests
cd frontend && npm run lint
cd frontend && npm run build
```

Current verified baseline after Phase 0:

```text
Backend: 13 tests pass
Frontend lint: pass
Frontend build: pass
```
