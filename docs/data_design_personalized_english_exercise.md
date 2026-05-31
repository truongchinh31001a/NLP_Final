# Thiết kế dữ liệu cho dự án Personalized English Exercise Chatbot

## 1. Mục tiêu và bối cảnh hiện tại

Tài liệu này mô tả thiết kế dữ liệu phù hợp với trạng thái hiện tại của dự án:

- Backend: `Python + FastAPI`
- NLP/RAG: `LangChain`
- Frontend: `Next.js`
- Vector store hiện tại: `LangChain InMemoryVectorStore`
- Vector store mục tiêu: `Chroma`
- Persistence hiện tại: `in-memory`
- Persistence mục tiêu: `SQLite + Chroma`

Mục tiêu của thiết kế dữ liệu là phục vụ 4 nhóm chức năng chính:

```text
1. Knowledge Data       -> làm nguồn retrieval cho RAG
2. Seed Exercise Data   -> làm ngân hàng câu hỏi mẫu / baseline
3. User Learning Data   -> theo dõi lịch sử học để cá nhân hóa
4. Evaluation Data      -> đánh giá retrieval, generation và personalization
```

Thiết kế này phải khớp với pipeline hiện có của dự án:

```text
User Request
  -> Intent Parser
  -> Personalization Planner
  -> Retrieval
  -> Generation
  -> Validation
  -> Scoring
  -> Recommendation
```

---

## 2. Nguyên tắc thiết kế dữ liệu

### 2.1. Tách rõ `level` và `difficulty`

- `level`: trình độ người học hoặc độ khó của tài liệu nền
- `difficulty`: độ khó của bài tập được sinh ra cho một phiên luyện tập

Ví dụ:

```text
learner level      = intermediate
knowledge level    = beginner / intermediate
exercise difficulty = easy / medium / hard
```

Không nên dùng 2 khái niệm này thay thế cho nhau.

### 2.2. Mọi thực thể quan trọng cần có khóa ổn định

Đặc biệt với dữ liệu RAG, cần có:

- `topic_code`
- `chunk_id`
- `exercise_code` hoặc `session_exercise_id`
- `generation_run_id`

Điều này giúp:

- map dữ liệu giữa SQLite và Chroma
- trace nguồn context đã truy xuất
- debug output sinh bài
- log dữ liệu cho fine-tune về sau

### 2.3. Phân biệt rõ dữ liệu mẫu và dữ liệu sinh động

Trong dự án này có 2 loại bài tập:

- `seed exercises`: câu hỏi mẫu được chuẩn bị trước
- `generated exercises`: câu hỏi được sinh theo yêu cầu từng phiên

Không nên ép 2 loại này vào cùng một bảng mà không có cờ phân biệt, vì:

- seed exercises dùng cho baseline, distractor reference, duplicate checking
- generated exercises cần lưu snapshot theo từng session

### 2.4. Lưu trace của mỗi lần sinh bài

Để đánh giá RAG và hỗ trợ fine-tune sau này, mỗi lần generate nên lưu:

- request gốc
- practice plan
- prompt snapshot
- retrieved chunk ids
- generator backend / model
- output exercises

---

## 3. Hệ thống nhãn chuẩn

Các nhãn nên được chuẩn hóa ngay từ đầu để khớp giữa parser, retrieval, database và UI.

### 3.1. Topic labels

```text
grammar
vocabulary
passive_voice
relative_clause
conditional_sentence
reported_speech
tenses
prepositions
articles
gerund_infinitive
word_formation
travel_vocabulary
```

### 3.2. Skill labels

```text
grammar
vocabulary
reading
```

### 3.3. Exercise type labels

```text
grammar_mcq
vocabulary_mcq
fill_blank
error_identification
reading_comprehension
```

### 3.4. Level labels

```text
beginner
intermediate
advanced
```

### 3.5. Difficulty labels

```text
easy
medium
hard
```

---

## 4. Phân nhóm dữ liệu

## 4.1. Knowledge Data

### Mục đích

Knowledge Data là nguồn dùng cho retrieval trong RAG. Đây là dữ liệu nền để model sinh bài tập, giải thích đáp án và recommendation.

### Thành phần nên có

```text
grammar rules
usage notes
example sentences
common mistakes
topic summary
```

### Ví dụ knowledge chunk

```json
{
  "chunk_id": "grammar_passive_001",
  "topic_code": "passive_voice",
  "skill": "grammar",
  "level": "beginner",
  "content": "The passive voice in present simple is formed by am/is/are + past participle.",
  "example": "The room is cleaned every day.",
  "common_mistake": "Using present simple active instead of passive structure.",
  "source": "grammar_notes",
  "language": "english"
}
```

### Nơi lưu

- `Chroma`: embeddings + metadata retrieval
- `SQLite`: raw normalized chunk text + metadata để trace và quản trị

---

## 4.2. Seed Exercise Data

### Mục đích

Seed Exercise Data không phải output cuối cùng của hệ thống, mà dùng để:

- làm ngân hàng câu hỏi mẫu
- tham khảo format
- hỗ trợ distractor generation
- duplicate checking
- evaluation baseline

### Ví dụ seed exercise

```json
{
  "exercise_code": "seed_passive_001",
  "topic_code": "passive_voice",
  "skill": "grammar",
  "learner_level": "beginner",
  "difficulty": "easy",
  "exercise_type": "grammar_mcq",
  "question_text": "The house ____ every week.",
  "options": {
    "A": "cleans",
    "B": "is cleaned",
    "C": "cleaned",
    "D": "is cleaning"
  },
  "correct_answer": "B",
  "explanation": "Present simple passive uses am/is/are + past participle.",
  "source": "grammar_exercise_dataset"
}
```

### Nơi lưu

- `SQLite`

---

## 4.3. Generated Exercise Data

### Mục đích

Đây là dữ liệu được sinh ra theo từng phiên luyện tập. Với dự án hiện tại, đây là phần cần lưu riêng vì output phụ thuộc vào:

- user request
- learner profile
- retrieved chunks
- generation backend

### Vì sao phải lưu snapshot theo session

Nếu chỉ lưu vào bảng `exercises` chung, bạn sẽ mất:

- prompt đã dùng
- context đã retrieve
- bài tập thực sự user đã nhìn thấy
- backend/model đã sinh ra output đó

### Ví dụ generated exercise

```json
{
  "session_exercise_id": "sess_12_q1",
  "generation_run_id": "gen_20260530_001",
  "topic_code": "passive_voice",
  "exercise_type": "grammar_mcq",
  "difficulty": "easy",
  "question_text": "The report ____ before noon.",
  "options": [
    { "label": "A", "text": "was finished", "is_correct": true },
    { "label": "B", "text": "was finish", "is_correct": false },
    { "label": "C", "text": "finished", "is_correct": false },
    { "label": "D", "text": "has finishing", "is_correct": false }
  ],
  "correct_answer": "A",
  "explanation": "Past simple passive uses was/were + past participle."
}
```

### Nơi lưu

- `SQLite`

---

## 4.4. User Learning Data

### Mục đích

Đây là lớp dữ liệu phục vụ personalization.

Hệ thống cần biết:

- learner level
- learning goal
- preferred difficulty
- topic accuracy
- weak topic score
- recent sessions
- recommendation history

### Ví dụ learner profile

```json
{
  "user_id": "demo-user",
  "level": "intermediate",
  "goal": "general_english",
  "preferred_difficulty": "medium",
  "topic_accuracy": {
    "passive_voice": 0.45,
    "relative_clause": 0.62
  },
  "weak_topics": {
    "passive_voice": 0.55,
    "relative_clause": 0.38
  }
}
```

### Rule đơn giản cho baseline

```text
accuracy < 0.60         -> weak
0.60 <= accuracy < 0.80 -> needs practice
accuracy >= 0.80        -> can increase difficulty
```

---

## 4.5. Evaluation Data

### Mục đích

Evaluation Data dùng để đánh giá:

- retrieval quality
- generation quality
- answerability
- distractor quality
- difficulty appropriateness
- personalization usefulness

### Ví dụ human evaluation record

```json
{
  "evaluation_id": "eval_001",
  "generation_run_id": "gen_20260530_001",
  "session_exercise_id": "sess_12_q1",
  "fluency": 4,
  "relevance": 5,
  "answerability": 5,
  "difficulty_appropriateness": 4,
  "distractor_quality": 4,
  "personalization_usefulness": 5,
  "comment": "Question is natural and suitable for beginner practice.",
  "annotator": "reviewer_01"
}
```

---

## 5. Data flow theo hệ thống hiện tại

## 5.1. Generate flow

```text
raw user message
  -> parsed request
  -> practice plan
  -> retrieved chunks
  -> generation run
  -> generated exercises
  -> API response
```

### Dữ liệu nên lưu sau bước generate

- `generation_runs`
- `session_exercises`
- optional cache để score phiên hiện tại

## 5.2. Score flow

```text
user answers
  -> answer checking
  -> session result
  -> user topic stats update
  -> recommendation update
```

### Dữ liệu nên lưu sau bước score

- `practice_sessions`
- `user_answers`
- `user_topic_stats`

---

## 6. Metadata chuẩn cho vector store

Mỗi document trong vector store nên có metadata tối thiểu:

```json
{
  "chunk_id": "grammar_passive_001",
  "topic_code": "passive_voice",
  "level": "beginner",
  "skill": "grammar",
  "source": "grammar_notes",
  "language": "english"
}
```

Nên tránh metadata quá lỏng hoặc mỗi chunk một kiểu khác nhau.

---

## 7. Thiết kế lưu trữ

## 7.1. Vector store

Mục tiêu:

- lưu embedding
- semantic search theo `topic_code`, `level`, `skill`

Backend mục tiêu:

```text
Chroma
```

Persist directory đề xuất:

```text
data/vector_store/chroma/
```

## 7.2. Relational database

Mục tiêu:

- lưu metadata chuẩn hóa
- lưu user progress
- lưu generated snapshots
- lưu evaluation

Backend mục tiêu:

```text
SQLite
```

Persist file đề xuất:

```text
data/sqlite/app.db
```

---

## 8. Schema dữ liệu gợi ý

## 8.1. Bảng `topics`

```sql
CREATE TABLE topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_code TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    skill TEXT NOT NULL,
    description TEXT
);
```

## 8.2. Bảng `knowledge_chunks`

```sql
CREATE TABLE knowledge_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id TEXT NOT NULL UNIQUE,
    topic_id INTEGER NOT NULL,
    level TEXT NOT NULL,
    skill TEXT NOT NULL,
    content TEXT NOT NULL,
    example TEXT,
    common_mistake TEXT,
    source TEXT,
    language TEXT DEFAULT 'english',
    metadata_json TEXT,
    created_at TEXT,
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);
```

Ghi chú:

- `chunk_id` là khóa ổn định để map với Chroma
- `metadata_json` lưu thêm field mở rộng nếu cần

## 8.3. Bảng `seed_exercises`

```sql
CREATE TABLE seed_exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_code TEXT NOT NULL UNIQUE,
    topic_id INTEGER NOT NULL,
    learner_level TEXT,
    difficulty TEXT,
    skill TEXT NOT NULL,
    exercise_type TEXT NOT NULL,
    question_text TEXT NOT NULL,
    correct_answer TEXT NOT NULL,
    explanation TEXT,
    source TEXT,
    created_at TEXT,
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);
```

## 8.4. Bảng `seed_exercise_options`

```sql
CREATE TABLE seed_exercise_options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_id INTEGER NOT NULL,
    option_label TEXT NOT NULL,
    option_text TEXT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    FOREIGN KEY (exercise_id) REFERENCES seed_exercises(id)
);
```

## 8.5. Bảng `users`

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_code TEXT NOT NULL UNIQUE,
    name TEXT,
    email TEXT,
    created_at TEXT
);
```

## 8.6. Bảng `user_profiles`

```sql
CREATE TABLE user_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    level TEXT NOT NULL,
    goal TEXT,
    preferred_difficulty TEXT,
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

## 8.7. Bảng `generation_runs`

```sql
CREATE TABLE generation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generation_run_id TEXT NOT NULL UNIQUE,
    user_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    exercise_type TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    num_questions INTEGER NOT NULL,
    raw_request_text TEXT NOT NULL,
    prompt_snapshot TEXT,
    retrieved_chunk_ids_json TEXT,
    generator_backend TEXT,
    model_name TEXT,
    created_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);
```

Ghi chú:

- bảng này rất quan trọng cho RAG trace, debug và fine-tune logging

## 8.8. Bảng `practice_sessions`

```sql
CREATE TABLE practice_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_code TEXT NOT NULL UNIQUE,
    user_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    generation_run_id INTEGER,
    difficulty TEXT NOT NULL,
    total_questions INTEGER NOT NULL,
    correct_count INTEGER NOT NULL,
    accuracy REAL NOT NULL,
    recommendation_text TEXT,
    started_at TEXT,
    ended_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (topic_id) REFERENCES topics(id),
    FOREIGN KEY (generation_run_id) REFERENCES generation_runs(id)
);
```

## 8.9. Bảng `session_exercises`

```sql
CREATE TABLE session_exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_exercise_code TEXT NOT NULL UNIQUE,
    generation_run_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    exercise_type TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    question_text TEXT NOT NULL,
    correct_answer TEXT NOT NULL,
    explanation TEXT,
    source_chunk_ids_json TEXT,
    display_order INTEGER,
    FOREIGN KEY (generation_run_id) REFERENCES generation_runs(id),
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);
```

## 8.10. Bảng `session_exercise_options`

```sql
CREATE TABLE session_exercise_options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_exercise_id INTEGER NOT NULL,
    option_label TEXT NOT NULL,
    option_text TEXT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    FOREIGN KEY (session_exercise_id) REFERENCES session_exercises(id)
);
```

## 8.11. Bảng `user_answers`

```sql
CREATE TABLE user_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    session_exercise_id INTEGER NOT NULL,
    selected_answer TEXT,
    is_correct BOOLEAN NOT NULL,
    error_tag TEXT,
    answer_time_ms INTEGER,
    created_at TEXT,
    FOREIGN KEY (session_id) REFERENCES practice_sessions(id),
    FOREIGN KEY (session_exercise_id) REFERENCES session_exercises(id)
);
```

Ghi chú:

- `error_tag` giúp support error analysis về sau
- `session_exercise_id` đúng hơn `exercise_id` vì bài tập có thể được sinh động

## 8.12. Bảng `user_topic_stats`

```sql
CREATE TABLE user_topic_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    attempts_count INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    accuracy REAL NOT NULL DEFAULT 0,
    weakness_score REAL NOT NULL DEFAULT 0,
    status TEXT,
    last_practiced_at TEXT,
    UNIQUE (user_id, topic_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);
```

Ghi chú:

- bảng này phù hợp hơn tên `user_weaknesses`, vì vừa lưu accuracy vừa lưu weakness

## 8.13. Bảng `evaluation_records`

```sql
CREATE TABLE evaluation_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_code TEXT NOT NULL UNIQUE,
    generation_run_id INTEGER,
    session_exercise_id INTEGER,
    evaluator TEXT,
    fluency INTEGER,
    relevance INTEGER,
    answerability INTEGER,
    difficulty_appropriateness INTEGER,
    distractor_quality INTEGER,
    personalization_usefulness INTEGER,
    comment TEXT,
    created_at TEXT,
    FOREIGN KEY (generation_run_id) REFERENCES generation_runs(id),
    FOREIGN KEY (session_exercise_id) REFERENCES session_exercises(id)
);
```

---

## 9. Cấu trúc thư mục dữ liệu đề xuất

```text
data/
├── raw/
│   ├── grammar_notes/
│   ├── vocabulary/
│   └── exercises/
│
├── processed/
│   ├── knowledge_chunks.json
│   ├── seed_exercises.json
│   └── topic_labels.json
│
├── sqlite/
│   └── app.db
│
├── vector_store/
│   └── chroma/
│
└── evaluation/
    ├── human_eval_samples.csv
    └── generated_questions.csv
```

---

## 10. Quy mô dữ liệu đề xuất cho MVP

### Mức tối thiểu

| Loại dữ liệu | Số lượng đề xuất |
|---|---:|
| Knowledge chunks | 100-200 |
| Seed exercises | 300-500 |
| Topic labels | 6-10 |
| User sessions giả lập | 20-50 |
| Evaluation samples | 50-100 |

### Data scope nên ưu tiên

```text
passive_voice
relative_clause
conditional_sentence
reported_speech
tenses
prepositions
```

Mỗi topic nên có:

```text
10-20 knowledge chunks
30-50 seed exercises
```

---

## 11. Mapping với code hiện tại

Thiết kế này khớp với các schema runtime hiện có trong backend:

- `PracticeRequest`
- `PracticePlan`
- `LearnerProfile`
- `KnowledgeChunk`
- `ExerciseItem`
- `GeneratedExerciseSet`
- `SessionResult`

Mapping gợi ý:

```text
PracticeRequest      -> generation_runs.raw_request_text
PracticePlan         -> generation_runs.topic_id / difficulty / exercise_type
KnowledgeChunk       -> knowledge_chunks + Chroma metadata
ExerciseItem         -> session_exercises + session_exercise_options
SessionResult        -> practice_sessions
LearnerProfile       -> user_profiles + user_topic_stats
```

---

## 12. Kết luận

Thiết kế dữ liệu phù hợp với dự án hiện tại cần đảm bảo 3 điểm:

1. Hỗ trợ tốt cho `RAG`, nghĩa là knowledge chunks phải có `chunk_id` và metadata chuẩn.
2. Hỗ trợ tốt cho `personalization`, nghĩa là phải lưu được session history, answers và topic stats.
3. Hỗ trợ tốt cho `debug / evaluation / fine-tune`, nghĩa là phải có `generation_runs` và `session_exercises` để trace output đã sinh.

Với baseline hiện tại, có thể tiếp tục dùng:

- `in-memory` cho chạy demo nhanh
- `FastAPI` cho API layer
- `Next.js` cho UI

Nhưng khi chuyển sang persistence thật, hướng nên đi là:

```text
SQLite  -> user data, session data, generated snapshots, evaluation
Chroma  -> retrieval embeddings cho knowledge chunks
```

Đây là thiết kế phù hợp nhất với repo hiện tại và cũng đủ chỗ để mở rộng sang fine-tune về sau.
