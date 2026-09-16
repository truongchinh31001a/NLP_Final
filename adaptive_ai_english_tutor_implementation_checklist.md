# Adaptive AI English Tutor — Refactor & Implementation Checklist

> Mục tiêu: chuyển hệ thống từ **Practice Chatbot** sang **Conversation Platform + Adaptive Learning Activities**, bám theo architecture đã chốt trên FigJam.

---

## Execution log

### 2026-09-06 — PR0/PR1 pass

- [x] Baseline backend regression: `python -m unittest discover tests` xanh `101 tests`.
- [x] AI eval baseline: `python scripts/run_evals.py` và `python scripts/check_eval_thresholds.py` xanh.
- [x] Frontend baseline: `npm --prefix frontend run lint` và `npm --prefix frontend run build` xanh.
- [x] LearningActivity lifecycle validation: reject invalid transitions, giữ transition idempotent.
- [x] ActivityStateEvent append-only contract: event có `event_id`, `activity_id`, `from_status`, `to_status`, `metadata`, `created_at`.
- [x] Repository parity: InMemory, SQLite, PostgreSQL cùng có transition validation và list state events.
- [x] Activity model bổ sung `parent_activity_id` và `config`.
- [x] API bổ sung `GET /api/users/{user_id}/activities` để list activity theo learner và filter status.
- [x] Frontend API/types nhận `parent_activity_id`, `config`, và có helper `listActivities`.
- [ ] Next actual gap: PR2 ConversationRouter audit/implementation; `conversation_id` nullable cho standalone activity tạm deferred vì repo hiện ràng activity với chat session.

### 2026-09-06 — FigJam 06 backend upgrade alignment

- [x] Đã đọc FigJam `06.1 — CANONICAL DATA MODEL · DATABASE SOURCE OF TRUTH`.
- [x] Đã đọc FigJam `06.2 — CANONICAL API MAP`.
- [x] Đã đọc FigJam `10.2 — Database Migration Order`.
- [x] Cập nhật checklist để xem FigJam 06 là north-star backend/data model, không phải yêu cầu rewrite tức thì.
- [x] Chốt nguyên tắc: database source of truth = 06.1; API source of truth = 06.2; business diagrams không tự định nghĩa DB; UI screens không tự định nghĩa domain state.

### 2026-09-06 — FigJam remaining diagrams alignment

- [x] Đã đọc các cụm FigJam còn lại: `01` product/domain, `02` learner journey, `03` tutor orchestration, `04` activity lifecycle, `05` architecture.
- [x] Đã đọc sequence flows `07` và `08`: practice happy path, pending clarification, explain/review/progress, creation/generation, fallback/retry, submit-to-recommendation, accept recommendation.
- [x] Đã đọc migration/frontend/testing/ops tracks `09` đến `15`.
- [x] Cập nhật checklist thành các track north-star còn lại, tách rõ product/frontend/ops/security/analytics/release khỏi FigJam 06 DB/API.

### 2026-09-06 — PR2 ConversationRouter pass

- [x] `ConversationRoute` domain contract có `requires_context`, `target_activity_id`, `missing_slots`, `next_action`.
- [x] Router giữ deterministic routes cho PRACTICE, EXPLAIN, REVIEW, PROGRESS, PROFILE_UPDATE, GENERAL.
- [x] PRACTICE route vẫn dispatch xuống `PracticeIntentInterpreter`.
- [x] LLM fallback cho ambiguous turns được test bằng mock Ollama, không cần runtime thật.
- [x] Route metadata/API/frontend types nhận đủ canonical route contract, giữ `referenced_activity_id` để tương thích.
- [x] Verification: `tests.test_conversation_router` xanh 24 tests; conversation discover xanh 54 tests; full backend unit xanh 107 tests; frontend lint/build xanh.

### 2026-09-06 — PR3 ConversationService pass

- [x] `ConversationService.handle_message` persists user message, builds turn context, routes, dispatches capability, persists assistant message, and returns `ConversationTurnResult`.
- [x] Conversation state exposes conversation id, recent messages, memory summary, active intent, pending clarification, active activity, and recent context ids.
- [x] Pending clarification now carries `active_activity_id` through domain model, repository payloads, API response, and frontend types.
- [x] Pending PRACTICE follow-up merges collected slots before fresh routing and clears stored pending state once complete.
- [x] Direct service tests cover context loading, pending resolution, PRACTICE/EXPLAIN/REVIEW/PROGRESS/PROFILE_UPDATE/GENERAL dispatch, and assistant persistence.
- [x] Verification: `python -m unittest discover tests` xanh `112 tests`; `npm --prefix frontend run lint` xanh; `npm --prefix frontend run build` xanh; `python scripts/run_evals.py` và `python scripts/check_eval_thresholds.py` xanh.

---

## 0. Nguyên tắc triển khai

- [x] Không rewrite toàn bộ hệ thống cùng lúc.
- [x] Giữ flow cũ hoạt động trong giai đoạn migration.
- [x] Refactor theo PR nhỏ, có test và rollback rõ ràng.
- [x] `activity_id` là **business identity**.
- [x] `generation_run_id` chỉ là **execution / observability identity**.
- [x] Frontend không được định nghĩa business state bằng screen local.
- [x] Backend sở hữu generation, fallback, grading và domain lifecycle.
- [x] `PracticeIntentInterpreter` tiếp tục tồn tại nhưng nằm dưới `ConversationRouter`.
- [x] Recommendation phải tạo next activity từ structured spec, không copy text vào composer để parse lại.

---

# P0 — FOUNDATION

## 1. Baseline Regression Tests

- [x] Chạy toàn bộ test hiện tại và lưu baseline.
- [x] Ghi lại API flow hiện tại:
  - [x] `/api/practice/generate`
  - [x] `/api/practice/score`
  - [x] `/api/users/{user_id}/practice/interpret`
  - [x] `/api/users/{user_id}/chat/*`
  - [x] `/api/users/{user_id}/profile`
- [x] Thêm test cho generate → score flow hiện tại.
- [x] Thêm test cho chat session/history hiện tại.
- [x] Thêm test cho practice intent interpreter.
- [x] Xác nhận InMemory repository hoạt động.
- [x] Xác nhận SQLite repository hoạt động.
- [x] Xác nhận frontend vẫn build/run trước khi refactor.

---

# PR 1 — LearningActivity Foundation

## 2. Tạo domain `activity`

Target:

```text
app/
└── activity/
    ├── __init__.py
    ├── models.py
    ├── lifecycle.py
    ├── repository.py
    └── service.py
```

### 2.1 `LearningActivity`

- [x] Tạo `LearningActivity`.
- [x] Thêm `activity_id`.
- [x] Thêm user identity (`learner_id` trong domain hiện tại).
- [ ] Thêm nullable `conversation_id`.
- [x] Thêm nullable `parent_activity_id`.
- [x] Thêm `activity_type` (`type` trong domain hiện tại).
- [x] Thêm `status`.
- [x] Thêm nullable `difficulty`.
- [x] Thêm `config`.
- [x] Thêm `created_at`.
- [x] Thêm `updated_at`.

### 2.2 Activity lifecycle

Canonical states:

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

FAILED
CANCELLED
```

- [x] Tạo `ActivityStatus`.
- [x] Định nghĩa valid transitions.
- [x] Reject invalid transitions.
- [x] Tạo helper validate transition (`validate_learning_activity_transition`).
- [x] Không dùng frontend screen làm domain status.

### 2.3 ActivityStateEvent

- [x] Tạo append-only `ActivityStateEvent`.
- [x] `event_id`.
- [x] `activity_id`.
- [x] `from_status`.
- [x] `to_status`.
- [x] nullable `reason`.
- [x] metadata.
- [x] `created_at`.

### 2.4 Repository contract

Bổ sung các operation:

- [x] `create_activity(...)` qua `create_learning_activity(...)`
- [x] `get_activity(activity_id)` qua `get_learning_activity(user_id, activity_id)`
- [x] `update_activity(...)` qua metadata/status update methods hiện có
- [x] `transition_activity(...)` qua `update_learning_activity_status(...)`
- [x] `list_user_activities(...)`
- [x] `save_activity_state_event(...)` qua append-only `_record_activity_event(...)`
- [x] `list_activity_state_events(...)`

### 2.5 InMemory persistence

- [x] Implement activity persistence trong `InMemoryLearningRepository`.
- [x] Implement state-event persistence.
- [x] Test create/get/update.
- [x] Test valid transition.
- [x] Test invalid transition.
- [x] Test list activities theo learner.

### 2.6 SQLite persistence

- [x] Additive migration cho `learning_activities`.
- [x] Additive migration cho `activity_state_events`.
- [x] Thêm index cần thiết.
- [x] Thêm FK khi phù hợp.
- [x] Implement create/get/update.
- [x] Implement lifecycle event append.
- [x] Không xóa schema cũ ở PR này.

### 2.7 Test PR 1

```text
tests/
└── activity/
    ├── test_activity_lifecycle.py
    └── test_activity_repository.py
```

- [x] CREATED → GENERATING.
- [x] GENERATING → READY.
- [x] READY → IN_PROGRESS.
- [x] IN_PROGRESS → SUBMITTED.
- [x] SUBMITTED → GRADED.
- [x] GRADED → COMPLETED.
- [x] Failure path.
- [x] Cancel path.
- [x] Invalid transition rejected.
- [x] InMemory parity.
- [x] SQLite parity.

---

# PR 2 — ConversationRouter

## 3. Tạo domain `conversation`

Target:

```text
app/
└── conversation/
    ├── __init__.py
    ├── models.py
    ├── router.py
    └── context.py
```

### 3.1 Top-level intents

- [x] `PRACTICE`
- [x] `EXPLAIN`
- [x] `REVIEW`
- [x] `PROGRESS`
- [x] `PROFILE_UPDATE`
- [x] `GENERAL`

### 3.2 Router output contract

- [x] `intent`
- [x] `confidence`
- [x] `requires_context`
- [x] nullable `target_activity_id`
- [x] `slots`
- [x] `missing_slots`
- [x] `next_action`

### 3.3 Routing strategy

- [x] Deterministic routing cho strong signals.
- [x] LLM fallback cho ambiguous requests.
- [x] Không biến mọi message thành PRACTICE.
- [x] Không xóa `PracticeIntentInterpreter`.
- [x] PRACTICE route phải dispatch xuống `PracticeIntentInterpreter`.

Canonical:

```text
User Message
    ↓
ConversationRouter
    ├── PRACTICE → PracticeIntentInterpreter
    ├── EXPLAIN
    ├── REVIEW
    ├── PROGRESS
    ├── PROFILE_UPDATE
    └── GENERAL
```

### 3.4 Router tests

- [x] “Cho tôi 5 câu Past Simple” → PRACTICE.
- [x] “Present Perfect dùng khi nào?” → EXPLAIN.
- [x] “Tại sao câu 3 sai?” → REVIEW.
- [x] “Tôi đang yếu phần nào?” → PROGRESS.
- [x] “Từ giờ mỗi bài 5 câu thôi.” → PROFILE_UPDATE.
- [x] Generic conversational message → GENERAL.
- [x] Ambiguous intent handling.
- [x] Confidence behavior.

---

# PR 3 — ConversationService

## 4. Tạo `ConversationService`

Target:

```text
app/conversation/service.py
```

Canonical flow:

```text
handle_message
    ↓
persist user message
    ↓
load conversation state
    ↓
resolve pending intent
    ↓
load learner context
    ↓
extract profile facts
    ↓
route
    ↓
dispatch
    ↓
persist assistant result
    ↓
return typed response
```

### 4.1 Conversation state

- [x] `conversation_id`
- [x] `messages`
- [x] `memory_summary`
- [x] `active_intent`
- [x] `pending_clarification`
- [x] `recent_context`

### 4.2 Pending intent

- [x] `pending_intent`
- [x] `missing_fields`
- [x] `collected_slots`
- [x] `active_activity_id`
- [x] Merge follow-up message vào pending intent trước fresh routing.
- [x] Clear pending state khi đủ slot.

Example:

```text
User: Tôi muốn luyện ngữ pháp
→ PRACTICE
→ thiếu topic

Assistant: Bạn muốn luyện chủ đề nào?

User: Past Simple
→ merge topic
→ vẫn giữ PRACTICE context

User: 5 câu thôi
→ merge num_questions
→ generate activity
```

### 4.3 ConversationService tests

- [x] Persist user message.
- [x] Load conversation context.
- [x] Resolve pending clarification.
- [x] Dispatch PRACTICE.
- [x] Dispatch EXPLAIN.
- [x] Dispatch REVIEW.
- [x] Dispatch PROGRESS.
- [x] Dispatch PROFILE_UPDATE.
- [x] Dispatch GENERAL.
- [x] Persist assistant response.

---

# P0 — PRACTICE MIGRATION

# PR 4 — Practice behind ActivityService

## 5. Tạo `ActivityService`

- [x] `create_activity(...)`
- [x] `get_activity(...)`
- [x] `start_generation(...)`
- [x] `mark_ready(...)`
- [x] `start_activity(...)`
- [x] `submit_activity(...)`
- [x] `grade_activity(...)`
- [x] `complete_activity(...)`
- [x] `fail_activity(...)`

### 5.1 Generation flow

Target:

```text
ConversationService
      ↓
ActivityService.create()
      ↓
LearningActivity CREATED
      ↓
GENERATING
      ↓
PracticeService.generate()
      ↓
READY
```

- [x] Activity phải được tạo **trước generation**.
- [x] Có `activity_id` ngay từ CREATED.
- [x] Persist exercise set dưới activity.
- [x] `generation_run_id` chỉ dùng trace.
- [x] Không dùng `generation_run_id` làm business key.

---

## 6. Tạo / chuẩn hóa `practice` package

Target:

```text
app/
└── practice/
    ├── service.py
    ├── planner.py
    ├── generator.py
    ├── validator.py
    └── grader.py
```

- [x] Wrap module generation hiện tại thay vì rewrite.
- [x] Wrap retrieval hiện tại.
- [x] Wrap personalization hiện tại.
- [x] Wrap validator hiện tại.
- [x] Tách grading khỏi frontend.
- [x] Giữ compatibility với pipeline cũ trong migration.

---

# PR 5 — Backend Ownership

## 7. Backend owns generation

- [ ] Generate exercise ở backend.
- [ ] Validate exercise ở backend.
- [ ] Fallback exercise ở backend.
- [ ] Persist fallback như canonical activity content.
- [ ] Record failure/recovery state event.
- [ ] Không tạo preview fallback ở frontend.

## 8. Backend owns grading

Target:

```text
activity_id
   ↓
Submission
   ↓
Backend Grader
   ↓
Score
```

- [ ] Submit bằng `activity_id`.
- [ ] Không yêu cầu `generation_run_id` để submit.
- [ ] Grading ở backend.
- [ ] Không local scoring theo `correctAnswer` ở frontend.
- [ ] Validation answer payload.
- [ ] Persist submission.
- [ ] Persist answers.

---

# P1 — ADAPTIVE LEARNING

# PR 6 — Assessment Evidence & Mastery

## 9. Canonical evidence chain

```text
LearningActivity
    ↓
ExerciseSet
    ↓
Exercise
    ↓
Submission
    ↓
Answer
    ↓
SkillObservation
    ↓
MasteryEvent
    ↓
LearnerSkillMastery
```

### 9.1 Submission

- [ ] `submission_id`
- [ ] `activity_id`
- [ ] `learner_id`
- [ ] timestamps
- [ ] total score
- [ ] metadata

### 9.2 Answer

- [ ] `answer_id`
- [ ] `submission_id`
- [ ] `exercise_id`
- [ ] learner answer
- [ ] nullable `is_correct`
- [ ] partial score
- [ ] feedback

### 9.3 Skill

- [ ] Canonical `Skill`.
- [ ] `parent_skill_id`.
- [ ] Optional `SkillRelation`.
- [ ] Exercise → multi-skill mapping.

### 9.4 SkillObservation

- [ ] Raw evidence.
- [ ] `learner_id`
- [ ] `skill_id`
- [ ] `answer_id`
- [ ] evidence value
- [ ] confidence
- [ ] metadata
- [ ] append-only

### 9.5 MasteryEvent

- [ ] append-only
- [ ] model type
- [ ] model version
- [ ] evidence refs
- [ ] mastery before
- [ ] mastery after
- [ ] confidence
- [ ] metadata

### 9.6 LearnerSkillMastery

- [ ] Composite identity learner + skill.
- [ ] Current mastery snapshot.
- [ ] Last updated.
- [ ] Confidence.
- [ ] Không mất history vì đã có MasteryEvent.

### 9.7 ReviewSchedule

- [ ] learner + skill uniqueness.
- [ ] next review time.
- [ ] interval.
- [ ] scheduling metadata.

---

# P1 — TUTOR CAPABILITIES

# PR 7 — Explain / Review / Progress / Profile

## 10. EXPLAIN

- [ ] Tạo explanation service.
- [ ] Retrieval grounding.
- [ ] Return `assistant_message`.
- [ ] Citation/source metadata nếu có.
- [ ] Không generate practice khi user chỉ hỏi giải thích.

## 11. REVIEW

- [ ] Resolve active/latest activity.
- [ ] Resolve “câu 3”.
- [ ] Load submission.
- [ ] Load answer.
- [ ] Load diagnosis.
- [ ] Explain mistake.
- [ ] Return `review_result`.
- [ ] Review là domain capability, không chỉ `setScreen("practice")`.

## 12. PROGRESS

- [ ] Load mastery snapshot.
- [ ] Load history.
- [ ] Detect weak skills.
- [ ] Detect strength.
- [ ] Score trend.
- [ ] Return `progress_summary`.

## 13. PROFILE_UPDATE

- [ ] Progressive profiling.
- [ ] Update learner preferences.
- [ ] Update goals.
- [ ] Update preferred difficulty.
- [ ] Update preferred number of questions.
- [ ] Return `profile_update_confirmation`.
- [ ] Không reset learner model khi tạo New Chat.

## 14. GENERAL

- [ ] General tutor response.
- [ ] Không cưỡng ép practice generation.
- [ ] Giữ conversation continuity.

---

# P1 — RECOMMENDATION LOOP

# PR 8 — Structured Recommendation

## 15. Recommendation entity

- [ ] `recommendation_id`
- [ ] `source_activity_id`
- [ ] nullable `target_skill_id`
- [ ] `activity_spec`
- [ ] `accepted`
- [ ] `dismissed`
- [ ] nullable `result_activity_id`
- [ ] optional expiry

### 15.1 Recommendation acceptance

Target:

```text
Recommendation
     ↓
activity_spec
     ↓
ActivityService.create()
     ↓
new activity_id
```

- [ ] `POST /recommendations/{id}/accept`
- [ ] Load structured recommendation.
- [ ] Check current learner state.
- [ ] Create new LearningActivity.
- [ ] Generate content.
- [ ] Persist READY.
- [ ] Set `result_activity_id`.
- [ ] Return `learning_activity`.
- [ ] Không copy recommendation text vào composer.
- [ ] Không parse recommendation text lại.

---

# P1 — CANONICAL API

# PR 9 — Canonical API Surface

## 16. Conversation API

- [ ] `POST /api/conversations`
- [ ] `GET /api/conversations/{id}`
- [ ] `POST /api/conversations/{id}/messages`

## 17. Activity API

- [ ] `GET /api/activities/{id}`
- [ ] `POST /api/activities/{id}/submit`
- [ ] `GET /api/activities/{id}/review`

## 18. Learner API

- [ ] `GET /api/learners/{id}`
- [ ] `PATCH /api/learners/{id}/profile`
- [ ] `GET /api/learners/{id}/mastery`
- [ ] `GET /api/learners/{id}/progress`

## 19. Recommendation API

- [ ] `GET /api/recommendations`
- [ ] `POST /api/recommendations/{id}/accept`

## 20. Learning Plan API

- [ ] LearningPlan endpoints khi feature được triển khai.
- [ ] Không bắt buộc cho MVP đầu tiên.

---

# PR 10 — Typed Response Contract

## 21. Canonical response types

- [ ] `assistant_message`
- [ ] `clarification`
- [ ] `learning_activity`
- [ ] `progress_summary`
- [ ] `review_result`
- [ ] `profile_update_confirmation`

Example:

```ts
type ConversationTurnResponse =
  | { type: "assistant_message"; message: AssistantMessageDto }
  | { type: "clarification"; message: AssistantMessageDto; pending: PendingIntentDto }
  | { type: "learning_activity"; message?: AssistantMessageDto; activity: LearningActivitySummaryDto }
  | { type: "progress_summary"; message?: AssistantMessageDto; summary: ProgressSummaryDto }
  | { type: "review_result"; message?: AssistantMessageDto; review: ReviewResultDto }
  | {
      type: "profile_update_confirmation";
      message?: AssistantMessageDto;
      profile: LearnerProfileDto;
      updatedFields: string[];
    };
```

- [ ] Backend response type là source of truth.
- [ ] Frontend không infer flow từ ad-hoc data shape.

---

# P1 — FRONTEND MIGRATION

# PR 11 — Typed Rendering & State Ownership

## 22. Target frontend structure

```text
frontend/
├── app/
├── features/
│   ├── tutor/
│   ├── activity/
│   ├── progress/
│   └── profile/
├── components/
│   └── shared/
├── hooks/
├── lib/
│   └── api/
└── types/
```

## 23. TutorResponseRenderer

- [ ] Render theo `response.type`.
- [ ] `AssistantMessage`
- [ ] `ClarificationCard`
- [ ] `LearningActivityCard`
- [ ] `ProgressSummaryCard`
- [ ] `ReviewResultCard`
- [ ] `ProfileUpdateConfirmation`

## 24. LearningActivity rendering

Map status:

- [ ] CREATED → generating/loading UI.
- [ ] GENERATING → generating UI.
- [ ] READY → practice workspace.
- [ ] IN_PROGRESS → practice workspace.
- [ ] SUBMITTED → submitting/waiting UI.
- [ ] GRADED → result UI.
- [ ] COMPLETED → result/history UI.
- [ ] FAILED → failure/retry UI.
- [ ] CANCELLED → cancelled UI.

## 25. State ownership

### Server State

- [ ] Conversations/messages.
- [ ] Learning activities.
- [ ] Learner profile/preferences.
- [ ] Mastery/progress.
- [ ] Recommendations.

### Feature Client State

- [ ] active conversation ID.
- [ ] active activity ID.
- [ ] draft answers.
- [ ] composer draft.
- [ ] loading/submitting flags.

### Component Local State

- [ ] modal state.
- [ ] drawer state.
- [ ] expanded/collapsed.
- [ ] focus/temp input.

---

# PR 12 — Split Frontend God Component

## 26. `chat-workbench.tsx`

- [ ] Không rewrite file này trước khi canonical backend contract ổn định.
- [ ] Tách Tutor workspace.
- [ ] Tách Activity workspace.
- [ ] Tách Progress view.
- [ ] Tách Profile view.
- [ ] Tách response renderer.
- [ ] Tách API client.
- [ ] Tách hooks/store.
- [ ] Bỏ onboarding-vs-generate branching.
- [ ] Bỏ frontend local preview generation.
- [ ] Bỏ frontend local grading.
- [ ] New Chat chỉ reset conversation state.
- [ ] New Chat không reset learner profile/mastery/preferences.

---

# P2 — LEGACY MIGRATION & CLEANUP

## 27. Legacy compatibility adapters

Giữ tạm:

- [ ] `/api/users/{user_id}/chat/*`
- [ ] `/api/users/{user_id}/practice/interpret`
- [ ] `/api/practice/generate`
- [ ] `/api/practice/score`
- [ ] `/api/users/{user_id}/onboarding/interpret`

Rules:

- [ ] Legacy route chỉ validate/map/delegate.
- [ ] Không duplicate business logic.
- [ ] Legacy và canonical cùng gọi shared application services.
- [ ] Contract parity tests.
- [ ] Add deprecation notes.

## 28. Remove legacy flow

Chỉ làm sau khi canonical frontend đã cutover:

- [ ] Xóa frontend local fallback.
- [ ] Xóa duplicated business branching.
- [ ] Xóa deprecated endpoints.
- [ ] Xóa compatibility writes.
- [ ] Xóa legacy DB columns khi đã backfill và verify.
- [ ] Không xóa GenerationRun observability data.

---

# TESTING STRATEGY

## 29. Unit tests

- [x] ConversationRouter.
- [ ] PracticeIntentInterpreter.
- [ ] Activity lifecycle.
- [ ] Activity repository.
- [ ] Grading.
- [ ] Mastery update.
- [ ] Recommendation generation.
- [ ] Recommendation acceptance.

## 30. Contract tests

- [ ] Canonical API response types.
- [ ] Typed schema validation.
- [ ] Legacy adapter parity.
- [ ] `activity_id` usage.
- [ ] `generation_run_id` không còn bắt buộc cho submit.

## 31. Integration tests

- [ ] Practice happy path.
- [ ] Pending clarification.
- [ ] Generation fallback.
- [ ] Submit → grading.
- [ ] Submit → SkillObservation.
- [ ] SkillObservation → MasteryEvent.
- [ ] MasteryEvent → LearnerSkillMastery.
- [ ] Mastery → recommendation.
- [ ] Recommendation → next activity.

## 32. E2E acceptance tests

- [ ] “Cho tôi 5 câu Past Simple”.
- [ ] “Tôi muốn luyện ngữ pháp” → clarification.
- [ ] “Past Simple” → resume pending PRACTICE.
- [ ] “Tại sao câu 3 sai?” → REVIEW.
- [ ] “Tôi đang yếu phần nào?” → PROGRESS.
- [ ] “Present Perfect dùng khi nào?” → EXPLAIN.
- [ ] “Từ giờ mỗi bài 5 câu thôi.” → PROFILE_UPDATE.
- [ ] New Chat preserves learner state.
- [ ] Submit uses `activity_id`.
- [ ] Accept recommendation creates next activity directly.

---

# OBSERVABILITY / EVALUATION / MLOPS

## 33. Trace model

Business IDs:

- [ ] `conversation_id`
- [ ] `message_id`
- [ ] `activity_id`
- [ ] `submission_id`
- [ ] `recommendation_id`

Execution IDs:

- [ ] `trace_id`
- [ ] `generation_run_id`

Rule:

```text
activity_id       = business identity
trace_id          = workflow execution
generation_run_id = one AI generation execution
```

## 34. Structured telemetry

- [ ] Router span.
- [ ] Application service span.
- [ ] Retrieval span.
- [ ] LLM span.
- [ ] Validation span.
- [ ] Grading span.
- [ ] Mastery update span.
- [ ] Recommendation span.

Metrics:

- [ ] latency p50/p95.
- [ ] error rate.
- [ ] fallback rate.
- [ ] token usage.
- [ ] cost.
- [ ] retrieval quality.
- [ ] generation validity.
- [ ] grading failures.
- [ ] recommendation acceptance.
- [ ] activity completion.

## 35. AI Evaluation

### Routing

- [ ] intent accuracy.
- [ ] clarification precision.

### Retrieval

- [ ] Recall@K.
- [ ] MRR.
- [ ] grounding coverage.

### Generation

- [ ] correctness.
- [ ] relevance.
- [ ] validity.
- [ ] groundedness.
- [ ] difficulty fit.

### Adaptation

- [ ] recommendation relevance.
- [ ] mastery calibration.
- [ ] next-activity fit.

Evaluator types:

- [ ] deterministic.
- [ ] reference-based.
- [ ] LLM-as-judge.
- [ ] human review.

---

# SECURITY

## 36. Trust boundaries

- [ ] Authentication.
- [ ] Authorization.
- [ ] Rate limiting.
- [ ] Input validation.
- [ ] Ownership check.
- [ ] Purpose-limited access.
- [ ] Audit trail.

Principles:

```text
Model output != trusted data
Retrieved content != trusted instruction
Client-provided ID != authorization
Tool call != permission to execute
```

## 37. LLM / Agent guardrails

- [ ] Prompt injection detection.
- [ ] PII redaction.
- [ ] Retrieval content isolation.
- [ ] Tool allowlist.
- [ ] Tool argument validation.
- [ ] Authorization before tool execution.
- [ ] Timeout.
- [ ] Cost/token budget.
- [ ] Output validation.
- [ ] Fail-safe behavior.

---

# DEPLOYMENT & OPERATIONS

## 38. CI/CD

- [ ] Unit tests.
- [ ] Contract tests.
- [ ] Integration tests.
- [ ] AI eval.
- [ ] Security checks.
- [ ] Migration checks.
- [ ] Staging deployment.
- [ ] Smoke tests.
- [ ] E2E tests.
- [ ] Production deployment.
- [ ] Post-deploy telemetry verification.
- [ ] Rollback strategy.

## 39. Runtime configuration

- [ ] Versioned app config.
- [ ] Secrets management.
- [ ] Prompt/policy version.
- [ ] Model/provider version.
- [ ] Embedding version.
- [ ] Retriever/reranker version.
- [ ] Mastery model version.
- [ ] Evaluation dataset version.

---

# PRODUCT ANALYTICS & LEARNING EFFECTIVENESS

## 40. Core learning metrics

- [ ] activity completion.
- [ ] score trend.
- [ ] mastery change.
- [ ] review success.
- [ ] recommendation acceptance.
- [ ] next activity completion.
- [ ] difficulty match.
- [ ] retention/review performance.

## 41. Adaptive product north-star

Every new feature should answer:

> **Does this feature help the system understand the learner better or help the learner receive a more appropriate learning activity?**

- [ ] Nếu có → prioritize.
- [ ] Nếu liên kết yếu → simplify/defer.

---

# FIGJAM 06 CANONICAL BACKEND UPGRADE TRACK

Track này bám theo FigJam `06.1` (database source of truth), `06.2` (API source of truth), và `10.2` (database migration order). Đây là north-star để hoàn thiện hệ thống sau MVP, không phải rewrite một lần.

## 42. Source-of-truth rules từ FigJam

- [ ] `06.1` là nguồn chuẩn cho database/data contract.
- [ ] `06.2` là nguồn chuẩn cho API contract.
- [ ] Business/product diagrams không tự định nghĩa database tables.
- [ ] UI screens không tự định nghĩa domain state.
- [ ] Legacy endpoints chỉ là migration-only compatibility layer.
- [ ] Migration luôn additive trước.
- [ ] Sau additive migration phải backfill canonical IDs/relations.
- [ ] Tạm thời dual-write khi cần để giữ read parity.
- [ ] Chỉ switch read path sau khi verify counts, FK coverage, và read parity.
- [ ] Chỉ thêm NOT NULL/unique/FK strict constraints sau khi dữ liệu cũ đã sạch.
- [ ] Chỉ remove legacy columns/compatibility writes sau frontend/API cutover hoàn tất.

## 43. FigJam DB Phase 1 - Activity Foundation

Source: FigJam `10.2 — Phase 1 - Activity Foundation`.

- [x] `LearningActivity` tồn tại với `activity_id`, learner, conversation, parent activity, type/status/difficulty/config.
- [x] `ActivityStateEvent` có from/to status, reason, metadata, created time.
- [ ] Tạo canonical `ActivitySkill` join table thay vì chỉ lưu `target_skills_json`.
- [ ] Tạo canonical `ExerciseSet` entity/linkage thay vì dùng `generation_runs` như exercise set chính.
- [ ] Backfill `ActivitySkill` từ `learning_activities.target_skills_json`.
- [ ] Backfill `ExerciseSet.activityId` từ `generation_runs.activity_id`.
- [ ] Add index theo learner/status/activity type/updated time cho activity listing.
- [ ] Repository read path trả được activity kèm activity skills và exercise sets.
- [ ] Tests verify old JSON fields và canonical tables cho kết quả tương đương.

## 44. FigJam DB Phase 2 - Assessment Evidence

Source: FigJam `10.2 — Phase 2 - Assessment Evidence`.

- [ ] Tạo canonical `Submission` table hoặc mapping rõ từ `practice_sessions`.
- [ ] `Submission` có `activityId`, `attemptNo`, `rawScore`, `maxScore`, `normalizedScore`, `startedAt`, `submittedAt`.
- [ ] Tạo canonical `Answer` table hoặc nâng cấp `user_answers` theo contract FigJam.
- [ ] `Answer` có `submissionId`, `exerciseId`, `userAnswer`, `isCorrect`, `score`, `maxScore`, `latencyMs`.
- [ ] Tạo canonical `ExerciseSkill` join table.
- [ ] Tạo canonical `SkillObservation`.
- [ ] Mỗi answer/diagnosis sinh `SkillObservation` có learner, skill, activity, answer, score, max score, weight, metadata.
- [ ] Backfill `ExerciseSkill` từ exercise skill/subtopic/error tags hiện có.
- [ ] Backfill `SkillObservation` từ `answer_diagnoses` và `user_skill_mastery_history`.
- [ ] Tests verify evidence chain: activity -> exercise set -> exercise -> submission -> answer -> skill observation.

## 45. FigJam DB Phase 3 - Learner Model

Source: FigJam `10.2 — Phase 3 - Learner Model`.

- [ ] Tạo canonical `MasteryEvent`.
- [ ] `MasteryEvent` lưu learner, skill, activity, observation, model type/version, before score, after score, created time.
- [ ] Chuyển `user_skill_mastery_history` thành source/backfill cho `MasteryEvent`.
- [ ] Chuẩn hóa `LearnerSkillMastery` snapshot theo FigJam: learnerId + skillId, masteryScore, confidence, lastPracticedAt, updatedAt.
- [ ] Tạo canonical `ReviewSchedule`.
- [ ] `ReviewSchedule` có next/last review, algorithm, algorithmVersion, schedulerState, status.
- [ ] Repository/API progress đọc từ canonical mastery snapshot nhưng giữ compatibility với stats hiện có.
- [ ] Tests verify mastery update tạo observation + mastery event + snapshot update.
- [ ] Tests verify review schedule update không mất lịch sử mastery.

## 46. FigJam DB Phase 4 - Recommendation and Planning

Source: FigJam `10.2 — Phase 4 - Recommendation and Planning`.

- [ ] Tạo persistent `Recommendation` table.
- [ ] `Recommendation` có learnerId, sourceActivityId, targetSkillId, recommendationType, activitySpec, reason, status, resultActivityId, createdAt.
- [ ] Accept recommendation phải materialize activity từ `activitySpec`, không parse lại prompt text.
- [ ] Dismiss recommendation đổi status và giữ audit trail.
- [ ] Backfill recommendation records từ completed activities nếu có evidence đủ.
- [ ] Tạo canonical `LearningPlan`.
- [ ] Tạo `PlanGoal` join giữa learning plan và learning goals.
- [ ] Tạo `PlanItem` có skillId, activityId, activityType, activitySpec, priority, position, status, dueAt.
- [ ] `LearningPlanService` materialize plan item thành activity qua `ActivityService`.
- [ ] Tests verify recommendation accepted -> resultActivityId được set.
- [ ] Tests verify plan item -> activity giữ parent/source relation.

## 47. FigJam DB Phase 5 - Content, Media, and Observability

Source: FigJam `10.2 — Phase 5 - Content and Observability`.

- [ ] Nâng `GenerationRun` theo FigJam: activityId, conversationId, messageId, parentRunId, purpose, modelName, promptVersion, status, usage, createdAt.
- [ ] Tách `generation_run_id` khỏi business identity hoàn toàn trong read/write contracts.
- [ ] Tạo `ContentSource`.
- [ ] Tạo `ContentChunk`.
- [ ] Tạo `ContentChunkSkill`.
- [ ] Tạo `ContentEmbedding` có modelName/modelVersion/embedding.
- [ ] Backfill content source/chunk từ `knowledge_chunks`.
- [ ] Nếu dùng Chroma/pgvector song song, verify retrieval parity trước khi cutover.
- [ ] Tạo `MediaAsset`.
- [ ] Tạo `ExerciseAsset`.
- [ ] Tạo `AnswerAsset`.
- [ ] Media asset contract phục vụ listening/speaking/writing attachment sau này.
- [ ] Tests verify generation run trace gắn activity/conversation/message.
- [ ] Tests verify content chunk skill mapping ảnh hưởng retrieval/reranking đúng.

## 48. FigJam 06.2 Canonical API Gap List

Conversation API:

- [x] `POST /api/conversations`.
- [x] `GET /api/conversations`.
- [x] `GET /api/conversations/{conversationId}`.
- [x] `POST /api/conversations/{conversationId}/messages`.

Learning Activity API:

- [x] `GET /api/activities/{activityId}`.
- [ ] `POST /api/activities/{activityId}/start`.
- [x] `POST /api/activities/{activityId}/submit`.
- [x] `GET /api/activities/{activityId}/review`.
- [x] `GET /api/users/{user_id}/activities` as learner activity listing extension.

Recommendation API:

- [x] `GET learner recommendations`.
- [x] `POST /api/recommendations/{recommendationId}/accept`.
- [ ] `POST /api/recommendations/{recommendationId}/dismiss`.
- [ ] Recommendation response đọc từ persistent recommendation table sau Phase 4.

Learner API:

- [x] `GET/PATCH profile`.
- [ ] `GET/PATCH preferences` as canonical separate endpoint.
- [x] `GET mastery`.
- [x] `GET progress`.
- [ ] `GET/POST goals`.

Learning Plan API:

- [ ] `GET learner plans`.
- [ ] `POST learner plans`.
- [ ] `GET /api/plans/{planId}`.

Conversation response types:

- [x] `assistant_message`.
- [x] `clarification`.
- [x] `learning_activity`.
- [x] `progress_summary`.
- [x] `review_result`.
- [x] `profile_update_confirmation`.
- [ ] Add contract tests to ensure typed response variants stay stable.

Legacy migration-only API:

- [ ] Mark `practice interpret / generate / score` as legacy in docs and response headers where possible.
- [ ] Mark `/api/users/{user_id}/chat/*` as legacy in docs and response headers where possible.
- [ ] Mark onboarding interpret endpoint as migration-only after learner profile/preferences endpoints are canonical.
- [ ] Remove frontend reliance on legacy endpoints before deleting backend compatibility.

## 49. Canonical Data Model Coverage Matrix

Learner and profile:

- [x] `Learner` partially covered by `users`.
- [x] `LearnerProfile` partially covered by `user_profiles`.
- [ ] `LearnerPreference` should become canonical table/API, not only profile fields.
- [ ] `LearningGoal` should become canonical table/API.
- [ ] `LearnerMemoryFact` should become queryable table, not only summary JSON.

Conversation:

- [x] `Conversation` covered by `chat_sessions`.
- [x] `Message` covered by `chat_messages`.
- [x] `ConversationState` partially covered by pending clarification, active activity, and memory summary.
- [ ] Add optimistic `version` to conversation state when concurrent updates matter.

Activity and exercises:

- [x] `LearningActivity` covered.
- [x] `ActivityStateEvent` covered.
- [ ] `ActivitySkill` missing.
- [ ] `ExerciseSet` needs canonical table.
- [ ] `Exercise` needs canonical table or renamed/read-compatible mapping from `session_exercises`.
- [ ] `ExerciseTemplate` still seed/template-like, not canonical versioned template.
- [ ] `ExerciseSkill` missing.

Assessment:

- [ ] `Submission` needs canonical table or explicit mapping from `practice_sessions`.
- [ ] `Answer` needs canonical userAnswer/score/maxScore contract.
- [x] `ErrorDiagnosis` partially covered by `answer_diagnoses`.
- [ ] `SkillObservation` missing.
- [ ] `MasteryEvent` missing.

Adaptive planning:

- [ ] `Recommendation` persistent table missing.
- [ ] `LearningPlan` missing.
- [ ] `PlanGoal` missing.
- [ ] `PlanItem` missing.
- [x] `LearnerSkillMastery` partially covered by `user_skill_mastery`.
- [ ] `ReviewSchedule` should become canonical, currently mixed into mastery snapshot.

Content and media:

- [x] `Skill` partially covered by `skills`.
- [x] `SkillRelation` partially covered by `skill_dependencies`.
- [ ] `ContentSource` missing.
- [x] `ContentChunk` partially covered by `knowledge_chunks`.
- [ ] `ContentChunkSkill` missing.
- [ ] `ContentEmbedding` not canonical in SQLite schema.
- [ ] `MediaAsset` missing.
- [ ] `ExerciseAsset` missing.
- [ ] `AnswerAsset` missing.

---

# FIGJAM FULL BOARD ALIGNMENT TRACK

Track này gom các sơ đồ còn lại ngoài FigJam 06. Mục tiêu là giữ roadmap bám đúng product map tổng thể, nhưng vẫn triển khai tuần tự theo PR nhỏ.

## 50. FigJam 01-05 - Product, Journey, Orchestration, Lifecycle, Architecture

Sources: FigJam `01 Product Domain Overview`, `02 Learner Experience Flow`, `03 Tutor Conversation Orchestration`, `04 Learning Activity Lifecycle`, `05 System Architecture`.

- [x] Giữ nguyên tắc: business/product diagrams là conceptual, không tự biến thành DB schema.
- [x] Giữ nguyên tắc: UI screens không định nghĩa domain status.
- [ ] Map product modules thành bounded capabilities: Home/Dashboard, Goals/Plan, Learn/Knowledge, Practice, AI Tutor, Progress, Profile/Settings.
- [ ] Map conceptual domains thành service ownership: Tutor/Conversation, Learner Model, Learning Activity, Assessment, Recommendation, Content, Infrastructure.
- [ ] Learner journey phải hỗ trợ: returning learner, progressive onboarding/profile enrichment, today's focus, practice/review, progress, next best activity.
- [ ] Conversation orchestration phải chạy qua: load/create conversation, persist message, load turn context, extract learner facts, route intent, dispatch capability, persist response.
- [x] LearningActivity lifecycle canonical đã có CREATED, GENERATING, READY, IN_PROGRESS, SUBMITTED, GRADED, COMPLETED, FAILED, CANCELLED.
- [ ] Activity lifecycle transitions phải được dùng trong mọi service path, không chỉ repository tests.
- [ ] System architecture giữ modular monolith: Web Frontend, FastAPI API, Modular Tutor Backend, Primary DB, Vector Store, LLM runtime, Observability, optional background queue.
- [ ] Background worker chỉ thêm khi có long-running generation/eval/retry thật sự cần.

## 51. FigJam 07-08 - Conversation and Learning Activity Sequences

Sources: FigJam `07.1`, `07.2`, `07.3A/B/C`, `08.1`, `08.2`, `08.3`, `08.4`.

- [ ] Practice happy path: user message -> ConversationService -> Router -> PracticeInterpreter -> ActivityService -> typed `learning_activity`.
- [ ] Pending clarification: save pending intent/slots, merge follow-up slots, clear pending state, then create activity.
- [ ] EXPLAIN flow: route EXPLAIN, fetch grounded context, return `assistant_message`, never create practice accidentally.
- [ ] REVIEW flow: resolve target activity/question, load answer context, return `review_result`.
- [ ] PROGRESS flow: load mastery/history, return `progress_summary`.
- [ ] Activity creation/generation: persist CREATED first, transition GENERATING, retrieve context, generate, validate, persist exercise set, transition READY.
- [ ] Generation failure path: record failed candidate/validation failure, build backend fallback, persist fallback content, record recovery event, transition READY.
- [ ] Submit path: POST by `activityId`, create Submission and Answers, grade by submission, derive SkillObservation, update mastery, persist Recommendation, return result bundle.
- [ ] Recommendation accept path: load persistent recommendation, load learner state, create next activity from structured `activitySpec`, set `resultActivityId`, return `learning_activity`.
- [ ] Add integration tests for all 07/08 sequence happy paths and fallback paths.

## 52. FigJam 09 - Frontend Navigation, Components, State Ownership, Rendering Contract

Sources: FigJam `09.1` to `09.4`.

- [ ] Navigation supports Home, Tutor, Activities, Progress, Profile.
- [ ] Tutor workspace separates ConversationHistory, ConversationView, MessageList, TutorComposer, TutorResponseRenderer.
- [ ] Activity workspace separates ActivityHeader, ExerciseRenderer, AnswerControls, SubmissionControls, ActivityResultView, MistakeReview, RecommendationCard.
- [ ] Server state source of truth: conversations/messages, learning activities, learner profile/preferences, mastery/progress, recommendations.
- [ ] Feature client state only stores active conversation/activity, drafts, composer text, loading/submitting flags.
- [ ] Component local state only stores modal/drawer/expanded/focus/temp input.
- [ ] `TutorResponseRenderer` renders strictly by canonical `response.type`.
- [ ] LearningActivity UI renders strictly by backend `status`: generating, ready/in-progress workspace, submitting, result, failure/cancelled.
- [ ] Remove frontend branches that infer business flow from onboarding/generate ad-hoc shapes.
- [ ] Add frontend contract tests for every response type and activity status view.

## 53. FigJam 10 - Delivery Order, API Compatibility, Testing Gates

Sources: FigJam `10.1`, `10.3`, `10.4`; DB order remains tracked in FigJam 06 section.

- [ ] Align implementation order: Conversation Foundation -> Practice Migration -> Tutor Capabilities -> Frontend Migration -> Compatibility Cleanup.
- [ ] Canonical APIs become primary: `/api/conversations/*`, `/api/activities/*`, `/api/learners/*`, `/api/recommendations/*`, `/api/learning-plans/*`.
- [ ] Legacy APIs remain adapters only during migration: chat, practice interpret/generate/score, onboarding interpret.
- [ ] Dual-run canonical and legacy flows where needed.
- [ ] Add parity tests between legacy adapters and canonical application services.
- [ ] Do not remove compatibility adapters until migrated frontend uses canonical API surface.
- [ ] Merge gate requires unit, contract, integration, migration, and E2E acceptance checks.
- [ ] Migration gate requires backfill checks, dual-write parity, canonical read parity, constraint readiness.

## 54. FigJam 11 - Observability, AI Evaluation, MLOps

Sources: FigJam `11.1` to `11.4`.

- [ ] Standardize business trace context: conversationId, messageId, activityId, submissionId, recommendationId.
- [ ] Standardize execution trace context: traceId, GenerationRun, router/service/retrieval/LLM/validation/grading/mastery/recommendation spans.
- [ ] Persist structured telemetry for latency, cost, tokens, fallback rate, reliability, AI quality, and learning outcomes.
- [ ] Keep versioned AI artifacts: model/provider, prompt/policy, embedding model, retriever/reranker config, mastery model, eval dataset.
- [ ] Add evaluation dimensions: routing, retrieval, generation, adaptation.
- [ ] Add evaluator types: deterministic, reference-based, LLM-as-judge, human review.
- [ ] Attach release/config/eval version metadata to GenerationRun and traces.
- [ ] Use production telemetry and learner outcomes to curate new eval cases.
- [ ] Add dashboards or report outputs for engineering, AI quality, learning analytics, and product/adaptation.

## 55. FigJam 12 - Deployment, Runtime Config, Reliability

Sources: FigJam `12.1` to `12.4`.

- [ ] Target deployment topology documents Web Frontend, Tutor Backend, worker, reverse proxy/API gateway, DB, vector store, object storage, LLM runtime, observability, secrets manager, task queue.
- [ ] CI/CD pipeline includes static checks, unit tests, build, integration/contract tests, offline AI eval, staging smoke/E2E, production telemetry verification.
- [ ] Runtime config is versioned and startup-validated.
- [ ] Secrets resolve only at runtime through secrets manager or equivalent deployment secret mechanism.
- [ ] AI release config tracks prompt/model/retrieval/mastery versions.
- [ ] Every request trace includes app config version and AI release version.
- [ ] Reliability path handles health checks, dependency failure, timeout, bounded retry, safe fallback, explicit failure, and failure/recovery trace.
- [ ] Long-running generation/eval/retry can be moved to queue/worker with persisted retry context.

## 56. FigJam 13 - Security, Privacy, LLM and Tool Guardrails

Sources: FigJam `13.1` to `13.4`.

- [ ] Add ingress controls: authentication, authorization, rate limiting, input validation and normalization.
- [ ] Enforce server-side ownership checks; client-provided IDs never bypass authorization.
- [ ] Add purpose-limited data access for profile, conversations, activities, mastery/progress, recommendations.
- [ ] Audit access/security events.
- [ ] Classify learner data by purpose and sensitivity.
- [ ] Define privacy retention/deletion plan for profile/preferences, conversations/messages, activities/submissions, mastery/recommendations, analytics identifiers.
- [ ] Learner deletion flow verifies identity, builds deletion plan, deletes/anonymizes, verifies coverage, records privacy audit event.
- [ ] LLM guardrails redact sensitive fields, isolate retrieved content from instructions, validate outputs, and fail safely.
- [ ] Tool/agent guardrails require allowlisted tools, argument validation, resource authorization, rate/cost/time limits.

## 57. FigJam 14 - Analytics and Learning Effectiveness

Sources: FigJam `14.1` to `14.4`.

- [ ] Define canonical analytics event types: conversation, learning activity, assessment, mastery change, recommendation, product interaction.
- [ ] Define common event envelope: eventId, eventType, occurredAt, learnerId, optional conversation/activity, traceId, releaseVersion, experimentVariant.
- [ ] Validate analytics schemas and remove unnecessary sensitive fields before ingestion.
- [ ] Aggregate by learner, skill, activity, cohort, release, and experiment.
- [ ] Measure learning effectiveness with baseline mastery, placement/calibration, recent error patterns, learning goals, exposure, score/accuracy gain, mastery gain, retention, transfer, gain per effort.
- [ ] Report confidence/sample size and avoid treating engagement alone as learning improvement.
- [ ] Experiment framework includes eligibility, control/candidate variant, exposure event, observation window, primary and guardrail metrics.
- [ ] Product decision loop links KPI changes to UX, tutor behavior, content/difficulty, model/prompt/retrieval, or adaptation policy.
- [ ] North-star metric stays: appropriate next activity that produces measurable learner progress.

## 58. FigJam 15 - Roadmap, MVP Scope, Release Readiness, Product Evolution

Sources: FigJam `15.1` to `15.4`.

- [ ] Phase gates stay aligned: Domain foundation -> Practice migration -> Tutor capabilities -> Frontend migration -> Operations and safety.
- [ ] MVP must include profile/preferences, practice clarification, LearningActivity lifecycle, backend grading/diagnosis, mastery/recommendation, review/progress, conversation history.
- [ ] After MVP: grounded explanations, learning plans, advanced analytics, experimentation framework.
- [ ] Later/optional: complex multi-agent orchestration, microservices, large skill graph, event streaming.
- [ ] Release candidate gate: code/contract tests pass.
- [ ] Release candidate gate: AI evaluation passes.
- [ ] Release candidate gate: migration/data checks pass.
- [ ] Release candidate gate: security/reliability checks pass.
- [ ] Staging gate: smoke and E2E pass.
- [ ] Production gate: telemetry, latency, error rate healthy; rollback/disable risky capability if not.
- [ ] Product evolution loop: observe metrics/outcomes, diagnose gap, design controlled improvement, offline eval, controlled rollout, compare impact, promote/rollback.

---

# MVP SCOPE

## 59. Must-have for MVP

- [ ] Learner profile/preferences.
- [ ] Practice request + clarification.
- [ ] LearningActivity lifecycle.
- [ ] Backend generation.
- [ ] Backend grading.
- [ ] Diagnosis.
- [ ] Mastery update.
- [ ] Recommendation.
- [ ] Review.
- [ ] Progress insights.
- [ ] Conversation history.
- [ ] New Chat preserves learner state.

## 60. Should-have after MVP

- [ ] Grounded explanation.
- [ ] Learning plan.
- [ ] richer review schedule.
- [ ] stronger analytics.
- [ ] experimentation framework.

## 61. Later / optional

- [ ] Complex multi-agent orchestration.
- [ ] Microservice split.
- [ ] Large skill graph.
- [ ] Event streaming platform.
- [ ] Full event sourcing.
- [ ] Advanced planning agent.

---

# SPRINT 1 — BẮT ĐẦU NGAY

Đây là phạm vi nên triển khai trước, không mở rộng thêm cho tới khi hoàn thành.

## PR 0 — Baseline Regression Tests

- [x] Lock current behavior with tests.
- [x] Generate/score regression.
- [x] Chat session regression.
- [x] Persistence baseline.
- [x] Frontend build baseline.

## PR 1 — LearningActivity Foundation

- [x] `app/activity/` equivalent mapped to existing `app/schemas.py`, `app/activities/`, and `app/persistence/*`.
- [x] `LearningActivity`.
- [x] `ActivityStatus`.
- [x] `ActivityStateEvent`.
- [x] lifecycle validation.
- [x] repository interface.
- [x] InMemory implementation.
- [x] SQLite implementation.
- [x] additive DB migration.
- [x] unit tests.

## PR 2 — ConversationRouter

- [x] top-level intents.
- [x] deterministic routing.
- [x] LLM fallback.
- [x] router output contract.
- [x] PracticeIntentInterpreter downstream.
- [x] tests.

## PR 3 — ConversationService

- [x] `handle_message`.
- [x] persistence.
- [x] context loading.
- [x] pending intent.
- [x] route dispatch.
- [x] typed response.
- [x] tests.

## PR 4 — Practice behind ActivityService

- [x] create activity before generation.
- [x] use `activity_id`.
- [x] persist exercise set.
- [x] backend generation.
- [x] backend fallback.
- [x] backend grading.
- [x] submit by `activity_id`.
- [x] integration tests.

---

# Definition of Done — Sprint 1

Sprint 1 chỉ được xem là hoàn thành khi:

- [x] Existing features vẫn chạy.
- [x] `LearningActivity` tồn tại như domain entity độc lập.
- [x] Activity lifecycle được enforce ở backend.
- [x] `activity_id` tồn tại trước khi generation bắt đầu.
- [x] `generation_run_id` không còn là business identity.
- [x] `ConversationRouter` route được 6 top-level intents.
- [x] `PracticeIntentInterpreter` chỉ xử lý PRACTICE detail.
- [x] Pending clarification hoạt động.
- [x] Practice generation đi qua `ActivityService`.
- [x] Submission dùng `activity_id`.
- [x] Backend owns grading.
- [x] Backend owns fallback.
- [x] Unit + integration tests pass.
- [x] Frontend cũ vẫn có thể hoạt động qua compatibility layer.

---

# Target Transformation

```text
Current
───────
Chat UI
  ↓
Practice Interpreter
  ↓
Generate Exercises
  ↓
generation_run_id
  ↓
Score
```

```text
Target
──────
Conversation
    ↓
ConversationRouter
    ↓
Application Capability
    ↓
LearningActivity
    ↓
Submission
    ↓
Skill Evidence
    ↓
Learner Model
    ↓
Recommendation
    ↓
Next LearningActivity
```

---

## Ghi chú triển khai

- Ưu tiên **modular monolith**, chưa cần microservices.
- Không tạo agent chỉ để thay cho function/service đơn giản.
- LangGraph có thể dùng ở workflow phù hợp nhưng không thay thế domain boundaries.
- Database migration theo chiến lược:
  - expand
  - backfill
  - dual-write
  - verify
  - cutover
  - constrain
  - cleanup
- Không refactor frontend lớn trước khi canonical backend contract ổn định.
- Không xóa legacy API trước khi frontend cutover hoàn tất.
