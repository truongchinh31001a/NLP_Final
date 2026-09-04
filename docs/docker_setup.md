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
- Workflow graph: `http://localhost:8000/api/debug/workflow`
- Metrics snapshot: `http://localhost:8000/api/debug/metrics`

## Luu y

- Frontend se goi backend qua `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
- Backend mac dinh van co the dung SQLite/Chroma de demo gon nhe
- Co the bat PostgreSQL repository bang `LEARNING_REPOSITORY_BACKEND=postgres`
- Co the bat pgvector retrieval bang `VECTOR_STORE_BACKEND=pgvector`
- Co the bat auth token bang `AUTH_MODE=demo_token`
- Neu backend khong san sang, frontend van co local preview fallback

## Bien moi truong quan trong

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `LEARNING_REPOSITORY_BACKEND`
- `POSTGRES_DATABASE_URL`
- `VECTOR_STORE_BACKEND`
- `PGVECTOR_DATABASE_URL`
- `AUTH_MODE`
- `AUTH_TOKEN_SECRET`
- `OTEL_ENABLED`
- `OTEL_EXPORTER_OTLP_ENDPOINT`
- `CORS_ORIGINS`
