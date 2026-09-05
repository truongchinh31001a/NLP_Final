# Smoke Report

Live smoke evidence for the local Docker demo stack.

## Run Metadata

- Date: 2026-09-05
- Operator: Codex live Docker smoke
- Environment profile: Docker Compose local stack
- Backend URL: `http://localhost:8000`
- Frontend URL: `http://localhost:3000`
- Docker Compose project: `nlp_final`
- Backend health:
  - `generator_backend=langchain-ollama:llama3.1:8b`
  - `repository_backend=sqlite`
  - `vector_store_backend=chroma`
- Ollama route:
  - Backend container: `http://ollama:11434`
  - Host debug: `http://localhost:11435`

## Commands

```bash
docker compose up -d --build --force-recreate
python scripts/smoke_conversation_flow.py
python scripts/smoke_docker_stack.py
python scripts/smoke_pgvector_retrieval.py
```

## Results

- Frontend HTTP smoke: passed; `/` and `/personalization` returned 200.
- Manual browser smoke: blocked by the execution environment; CUA reported no browser and visible URL launch was rejected by policy.
- Local API smoke: passed 14/14 checks.
- Docker stack smoke: passed 5/5 checks.
- pgvector retrieval smoke: passed 3/3 checks.

## Notes

- Conversation id: `chat_571918bc7ee94cca9737acb89248359f`
- Second conversation id: `chat_989e277a9e774c448e61acb0ac59a88e`
- Practice activity id: `activity_ae43ce94deda4a4d8d95852308e23438`
- Unsubmitted context activity id: `activity_f7f38d1829944876ae70d25c9088cfc8`
- Session code: `sess_2f9a9fb53dca4e4c8209944de514fc90`
- Skill mastery count: 2
- pgvector top-k chunks: `grammar_passive_007`, `grammar_passive_002`, `grammar_passive_006`
- Issues found: browser UI control was unavailable; script/API/Docker checks passed.
- Regression test added: pending clarification persistence and latest submitted activity review resolution.
