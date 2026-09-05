# Refactor Plan — Adaptive AI English Learning Platform

## 1. Mục tiêu

Code hiện tại đã khá tốt ở phần:

```text
Practice Request
→ Interpret
→ Retrieve
→ Generate
→ Validate
→ Score
→ Diagnose
→ Recommend
```

Vấn đề chính hiện tại nằm ở tầng trên: `Conversation`.

Target nên là:

```text
Conversation
→ Conversation Router
→ Capability phù hợp
```

với các capability:

```text
PRACTICE
EXPLAIN
REVIEW
PROGRESS
PROFILE_UPDATE
GENERAL
```

Mục tiêu refactor là giữ lại phần practice hiện có, nhưng đưa nó thành một capability trong một hệ thống học tập lớn hơn.

---

# 2. Phần nên giữ lại

Không rewrite toàn bộ. Giữ tối đa các module hiện có:

```text
OnboardingInterpreter
PracticeIntentInterpreter
PersonalizationService
RetrievalService
ExerciseGenerator
ExerciseValidator
PracticeReviewService
RecommendationService
Scoring / Grading
Error Diagnosis
Chat Session / History
Memory Summary
LearningAgent
LearningWorkflowGraph
```

Refactor chủ yếu:

```text
Conversation orchestration
Intent routing
Domain identity
Activity lifecycle
State boundaries
```

---

# 3. Priority 1 — ConversationRouter

## Intent enum

```python
from enum import Enum

class ConversationIntent(str, Enum):
    PRACTICE = "practice"
    EXPLAIN = "explain"
    REVIEW = "review"
    PROGRESS = "progress"
    PROFILE_UPDATE = "profile_update"
    GENERAL = "general"
```

Router chỉ trả lời:

```text
User muốn làm gì?
```

Không thay thế `PracticeIntentInterpreter`.

Flow:

```text
User Message
      ↓
ConversationRouter
      ↓
PRACTICE
      ↓
PracticeIntentInterpreter
      ↓
Practice Pipeline
```

---

## Router result

```python
class ConversationRoute:
    intent: ConversationIntent
    confidence: float
    requires_clarification: bool

    slots: dict
    missing_slots: list[str]

    referenced_activity_id: str | None
    next_action: str | None
```

Ví dụ:

```json
{
  "intent": "review",
  "confidence": 0.96,
  "requires_clarification": false,
  "slots": {
    "question_number": 3
  },
  "missing_slots": [],
  "referenced_activity_id": "act_123"
}
```

---

# 4. Routing strategy

Không nhất thiết mọi message đều gọi LLM.

Dùng hybrid routing:

```text
Strong signal
   ↓
Rule-based route
```

Nếu không chắc:

```text
LLM classifier
```

Ví dụ:

```text
"cho tôi 10 câu..."        → PRACTICE
"tại sao câu 2 sai"       → REVIEW
"tôi yếu phần nào"        → PROGRESS
"giải thích present perfect" → EXPLAIN
"từ giờ cho bài khó hơn"  → PROFILE_UPDATE
```

---

# 5. Priority 2 — Conversation State

Tách conversation state khỏi UI state.

```python
ConversationState:
    conversation_id
    learner_id

    recent_messages
    memory_summary

    active_intent
    pending_intent

    collected_slots
    missing_slots

    active_activity_id
```

---

# 6. Pending clarification

Ví dụ:

```text
User:
"Tôi muốn luyện tiếng Anh."

Assistant:
"Bạn muốn luyện chủ đề nào?"
```

State:

```text
pending_intent = PRACTICE
missing_slots = ["topic"]
```

User:

```text
"Past Simple."
```

System merge:

```text
topic = past_simple
```

Flow:

```text
Message
  ↓
Pending intent exists?
  │
  ├── Yes → Merge slots → Enough info?
  │
  └── No  → Route normally
```

---

# 7. Priority 3 — Introduce LearningActivity

Không dùng `generation_run_id` làm business identity chính.

```python
class LearningActivity:
    id: str
    learner_id: str
    conversation_id: str

    type: str
    status: str

    target_skills: list[str]
    difficulty: str | None

    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    generation_run_id: str | None
```

`generation_run_id` chỉ dùng cho:

```text
Tracing
Debugging
Observability
LLM analytics
```

Business identity là:

```text
activity_id
```

---

# 8. Activity types

Ban đầu:

```text
PRACTICE
REVIEW
CALIBRATION
```

Về sau:

```text
QUIZ
READING
WRITING
SPEAKING
VOCAB_REVIEW
SPACED_REVIEW
```

---

# 9. Activity lifecycle

```text
CREATED
   ↓
GENERATING
   ↓
READY
   ↓
IN_PROGRESS
   ↓
SUBMITTED
   ↓
GRADED
   ↓
COMPLETED
```

Optional:

```text
FAILED
CANCELLED
```

UI state vẫn có thể là:

```text
chat
generating
practice
result
```

nhưng:

```text
UI state != Business state
```

---

# 10. Priority 4 — Practice Pipeline thành capability

Không xóa current PracticePipeline.

Target:

```text
Conversation Router
        ↓
     PRACTICE
        ↓
Practice Capability
        ↓
PracticeIntentInterpreter
        ↓
PracticePipeline
```

Practice target flow:

```text
PRACTICE
   ↓
PracticeIntentInterpreter
   ↓
Enough request information?
   │
   ├── No → Save pending slots → Ask clarification
   │
   └── Yes
        ↓
Create LearningActivity
        ↓
Practice Planner
        ↓
Load Learner Context
        ↓
Retrieve Knowledge
        ↓
Generate
        ↓
Validate
        ↓
Retry / Backend Fallback
        ↓
Activity READY
```

---

# 11. Priority 5 — Backend owns fallback

Không nên:

```text
Backend failed
   ↓
Frontend creates fallback exercise
```

Target:

```text
Backend Generate
   ↓
Validate
   ↓
Failure
   ↓
Retry
   ↓
Template / Rule-based Fallback
   ↓
Canonical ExerciseSet
```

Frontend chỉ render `ExerciseSet`.

---

# 12. Remove local scoring fallback

Không nên:

```text
generationRunId exists?
   ├── Yes → backend score
   └── No  → local score
```

Target:

```text
LearningActivity
    ↓
Submission
    ↓
Backend Grader
    ↓
Result
```

---

# 13. Submission model

```python
Submission:
    id
    activity_id
    learner_id
    submitted_at
    score
    total_questions
```

```python
Answer:
    id
    submission_id
    exercise_id
    user_answer
    is_correct
```

Error diagnosis gắn với:

```text
Answer
   ↓
ErrorDiagnosis
```

---

# 14. Priority 6 — REVIEW capability

Ví dụ:

```text
User:
"Tại sao câu 3 sai?"
```

Flow:

```text
ConversationRouter
        ↓
REVIEW
        ↓
Resolve referenced activity
        ↓
Resolve question
        ↓
Load exercise + answer + diagnosis + mastery
        ↓
ReviewService
        ↓
Tutor explanation
```

Conversation cần:

```text
active_activity_id
recent_activity_ids
```

---

# 15. Priority 7 — PROGRESS capability

Ví dụ:

```text
"Tôi đang yếu gì?"
"Tôi tiến bộ không?"
"Tense nào tôi yếu nhất?"
```

Flow:

```text
PROGRESS
   ↓
LearnerProgressService
   ↓
Load mastery
   ↓
Load learning history
   ↓
Load error patterns
   ↓
Summarize
   ↓
Tutor response
```

Có thể expose:

```python
get_skill_mastery(user_id)
get_weak_skills(user_id)
get_recent_improvement(user_id)
get_error_patterns(user_id)
get_learning_summary(user_id)
```

---

# 16. Priority 8 — EXPLAIN capability

Ví dụ:

```text
"Past Perfect dùng khi nào?"
```

Không đi qua exercise generation.

```text
EXPLAIN
   ↓
TutorExplanationService
   ↓
Retrieve relevant knowledge
   ↓
RAG context
   ↓
Generate personalized explanation
```

---

# 17. Priority 9 — PROFILE_UPDATE capability

Ví dụ:

```text
"Từ giờ cho tôi bài khó hơn."
"Tôi muốn luyện IELTS."
"Mỗi bài khoảng 5 câu thôi."
```

Flow:

```text
PROFILE_UPDATE
       ↓
Extract learner facts
       ↓
Validate
       ↓
Update LearnerProfile / Preferences
       ↓
Confirm
```

Không đưa user trở lại onboarding mode.

---

# 18. Progressive profiling

Onboarding vẫn giữ được, nhưng không phải cổng bắt buộc.

Target:

```text
Minimum Viable Profile
       ↓
Progressive Profile Enrichment
```

Ví dụ user chưa có level nhưng nói:

```text
"Cho tôi 5 câu Present Simple."
```

Vẫn tạo activity được.

---

# 19. Priority 10 — Structured Recommendation

Không chỉ lưu recommendation dạng text.

```json
{
  "recommendation_id": "rec_123",
  "type": "next_practice",
  "target_skill": "past_simple",
  "difficulty": "medium",
  "num_questions": 5,
  "reason": "Repeated irregular verb errors"
}
```

Accept recommendation:

```text
Recommendation
    ↓
Accept
    ↓
Practice Planner
    ↓
Create LearningActivity
```

Không cần:

```text
recommendation → prompt → parse lại
```

---

# 20. Conversation model

```text
Conversation
│
├── Messages
├── Learning Activities
├── Memory Summary
└── Pending Context
```

Ví dụ:

```text
Conversation
├── User Message
├── Assistant Message
├── Practice Activity
├── Result
├── User: "why was question 3 wrong?"
├── Review Response
└── Recommendation
```

---

# 21. New Chat semantics

New Chat chỉ tạo:

```text
new Conversation
```

Không reset:

```text
LearnerProfile
Mastery
Preferences
LearningHistory
Goals
```

---

# 22. Suggested backend structure

```text
app/
├── conversation/
│   ├── router.py
│   ├── models.py
│   ├── service.py
│   └── context.py
│
├── learner/
│   ├── profile.py
│   ├── mastery.py
│   └── progress.py
│
├── activity/
│   ├── models.py
│   ├── lifecycle.py
│   └── repository.py
│
├── practice/
│   ├── service.py
│   ├── planner.py
│   ├── generator.py
│   ├── validator.py
│   └── grader.py
│
├── review/
│   └── service.py
│
├── tutor/
│   └── explanation.py
│
├── recommendation/
│   └── service.py
│
├── retrieval/
├── persistence/
├── llm/
└── api/
```

Không cần rename toàn bộ module hiện tại ngay.

---

# 23. ConversationService

Nên có entry point chung:

```python
class ConversationService:

    async def handle_message(
        self,
        learner_id: str,
        conversation_id: str,
        message: str,
    ):
        ...
```

Flow:

```text
Persist user message
      ↓
Load conversation context
      ↓
Resolve pending intent
      ↓
ConversationRouter
      ↓
Dispatch capability
      ↓
Persist assistant response / activity
      ↓
Return response
```

---

# 24. Dispatch pseudocode

```python
route = router.route(message, context)

match route.intent:

    case PRACTICE:
        return practice_service.handle(...)

    case EXPLAIN:
        return explanation_service.handle(...)

    case REVIEW:
        return review_service.handle(...)

    case PROGRESS:
        return progress_service.handle(...)

    case PROFILE_UPDATE:
        return profile_service.handle_update(...)

    case GENERAL:
        return tutor_service.respond(...)
```

---

# 25. API direction

## Conversation

```text
POST /api/conversations
GET  /api/conversations
GET  /api/conversations/{id}

POST /api/conversations/{id}/messages
```

## Activity

```text
GET  /api/activities/{id}
POST /api/activities/{id}/submit
GET  /api/activities/{id}/review
```

## Learner

```text
GET   /api/learners/{id}/profile
PATCH /api/learners/{id}/profile

GET /api/learners/{id}/mastery
GET /api/learners/{id}/progress
```

## Recommendation

```text
GET  /api/learners/{id}/recommendations
POST /api/recommendations/{id}/accept
```

Không cần xóa ngay API hiện tại:

```text
/api/practice/generate
/api/practice/score
```

Có thể migrate implementation bên trong trước.

---

# 26. Frontend refactor

Không nên để frontend quyết định:

```text
if onboarding:
    onboarding
else:
    generate practice
```

Target:

```text
submitMessage()
     ↓
POST conversation message
     ↓
Backend returns response type
```

Response có thể là:

```json
{
  "type": "message",
  "content": "..."
}
```

hoặc:

```json
{
  "type": "clarification",
  "content": "Bạn muốn bao nhiêu câu?"
}
```

hoặc:

```json
{
  "type": "learning_activity",
  "activity": {}
}
```

hoặc:

```json
{
  "type": "progress_summary",
  "data": {}
}
```

Frontend trở thành renderer.

---

# 27. Phase implementation

## Phase 1 — Conversation Router

- [ ] `ConversationIntent`
- [ ] `ConversationRoute`
- [ ] `ConversationRouter`
- [ ] unit tests
- [ ] PRACTICE
- [ ] EXPLAIN
- [ ] REVIEW
- [ ] PROGRESS
- [ ] PROFILE_UPDATE
- [ ] GENERAL fallback

## Phase 2 — ConversationService

- [ ] `handle_message()`
- [ ] load context
- [ ] persist user message
- [ ] route intent
- [ ] dispatch service
- [ ] persist assistant result
- [ ] pending clarification

## Phase 3 — LearningActivity

- [ ] `LearningActivity`
- [ ] `activity_id`
- [ ] `ActivityStatus`
- [ ] link `learner_id`
- [ ] link `conversation_id`
- [ ] optional `generation_run_id`
- [ ] persistence

## Phase 4 — Practice migration

- [ ] PracticePipeline creates activity
- [ ] `CREATED → GENERATING`
- [ ] generation output belongs to activity
- [ ] backend validation/fallback
- [ ] `READY`
- [ ] submission uses `activity_id`

## Phase 5 — Backend grading

- [ ] remove frontend score fallback
- [ ] backend owns grading
- [ ] Submission
- [ ] Answer
- [ ] ErrorDiagnosis
- [ ] `SUBMITTED → GRADED → COMPLETED`

## Phase 6 — Review

- [ ] `ReviewService`
- [ ] resolve activity
- [ ] resolve question
- [ ] explain diagnosis

## Phase 7 — Progress

- [ ] `LearnerProgressService`
- [ ] weak skills
- [ ] mastery summary
- [ ] recent improvement
- [ ] error patterns

## Phase 8 — Profile Update

- [ ] update preference outside onboarding
- [ ] progressive profiling
- [ ] preserve learner state across New Chat

## Phase 9 — Structured Recommendation

- [ ] recommendation entity
- [ ] structured next-activity parameters
- [ ] accept recommendation
- [ ] direct create activity

## Phase 10 — Frontend cleanup

- [ ] submit via Conversation API
- [ ] remove practice-only top-level routing
- [ ] remove frontend exercise fallback
- [ ] remove local scoring fallback
- [ ] render response types
- [ ] separate UI state / domain state

---

# 28. Suggested PR sequence

## PR 1

```text
feat/conversation-router
```

Scope:

```text
ConversationIntent
ConversationRoute
ConversationRouter
Router tests
```

Integration ban đầu:

```text
ConversationRouter
    ↓
PRACTICE
    ↓
current PracticeIntentInterpreter
```

## PR 2

```text
feat/conversation-service
```

Scope:

```text
ConversationService.handle_message()
context loading
message persistence
router dispatch
```

Ban đầu chỉ cần:

```text
PRACTICE
GENERAL
```

## PR 3

```text
feat/learning-activity
```

Scope:

```text
LearningActivity
ActivityStatus
activity persistence
PracticePipeline integration
```

---

# 29. Priority thực tế

```text
P0  ConversationRouter
P0  ConversationService
P0  LearningActivity + activity_id

P1  Backend grading / remove frontend fallback
P1  REVIEW
P1  PROGRESS

P2  PROFILE_UPDATE
P2  EXPLAIN
P2  Structured Recommendation

P3  More activity types
```

---

# 30. Chưa nên làm ngay

Tạm thời chưa cần:

```text
10-agent multi-agent system
complex autonomous agents
full LangGraph rewrite
microservices
Kafka
event sourcing
large skill graph
complex planning engine
```

Domain flow phải ổn trước.

---

# 31. LangGraph

Không cần rewrite toàn bộ conversation bằng LangGraph ngay.

Trước hết phải rõ:

```text
Conversation
Intent
Activity
Learner
```

Sau đó mới dùng LangGraph nơi có workflow thực sự nhiều bước, ví dụ:

```text
Practice generation
Adaptive review
Complex activity workflow
```

Router/domain boundaries không nên phụ thuộc framework.

---

# 32. Target architecture

```text
                        User
                         │
                         ▼
                  Conversation API
                         │
                         ▼
                Conversation Service
                         │
                         ▼
                Conversation Router
                         │
       ┌─────────────────┼──────────────────┐
       │                 │                  │
       ▼                 ▼                  ▼
    PRACTICE           REVIEW            EXPLAIN
       │                 │                  │
       ▼                 ▼                  ▼
Practice Service    Review Service    Tutor Service
       │
       ▼
LearningActivity
       │
       ▼
Practice Planner
       │
       ▼
Learner Context + RAG
       │
       ▼
Exercise Generator
       │
       ▼
Validator / Fallback
       │
       ▼
Activity READY
       │
       ▼
Submission
       │
       ▼
Grader
       │
       ▼
Error Diagnosis
       │
       ▼
Mastery Update
       │
       ▼
Recommendation
       │
       └──────────────→ Next Activity
```

Other branches:

```text
PROGRESS
   ↓
LearnerProgressService

PROFILE_UPDATE
   ↓
LearnerProfileService

GENERAL
   ↓
TutorConversationService
```

---

# 33. Definition of Done

Refactor đạt target cơ bản khi các case sau chạy đúng:

## Case 1 — Practice

```text
"Cho tôi 5 câu Past Simple."
```

→ tạo `LearningActivity(PRACTICE)`.

## Case 2 — Clarification

```text
"Tôi muốn luyện ngữ pháp."
```

Assistant hỏi chủ đề.

User:

```text
"Past Simple."
```

→ tiếp tục pending practice thay vì route mới.

## Case 3 — Review

```text
"Tại sao câu 3 sai?"
```

→ `REVIEW`, không generate bài mới.

## Case 4 — Progress

```text
"Tôi đang yếu phần nào?"
```

→ `PROGRESS`.

## Case 5 — Explain

```text
"Present Perfect dùng khi nào?"
```

→ `EXPLAIN`.

## Case 6 — Profile update

```text
"Từ giờ mỗi bài 5 câu thôi."
```

→ `PROFILE_UPDATE`.

## Case 7 — New Chat

Tạo conversation mới nhưng giữ:

```text
profile
mastery
preferences
learning history
```

## Case 8 — Backend failure

Frontend không tự generate bài.

Backend xử lý retry/fallback.

## Case 9 — Submission identity

Mọi submission dùng:

```text
activity_id
```

không phụ thuộc bắt buộc vào:

```text
generation_run_id
```

---

# 34. Tóm tắt

Current:

```text
Chat
  ↓
Practice-oriented orchestration
  ↓
Strong practice pipeline
```

Target:

```text
Conversation
      ↓
Intent Router
      ↓
Learning Capabilities
      ↓
Learning Activities
```

Các thay đổi quan trọng nhất:

```text
1. ConversationRouter
2. ConversationService
3. LearningActivity
4. activity_id thay business identity cho generation_run_id
5. Backend owns fallback and grading
6. REVIEW / PROGRESS / EXPLAIN / PROFILE_UPDATE thành capability riêng
7. Progressive profiling
8. Structured recommendation
9. Frontend chủ yếu render domain responses
```

Đây là đường refactor ngắn nhất để chuyển project từ:

```text
Personalized Exercise Chatbot
```

sang:

```text
Adaptive AI English Learning Platform
```

mà không rewrite những phần hiện tại đang hoạt động tốt.
