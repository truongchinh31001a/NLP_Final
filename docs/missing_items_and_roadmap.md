# Tong hop cac phan con thieu va roadmap bo sung

## 1. Trang thai hien tai

Du an hien da co khung end-to-end cho chatbot sinh bai tap tieng Anh ca nhan hoa:

- Backend `FastAPI`
- Frontend `Next.js`
- LangChain cho retrieval va generation
- Vector store abstraction, ho tro `InMemoryVectorStore` va `Chroma`
- Repository abstraction cho learning data
- Pipeline generate / score
- `LearningAgent` dieu phoi tool noi bo theo huong controlled agentic AI
- Baseline personalization, scoring va recommendation

Tuy nhien, he thong hien van dang o muc MVP/demo. Cac phan quan trong nhat con thieu la du lieu that, persistence that va evaluation.

---

## 2. Database that

### Hien tai

- `LearningRepository` moi co ban `InMemoryLearningRepository`.
- Profile va session result chi luu trong RAM.
- Restart backend thi du lieu hoc tap bi mat.

### Con thieu

- SQLite schema.
- SQLite repository implementation.
- Migration/init database script.
- Luu user profile, session, answers, generated exercises.
- Luu generation trace de debug va fine-tune ve sau.

### Bang nen co

```text
users
user_profiles
topics
knowledge_chunks
seed_exercises
seed_exercise_options
generation_runs
practice_sessions
session_exercises
session_exercise_options
user_answers
user_topic_stats
evaluation_records
```

### Muc tieu

```text
SQLite -> user data, profile, session, answer, generated snapshot, evaluation
Chroma -> embedding va semantic retrieval cho knowledge chunks
```

---

## 3. Knowledge base that

### Hien tai

- Retrieval dang seed mot so knowledge chunks mau truc tiep trong code.
- Chua co data pipeline rieng de tao va ingest knowledge base.

### Con thieu

- Thu muc du lieu `data/raw`, `data/processed`, `data/vector_store`.
- File `knowledge_chunks.json`.
- Script clean/chunk/normalize metadata.
- Script ingest vao Chroma.
- Khoang 100-200 knowledge chunks cho MVP.

### Metadata toi thieu

```json
{
  "chunk_id": "grammar_passive_001",
  "topic_code": "passive_voice",
  "subtopic": "present_simple_passive",
  "level": "beginner",
  "skill": "grammar",
  "source": "grammar_notes",
  "language": "english"
}
```

### Topic nen uu tien

```text
passive_voice
relative_clause
conditional_sentence
reported_speech
tenses
prepositions
travel_vocabulary
```

---

## 4. Exercise bank mau

### Hien tai

- Bai tap chu yeu duoc sinh bang LLM hoac fallback generator.
- Chua co ngan hang cau hoi mau.

### Con thieu

- Seed exercise dataset.
- Cau hoi mau theo topic, level, difficulty va exercise type.
- Options, correct answer, explanation.
- Duplicate checking giua bai sinh va bai mau.

### Loi ich

- Lam baseline evaluation.
- Lam reference cho distractor generation.
- Kiem tra chat luong cau hoi sinh ra.
- Ho tro fine-tune ve sau neu co du data.

### Quy mo MVP de xuat

```text
100-300 seed exercises
6-10 topics
30-50 cau/topic neu co thoi gian
```

---

## 5. Intent parser va generation chat luong hon

### Hien tai

- Intent parser dang rule-based/keyword-based.
- Fallback generation tao placeholder neu khong co API key.

### Con thieu

- Parser xu ly tieng Viet tot hon.
- Mapping topic, difficulty, exercise type da dang hon.
- LLM-based parser hoac classifier.
- Prompt generation co feedback tu validation.
- Prompt rieng cho tung exercise type.

### Vi du can parse tot hon

```text
"Toi yeu cau bi dong, tao 10 cau de"
"Cho minh vocab chu de travel muc trung binh"
"Sinh fill blank ve conditional sentence"
"Hom nay luyen lai phan minh sai nhieu nhat"
```

---

## 6. Agentic AI nang cao

### Hien tai

- Da co `LearningAgent` theo huong controlled agentic AI.
- Agent dieu phoi cac service noi bo:

```text
parse_learning_request
get_user_profile
build_practice_plan
retrieve_knowledge
generate_exercises
validate_exercises
recommend_next_practice
update_profile
save_session_result
```

### Gioi han hien tai

- Agent van rule-driven.
- Chua co LLM planner tu chon tool dong.
- Retry moi o muc generate/validate.
- Agent memory chua persist vao DB.

### Co the mo rong

- Them LLM planner.
- Cho agent quyet dinh co can retrieve lai hay generate lai khong.
- Dua validation feedback nguoc vao generation prompt.
- Luu agent trace vao `generation_runs`.
- Them tool `analyze_errors` rieng.

---

## 7. Error analysis

### Hien tai

- Score dang tinh dung/sai theo topic.
- Weak topic duoc update bang accuracy.

### Con thieu

- Phan tich loi sai theo subtopic.
- Gan `error_tag` cho tung cau sai.
- Feedback rieng cho tung dap an sai.
- Luu thong ke loi theo user/topic/subtopic.

### Error tag de xuat

```text
missing_be
wrong_participle
wrong_tense
active_passive_confusion
wrong_relative_pronoun
wrong_condition_type
vocabulary_meaning_confusion
preposition_error
```

### Loi ich

- Personalization thuyet phuc hon.
- Recommendation chinh xac hon.
- Co metric tot cho bao cao.

---

## 8. Evaluation

### Hien tai

- Chua co evaluation pipeline ro rang.

### Con thieu

- Retrieval evaluation.
- Question quality evaluation.
- Personalization evaluation.
- Human evaluation form/csv.
- Script tong hop metric va ve bieu do.

### Metric de xuat

#### Retrieval

```text
top_k_relevance
topic_match_rate
context_usefulness
```

#### Generation

```text
fluency
relevance
answerability
distractor_quality
explanation_quality
difficulty_appropriateness
```

#### Personalization

```text
weakness_targeting
level_appropriateness
recommendation_usefulness
accuracy_improvement
```

---

## 9. Test tu dong

### Hien tai

- Chua co test suite ro rang.

### Con thieu

- Unit test cho parser.
- Unit test cho validator.
- Unit test cho personalization update.
- Test cho repository.
- API test cho generate/score.

### Test nen them truoc

```text
tests/test_intent_parser.py
tests/test_exercise_validator.py
tests/test_personalization.py
tests/test_learning_agent.py
tests/test_api_practice.py
```

---

## 10. Production readiness

Phan nay khong bat buoc cho MVP, nhung neu muon he thong chinh chu hon thi can:

- Auth/user management.
- Logging co cau truc.
- Error handling API tot hon.
- Rate limit.
- Config `.env` day du.
- Docker volume cho SQLite/Chroma.
- CI pipeline.
- Khong track `__pycache__` va `.venv`.

---

## 11. Thu tu uu tien de lam tiep

### Uu tien cao

1. Implement SQLite repository.
2. Tao SQLite schema/init script.
3. Tao knowledge chunks that va ingest vao Chroma.
4. Tao seed exercise bank.
5. Luu generated exercise snapshots.

### Uu tien trung binh

1. Cai tien intent parser.
2. Them error analysis theo `error_tag`.
3. Them evaluation scripts.
4. Them test suite.
5. Hien thi agent trace/debug info trong UI neu can demo.

### Uu tien thap

1. LLM planner cho agent.
2. Dynamic tool selection.
3. Fine-tune model.
4. Auth/user management.
5. CI/CD.

---

## 12. Ket luan ngan gon

Du an hien tai da co khung chay duoc va da bat dau co huong agentic AI. Tuy nhien, de tro thanh mot he thong hoan chinh hon, can tap trung vao 3 phan lon:

```text
1. Persistence that: SQLite cho user/session/generated data
2. Data that: knowledge base + seed exercise bank
3. Evaluation that: metric, human eval va test suite
```

Neu lam duoc 3 phan nay, du an se vuot qua muc demo va co day du co so de trinh bay nhu mot he thong NLP/RAG ca nhan hoa hoan chinh.
