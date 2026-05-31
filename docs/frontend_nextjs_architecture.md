# Frontend Next.js Architecture

## Vai tro

Frontend dung `Next.js App Router` lam giao dien chinh cho he thong chatbot sinh bai tap tieng Anh ca nhan hoa.

Python backend phu trach:

- NLP parsing
- LangChain retrieval
- LLM generation
- scoring
- profile update

Next.js frontend phu trach:

- nhan request bang giao dien chat
- hien thi exercise set
- hien thi explanation va recommendation
- theo doi profile / lich su hoc
- fallback sang local preview neu backend tam thoi khong san sang

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

## Contract UI -> Backend de nghi

### `POST /api/practice/generate`

Request:

```json
{
  "user_id": "demo-user",
  "message": "I am weak at passive voice. Generate 5 medium multiple-choice questions."
}
```

Response:

```json
{
  "request": {
    "topic": "passive_voice",
    "difficulty": "medium",
    "exercise_type": "grammar_mcq",
    "num_questions": 5
  },
  "plan": {
    "focus_reason": "Focused on weak topic `passive_voice`."
  },
  "exercises": [
    {
      "exercise_id": "passive_voice-1",
      "question_text": "....",
      "options": [
        { "label": "A", "text": "....", "is_correct": false }
      ],
      "correct_answer": "B",
      "explanation": "...."
    }
  ],
  "recommendation": "Practice passive voice again with similar difficulty."
}
```

### `POST /api/practice/score`

Request:

```json
{
  "user_id": "demo-user",
  "topic": "passive_voice",
  "answers": [
    { "exercise_id": "passive_voice-1", "selected_answer": "B" }
  ]
}
```

Response:

```json
{
  "score": 0.8,
  "correct_count": 4,
  "total_questions": 5,
  "weak_topics_detected": ["passive_voice"],
  "recommendation": "Increase difficulty slightly after one more stable session."
}
```

## Man hinh baseline

1. `Dashboard`: profile, weak topics, session history.
2. `Chat workspace`: o nhap prompt tu nhien + nut generate.
3. `Exercise panel`: hien thi MCQ / fill-in-the-blank.
4. `Feedback panel`: diem, giai thich, recommendation.

## Huong nang cap tiep

- Them score flow day du tu UI den `POST /api/practice/score`.
- Them streaming response neu muon hien thi generation theo thoi gian thuc.
- Them auth neu can nhieu user.
