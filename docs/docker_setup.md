# Docker Setup

## Dich vu

- `backend`: Python + FastAPI + LangChain pipeline
- `frontend`: Next.js App Router UI

## Chay nhanh

```bash
docker compose up --build
```

Sau khi chay:

- Frontend: `http://localhost:3000`
- Backend healthcheck: `http://localhost:8000/api/health`

## Luu y

- Frontend se goi backend qua `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
- Backend hien dang dung in-memory repository va in-memory cache cho generated exercise sets
- Neu backend khong san sang, frontend van co local preview fallback

## Bien moi truong co the them sau

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `VECTOR_STORE_BACKEND`
- `CORS_ORIGINS`
