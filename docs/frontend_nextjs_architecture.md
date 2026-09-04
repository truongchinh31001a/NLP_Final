# Frontend Next.js Architecture

## Vai tro

Frontend dung `Next.js App Router` lam giao dien chinh cho he thong chatbot sinh bai tap tieng Anh ca nhan hoa.

Python backend phu trach:

- conversation routing
- learning activity lifecycle
- LangChain retrieval
- LLM/seed-bank generation
- LLM-backed tutor responses for general chat and explanations when configured
- scoring, diagnosis, review, recommendation
- profile and mastery update

Next.js frontend phu trach:

- nhan request bang giao dien chat
- hien thi exercise set
- hien thi explanation va recommendation
- theo doi profile / lich su hoc
- goi backend cho moi thao tac tao bai, nop bai, va chap nhan goi y

Router backend van rule-first de tranh tao bai sai intent. Noi dung tra loi
cho `GENERAL` va `EXPLAIN` duoc sinh boi tutor response service: uu tien LLM
neu `TUTOR_RESPONSE_LLM_ENABLED=true` va co `LLM_BACKEND` ho tro, fallback thi
dua vao message/profile/memory thay vi mot cau form co dinh.

## Cau truc thu muc

```text
frontend/
  app/
    layout.tsx
    page.tsx
    globals.css
  components/
    chat-workbench.tsx
  lib/
    api.ts
    mock-data.ts
    types.ts
```

## Contract UI -> Backend hien tai

### `POST /api/conversations`

Request:

```json
{
  "user_id": "demo-user"
}
```

Response:

```json
{
  "conversation_id": "chat_...",
  "has_history": false,
  "messages": [],
  "active_activity": null
}
```

### `POST /api/conversations/{conversation_id}/messages`

Request:

```json
{
  "user_id": "demo-user",
  "message": "I am weak at passive voice. Generate 5 medium questions."
}
```

Practice response shape:

```json
{
  "intent": "PRACTICE",
  "ui_action": "practice.start",
  "activity": {
    "activity_id": "activity_...",
    "status": "READY",
    "generation_run_id": "gen_...",
    "plan": {
      "topic": "passive_voice",
      "difficulty": "medium",
      "exercise_type": "grammar_mcq",
      "num_questions": 5
    },
    "exercises": []
  }
}
```

### `POST /api/activities/{activity_id}/submit`

Request:

```json
{
  "user_id": "demo-user",
  "answers": [
    { "exercise_id": "passive_voice-1", "selected_answer": "B" }
  ]
}
```

Response:

```json
{
  "ui_action": "practice.result",
  "result": {
    "score": 0.8,
    "correct_count": 4,
    "total_questions": 5,
    "recommendation": "Practice passive voice again with similar difficulty."
  },
  "next_activity_suggestion": {
    "recommendation_id": "rec_activity_...",
    "topic": "passive_voice",
    "difficulty": "medium",
    "exercise_type": "grammar_mcq",
    "num_questions": 5,
    "reason": "..."
  }
}
```

### `POST /api/recommendations/{recommendation_id}/accept`

Request:

```json
{
  "user_id": "demo-user",
  "conversation_id": "chat_..."
}
```

Response:

```json
{
  "ui_action": "practice.start",
  "recommendation": {
    "recommendation_id": "rec_activity_...",
    "topic": "passive_voice"
  },
  "activity": {
    "activity_id": "activity_...",
    "status": "READY",
    "exercises": []
  }
}
```

## Man hinh baseline

1. `Dashboard`: profile, weak topics, session history.
2. `Chat workspace`: o nhap prompt tu nhien, route intent, va lich su conversation.
3. `Exercise panel`: hien thi activity practice dang READY/IN_PROGRESS.
4. `Feedback panel`: diem, diagnosis, review, structured recommendation.

## Huong nang cap tiep

- Them streaming response neu muon hien thi generation theo thoi gian thuc.
- Them auth production neu can nhieu user.
