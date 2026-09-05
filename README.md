# Adaptive AI English Tutor

An adaptive English practice platform that combines retrieval-augmented
exercise generation, learner memory, skill-level mastery tracking, structured
error diagnosis, and personalized next-practice recommendations.

This repository started as a personalized English exercise chatbot. The current
direction is to make the AI core more explicit and measurable:

- RAG-backed exercise generation from English knowledge chunks.
- Seed-bank fallback for stable demos when an LLM is unavailable.
- Configurable embedding backends: local hash, OpenAI, or Ollama.
- Hybrid retrieval with sparse keyword search, dense vector search, metadata
  filtering, reciprocal-rank fusion, and a lightweight reranker.
- Skill taxonomy and prerequisite graph for English grammar/vocabulary.
- Bayesian Knowledge Tracing (BKT) for user skill mastery.
- Structured answer-level error diagnosis for mastery and review feedback.
- LLM-backed tutor responses for open conversation/explanations with offline
  context-aware fallbacks.
- Reading and writing activities with activity lifecycle, submit flow, and
  rubric/comprehension feedback.
- Topic, subtopic, error-pattern, and skill-level personalization dashboard.
- Offline AI evaluation scripts for retrieval, generation, diagnosis, and
  recommendation checks.
- Optional PostgreSQL repository backend and pgvector retrieval backend.
- Optional signed bearer-token auth for multi-user data isolation.
- In-process metrics plus optional OpenTelemetry tracing.
- Production-like env profile with auth/debug gates and CI eval thresholds.
- GitHub Actions CI for backend tests/evals and frontend lint/build.
- FastAPI backend with a Next.js frontend.

## Architecture

```text
Next.js UI
  -> FastAPI Conversation API
  -> Conversation Orchestrator
     -> intent router
     -> learning activities with stable activity_id
     -> profile/progress/explain/review/tutor response services
     -> recommendation accept flow
  -> LearningAgent for practice activities
     -> structured request or legacy parser
     -> personalization planner
     -> retrieval service
     -> exercise generator
     -> validator
     -> scorer / error diagnosis / review
     -> mastery update / structured recommendation
  -> SQLite or PostgreSQL persistence
  -> Chroma, in-memory, or pgvector retrieval
```

Key backend modules:

- `app/api/main.py`: FastAPI app bootstrap, middleware, debug/ops, and legacy routes.
- `app/api/routes/`: canonical conversation, activity, learner, and recommendation routes.
- `app/agent/`: bounded learning agent and LangGraph-compatible workflow graph.
- `app/activities/`: learning activity lifecycle for practice generation and submit.
- `app/auth/`: signed demo-token auth and user ownership checks.
- `app/conversation/`: conversation API orchestration, intent routing, and turn state.
- `app/learner/`: skill graph, BKT, review scheduling.
- `app/diagnosis/`: structured error classification and mastery impact.
- `app/personalization/`: practice plan selection from learner state.
- `app/recommendation/`: next-practice ranking from mastery and answer signals.
- `app/retrieval/`: dense/sparse/hybrid retrieval, embeddings, and reranking.
- `app/tutor/`: LLM-backed explain/general tutor responses with bounded fallbacks.
- `app/persistence/`: SQLite and PostgreSQL repositories.
- `app/observability/`: metrics registry and optional OpenTelemetry setup.
- `evals/`: offline datasets and evaluation report targets.

See `docs/architecture.md` for the current ownership map and cleanup rules.

## Canonical API Surface

New application code should use the platform vocabulary directly:

```text
POST /api/conversations
GET  /api/conversations?user_id={user_id}
GET  /api/conversations/{conversation_id}?user_id={user_id}
POST /api/conversations/{conversation_id}/messages

GET  /api/activities/{activity_id}?user_id={user_id}
GET  /api/activities/{activity_id}/review?user_id={user_id}
POST /api/activities/{activity_id}/submit

GET   /api/learners/{learner_id}/profile
PATCH /api/learners/{learner_id}/profile
GET   /api/learners/{learner_id}/mastery
GET   /api/learners/{learner_id}/progress
GET   /api/learners/{learner_id}/recommendations

POST /api/recommendations/{recommendation_id}/accept
```

Compatibility endpoints such as `/api/practice/*`, `/api/users/*`, and
`GET /api/recommendations?user_id=...` remain for older clients. See
`docs/conversation_activity_contract.md` for the full contract.

## Run Locally

Backend:

```bash
pip install -r requirements.txt
uvicorn app.api.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Docker:

```bash
docker compose up --build
```

Docker Compose starts PostgreSQL with pgvector, Ollama, the FastAPI backend, and
the Next.js frontend. SQLite/Chroma remain the default app storage/vector-store
backends, while Docker demo retrieval uses Ollama semantic embeddings by
default.
Inside Docker, the backend calls Ollama at `http://ollama:11434`. The compose
file exposes container Ollama on host port `11435` for debugging so it does not
get confused with a separate host Ollama running on `11434`.

## P2 Runtime Options

PostgreSQL learner storage:

```bash
LEARNING_REPOSITORY_BACKEND=postgres
POSTGRES_DATABASE_URL=postgresql://english_tutor:english_tutor@localhost:5432/english_tutor
```

pgvector retrieval:

```bash
VECTOR_STORE_BACKEND=pgvector
PGVECTOR_DATABASE_URL=postgresql://english_tutor:english_tutor@localhost:5432/english_tutor
PGVECTOR_TABLE_NAME=rag_documents
```

Token auth:

```bash
AUTH_MODE=demo_token
AUTH_TOKEN_SECRET=replace-this-secret
```

Tutor response generation:

```bash
LLM_BACKEND=ollama
DOCKER_OLLAMA_BASE_URL=http://ollama:11434
TUTOR_RESPONSE_LLM_ENABLED=true
TUTOR_RESPONSE_LLM_TIMEOUT_SECONDS=6
```

The conversation router remains rule-first for predictable activity routing.
When `LLM_BACKEND=openai` or `LLM_BACKEND=ollama` is configured, general chat and
explanation responses can use the tutor LLM. Without a chat model, the backend
uses context-aware fallback replies instead of a single canned response.

Get a local demo token:

```bash
curl -X POST http://localhost:8000/api/auth/dev-token \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":\"learner\"}"
```

Debug endpoints:

```bash
curl http://localhost:8000/api/debug/workflow
curl http://localhost:8000/api/debug/metrics
```

Smoke checks:

```bash
python scripts/smoke_conversation_flow.py --base-url http://localhost:8000
python scripts/smoke_docker_stack.py
python scripts/smoke_pgvector_retrieval.py
```

The smoke scripts do not start services. They verify a backend/Docker stack that
is already running.

Optional OpenTelemetry:

```bash
OTEL_ENABLED=true
OTEL_SERVICE_NAME=adaptive-ai-english-tutor
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

Production hardening:

```bash
DEPLOYMENT_ENVIRONMENT=production
AUTH_MODE=demo_token
AUTH_TOKEN_SECRET=<32+ random chars>
AUTH_DEV_TOKEN_ENABLED=false
DEBUG_ENDPOINTS_ENABLED=false
```

See `docs/production_hardening.md` and the env profiles in `env/` for the
local, Docker demo, and production-like runtime paths.

## Embedding And Retrieval Backends

The default embedding backend is `keyword_hash` so the project can run offline.
Docker demo uses `EMBEDDING_BACKEND=ollama` with
`OLLAMA_EMBEDDING_MODEL=nomic-embed-text`. For semantic retrieval outside
Docker, set one of:

```bash
EMBEDDING_BACKEND=openai
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

or:

```bash
EMBEDDING_BACKEND=ollama
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
```

Retrieval defaults to hybrid mode:

```bash
RETRIEVAL_MODE=hybrid
RERANKER_ENABLED=true
```

Use `RETRIEVAL_MODE=dense` or `RETRIEVAL_MODE=sparse` when you want to isolate
one retrieval path during debugging or evaluation.

See `docs/retrieval_backends.md` for the full backend matrix, hybrid fusion
behavior, reranker behavior, and pgvector smoke commands.

When changing embedding dimensions, use a new `CHROMA_COLLECTION_NAME` or rebuild
the Chroma collection:

```bash
python scripts/ingest_knowledge_chunks.py
```

## Test

```bash
python -m unittest discover tests
```

Run offline AI evaluations:

```bash
python scripts/run_evals.py
```

If LangChain retrieval dependencies are not installed in the current Python
environment, run the non-retrieval checks:

```bash
python scripts/run_evals.py --skip-retrieval
```

The eval suite includes tutor-response checks for naturalness guardrails,
repeated-menu avoidance, off-topic bridging, and learning-focus selections.
Optional live comparison can be run when the target backend is configured:

```bash
python scripts/run_evals.py --skip-retrieval --tutor-live-backends ollama
python scripts/run_evals.py --skip-retrieval --tutor-live-backends openai
```

Frontend checks:

```bash
cd frontend
npm run lint
npm run build
```
