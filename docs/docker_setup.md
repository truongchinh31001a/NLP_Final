# Docker Setup

## Dich vu

- `postgres`: PostgreSQL kem pgvector extension cho P2 storage/retrieval
- `ollama`: local LLM runtime cho fallback/demo
- `backend`: Python + FastAPI + LangChain pipeline
- `frontend`: Next.js App Router UI

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

## Luu y

- Frontend se goi backend qua `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
- Backend container goi Ollama qua Docker network: `OLLAMA_BASE_URL=http://ollama:11434`
- Port `11435` tren host chi de debug container Ollama, tranh nham voi Ollama host o `11434`
- Service `ollama-models` tu pull `OLLAMA_MODEL` truoc khi backend start
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
