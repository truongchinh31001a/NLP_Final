# Production Hardening Notes

Use these notes when moving from local/demo mode toward a real deployment.

## Environment Profiles

- Local: copy values from `env/local.env.example`.
- Docker demo: copy values from `env/docker-demo.env.example`.
- Production-like: start from `env/production-like.env.example` and replace every secret/service URL.

## Required Runtime Services

- FastAPI backend.
- Next.js frontend.
- PostgreSQL for learner state in production-like deployments.
- pgvector or Chroma for semantic retrieval.
- LLM provider: OpenAI or Ollama, configured through `LLM_BACKEND`.
- Embedding provider: OpenAI or Ollama, configured through `EMBEDDING_BACKEND`.
- Optional OpenTelemetry collector when `OTEL_ENABLED=true`.

## Required Secrets

- `OPENAI_API_KEY` when using OpenAI for chat/generation/embeddings.
- `POSTGRES_DATABASE_URL` or `DATABASE_URL`.
- `PGVECTOR_DATABASE_URL` when retrieval uses pgvector.
- `AUTH_TOKEN_SECRET`, at least 32 random characters for production-like deployments.

## Auth And Debug Gates

Production-like startup fails if `DEPLOYMENT_ENVIRONMENT=production` and auth is disabled.
It also fails when `AUTH_TOKEN_SECRET` is still the default placeholder or shorter than
32 characters.

Use these production-like settings:

```bash
DEPLOYMENT_ENVIRONMENT=production
AUTH_MODE=demo_token
AUTH_TOKEN_SECRET=<32+ random chars>
AUTH_DEV_TOKEN_ENABLED=false
DEBUG_ENDPOINTS_ENABLED=false
```

Debug routes under `/api/debug/*` are intended for local/demo only. Use
`/api/ops/observability` for the stable observability dashboard path, and put that
route behind infrastructure-level auth or a private network in production.

## CI Gates

The GitHub Actions workflow now runs:

- Python dependency integrity check with `pip check`.
- Python dependency security audit with `pip-audit`.
- Unit tests with `python -m unittest discover tests`.
- Offline AI evals with `python scripts/run_evals.py`.
- AI eval threshold gate with `python scripts/check_eval_thresholds.py`.
- Frontend dependency audit with `npm audit --omit=dev --audit-level=high`.
- Frontend lint/build.

Thresholds live in `evals/thresholds.json`.

The current CI audit explicitly ignores the published `chromadb 1.5.9`
advisories `PYSEC-2026-311`, `CVE-2026-45830`, `CVE-2026-45833`, and
`CVE-2026-45831` because PyPI does not yet offer a newer fixed `chromadb`
release. Remove those ignore flags as soon as a fixed Chroma release is
available, or switch production retrieval to `pgvector`.
