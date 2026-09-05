# Retrieval Backends

## Default Profiles

- Local Python default: `VECTOR_STORE_BACKEND=inmemory`,
  `RETRIEVAL_MODE=hybrid`, `EMBEDDING_BACKEND=keyword_hash`. This keeps tests
  and first-run development fully offline.
- Docker demo default: `VECTOR_STORE_BACKEND=chroma`,
  `RETRIEVAL_MODE=hybrid`, `EMBEDDING_BACKEND=ollama`,
  `OLLAMA_EMBEDDING_MODEL=nomic-embed-text`. Compose pulls both the chat model
  and the embedding model before backend startup.
- Production-like retrieval: use `VECTOR_STORE_BACKEND=pgvector`,
  `RETRIEVAL_MODE=hybrid`, and a semantic embedding backend (`ollama` for local
  infrastructure, `openai` when an API key is configured).

## Components

- `keyword_hash`: deterministic local embedding fallback. It is useful for
  tests, smoke scripts, and offline development, but it is lexical rather than
  semantic.
- `ollama`: local semantic embeddings via `OLLAMA_BASE_URL` and
  `OLLAMA_EMBEDDING_MODEL`. Docker exposes container Ollama on host port
  `11435`; inside Compose the backend uses `http://ollama:11434`.
- `openai`: hosted semantic embeddings via `OPENAI_API_KEY` and
  `OPENAI_EMBEDDING_MODEL`.
- `inmemory`: LangChain in-memory vector store, rebuilt on process start.
- `chroma`: local persisted vector store under `CHROMA_PERSIST_DIRECTORY`.
- `pgvector`: PostgreSQL table with vector column, metadata columns, and
  ivfflat cosine index.
- `sparse`: BM25-style keyword retriever over the same knowledge documents.
- `hybrid fusion`: reciprocal-rank fusion combines dense and sparse lists. The
  current default weights sparse retrieval slightly higher because knowledge
  chunks have reliable topic/subtopic labels.
- `reranker`: metadata-aware heuristic reranker that boosts topic, level,
  subtopic, CEFR, source, and query-token overlap. It is intentionally small so
  eval reports remain explainable.

## Evaluation

Run the offline retrieval eval:

```bash
python scripts/evaluate_retrieval.py --show-misses
```

The labeled CSV checks topic, level, subtopic, derived CEFR, source, and
expected chunk IDs. The report is written to
`evals/reports/retrieval_report.json`.

Run a pgvector contract smoke when Docker Postgres is already running:

```bash
python scripts/smoke_pgvector_retrieval.py
```

For Docker's Ollama embedding profile from the host:

```bash
python scripts/smoke_pgvector_retrieval.py --embedding-backend ollama --ollama-base-url http://localhost:11435
```

Both smoke commands use the isolated `rag_smoke_documents` table by default.
