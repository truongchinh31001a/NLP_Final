# Baseline Architecture

## Muc tieu baseline

Baseline nay uu tien chay duoc end-to-end cho MVP truoc khi them fine-tune:

1. Nhan yeu cau hoc bang ngon ngu tu nhien.
2. Chuan hoa yeu cau thanh `topic`, `difficulty`, `exercise_type`, `num_questions`.
3. Ket hop voi ho so nguoi hoc de tao `practice plan`.
4. Truy xuat kien thuc lien quan tu knowledge base / vector store.
5. Sinh bai tap co cau truc co dinh.
6. Kiem tra dinh dang, dap an, giai thich.
7. Cham bai, chan doan loi sai, cap nhat weakness profile va skill mastery, goi y buoi hoc tiep theo.

Baseline hien tai da duoc chuyen sang dung LangChain cho 3 phan:

- `ChatPromptTemplate` cho generation prompt.
- `Runnable` chain cho generation pipeline.
- `Document` + `VectorStore` + `Retriever` cho retrieval.

Baseline cung da co lop `LearningAgent` co kiem soat. Agent nay khong tu do
goi tool ben ngoai, ma chi dieu phoi cac service noi bo da duoc phe duyet:
parse request, lay profile, lap practice plan, retrieve knowledge, generate,
validate, score, update profile va recommend. Neu generation/validation loi,
agent co buoc reflection va retry truoc khi tra loi.

Ban P0/P1 them learner model va retrieval production-minded hon: skill graph,
BKT mastery, structured error diagnosis, adaptive recommendation, hybrid
retrieval, reranker, va offline evaluation suite.

Ban P2 them production foundation: PostgreSQL repository backend, pgvector
retrieval backend, signed bearer-token auth, LangGraph-compatible workflow
graph, metrics/OpenTelemetry instrumentation, va GitHub Actions CI.

## Luong xu ly baseline

```text
User Request
  -> Learning Agent
  -> Intent Parser Tool
  -> Profile Lookup Tool
  -> Personalization Planner Tool
  -> Retrieval Tool
  -> Exercise Generator Tool
  -> Exercise Validator Tool
  -> Reflection / Retry neu can
  -> Session Scoring
  -> Error Diagnosis
  -> Weakness Update
  -> Skill Mastery Update (BKT)
  -> Recommendation
```

## Nguyen tac thiet ke

- Tach rieng `retrieval`, `generation`, `personalization` de sau nay thay prompt, model hoac fine-tune ma khong dap vo toan bo he thong.
- Su dung schema du lieu ro rang ngay tu dau de sau nay log du lieu fine-tune duoc.
- Giu baseline don gian: parser co the rule-based, generation co the prompt-based, recommendation co the heuristic.
- Moi module co mot trach nhiem chinh, tranh tron UI, business logic va storage.

## Cau truc module de trien khai

```text
app/
  bootstrap.py                  # Noi ghep dependency cho baseline
  api/
    main.py                     # FastAPI layer cho frontend va Docker
    schemas.py                  # Request/response models cho HTTP API
  config.py                     # Cau hinh chung
  schemas.py                    # Dataclass / schema dung chung
  intent/
    parser.py                   # Phan tich yeu cau hoc tu raw text
  llm/
    factory.py                  # Chon ChatOpenAI hoac fallback Runnable
  retrieval/
    embeddings.py              # Chon keyword_hash / OpenAI / Ollama embeddings
    sparse.py                  # Keyword/BM25-style retrieval
    hybrid.py                  # Reciprocal-rank fusion
    reranker.py                # Lightweight metadata/query reranker
    service.py                  # Dieu phoi truy xuat context
    vector_store.py             # Dense/sparse/hybrid retriever backend
    pgvector_store.py           # PostgreSQL + pgvector retrieval backend
  generation/
    prompts.py                  # Prompt template
    output_models.py            # Pydantic schema cho parser
    service.py                  # LangChain generation chain
    validator.py                # Validate output
  personalization/
    service.py                  # Tao practice plan + cap nhat profile
  learner/
    skill_graph.py              # Taxonomy skill va prerequisite graph
    knowledge_tracing.py        # Bayesian Knowledge Tracing cho mastery
    spaced_repetition.py        # Lich review theo mastery/confidence
  diagnosis/
    service.py                  # Structured error classification
  recommendation/
    service.py                  # Goi y bai hoc tiep theo
  persistence/
    repository.py               # Interface luu profile/session
    postgres_repository.py      # PostgreSQL JSONB runtime backend
  auth/
    service.py                  # Signed bearer token + user isolation
  observability/
    metrics.py                  # In-process counters/timers
    tracing.py                  # Optional OpenTelemetry tracing
  agent/
    learning_agent.py           # Agent dieu phoi tool co kiem soat
    workflow_graph.py           # LangGraph-compatible node/edge contract
  orchestrator/
    pipeline.py                 # Adapter giu API cu va goi LearningAgent
chatbot.py                      # Entry point demo baseline hien tai
frontend/
  app/                          # Next.js App Router
  components/                   # UI blocks for dashboard/chat workspace
  lib/                          # Mock data, client types, API helpers
  package.json                  # Next.js frontend dependencies
evals/
  datasets/                     # Offline eval cases
  reports/                      # JSON reports generated by scripts
scripts/
  run_evals.py                  # Generation/diagnosis/recommendation/retrieval eval suite
  evaluate_retrieval.py         # Precision/recall/MRR/NDCG retrieval eval
.github/
  workflows/ci.yml              # Backend/frontend/eval regression gate
```

## Trach nhiem tung module

### `app/schemas.py`

- Dinh nghia cac doi tuong can tac nghiep xuyen suot he thong.
- Cac schema can co:
  - `PracticeRequest`
  - `PracticePlan`
  - `LearnerProfile`
  - `KnowledgeChunk`
  - `ExerciseItem`
  - `GeneratedExerciseSet`
  - `SessionResult`

### `app/intent/parser.py`

- Doc yeu cau tu nhien nhu:
  - "Toi muon luyen passive voice 5 cau muc de"
  - "Tao 10 cau vocab topic travel trung binh"
- Trich xuat:
  - topic
  - difficulty
  - exercise type
  - num questions

### `app/personalization/service.py`

- Hop nhat request voi ho so nguoi hoc.
- Neu user khong noi ro topic thi uu tien topic yeu nhat.
- Neu user khong noi ro do kho thi suy ra tu level / preferred difficulty.
- Sau khi nop bai, cap nhat `weak_topics`, accuracy, lan luyen gan nhat.
- Khi co skill mastery, uu tien skill yeu nhung prerequisite da san sang.

### `app/learner/*`

- Chuan hoa exercise metadata thanh `skill_id` on dinh.
- Luu prerequisite graph cho cac skill grammar/vocabulary chinh.
- Cap nhat `user_skill_mastery` bang Bayesian Knowledge Tracing sau tung cau tra loi.
- Tinh `next_review_at` de ho tro spaced review.

### `app/llm/factory.py`

- Neu co `OPENAI_API_KEY`, dung `ChatOpenAI` qua `langchain-openai`.
- Neu chua co API key, dung `RunnableLambda` de fallback local.
- Cung mot interface chain de sau nay doi backend khong anh huong business flow.

### `app/retrieval/*`

- Quan ly truy xuat context cho generator.
- Ho tro `inmemory` hoac `chroma` vector store.
- Ho tro `keyword_hash`, `openai`, hoac `ollama` embedding backend.
- Mac dinh dung hybrid retrieval:
  - dense vector retrieval
  - sparse keyword retrieval
  - metadata filtering
  - reciprocal-rank fusion
  - lightweight reranking

### `app/generation/*`

- Tao `ChatPromptTemplate`.
- Chay chain `prompt -> llm/runnable -> parser`.
- Ep output ve schema co dinh bang `PydanticOutputParser`.
- Validate:
  - du so cau hoi
  - dung format
  - MCQ co 4 option
  - chi 1 dap an dung
  - co explanation

### `app/recommendation/service.py`

- Sinh goi y hoc tiep theo dua tren ket qua vua lam.
- Neu co answer-level metadata/diagnosis, uu tien skill vua sai va mastery con thap.
- Neu chua co mastery, fallback ve heuristic:
  - neu accuracy < 60% -> giam do kho / giu nguyen topic
  - neu accuracy > 80% -> tang do kho hoac chuyen subtopic

### `app/diagnosis/service.py`

- Phan loai loi sai thanh schema on dinh:
  - `error_type`
  - `skill_id`
  - `subtype`
  - `severity`
  - `mastery_impact`
- Dung diagnosis de lam review feedback cu the hon va lam input sach cho learner model.

### `app/persistence/repository.py`

- Truu tuong hoa storage de co the thay bang:
  - in-memory
  - SQLite
  - service khac
- Nhung du lieu phai luu som:
  - learner profile
  - practice sessions
  - generated exercises
  - user answers
  - recommendation history

### `frontend/*`

- `Next.js` la UI layer chinh cho project.
- Frontend chi nen xu ly:
  - chat input
  - hien thi exercise set
  - hien thi feedback / recommendation
  - quan sat profile va history
- Business logic NLP, retrieval, generation va scoring van nam o Python backend.
- Frontend hien da co the goi Python API va van giu local preview fallback.

### `app/api/*`

- Cung cap cac endpoint HTTP de frontend va Docker stack su dung.
- Baseline hien co:
  - `GET /api/health`
  - `POST /api/practice/generate`
  - `POST /api/practice/score`
- Practice sets duoc cache trong memory cho baseline scoring flow.

## Thu tu implement de nghi

1. `schemas.py`, `parser.py`, `personalization/service.py`
2. `persistence/repository.py`
3. `retrieval/vector_store.py`, `retrieval/service.py`
4. `generation/prompts.py`, `generation/service.py`, `generation/validator.py`
5. `agent/learning_agent.py`, `orchestrator/pipeline.py`
6. `app/api/main.py`
7. `frontend/app/page.tsx`
8. mo rong persistence va answer checking that

## Diem chen fine-tune ve sau

- `generation/service.py`: thay prompt-only bang model fine-tuned.
- `retrieval/vector_store.py`: thay embedding baseline bang embedding that / fine-tuned / reranker.
- `persistence/repository.py`: log them `prompt`, `context`, `output`, `user_feedback` de tao dataset fine-tune.

## Definition of Done cho baseline

- User nhap mot cau lenh tu nhien va he thong tra ve mot exercise set hop le.
- Bai tap co format on dinh va cham duoc.
- Ho so nguoi hoc duoc cap nhat sau moi session.
- He thong tra ve goi y cho buoi hoc tiep theo.
