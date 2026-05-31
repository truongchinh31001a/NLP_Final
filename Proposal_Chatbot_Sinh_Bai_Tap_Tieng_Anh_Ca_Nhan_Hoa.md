# Proposal Đồ án NLP

## Tên đề tài

### Tiếng Việt
**Xây dựng chatbot sinh bài tập tiếng Anh cá nhân hóa sử dụng truy xuất ngữ nghĩa và mô hình Transformer**

### Tiếng Anh
**Personalized English Exercise Generation using Semantic Retrieval and Transformer-based Models**

---

## 1. Tổng quan đề tài

Đề tài hướng đến việc xây dựng một hệ thống chatbot hỗ trợ người học tiếng Anh luyện tập theo hướng cá nhân hóa. Thay vì sinh bài tập ngẫu nhiên, hệ thống sẽ dựa trên mục tiêu học tập, trình độ, lịch sử làm bài và điểm yếu của từng người học để tạo ra các bài tập phù hợp.

Hệ thống áp dụng các kỹ thuật xử lý ngôn ngữ tự nhiên và Retrieval-Augmented Generation, kết hợp giữa:

- phân tích yêu cầu người dùng bằng ngôn ngữ tự nhiên
- truy xuất ngữ nghĩa từ knowledge base
- sinh bài tập bằng mô hình ngôn ngữ
- chấm bài và phân tích lỗi sai
- cập nhật hồ sơ học tập để đề xuất bài luyện tiếp theo

Phiên bản hiện tại của dự án được định hướng triển khai bằng:

- `Next.js` cho giao diện người dùng
- `FastAPI` cho backend API
- `LangChain` cho orchestration của retrieval và generation
- `SQLite` cho dữ liệu có cấu trúc
- `Chroma` cho vector store

---

## 2. Bài toán cần giải quyết

Người học tiếng Anh thường gặp các vấn đề sau:

- Không biết mình yếu phần nào.
- Bài tập luyện thường không phù hợp trình độ.
- Thiếu phản hồi chi tiết sau khi làm sai.
- Không có lộ trình luyện tập tiếp theo.
- Nhiều nền tảng chỉ dùng ngân hàng bài tập cố định, ít cá nhân hóa.

Từ đó, đề tài đặt ra bài toán:

> Làm thế nào để xây dựng một chatbot có thể tự động sinh bài tập tiếng Anh phù hợp với trình độ, mục tiêu và điểm yếu của từng người học, đồng thời có khả năng giải thích, chấm bài và đề xuất vòng luyện tập tiếp theo?

---

## 3. Mục tiêu đề tài

Hệ thống cần đạt các mục tiêu chính:

1. Cho phép người dùng nhập yêu cầu luyện tập bằng ngôn ngữ tự nhiên.
2. Phân tích topic, số lượng câu hỏi, loại bài và độ khó mong muốn.
3. Truy xuất kiến thức tiếng Anh liên quan từ vector database.
4. Sinh bài tập tiếng Anh cá nhân hóa theo topic và learner profile.
5. Tạo đáp án, distractor và giải thích.
6. Chấm bài sau khi người dùng trả lời.
7. Phân tích lỗi sai và cập nhật hồ sơ học tập.
8. Đề xuất bài luyện tiếp theo dựa trên weakness profile.

---

## 4. Phạm vi đề tài

### 4.1. Phạm vi MVP

Phiên bản MVP tập trung vào:

- Grammar MCQ
- Vocabulary MCQ
- Fill-in-the-blank
- Cá nhân hóa theo learner profile
- Phân tích lỗi sai ở mức topic / subtopic
- Đề xuất bài luyện tiếp theo

### 4.2. Các phần chưa triển khai trong MVP

Các phần sau được xem là future work:

- Speaking practice
- Pronunciation assessment
- Essay writing correction
- Voice-based chatbot
- Adaptive learning nâng cao
- Fine-tune mô hình theo dữ liệu nội bộ

---

## 5. Đối tượng sử dụng

Hệ thống hướng đến nhiều nhóm người học tiếng Anh, bao gồm:

- Người mới học tiếng Anh
- Học sinh, sinh viên
- Người đi làm muốn ôn lại ngữ pháp
- Người học cần luyện tập theo điểm yếu cá nhân
- Người chuẩn bị cho các kỳ thi tiếng Anh cơ bản

---

## 6. Workflow hệ thống

```mermaid
flowchart TD
    A[User Input via Chat UI]
    --> B[Intent and Goal Extraction]

    B --> C[User Profile Retrieval]

    C --> D{New User?}

    D -->|Yes| E[Placement or Default Level Setup]
    D -->|No| F[Load Learning History]

    E --> G[Personalized Learning State]
    F --> G

    G --> H[Topic and Difficulty Selection]

    H --> I[Knowledge Retrieval from Vector DB]

    I --> J[Relevant Context Selection]

    J --> K[Exercise Generation Chain]

    K --> L[Answer and Distractor Generation]

    L --> M[Exercise Validation]

    M --> N[Personalized Exercise Output]

    N --> O[User Answers]

    O --> P[Answer Checking]

    P --> Q[Error Analysis]

    Q --> R[Update User Topic Stats]

    R --> S[Recommendation for Next Practice]
```

---

## 7. Giải thích workflow

### 7.1. User Input via Chat UI

Người học nhập yêu cầu vào giao diện chatbot.

Ví dụ:

```text
Tôi yếu passive voice, tạo cho tôi 10 câu mức dễ.
```

Hoặc:

```text
Tạo bài luyện vocabulary chủ đề business mức intermediate.
```

### 7.2. Intent and Goal Extraction

Hệ thống phân tích yêu cầu để trích xuất:

- topic
- difficulty
- số lượng câu hỏi
- loại bài
- mục tiêu học tập

Ví dụ:

```json
{
  "intent": "generate_exercise",
  "topic": "passive_voice",
  "num_questions": 10,
  "difficulty": "easy",
  "goal": "grammar_practice"
}
```

Hướng triển khai MVP:

- rule-based keyword mapping
- regex
- có thể mở rộng bằng LLM parser hoặc classifier về sau

### 7.3. User Profile Retrieval

Hệ thống lấy hồ sơ học tập của người dùng, gồm:

- trình độ hiện tại
- preferred difficulty
- topic accuracy
- weak topics
- lịch sử làm bài

Ví dụ:

```json
{
  "user_id": "demo-user",
  "level": "intermediate",
  "preferred_difficulty": "medium",
  "weak_topics": {
    "passive_voice": 0.55,
    "relative_clause": 0.38
  },
  "topic_accuracy": {
    "passive_voice": 0.45,
    "tenses": 0.78
  }
}
```

### 7.4. Placement or Default Level Setup

Nếu là người dùng mới, hệ thống có thể:

- dùng một bài test ngắn để gán level ban đầu
- hoặc dùng default level trong MVP nếu chưa có placement test đầy đủ

### 7.5. Topic and Difficulty Selection

Dựa trên yêu cầu người dùng và learner profile, hệ thống chọn:

- topic phù hợp
- difficulty phù hợp
- exercise type phù hợp

Ví dụ:

- nếu topic accuracy của `passive_voice` nhỏ hơn 0.6 thì ưu tiên mức `easy`
- nếu accuracy lớn hơn hoặc bằng 0.8 thì có thể tăng lên `medium` hoặc đổi subtopic

### 7.6. Knowledge Retrieval from Vector DB

Hệ thống truy xuất context liên quan từ vector database.

Ví dụ query:

```text
passive voice beginner grammar exercises
```

Vector DB trả về các grammar chunks như:

```text
The present simple passive is formed with am/is/are + past participle.
```

### 7.7. Relevant Context Selection

Từ các kết quả retrieval, hệ thống chọn các context phù hợp nhất để đưa vào generation chain.

### 7.8. Exercise Generation Chain

Prompt chain kết hợp:

- request của người dùng
- learner profile
- retrieved context
- output schema

Ví dụ:

```text
Context:
The present simple passive is formed with am/is/are + past participle.

Task:
Generate 5 beginner-level multiple-choice grammar questions about passive voice.
Each question must have 4 options, one correct answer, and explanation.
```

### 7.9. Answer and Distractor Generation

Hệ thống sinh:

- đáp án đúng
- distractor hợp lý
- explanation

Ví dụ:

```text
Question: The room ____ every day.

A. cleans
B. is cleaned
C. cleaned
D. cleaning

Correct answer: B
```

### 7.10. Exercise Validation

Trước khi trả bài cho người dùng, hệ thống kiểm tra:

- có đủ số câu hỏi
- MCQ có đủ 4 options
- chỉ có 1 đáp án đúng
- output đúng topic
- distractor không quá vô lý
- explanation không rỗng
- bài sinh ra không quá trùng lặp

### 7.11. User Answers

Người dùng làm bài trực tiếp trong giao diện web chatbot.

Trong định hướng hiện tại của dự án:

- giao diện dùng `Next.js`
- frontend gọi backend `FastAPI` qua HTTP API

### 7.12. Answer Checking

Hệ thống chấm đáp án bằng cách so sánh câu trả lời của người học với `correct_answer` đã lưu trong session exercise snapshot.

Ví dụ:

```python
if user_answer == correct_answer:
    result = "correct"
else:
    result = "incorrect"
```

### 7.13. Error Analysis

Hệ thống phân tích người dùng sai ở topic nào, subtopic nào, và loại lỗi nào.

Ví dụ:

```json
{
  "topic": "passive_voice",
  "subtopic": "past_simple_passive",
  "accuracy": 0.4,
  "weakness_score": 0.6,
  "status": "weak"
}
```

### 7.14. Update User Topic Stats

Sau mỗi phiên luyện tập, hệ thống cập nhật:

- attempts count
- correct count
- accuracy
- weakness score
- last practiced time

### 7.15. Recommendation for Next Practice

Hệ thống đề xuất bài luyện tiếp theo.

Ví dụ:

```text
Bạn đang sai nhiều ở Passive Voice - Past Simple.
Mình đề xuất bạn luyện thêm 10 câu mức easy-medium về chủ đề này.
```

---

## 8. Kiến trúc hệ thống

Hệ thống được chia thành 5 layer chính:

### 8.1. Interaction Layer

Chức năng:

- Chat UI
- Nhận yêu cầu người dùng
- Hiển thị bài tập
- Hiển thị kết quả và gợi ý

Công nghệ đề xuất:

- `Next.js App Router`
- React
- fetch API đến FastAPI backend

### 8.2. API and Orchestration Layer

Chức năng:

- nhận request từ frontend
- điều phối pipeline generate / score
- quản lý request schema và response schema

Công nghệ đề xuất:

- `FastAPI`
- Pydantic
- Python service orchestration

### 8.3. Retrieval Layer

Chức năng:

- lưu knowledge chunks
- chunking
- embedding
- semantic retrieval

Công nghệ đề xuất:

- `LangChain`
- `Chroma`
- `RecursiveCharacterTextSplitter`
- embedding backend có thể thay thế: `sentence-transformers` hoặc `Ollama embeddings`

### 8.4. Generation Layer

Chức năng:

- sinh câu hỏi
- sinh đáp án
- sinh distractors
- sinh explanation
- validate bài tập

Công nghệ đề xuất:

- `LangChain` prompt chain
- backend LLM linh hoạt: `OpenAI` hoặc `Ollama/local model`
- Pydantic output parser
- Python validation rules

### 8.5. Personalization Layer

Chức năng:

- lưu user profile
- theo dõi history
- lưu session snapshots
- phân tích lỗi sai
- cập nhật topic stats
- đề xuất bài luyện tiếp theo

Công nghệ đề xuất:

- `SQLite`
- Python statistics
- rule-based recommendation

---

## 9. Tech Stack

| Module | Công nghệ đề xuất |
|---|---|
| Chatbot UI | Next.js |
| Backend API | Python / FastAPI |
| Orchestration | LangChain |
| Intent Extraction | Rule-based + regex |
| User Profile Storage | SQLite |
| Knowledge Base Format | Markdown / JSON / SQLite |
| Chunking | LangChain RecursiveCharacterTextSplitter |
| Embedding Backend | sentence-transformers hoặc Ollama embeddings |
| Vector Database | Chroma |
| Semantic Retrieval | LangChain Retriever + Chroma |
| Generation | LangChain prompt chain + LLM backend |
| LLM Backend | OpenAI hoặc Ollama/local model |
| Validation | Pydantic + Python rules |
| Answer Checking | Python logic |
| Error Analysis | Python + SQLite |
| Recommendation | Rule-based recommendation |
| Evaluation | Pandas + Matplotlib |
| Demo | Next.js + FastAPI + Docker |

---

## 10. Data Design

Dữ liệu của hệ thống gồm 4 nhóm chính:

```text
1. Knowledge Base
2. Exercise Bank
3. User Learning Data
4. Evaluation Data
```

Thiết kế dữ liệu phải phục vụ đồng thời:

- retrieval trong RAG
- generation và validation
- personalization
- evaluation và trace output

---

## 11. Knowledge Base

Knowledge Base là dữ liệu kiến thức chính được đưa vào vector database.

### 11.1. Mục đích

Knowledge Base dùng để:

- cung cấp grammar rules
- cung cấp usage notes
- cung cấp example sentences
- cung cấp common mistakes
- làm context cho generation

### 11.2. Nguồn dữ liệu đề xuất

- British Council LearnEnglish
- Perfect English Grammar
- EF English Grammar Guide

### 11.3. Data MVP chốt

Làm trước 6 topic:

```text
1. Tenses
2. Passive Voice
3. Relative Clauses
4. Conditionals
5. Reported Speech
6. Prepositions
```

Mỗi topic:

- 15-25 grammar chunks
- 30-50 exercise samples

Tổng MVP:

- khoảng 120 grammar chunks
- khoảng 300 bài tập mẫu

### 11.4. Grammar chunk format

Mỗi grammar chunk nên có cấu trúc:

```json
{
  "chunk_id": "grammar_passive_001",
  "topic_code": "passive_voice",
  "subtopic": "present_simple_passive",
  "level": "beginner",
  "skill": "grammar",
  "content": "The present simple passive is formed with am/is/are + past participle.",
  "formula": "S + am/is/are + V3/ed",
  "examples": [
    "English is spoken in many countries."
  ],
  "common_mistakes": [
    "Forgetting the verb be.",
    "Using base verb instead of past participle."
  ],
  "source": "british_council",
  "language": "english"
}
```

---

## 12. Exercise Bank

Exercise Bank là dữ liệu bài tập mẫu, không phải output cuối cùng của hệ thống.

### 12.1. Mục đích

Exercise Bank dùng để:

- tham khảo format
- hỗ trợ distractor generation
- kiểm tra trùng lặp
- làm baseline evaluation

### 12.2. Nguồn dữ liệu đề xuất

- Perfect English Grammar
- All Things Grammar
- các bộ bài tập grammar public khác

### 12.3. Exercise format

```json
{
  "exercise_code": "seed_passive_001",
  "exercise_type": "grammar_mcq",
  "topic_code": "passive_voice",
  "subtopic": "present_simple_passive",
  "level": "beginner",
  "difficulty": "easy",
  "question_text": "The room ____ every day.",
  "options": [
    { "label": "A", "text": "cleans", "is_correct": false },
    { "label": "B", "text": "is cleaned", "is_correct": true },
    { "label": "C", "text": "cleaned", "is_correct": false },
    { "label": "D", "text": "cleaning", "is_correct": false }
  ],
  "correct_answer": "B",
  "explanation": "Present simple passive uses am/is/are + V3.",
  "source": "perfect_english_grammar"
}
```

### 12.4. Generated exercise snapshots

Ngoài Exercise Bank, hệ thống còn cần lưu generated exercise snapshots theo từng session để:

- trace prompt và retrieval context
- chấm bài đúng theo bài user đã nhìn thấy
- phục vụ evaluation và fine-tune về sau

---

## 13. Error Analysis và User Learning Data

### 13.1. Error Analysis Data

Error Analysis Data dùng cho phần cá nhân hóa.

Nguồn có thể tham khảo:

- Kaggle Grammar Error Correction Dataset
- Hugging Face grammar-correction datasets

Tuy nhiên trong MVP, phần error analysis nên ưu tiên dựa trên:

- wrong answers
- topic / subtopic
- rule-based error tags

Data này giúp:

- nhận diện lỗi thường gặp
- phân loại lỗi theo topic
- gợi ý bài luyện tiếp theo

### 13.2. User Learning Data

Hệ thống cần lưu dữ liệu học tập của người dùng.

Ví dụ learner profile:

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

Ví dụ practice session:

```json
{
  "session_id": 12,
  "user_id": "demo-user",
  "topic": "passive_voice",
  "difficulty": "easy",
  "total_questions": 10,
  "correct_count": 6,
  "accuracy": 0.6
}
```

Rule đơn giản cho MVP:

```text
accuracy < 0.60         -> weak
0.60 <= accuracy < 0.80 -> needs practice
accuracy >= 0.80        -> can increase difficulty
```

---

## 14. Evaluation Data

Evaluation Data dùng để chứng minh hệ thống hoạt động tốt.

Các nhóm đánh giá chính:

- question quality
- retrieval quality
- personalization quality
- user performance

Ví dụ human evaluation record:

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
  "comment": "Question is natural and suitable for beginner practice."
}
```

---

## 15. Data Pipeline

```text
Public grammar sources
-> clean text
-> normalize labels
-> split into grammar chunks
-> validate chunk quality
-> add metadata: topic, level, skill
-> embed chunks
-> store in Chroma
-> store chunk metadata, exercise bank and user logs in SQLite
```

Mermaid:

```mermaid
flowchart TD
    A[Public Grammar Sources] --> B[Data Cleaning]
    B --> C[Normalize Labels]
    C --> D[Chunking]
    D --> E[Metadata Tagging]
    E --> F[Embedding Backend]
    F --> G[(Chroma Vector Store)]

    E --> H[(SQLite)]
    H --> I[Knowledge Metadata / Exercise Bank / User Logs]
```

---

## 16. Database Design

Hệ thống sử dụng:

- `SQLite` để lưu dữ liệu có cấu trúc
- `Chroma` để lưu embedding và metadata retrieval

### 16.1. Nguyên tắc thiết kế

- tách rõ `level` và `difficulty`
- dùng khóa ổn định như `chunk_id`, `exercise_code`, `generation_run_id`
- tách `seed exercises` và `generated session exercises`
- lưu trace của mỗi lần generate

### 16.2. Các bảng chính đề xuất

- `topics`
- `knowledge_chunks`
- `seed_exercises`
- `seed_exercise_options`
- `users`
- `user_profiles`
- `generation_runs`
- `practice_sessions`
- `session_exercises`
- `session_exercise_options`
- `user_answers`
- `user_topic_stats`
- `evaluation_records`

### 16.3. Giải thích các bảng quan trọng

`knowledge_chunks`
: lưu raw chunk text và metadata để map với Chroma.

`seed_exercises`
: lưu bài tập mẫu để tham khảo format, distractor và evaluation baseline.

`generation_runs`
: lưu request gốc, prompt snapshot, retrieved chunk ids, generator backend.

`session_exercises`
: lưu đúng các bài đã sinh trong từng phiên để chấm bài và trace output.

`user_topic_stats`
: lưu accuracy, weakness score và trạng thái luyện tập theo từng topic.

---

## 17. Vector DB Metadata

Mỗi chunk trong Chroma nên có metadata như sau:

```json
{
  "chunk_id": "grammar_passive_001",
  "topic_code": "passive_voice",
  "subtopic": "present_simple_passive",
  "level": "beginner",
  "skill": "grammar",
  "source": "british_council",
  "language": "english"
}
```

Metadata cần nhất quán để retrieval và trace hoạt động ổn định.

---

## 18. Evaluation

### 18.1. Question Quality

| Metric | Mô tả |
|---|---|
| Fluency | Câu hỏi có tự nhiên không |
| Relevance | Câu hỏi có đúng topic không |
| Answerability | Câu hỏi có một đáp án đúng rõ ràng không |
| Distractor Quality | Đáp án nhiễu có hợp lý không |
| Explanation Quality | Giải thích có rõ ràng không |

### 18.2. Retrieval Quality

| Metric | Mô tả |
|---|---|
| Top-k Relevance | Context retrieve có đúng chủ đề không |
| Retrieval Accuracy | Tỷ lệ context đúng topic |
| Context Usefulness | Context có giúp sinh câu hỏi tốt không |

### 18.3. Personalization Quality

| Metric | Mô tả |
|---|---|
| Level Appropriateness | Bài tập có phù hợp trình độ không |
| Weakness Targeting | Có nhắm đúng điểm yếu không |
| Recommendation Usefulness | Gợi ý tiếp theo có hợp lý không |

### 18.4. User Performance

| Metric | Mô tả |
|---|---|
| Accuracy by Topic | Tỷ lệ đúng theo từng topic |
| Improvement Rate | Mức tiến bộ qua nhiều session |
| Error Reduction | Lỗi sai có giảm không |

---

## 19. Roadmap phát triển

### Tuần 1: Khảo sát và chuẩn bị dữ liệu

- Chốt 6 topic MVP
- Thu thập grammar materials
- Tạo 100-200 grammar chunks
- Chuẩn hóa metadata

### Tuần 2: Xây Knowledge Base và Retrieval

- Implement cleaning và chunking
- Gắn metadata chuẩn
- Tạo vector store bằng Chroma
- Test semantic retrieval qua LangChain

### Tuần 3: Xây Exercise Generation Pipeline

- Thiết kế prompt chain
- Tích hợp LLM backend qua LangChain
- Sinh MCQ và fill-in-the-blank
- Validate output

### Tuần 4: Xây Personalization Module

- Thiết kế SQLite schema
- Lưu user profile và session data
- Theo dõi topic stats
- Rule-based recommendation

### Tuần 5: Xây Chatbot UI / Demo

- Next.js interface
- FastAPI endpoints
- Hiển thị bài tập
- Chấm bài
- Hiển thị feedback và recommendation

### Tuần 6: Evaluation và hoàn thiện báo cáo

- Human evaluation
- Test retrieval
- Test personalization
- Viết báo cáo
- Chuẩn bị slide bảo vệ

---

## 20. Future Work

Các hướng mở rộng:

- Fine-tune mô hình sinh bài tập trên exercise dataset
- Speaking practice
- Pronunciation assessment
- Essay writing correction
- Tích hợp spaced repetition
- Adaptive learning nâng cao
- Hỗ trợ chuẩn CEFR chi tiết hơn
- Mở rộng thêm nhiều chủ đề và kỹ năng

---

## 21. Có cần fine-tune không?

Trong MVP, fine-tune không bắt buộc.

Hướng triển khai khuyến nghị:

```text
RAG + Prompt Engineering + Rule-based Personalization
```

Fine-tune được xem là future work nếu có:

- dataset đủ lớn
- compute phù hợp
- thời gian training và evaluation
- dữ liệu sạch, có format ổn định

---

## 22. Điểm mạnh của đề tài

Đề tài có các điểm mạnh:

- Có ứng dụng thực tế rõ ràng
- Có yếu tố NLP đầy đủ
- Có retrieval bằng vector database
- Có generation bằng mô hình ngôn ngữ
- Có chatbot interface
- Có personalization loop
- Có user tracking và session tracking
- Có thể demo trực quan
- Scope vừa đủ cho đồ án môn NLP

---

## 23. Kết luận

Đề tài **“Xây dựng chatbot sinh bài tập tiếng Anh cá nhân hóa sử dụng truy xuất ngữ nghĩa và mô hình Transformer”** là một hướng đồ án phù hợp cho môn NLP vì kết hợp được nhiều thành phần quan trọng:

- semantic retrieval
- vector database
- generation bằng mô hình ngôn ngữ
- personalization theo learner profile
- backend API và giao diện tương tác

Hệ thống không chỉ sinh bài tập đơn thuần mà còn có khả năng theo dõi quá trình học, phân tích lỗi sai và đề xuất bài luyện tiếp theo. Đây là điểm khác biệt quan trọng so với các hệ thống tạo bài tập truyền thống.

MVP của đề tài nên tập trung vào grammar và vocabulary exercises, sử dụng knowledge base tự xây dựng từ các nguồn public, Chroma cho retrieval, LangChain cho orchestration, LLM backend linh hoạt cho generation, và SQLite cho lưu trữ learner profile cùng session data.
