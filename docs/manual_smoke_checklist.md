# Manual Smoke Checklist

Use this checklist after backend and frontend are running. It is intentionally
manual because it checks the real browser experience, not only API contracts.

## Setup

```bash
docker compose up -d --build --force-recreate
```

Open:

```text
Frontend: http://localhost:3000
Backend health: http://localhost:8000/api/health
Ollama container debug: http://localhost:11435/api/tags
```

## Browser Flow

- [ ] Open the tutor UI and start a new conversation.
- [ ] Send: `Cho toi 2 cau passive voice.`
- [ ] Confirm a practice activity card appears.
- [ ] Confirm the activity has an `activity_id` in network/API payloads.
- [ ] Submit at least one wrong answer.
- [ ] Confirm the result/review panel appears.
- [ ] Send: `Tai sao cau 1 sai?`
- [ ] Confirm the tutor reviews the latest submitted activity instead of
  generating a new exercise set.
- [ ] Send: `Toi dang yeu phan nao?`
- [ ] Confirm the tutor returns progress/weak-skill information.
- [ ] Click New Chat.
- [ ] Confirm the new conversation has a different `conversation_id`.
- [ ] Confirm learner profile/mastery/preferences did not reset.
- [ ] Send: `doc truoc di`
- [ ] Confirm the tutor accepts reading focus and does not repeat the old
  `noi/nghe/doc/viet` menu.

## API Smoke Alternative

When you want a repeatable API smoke without opening the browser:

```bash
python scripts/smoke_conversation_flow.py --base-url http://localhost:8000
```

This does not start the server. It only checks a running backend.

## Docker Runtime Smoke

```bash
python scripts/smoke_docker_stack.py
python scripts/smoke_pgvector_retrieval.py
```

The Docker smoke checks:

- `docker compose config`
- backend health endpoint
- Ollama container debug endpoint
- backend container can reach `http://ollama:11434`
- PostgreSQL has the `vector` extension

The pgvector retrieval smoke checks an actual retrieval query against the
isolated `rag_smoke_documents` table.

Use `--soft` if you want a diagnostic report without a non-zero exit code.
