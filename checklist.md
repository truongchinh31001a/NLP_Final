# Checklist refactor chat flow

Checklist này được lập từ `chat_flow_redesign_refactor_plan.md` sau khi đối chiếu với hiện trạng repo. Mục tiêu là refactor dần từ flow "chat để tạo bài tập" sang nền tảng hội thoại có nhiều learning activity, nhưng vẫn giữ các phần đang chạy ổn như RAG, generator, validator, scorer, diagnosis, recommendation và chat session.

## Hiện Trạng Nhanh

- [x] Backend FastAPI đang có practice flow chính qua `POST /api/practice/generate` và `POST /api/practice/score`.
- [x] Backend đã có chat session/message/memory endpoints qua `app/api/main.py`.
- [x] `PracticeIntentInterpreter` đã xử lý yêu cầu luyện tập tự nhiên và có clarification cơ bản.
- [x] `LearningAgent` đã có retry generation, validate, seed-bank fallback backend, diagnosis, mastery update, recommendation và practice review.
- [x] SQLite repository đã có bảng chat, generation run, practice session, answers, diagnoses, reviews, topic/subtopic/error/skill stats.
- [x] PostgreSQL repository đang dùng JSONB tables cho profile, generated runs, practice sessions, chat sessions/messages/memory.
- [x] Backend test đã xanh; sau Phase 11 `python -m unittest discover tests` chạy 60 tests pass.
- [x] Đã xử lý nhánh `GENERAL` và `EXPLAIN` để ưu tiên LLM-backed response khi có cấu hình, fallback theo context khi không có LLM.

## Nguyên Tắc Khi Làm

- [x] Không rewrite toàn bộ. Giữ lại `PracticeIntentInterpreter`, `IntentParser`, `LearningAgent`, RAG, generator, validator, scorer, diagnosis, recommendation, review.
- [x] Mỗi phase phải giữ demo hiện tại chạy được hoặc có compatibility endpoint rõ ràng.
- [ ] `generation_run_id` chỉ còn là tracing/debug identity, không dùng làm business identity của practice/activity.
- [x] Frontend không tự sinh bài/chấm bài fallback bằng local logic sau khi backend activity flow đã sẵn sàng.
- [x] Router có thể rule-first để ổn định, nhưng nội dung trả lời cho `GENERAL`/chat tự do nên dùng LLM khi có cấu hình, và fallback phải context-aware thay vì một form cố định.
- [x] Mọi thay đổi persistence phải cập nhật đủ `LearningRepository`, `InMemoryLearningRepository`, `SQLiteLearningRepository`, `PostgreSQLLearningRepository` và test tương ứng.

## Phase 0 - Pre-Flight Và Guardrails

- [x] Kiểm tra tính tái lập của `langgraph`: đã thêm `langgraph>=1.0.0` vào `requirements.txt`.
- [x] Chạy lại `python -m unittest discover tests` và ghi baseline xanh trước khi refactor.
- [x] Chạy `cd frontend && npm run lint` để biết baseline frontend.
- [x] Chạy `cd frontend && npm run build` nếu muốn khóa baseline UI/build trước khi đổi API.
- [x] Tạo test fixture nhỏ cho practice generation/score không cần LLM thật, dùng seed-bank hoặc in-memory generator.
- [x] Ghi lại compatibility contract hiện tại của `/api/practice/generate`, `/api/practice/score`, `/api/users/{user_id}/chat/*`.

## Phase 1 - Domain Boundaries

- [x] Thêm domain model cho conversation intent: `PRACTICE`, `EXPLAIN`, `REVIEW`, `PROGRESS`, `PROFILE_UPDATE`, `GENERAL`.
- [x] Thêm model `ConversationTurnContext` gồm learner profile, conversation/session id, recent messages, memory summary, active activity, pending clarification.
- [x] Thêm model `PendingClarification` gồm `pending_intent`, `missing_fields`, `collected_slots`, `question`.
- [x] Thêm model `LearningActivity` gồm `activity_id`, `conversation_id`, `learner_id`, `type`, `status`, `target_skills`, `difficulty`, timestamps.
- [x] Thêm enum lifecycle cho practice/activity: `CREATED`, `GENERATING`, `READY`, `IN_PROGRESS`, `SUBMITTED`, `GRADED`, `COMPLETED`, `FAILED`, `CANCELLED`.
- [x] Tách rõ `LearnerProfile` là long-term state, không bị reset khi tạo new chat.
- [x] Giữ `GeneratedExerciseSet.generation_run_id` nhưng thêm đường liên kết tới `activity_id`.
- [x] Thêm unit tests cho dataclass/model default và serialize/deserialize.

File dự kiến:

- `app/schemas.py`
- `app/api/schemas.py`
- Có thể thêm package mới `app/conversation/`
- Có thể thêm package mới `app/activities/`

## Phase 2 - Persistence Cho LearningActivity

- [x] Mở rộng `LearningRepository` protocol với các method activity: create, get, update status, attach generated set, submit/grade result, get latest activity by conversation.
- [x] In-memory repository lưu `learning_activities`, activity events, active activity per chat session.
- [x] SQLite schema thêm bảng `learning_activities` và cột/link cần thiết từ `generation_runs`, `practice_sessions`, `chat_sessions`.
- [x] SQLite migration/init không phá database cũ; dùng `CREATE TABLE IF NOT EXISTS` và `_ensure_column` nếu cần.
- [x] PostgreSQL repository thêm JSONB table hoặc normalized table cho `tutor_learning_activities`.
- [x] Khi save generated set, persist cả `activity_id` nếu có.
- [x] Khi save session result, link result vào `activity_id` thay vì chỉ `session_code/generation_run_id`.
- [x] Thêm query lấy latest completed/graded activity để phục vụ intent `REVIEW`.
- [x] Thêm tests cho in-memory và SQLite: create activity, lifecycle update, link conversation, link generated run, submit result.
- [x] Thêm test ownership: user A không đọc được activity của user B.

File dự kiến:

- `app/persistence/repository.py`
- `app/persistence/schema.sql`
- `app/persistence/sqlite_repository.py`
- `app/persistence/postgres_repository.py`
- `tests/test_learning_activities.py`

## Phase 3 - Conversation Router

- [x] Tạo `ConversationRouter` đứng trước `PracticeIntentInterpreter`.
- [x] Router rule-first cho các intent rõ ràng; chỉ gọi LLM khi cấu hình cho phép và thật sự cần.
- [x] `PRACTICE`: route sang `PracticeIntentInterpreter`.
- [x] `EXPLAIN`: nhận câu hỏi khái niệm như "Past Perfect dùng khi nào?".
- [x] `REVIEW`: nhận câu hỏi sau bài như "Tại sao câu 3 sai?", "Giải thích câu vừa rồi".
- [x] `PROGRESS`: nhận câu hỏi như "Tôi đang yếu phần nào?", "Kỹ năng nào thấp nhất?".
- [x] `PROFILE_UPDATE`: nhận câu như "Từ giờ cho tôi bài khó hơn", "Tôi muốn 10 câu mỗi lần".
- [x] `GENERAL`: fallback hội thoại học tập, không ép qua practice.
- [x] Router dùng recent chat/activity context để phân biệt "luyện tiếp" với "giải thích tiếp".
- [x] Thêm `confidence`, `source`, `reason`, `slots`, `needs_clarification`.
- [x] Thêm tests cho toàn bộ ví dụ trong plan.

File dự kiến:

- `app/conversation/router.py`
- `app/conversation/schemas.py`
- `app/orchestrator/pipeline.py`
- `tests/test_conversation_router.py`

## Phase 4 - Conversation Orchestrator Và API Mới

- [x] Tạo `ConversationService` hoặc `ConversationOrchestrator` quản lý một turn chat: persist user message, load context, profile enrichment, route intent, call service, persist assistant response.
- [x] API mới: `POST /api/conversations`, `GET /api/conversations`, `GET /api/conversations/{id}`.
- [x] API mới: `POST /api/conversations/{id}/messages` nhận user message và trả về response canonical.
- [x] Response canonical gồm `conversation_id`, `message`, `intent`, `assistant_reply`, `pending_clarification`, `activity`, `ui_action`.
- [x] Map chat session hiện tại sang concept conversation để không phải migrate frontend một phát lớn.
- [x] Giữ legacy endpoints `/api/users/{user_id}/chat/*` trong giai đoạn chuyển đổi.
- [x] Giữ legacy practice endpoints trong phase đầu, nhưng bên trong gọi orchestration/activity mới khi đã có.
- [x] Thêm API tests cho message turn: practice, explain, review, progress, profile update, general.

File dự kiến:

- `app/api/main.py`
- `app/api/schemas.py`
- `app/orchestrator/pipeline.py`
- `app/conversation/service.py`
- `tests/test_conversation_api.py`

## Phase 5 - Practice Thành Learning Activity

- [x] Đổi practice generation path thành create activity trước, sau đó activity đi qua lifecycle `CREATED -> GENERATING -> READY`.
- [x] `LearningAgent.create_exercise_set` nhận/ghi `activity_id` hoặc được gọi bởi `PracticeActivityService`.
- [x] API generate trả `activity_id` cùng `generation_run_id` trong giai đoạn compatibility.
- [x] API submit/score mới dùng `activity_id`: `POST /api/activities/{activity_id}/submit`.
- [x] Sau submit, activity đi qua `SUBMITTED -> GRADED -> COMPLETED`.
- [x] Backend trả canonical result gồm exercises, answers, diagnoses, review, recommendation, next structured activity suggestion.
- [x] Không tạo preview recommendation giả trong `generate_practice` bằng score giả như hiện tại nếu recommendation chưa dựa trên kết quả thật.
- [x] `session_code` vẫn có thể dùng cho report/review, nhưng không là ID chính của activity.
- [x] Thêm tests cho lifecycle happy path và failure path.

File dự kiến:

- `app/activities/practice_service.py`
- `app/agent/learning_agent.py`
- `app/orchestrator/pipeline.py`
- `app/api/main.py`
- `app/api/schemas.py`

## Phase 6 - Backend Capabilities Ngoài Practice

- [x] `TutorExplainService`: giải thích khái niệm, ưu tiên RAG context khi có topic/subtopic.
- [x] `ReviewService` theo intent: load latest/target activity, câu hỏi, user answer, correct answer, diagnosis, explanation.
- [x] `ProgressService`: đọc personalization snapshot/mastery để trả lời điểm yếu, kỹ năng thấp, gợi ý học tiếp.
- [x] `ProfileUpdateService`: cập nhật difficulty, num_questions, goals, weak topics từ câu chat.
- [x] `GeneralTutorService`: fallback hội thoại trong phạm vi học tiếng Anh, không tạo bài nếu user không yêu cầu.
- [x] Response của mỗi service phải persist assistant message vào conversation.
- [x] Thêm tests cho từng capability với context tối thiểu.

File dự kiến:

- `app/explanation/service.py` hoặc `app/tutor/service.py`
- `app/review/service.py`
- `app/personalization/service.py`
- `app/conversation/service.py`
- `tests/test_conversation_capabilities.py`

## Phase 7 - Progressive Profiling

- [x] Chuyển onboarding từ wizard bắt buộc sang profile enrichment per turn.
- [x] Tận dụng `OnboardingInterpreter` hiện có để extract nhiều facts trong một message.
- [x] Định nghĩa Minimum Viable Profile: đủ thông tin từ request hiện tại thì cho tạo activity ngay.
- [x] Chỉ hỏi clarification cho field thật sự cần tại turn đó.
- [x] Cập nhật chat memory extraction: lưu `display_name`, `level`, `goals`, `weak_topics`, `preferred_difficulty`, `preferred_num_questions`, `last_topic_requested`, `recent_topics`, `preferred_content_theme`.
- [x] Không set `onboarding_completed` như cổng chặn practice.
- [x] Frontend bỏ trạng thái "guided onboarding" như luồng bắt buộc; giữ nút cập nhật hồ sơ như một conversation action.
- [x] Thêm tests cho message chứa nhiều profile facts trong một turn.

File dự kiến:

- `app/onboarding/service.py`
- `app/persistence/repository.py`
- `app/persistence/sqlite_repository.py`
- `app/persistence/postgres_repository.py`
- `frontend/components/chat-workbench.tsx`

## Phase 8 - Frontend Migration

- [x] Thêm client API mới cho conversations và activities trong `frontend/lib/api.ts`.
- [x] Tách state frontend thành `conversationState` và `activityState`; không để `Screen` đại diện cho business state.
- [x] Thay `generationRunId` bằng `activeActivityId` ở UI logic; giữ `generationRunId` chỉ để hiển thị/debug nếu cần.
- [x] `handleSubmitMessage` gọi conversation message endpoint thay vì luôn `handleGenerate`.
- [x] Render activity như một phần của conversation: chat message có thể kèm practice activity card/result/review.
- [x] Loại bỏ `interpretPracticeRequestWithFallback` ở frontend sau khi router backend hoạt động.
- [x] Loại bỏ `buildPracticeIntentFallback`, `buildPreviewFromPrompt`, `buildFallbackExercise` và scoring fallback local.
- [x] Nộp bài luôn gọi backend bằng `activity_id`.
- [x] Nút "Dùng gợi ý luyện tiếp" gọi accept recommendation hoặc create activity trực tiếp, không nhét prompt lại để parse.
- [x] New Chat chỉ tạo conversation mới, không reset learner profile/mastery/preferences.
- [x] Chạy `npm run lint` và `npm run build` sau mỗi bước frontend lớn.

File dự kiến:

- `frontend/lib/api.ts`
- `frontend/lib/types.ts`
- `frontend/components/chat-workbench.tsx`
- `frontend/app/globals.css`

## Phase 9 - Recommendation Continuation

- [x] Đổi recommendation từ string thuần sang structured object có `recommendation_id`, `skill`, `topic`, `subtopic`, `difficulty`, `exercise_type`, `num_questions`, `reason`.
- [x] API `GET /api/recommendations` trả danh sách recommendation hiện hành.
- [x] API `POST /api/recommendations/{id}/accept` tạo activity trực tiếp.
- [x] Practice review `next_practice_prompt` có thể giữ làm text hiển thị, nhưng phải có structured next activity đi kèm.
- [x] Thêm tests accept recommendation không đi qua parse practice request.

File dự kiến:

- `app/recommendation/service.py`
- `app/review/service.py`
- `app/api/schemas.py`
- `app/api/main.py`
- `frontend/lib/api.ts`

## Phase 10 - Cleanup Legacy Flow

- [x] Deprecate hoặc wrap `/api/practice/generate` bằng activity service.
- [x] Deprecate hoặc wrap `/api/practice/score` bằng activity submit service.
- [x] Xóa frontend local fallback generation/scoring khi backend path ổn định.
- [x] Audit mọi nơi còn dùng `generationRunId` như identity chính.
- [x] Cập nhật `README.md` architecture từ `LearningAgent -> practice generator` sang `Conversation API -> Conversation Orchestrator -> Intent Router -> Learning Activities`.
- [x] Cập nhật `frontend/README.md` endpoint list.
- [x] Cập nhật `docs/frontend_nextjs_architecture.md` nếu vẫn dùng làm tài liệu frontend.
- [x] Cập nhật `app/agent/workflow_graph.py` để graph thể hiện conversation router và activity lifecycle, hoặc tách thêm graph riêng.

## Phase 11 - Natural Conversational Tutor

- [x] Audit các câu trả lời hard-code trong `GeneralTutorService`, `_assistant_reply`, `TutorExplainService`, `ProgressService`, `ProfileUpdateService`.
- [x] Thêm capability trả lời hội thoại tự nhiên cho `GENERAL`: dùng LLM khi `LLM_BACKEND` hỗ trợ, kèm system prompt giới hạn vai trò English tutor.
- [x] General chat phải dùng `message`, profile, memory summary, recent messages và active activity để trả lời sát ngữ cảnh, không ignore `route/context`.
- [x] Fallback khi không có LLM vẫn phải có nhiều template theo intent/ngữ cảnh, tránh chỉ trả một câu cố định.
- [x] Cải thiện `EXPLAIN`: ưu tiên LLM/RAG response khi có backend LLM, chỉ dùng `_concept_spec()` như fallback.
- [x] Thêm config rõ ràng, ví dụ `TUTOR_RESPONSE_LLM_ENABLED`, timeout riêng và chế độ fallback an toàn.
- [x] Thêm tests fake LLM cho `GENERAL` chứng minh response dựa trên nội dung user message/context.
- [x] Thêm tests LLM disabled cho fallback context-aware, không lặp nguyên một form cho mọi câu chat.
- [x] Thêm API/conversation test: câu ngoài luồng vẫn trả `conversation.reply` nhưng nội dung không phải canned text cố định.
- [x] Cập nhật docs để nói rõ hệ thống là rule-first router + LLM-backed response generator, không phải toàn bộ đều template.
- [x] Khoa regression cho cau tra loi ngan chon focus hoc `doc/nghe/noi/viet`, tranh hoi lai menu cu.

File dự kiến:

- `app/tutor/service.py`
- `app/conversation/service.py`
- `app/config.py`
- `app/bootstrap.py`
- `tests/test_conversation_capabilities.py`
- `tests/test_conversation_api.py`
- `README.md`
- `docs/frontend_nextjs_architecture.md`

## Test Matrix Mỗi Phase

- [x] Backend unit: `python -m unittest discover tests`.
- [x] Router examples: 7 câu mẫu trong plan phải route đúng intent.
- [ ] Persistence: in-memory và SQLite luôn có test tương đương; PostgreSQL có smoke test hoặc contract test nếu chưa chạy DB.
- [x] API: practice happy path, submit happy path, review latest activity, progress snapshot, profile update.
- [x] Tutor response: `GENERAL`/`EXPLAIN` có test cho LLM-enabled path và fallback context-aware path.
- [x] Frontend static: `cd frontend && npm run lint`.
- [x] Frontend build: `cd frontend && npm run build`.
- [ ] Manual smoke: mở chat, tạo bài, nộp bài, hỏi "Tại sao câu 2 sai?", hỏi "Tôi đang yếu phần nào?", bấm "New Chat", kiểm tra learner state còn giữ.

## Thứ Tự Làm Đề Xuất

- [x] 0.1 Fix baseline test/dependency.
- [x] 1.1 Thêm intent/activity schemas không đổi behavior.
- [x] 2.1 Thêm persistence activity ở in-memory + SQLite.
- [x] 3.1 Thêm router và tests route, chưa đổi frontend.
- [x] 4.1 Thêm conversation message endpoint gọi router.
- [x] 5.1 Wrap practice generation vào activity lifecycle.
- [x] 5.2 Thêm submit bằng `activity_id`.
- [x] 8.1 Frontend gọi conversation endpoint cho message thường.
- [x] 8.2 Frontend chuyển score sang `activity_id`.
- [x] 6.1 Thêm review/progress/explain/profile services.
- [x] 7.1 Progressive profiling.
- [x] 9.1 Structured recommendation accept.
- [x] 10.1 Cleanup legacy và cập nhật docs.
- [x] 11.1 LLM-backed natural response cho `GENERAL`.
- [x] 11.2 Cải thiện `EXPLAIN` dùng LLM/RAG, giữ rule fallback.

## Definition Of Done

- [x] User có thể gửi câu practice và nhận activity có `activity_id`.
- [x] User có thể nộp bài bằng `activity_id`, backend chấm và cập nhật mastery.
- [x] User có thể hỏi review sau result mà không tạo bài mới.
- [x] User có thể hỏi progress mà không đi qua `PracticeIntentInterpreter`.
- [x] User có thể update preference bằng chat tự nhiên.
- [x] New Chat tạo conversation mới nhưng giữ profile/mastery/preferences.
- [x] Frontend không còn local fallback bài tập/chấm điểm.
- [x] Chat tự do không còn trả một form cố định; phản hồi phải dựa trên message/context.
- [x] Explain không chỉ đọc bảng hard-code khi có LLM/RAG khả dụng.
- [ ] `generation_run_id` chỉ còn trong trace/debug/observability.
- [x] Tests backend xanh và frontend lint/build xanh.
