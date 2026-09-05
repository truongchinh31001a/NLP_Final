# Docker Setup

## Dich vu

- `postgres`: PostgreSQL kem pgvector extension cho P2 storage/retrieval
- `ollama`: local LLM runtime cho fallback/demo
- `backend`: Python + FastAPI + LangChain pipeline
- `frontend`: Next.js App Router UI
- `ollama-models`: one-shot pull for `OLLAMA_MODEL`
- `ollama-embedding-models`: one-shot pull for `OLLAMA_EMBEDDING_MODEL`

## Chay nhanh

```bash
docker compose up --build
```

Sau khi chay:

- Frontend: `http://localhost:3000`
- Backend healthcheck: `http://localhost:8000/api/health`
- Ollama Docker debug: `http://localhost:11435/api/tags`
- Workflow graph: `http://localhost:8000/api/debug/workflow`
- Metrics snapshot: `http://localhost:8000/api/debug/metrics`

## Smoke checks

```bash
python scripts/smoke_docker_stack.py
python scripts/smoke_conversation_flow.py --base-url http://localhost:8000
python scripts/smoke_pgvector_retrieval.py
```

`smoke_docker_stack.py` kiem tra `docker compose config`, backend health,
Ollama debug port, backend-to-Ollama network call, va PostgreSQL `vector`
extension. Script khong tu start container.

`smoke_conversation_flow.py` tao conversation, tao practice activity, submit
bang `activity_id`, hoi review/progress, tao New Chat, va check learner state
qua API. Script khong mo browser; browser checklist nam o
`docs/manual_smoke_checklist.md`.

`smoke_pgvector_retrieval.py` kiem tra search that qua pgvector neu Docker
Postgres dang chay. Mac dinh script dung table rieng `rag_smoke_documents`.

## Luu y

- Frontend se goi backend qua `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
- Backend container goi Ollama qua Docker network: `OLLAMA_BASE_URL=http://ollama:11434`
- Port `11435` tren host chi de debug container Ollama, tranh nham voi Ollama host o `11434`
- Service `ollama-models` tu pull `OLLAMA_MODEL` truoc khi backend start
- Service `ollama-embedding-models` tu pull `OLLAMA_EMBEDDING_MODEL` cho semantic retrieval
- Backend mac dinh van co the dung SQLite/Chroma de demo gon nhe
- Co the bat PostgreSQL repository bang `LEARNING_REPOSITORY_BACKEND=postgres`
- Co the bat pgvector retrieval bang `VECTOR_STORE_BACKEND=pgvector`
- Co the bat auth token bang `AUTH_MODE=demo_token`
- Frontend khong con local generation/scoring fallback; backend can san sang truoc khi demo

## Bien moi truong quan trong

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `LLM_BACKEND`
- `OLLAMA_MODEL`
- `OLLAMA_EMBEDDING_MODEL`
- `EMBEDDING_BACKEND`
- `DOCKER_OLLAMA_BASE_URL`
- `DOCKER_OLLAMA_HOST_PORT`
- `TUTOR_RESPONSE_LLM_ENABLED`
- `TUTOR_RESPONSE_LLM_TIMEOUT_SECONDS`
- `CONVERSATION_ROUTER_LLM_ENABLED`
- `LEARNING_REPOSITORY_BACKEND`
- `POSTGRES_DATABASE_URL`
- `VECTOR_STORE_BACKEND`
- `PGVECTOR_DATABASE_URL`
- `AUTH_MODE`
- `AUTH_TOKEN_SECRET`
- `OTEL_ENABLED`
- `OTEL_EXPORTER_OTLP_ENDPOINT`
- `CORS_ORIGINS`
