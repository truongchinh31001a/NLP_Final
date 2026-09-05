# Adaptive AI English Tutor — Upgrade Roadmap

## 1. Project Direction

### Current project
**Personalized English Exercise Chatbot**

### Recommended V2 direction
**Adaptive AI English Tutor — RAG + Learner Modeling + Agentic Workflow + Evaluation/MLOps**

The goal is **not to rewrite the entire project**, but to keep the existing product and upgrade the AI core so the system can:

- Understand what the learner is weak at
- Track mastery over time
- Select the next best learning activity
- Generate exercises using grounded knowledge
- Diagnose learner mistakes
- Adapt exercise difficulty
- Maintain long-term learner memory
- Evaluate retrieval, generation, recommendation, and learning effectiveness
- Operate as a production-oriented AI system

### Current implementation snapshot - 2026-09-05

The chat-flow refactor checklist is now implemented through Phase 17. The
project is no longer just a "chat to generate exercises" app; it now has the
foundation of a production-oriented adaptive tutor:

- Conversation API, `ConversationService`, and rule-first `ConversationRouter`
- Intent capabilities for `PRACTICE`, `EXPLAIN`, `REVIEW`, `PROGRESS`,
  `PROFILE_UPDATE`, and `GENERAL`
- `LearningActivity` lifecycle and `activity_id` as the primary practice
  identity
- Backend-owned generation, validation, scoring, diagnosis, mastery update,
  review, and recommendation continuation
- Progressive learner profiling instead of a mandatory onboarding gate
- Frontend migration to conversation/activity state, with local exercise and
  scoring fallbacks removed
- LLM-backed tutor responses for `GENERAL` and `EXPLAIN`, plus bounded
  context-aware fallback behavior
- First-class reading and writing activities inside the conversation UI
- Listening and speaking are explicitly scoped as follow-up work until the
  audio/STT/TTS stack is selected
- AI eval thresholds, dependency/security checks, environment profiles, and
  production-hardening docs
- Docker Compose path for backend-to-Ollama calls through the Docker network

The remaining roadmap should focus on live smoke testing, real deployment
integration, and deeper multimodal learning activities.

---

# 2. Current Gaps After The Chat-Flow Refactor

| Area | Current status | Recommended next upgrade |
|---|---|---|
| Conversation platform | Implemented through `ConversationRouter`, `ConversationService`, canonical conversation APIs, and learning activities | Add richer multi-turn tutor policies and manual smoke coverage |
| Tutor response | `GENERAL` and `EXPLAIN` can use LLM-backed responses with safe fallbacks | Add qualitative evals for naturalness, repetition, scope control, and Vietnamese/English switching |
| Embeddings | Configurable `keyword_hash`, OpenAI, and Ollama paths exist | Use a real semantic embedding model by default in production profiles |
| Retrieval | Dense/sparse/hybrid retrieval and heuristic reranking exist | Add stronger reranker evaluation and source-grounded answer checks |
| Recommendation | Structured recommendation and accept flow exist | Move toward ranking by mastery gap, forgetting risk, goals, and prerequisite readiness |
| Learner model | BKT-style mastery, skill graph, confidence, history, and review timing exist | Calibrate mastery parameters with eval data and add spaced-review policies |
| Error diagnosis | Structured diagnosis is persisted and shown in review | Improve diagnosis quality with examples, rubrics, and regression datasets |
| Activity model | Practice, reading, and writing are `LearningActivity` flows with UI panels | Add real listening/speaking once audio/STT/TTS is selected |
| Production runtime | Docker Compose includes FastAPI, Next.js, PostgreSQL/pgvector, and Ollama; env profiles and auth/debug gates are documented | Connect production auth/observability to the chosen deployment platform |
| Tests | Backend unit tests, frontend lint/build, eval thresholds, and dependency checks are green | Run browser and live Docker smoke against the user's local stack |

---

# 3. Core Feature: Learner Knowledge Model

The most important upgrade should be a real learner model.

Instead of:

```text
User completes exercise
        ↓
Score = 3/5
        ↓
topic_accuracy = 0.6
        ↓
Select difficulty using thresholds
```

Build:

```text
                   Learner Knowledge State
                            │
            ┌───────────────┼───────────────┐
            ↓               ↓               ↓
         Grammar         Vocabulary       Reading
            │
     ┌──────┼──────┐
     ↓      ↓      ↓
  Tenses  Article  Preposition
     │
 ┌───┴────────┐
 ↓            ↓
Present      Past
Simple       Simple
```

Example learner mastery:

```text
present_simple = 0.82
past_simple    = 0.41
article_a_an   = 0.67
preposition    = 0.32
```

Each skill can store:

```python
SkillMastery:
    user_id
    skill_id
    mastery_probability
    attempts
    correct_count
    incorrect_count
    confidence
    difficulty_history
    error_frequency
    last_practiced_at
    next_review_at
```

Updated learning loop:

```text
Answer
  ↓
Error Classification
  ↓
Affected Skill
  ↓
Mastery Update
  ↓
Learner State
  ↓
Next Best Exercise
```

---

# 4. Knowledge Tracing

A strong upgrade is to introduce a real learner modeling algorithm.

## Option 1: Bayesian Knowledge Tracing

Example:

```text
P(know Present Simple) = 0.42

User answers correctly
          ↓

Bayesian update
          ↓

P(know Present Simple) = 0.61
```

Over time:

```text
Session 1   0.31
Session 2   0.42
Session 3   0.59
Session 4   0.73
Session 5   0.86
```

When mastery exceeds a threshold:

```text
Present Simple mastered
          ↓
Unlock prerequisite-dependent skill
          ↓
Present Continuous
```

## Possible progression

```text
BKT
 +
Item Response Theory
 +
Spaced Repetition
```

### Responsibility separation

LLM:

```text
Generate exercises
Explain answers
Classify errors
Tutor conversation
```

Adaptive engine:

```text
What should the learner study next?
How difficult should the exercise be?
When should the skill be reviewed?
Which skill is currently weak?
```

---

# 5. RAG Upgrade

The current retrieval layer should become a real semantic retrieval system.

## Target ingestion pipeline

```text
Knowledge Sources
      ↓
Document Loader
      ↓
Semantic Chunking
      ↓
Metadata Enrichment
      ↓
Embedding Model
      ↓
Vector Database
```

Example metadata:

```json
{
  "skill_id": "grammar.present_perfect_continuous",
  "cefr": "B1",
  "topic": "grammar",
  "subtopic": "present_perfect_continuous",
  "difficulty": 0.62,
  "source": "english_grammar_reference",
  "exercise_types": [
    "mcq",
    "fill_blank"
  ],
  "prerequisites": [
    "present_perfect"
  ]
}
```

## Hybrid retrieval

```text
Learner Request
      │
      ├── Dense Semantic Retrieval
      │
      ├── Keyword Search
      │
      └── Metadata Filtering
                ↓
              Fusion
                ↓
             Reranker
                ↓
              Top K
```

Possible production storage:

```text
PostgreSQL
+
pgvector
```

instead of:

```text
SQLite
+
Chroma
```

---

# 6. Adaptive Recommendation Engine

Replace simple score-based recommendations with a ranking engine.

## Pipeline

```text
Candidate Skills
       ↓
Prerequisite Filter
       ↓
Mastery Gap
       ↓
Forgetting Risk
       ↓
Learner Goal
       ↓
Recent Performance
       ↓
Difficulty Match
       ↓
Ranking
       ↓
Next Best Learning Activity
```

Possible scoring function:

```text
priority(skill) =
    weakness_score
  × forgetting_probability
  × goal_relevance
  × prerequisite_readiness
```

Example recommendation:

```text
Recommended next skill:
Past Perfect

Why:
- mastery = 0.43
- 4/7 recent errors are related to tense sequencing
- prerequisite Past Simple mastery = 0.87
- last practiced 6 days ago

Difficulty:
Medium

Exercise mix:
- 5 fill-in-the-blank
- 3 error-correction questions
```

---

# 7. Error Diagnosis Engine

Instead of only marking an answer as incorrect, classify the error.

Example learner sentence:

```text
She go to school yesterday.
```

Structured diagnosis:

```json
{
  "error_type": "verb_tense",
  "skill": "grammar.past_simple",
  "subtype": "missing_past_inflection",
  "severity": 0.8,
  "mastery_impact": -0.12,
  "explanation": "The verb should use the past form because the sentence refers to yesterday."
}
```

Learner state can then become:

```text
User
 ├── Present Simple      82%
 ├── Past Simple         41%
 │     ├── Irregular verbs     32%
 │     └── Time expressions    71%
 │
 ├── Articles            68%
 └── Prepositions        37%
```

This should become one of the major AI components of the project.

---

# 8. Agent Workflow

Do not turn the application into an unnecessarily complex multi-agent system.

Recommended approach:

**Stateful bounded agent**

Possible implementation with LangGraph:

```text
START
  ↓
Understand Intent
  ↓
Load Learner State
  ↓
Select Learning Goal
  ↓
Retrieve Knowledge
  ↓
Generate Exercise
  ↓
Validate Exercise
  │
  ├── Invalid → Regenerate
  │
  ↓
Serve Exercise
  ↓
Receive Answer
  ↓
Grade
  ↓
Diagnose Error
  ↓
Update Mastery
  ↓
Recommend Next Skill
  ↓
Update Long-term Memory
  ↓
END
```

LangGraph should be treated as orchestration infrastructure.

The actual project contribution should still be:

- learner adaptation
- skill modeling
- recommendation
- evaluation

---

# 9. Memory Architecture

Split memory into three levels.

```text
Memory
│
├── Short-Term Memory
│   ├── Current conversation
│   ├── Current exercise
│   └── Current learning goal
│
├── Episodic Memory
│   ├── Session history
│   ├── Previous mistakes
│   └── Previous recommendations
│
└── Semantic Learner Memory
    ├── Skill mastery
    ├── Preferences
    ├── Goals
    ├── Common errors
    └── Learning pace
```

This makes the term **personalized learning** technically meaningful.

---

# 10. Skill Graph

Add an explicit skill dependency graph.

Example:

```text
               English
                  │
        ┌─────────┴─────────┐
        ↓                   ↓
     Grammar             Vocabulary
        │
 ┌──────┼──────┐
 ↓      ↓      ↓
Tense Article Preposition
 │
 ├── Present Simple
 ├── Present Continuous
 ├── Past Simple
 ├── Present Perfect
 └── Past Perfect
```

Prerequisite relationships:

```text
Past Simple
     ↓
Present Perfect
     ↓
Past Perfect
```

The recommendation engine should avoid recommending advanced skills when prerequisites are not sufficiently mastered.

Possible data model:

```text
skills
skill_dependencies
skill_prerequisites
skill_cefr_levels
exercise_skill_mapping
user_skill_mastery
```

---

# 11. AI Evaluation

Create:

```text
evals/
```

Recommended evaluation groups:

## Generation Quality

```text
Schema validity
Answer correctness
Difficulty match
Grammar correctness
Groundedness
Instruction compliance
```

## Retrieval

```text
Recall@K
Precision@K
MRR
NDCG@K
Reranker accuracy
```

## Adaptive Learning

```text
Mastery gain
Error recurrence
Retention
Difficulty calibration
Recommendation acceptance
Skill progression
```

## System

```text
P50 latency
P95 latency
LLM failure rate
Fallback rate
Validation failure rate
Token usage
Cost per session
```

Example dashboard:

```text
Generation Quality
─────────────────────
Schema validity       99.1%
Answer correctness    96.4%
Difficulty match      88.3%
Groundedness          93.2%

Retrieval
─────────────────────
Recall@5              0.91
MRR                   0.84
NDCG@5                0.89
```

---

# 12. Production / MLOps

Recommended CI/CD pipeline:

```text
GitHub Actions
      ↓
pytest
      ↓
ruff
      ↓
mypy
      ↓
AI evaluation regression
      ↓
Docker build
      ↓
Security scan
      ↓
Deploy
```

Recommended runtime:

```text
Next.js
   ↓
FastAPI
   ↓
AI Orchestrator
   ├── LLM
   ├── Embedding
   ├── Reranker
   └── Adaptive Learning Engine
          ↓
PostgreSQL + pgvector
          ↓
Observability
```

Monitor:

```text
HTTP latency
LLM latency
Retrieval latency
Token usage
LLM failure rate
Fallback rate
Validation failure
Retrieval hit rate
```

Recommended observability stack:

```text
OpenTelemetry
Prometheus
Grafana
```

Optional:

```text
Langfuse
```

for LLM tracing and evaluation.

---

# 13. Repository Upgrade

Rename the repository from an academic-style name such as:

```text
NLP_Final
```

to something like:

```text
adaptive-ai-english-tutor
```

Alternative names:

```text
lingua-agent
adaptive-learning-agent
english-ai-tutor
```

Recommended repository description:

```text
An adaptive AI English learning platform using RAG,
learner modeling, mastery tracking, LLM agents,
personalized recommendation, and AI evaluation.
```

Suggested GitHub topics:

```text
nlp
llm
rag
langgraph
fastapi
nextjs
adaptive-learning
recommendation-system
knowledge-tracing
pgvector
ai-agent
education
```

---

# 14. Recommended Repository Structure

```text
adaptive-ai-english-tutor/
│
├── app/
│   ├── api/
│   │   ├── routes/
│   │   ├── dependencies/
│   │   └── middleware/
│   │
│   ├── agent/
│   │   ├── graph.py
│   │   ├── state.py
│   │   ├── nodes/
│   │   └── tools/
│   │
│   ├── learner/
│   │   ├── mastery.py
│   │   ├── knowledge_tracing.py
│   │   ├── spaced_repetition.py
│   │   └── skill_graph.py
│   │
│   ├── recommendation/
│   │   ├── engine.py
│   │   ├── ranking.py
│   │   └── policies.py
│   │
│   ├── retrieval/
│   │   ├── embeddings.py
│   │   ├── dense.py
│   │   ├── sparse.py
│   │   ├── hybrid.py
│   │   └── reranker.py
│   │
│   ├── generation/
│   │   ├── exercise_generator.py
│   │   ├── explanation_generator.py
│   │   └── validator.py
│   │
│   ├── diagnosis/
│   │   ├── error_classifier.py
│   │   ├── error_schema.py
│   │   └── mastery_impact.py
│   │
│   ├── memory/
│   │   ├── short_term.py
│   │   ├── episodic.py
│   │   └── learner_memory.py
│   │
│   ├── persistence/
│   │   ├── models/
│   │   ├── repositories/
│   │   └── database.py
│   │
│   ├── observability/
│   │   ├── tracing.py
│   │   └── metrics.py
│   │
│   └── config/
│
├── frontend/
│
├── knowledge/
│   ├── grammar/
│   ├── vocabulary/
│   ├── reading/
│   └── metadata/
│
├── evals/
│   ├── datasets/
│   ├── retrieval/
│   ├── generation/
│   ├── recommendation/
│   └── reports/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── ai/
│
├── scripts/
│   ├── ingest.py
│   ├── seed_skills.py
│   └── run_evals.py
│
├── migrations/
├── docker/
├── docs/
│   ├── architecture.md
│   ├── rag.md
│   ├── learner-model.md
│   └── evaluation.md
│
├── docker-compose.yml
├── pyproject.toml
├── .github/
│   └── workflows/
│
└── README.md
```

---

# 15. Priority Roadmap

| Priority | Upgrade | Current status | Next action |
|---|---|---|---|
| P0 | Root README + architecture documentation | Done | Keep docs aligned with the implemented conversation/activity architecture |
| P0 | Skill taxonomy | Done | Expand coverage as new activity types are added |
| P0 | Exercise-skill tagging | Done | Add stricter validation/evals for generated items |
| P0 | Learner mastery model | Done | Calibrate BKT parameters and review intervals with real usage data |
| P0 | Conversation platform | Done through checklist Phase 11 | Manual smoke and richer tutor-response evals |
| P1 | Error diagnosis engine | Implemented | Improve diagnosis rubrics and add regression datasets |
| P1 | Adaptive recommendation engine | Implemented baseline | Upgrade ranking with forgetting risk, goals, and prerequisite readiness |
| P1 | Hybrid RAG | Implemented baseline | Benchmark retrieval quality and tune reranking |
| P1 | Evaluation framework | Implemented baseline | Add conversation-quality, grounding, and repetition evals |
| P1 | Real semantic embedding model | Optional provider path exists | Choose production default and document setup clearly |
| P2 | LangGraph orchestration | Contract/workflow implemented | Decide whether to move more runtime orchestration into graph nodes |
| P2 | PostgreSQL + pgvector | Optional Docker/runtime path exists | Add smoke tests against containerized Postgres/pgvector |
| P2 | Authentication + multi-user | Demo-token mode implemented | Harden auth model before real deployment |
| P2 | OpenTelemetry | Optional tracing implemented | Wire metrics/traces into real dashboards |
| P2 | CI/CD + regression evaluation | Implemented baseline | Add AI eval thresholds as required checks |
| P3 | Reading/listening/speaking/writing activities | Domain enum exists; practice is first-class | Build dedicated activity services and UI panels |
| P3 | Speech-to-text | Not started | Add when speaking/listening becomes a product priority |
| P3 | Text-to-speech | Not started | Add when listening/speaking activities need audio output |
| P3 | Kubernetes / scaling | Not started | Defer until deployment scale requires it |

---

## P0/P1 Implementation Status - 2026-09-03

Current repository status:

- P0 Root README + architecture documentation: done via `README.md`,
  `docs/baseline_architecture.md`, and `docs/learner_model.md`.
- P0 Real embedding model: code path done via configurable
  `EMBEDDING_BACKEND=keyword_hash|openai|ollama`; semantic providers require
  installing dependencies and setting provider credentials/runtime.
- P0 Skill taxonomy: done in `app/learner/skill_graph.py` and seeded into
  SQLite tables `skills` and `skill_dependencies`.
- P0 Exercise-skill tagging: done through generated/seed exercise metadata
  validation and `target_skill_id` practice planning.
- P0 Learner mastery model: done with Bayesian Knowledge Tracing, persistent
  `user_skill_mastery`, `user_skill_mastery_history`, confidence, attempts, and
  `next_review_at`.
- P1 Error diagnosis engine: done with `AnswerDiagnosis`, `app/diagnosis/`,
  `answer_diagnoses` persistence, API response mapping, and frontend review UI.
- P1 Adaptive recommendation engine: done with latest missed-skill signals,
  mastery gap, prerequisite readiness, and difficulty adaptation.
- P1 Hybrid RAG: done with dense retrieval, sparse keyword retrieval, metadata
  scoring/filtering, and reciprocal-rank fusion.
- P1 Reranker: done with a lightweight query/metadata heuristic reranker,
  configurable through `RERANKER_ENABLED`.
- P1 Evaluation framework: done with `evals/`, `scripts/run_evals.py`, and
  retrieval metrics in `scripts/evaluate_retrieval.py`.

Verification commands:

```bash
python -m compileall app scripts tests
python -m unittest discover tests
python scripts/run_evals.py
cd frontend
npm run lint
npm run build
```

If LangChain retrieval dependencies are not installed in the current Python
environment, run the non-retrieval checks while setting up dependencies:

```bash
python scripts/run_evals.py --skip-retrieval
```

---

## P2 Implementation Status - 2026-09-04

Current repository status:

- P2 LangGraph orchestration: done as a LangGraph-compatible workflow contract
  in `app/agent/workflow_graph.py`, exposed by `GET /api/debug/workflow`, with
  tests proving the generation path can compile and run through LangGraph.
- P2 PostgreSQL + pgvector: done as optional runtime backends. Set
  `LEARNING_REPOSITORY_BACKEND=postgres` for JSONB learner/session storage and
  `VECTOR_STORE_BACKEND=pgvector` for PostgreSQL vector retrieval. Docker
  Compose now includes a `pgvector/pgvector` Postgres service.
- P2 Authentication + multi-user: done as optional HMAC bearer-token auth. Set
  `AUTH_MODE=demo_token`, create a token with `POST /api/auth/dev-token`, then
  send `Authorization: Bearer <token>`; user routes reject cross-user access.
- P2 OpenTelemetry: done as optional tracing with `OTEL_ENABLED=true`, plus
  always-available in-process counters/timers at `GET /api/debug/metrics`.
- P2 CI/CD + regression evaluation: done with `.github/workflows/ci.yml`,
  running Python compile, unit tests, AI evals, frontend lint, and frontend
  production build.

Verification commands:

```bash
python -m compileall app scripts tests
python -m unittest discover tests
python scripts/run_evals.py
cd frontend
npm run lint
npm run build
```

PostgreSQL/pgvector runtime requires a running Postgres server with the
`vector` extension. The included Docker Compose stack provides that service.

---

## Conversation Platform Implementation Status - 2026-09-05

Current repository status after `checklist.md`:

- Conversation domain boundaries are implemented with `ConversationIntent`,
  `ConversationTurnContext`, `PendingClarification`, and `LearningActivity`.
- `ConversationRouter` routes learner turns before practice interpretation,
  keeping review/progress/explanation/profile/general chat out of the generic
  practice parser.
- New conversation APIs are implemented:
  `POST /api/conversations`, `GET /api/conversations`,
  `GET /api/conversations/{id}`, and
  `POST /api/conversations/{id}/messages`.
- Practice generation and submission are wrapped in the activity lifecycle.
  Compatibility endpoints remain, but the canonical flow uses `activity_id`.
- Review, progress, explanation, profile update, and general tutor responses
  are implemented as separate backend capabilities.
- Frontend state is split into conversation state and activity state; local
  exercise generation/scoring fallbacks have been removed.
- Structured recommendations can be accepted directly without reparsing a text
  prompt as a new generic practice request.
- `GENERAL` and `EXPLAIN` responses can use the configured tutor-response LLM,
  with bounded context-aware fallback behavior when the model is unavailable.
- Short learner choices such as `doc truoc di` are handled as learning-focus
  selections instead of repeating the previous menu.
- Reading and writing are first-class activities with backend lifecycle,
  persistence, API submission paths, and frontend panels.
- Listening and speaking are routed as intentional follow-up activities, with
  product work deferred until audio, STT, and TTS choices are made.
- Production hardening now includes stricter auth configuration, debug endpoint
  gates, an observability dashboard path, env profiles, CI eval thresholds, and
  dependency/security checks.
- Docker Compose is configured so backend calls Ollama through
  `http://ollama:11434` inside the Docker network.

Known follow-up items from the checklist:

- Verify manually in the browser: create a conversation, generate practice,
  submit by `activity_id`, ask for mistake review, ask progress, start a new
  chat, and confirm learner state persists.
- Run the Docker/API smoke scripts against a live stack after starting the
  containers locally.
- Choose the audio/STT/TTS stack before turning listening and speaking into
  real interactive activities.
- Connect auth and observability to the real deployment provider if the project
  moves beyond demo/local production-like mode.

---

# 16. Development Phases

The original phase list below was written before the chat-flow refactor. After
`checklist.md`, the implementation phases are complete except for manual/live
smoke tasks that require running the local stack.

## Implemented Phases And Remaining Smoke Work

### Phase A - Manual Smoke And Contract Hardening

Status after Phase 12 implementation:

- Contract docs, `generation_run_id` audit, Docker smoke script, and API smoke
  script are added.
- Manual browser smoke is still pending because it must be run against the real
  UI/runtime.

Objectives:

- Run the full browser smoke path: create conversation, generate practice,
  submit by `activity_id`, review a wrong answer, ask progress, start a new
  chat, and confirm learner state persists.
- Audit all remaining `generation_run_id` usage and keep it as trace/debug
  identity only.
- Add contract notes for legacy `/api/practice/*` wrappers versus canonical
  conversation/activity endpoints.
- Add a PostgreSQL/pgvector smoke path for Docker Compose.

Deliverable:

```text
Conversation/activity platform is verified end-to-end, not only by unit tests.
```

### Phase B - Tutor Response Quality Evaluation

Status after Phase 13 implementation:

- Offline tutor response dataset, checks, eval runner integration, and optional
  live backend comparison path are added.

Objectives:

- Add a small eval dataset for natural tutor chat, explanation, off-topic
  bridging, scope control, and repetition avoidance.
- Include Vietnamese short replies such as `doc truoc di`, `nghe truoc`,
  `viet truoc`, and ambiguous complaints such as `nghe ki phet`.
- Track fallback rate, LLM timeout rate, repeated-menu rate, and answer
  naturalness.
- Compare Ollama and OpenAI response behavior with the same payload format.

Deliverable:

```text
Tutor conversation quality can be measured before and after prompt/code changes.
```

### Phase C - Production Retrieval And Grounding

Status after Phase 14 implementation:

- Production embedding profile, expanded retrieval evals, hybrid/reranker
  tuning, and grounding checks are implemented.

Objectives:

- Choose a production embedding default for Docker/local development.
- Expand retrieval evals with topic, subtopic, CEFR, and source-grounding
  checks.
- Tune hybrid retrieval and reranking against the eval dataset.
- Require grounded citations/context for explanation answers where relevant.

Deliverable:

```text
RAG quality is measured and stable enough for portfolio/demo use.
```

### Phase D - Adaptive Recommendation Depth

Status after Phase 15 implementation:

- Recommendation ranking now uses mastery gap, forgetting risk, prerequisite
  readiness, learner goals, recent performance, and difficulty match.
- Mastery calibration, spaced-review policy, persisted recommendation evidence,
  and recommendation eval coverage are implemented.

Objectives:

- Improve next-activity ranking with mastery gap, forgetting risk, prerequisite
  readiness, learner goals, and recent performance.
- Calibrate BKT/mastery parameters with observed answer history.
- Add spaced-review policies using `next_review_at`.
- Evaluate recommendation acceptance and repeated-error reduction.

Deliverable:

```text
Recommendations become meaningfully adaptive instead of just plausible.
```

### Phase E - First-Class Reading/Listening/Speaking/Writing Activities

Status after Phase 16 implementation:

- Reading and writing are implemented as real activity services with API
  lifecycle, persistence, frontend panels, and tests.
- Listening and speaking are intentionally left as design-ready follow-up
  activities until audio/STT/TTS is selected.

Objectives:

- Turn the existing `LearningActivityType` enum values into real activity
  services and UI panels.
- Start with reading: passage, vocabulary support, comprehension questions,
  and explanation.
- Add writing correction with rubric-based feedback.
- Add listening/speaking later when audio/STT/TTS is a product priority.

Deliverable:

```text
The tutor supports multiple learning activity types, not only practice quizzes.
```

### Phase F - Production Hardening

Status after Phase 17 implementation:

- Auth config is hardened for production-like mode, debug endpoints are gated,
  an observability dashboard path is exposed, env profiles are documented, and
  CI runs AI eval thresholds plus dependency/security checks.

Objectives:

- Harden auth beyond demo-token mode.
- Wire OpenTelemetry metrics/traces into dashboards.
- Add AI eval thresholds to CI once eval data is stable.
- Prepare deployment docs, security checks, and environment profiles.

Deliverable:

```text
The project is ready to present as a production-oriented adaptive AI tutor.
```

## Historical Pre-Checklist Phases

## Phase 0 — Repository Cleanup

Objectives:

- Rename repository
- Create root README
- Add architecture diagram
- Add `.env.example`
- Clean dependency files
- Improve Docker configuration
- Organize tests

Deliverable:

```text
Professional portfolio-ready repository
```

---

## Phase 1 — Skill Modeling

Implement:

```text
Skill Taxonomy
Skill Graph
Exercise → Skill Mapping
User Skill Mastery
```

Example database:

```text
users
skills
skill_dependencies
exercise_templates
exercise_skills
user_skill_mastery
learning_sessions
attempts
```

Deliverable:

```text
System understands what skill every exercise evaluates
```

---

## Phase 2 — Knowledge Tracing

Implement:

```text
Initial mastery
      ↓
Answer observation
      ↓
BKT update
      ↓
Updated mastery
```

Store mastery history.

Deliverable:

```text
Persistent learner knowledge state
```

---

## Phase 3 — Error Diagnosis

Implement structured error schema.

```text
Answer
  ↓
Correctness
  ↓
Error Type
  ↓
Skill
  ↓
Subtype
  ↓
Severity
  ↓
Mastery Impact
```

Deliverable:

```text
System knows why the learner made a mistake
```

---

## Phase 4 — Adaptive Recommendation

Input:

```text
Learner mastery
Skill graph
Recent errors
Learning goal
Review schedule
Difficulty
```

Output:

```text
Next Best Learning Activity
```

Deliverable:

```text
Adaptive curriculum engine
```

---

## Phase 5 — Production RAG

Replace development retrieval with:

```text
Embedding Model
+
Hybrid Search
+
Metadata Filtering
+
Reranker
```

Possible stack:

```text
Sentence Transformers / OpenAI Embeddings
PostgreSQL
pgvector
BM25 / PostgreSQL FTS
Cross Encoder Reranker
```

Deliverable:

```text
Production-grade knowledge retrieval
```

---

## Phase 6 — Stateful Agent

Move orchestration into a graph.

```text
Intent
 ↓
Learner State
 ↓
Learning Planner
 ↓
RAG
 ↓
Generation
 ↓
Validation
 ↓
Evaluation
 ↓
Mastery Update
 ↓
Recommendation
```

Deliverable:

```text
Stateful adaptive learning agent
```

---

## Phase 7 — Evaluation

Create a benchmark dataset.

Evaluate:

```text
RAG
Generation
Difficulty
Error diagnosis
Recommendation
System latency
```

Deliverable:

```text
Quantitative AI evaluation report
```

---

## Phase 8 — Production Engineering

Add:

```text
PostgreSQL
Authentication
OpenTelemetry
Prometheus
Grafana
CI/CD
Docker
Security
Deployment
```

Deliverable:

```text
Production-ready AI application
```

---

# 17. Target System Architecture

```text
                         ┌─────────────────────┐
                         │      Next.js UI     │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │       FastAPI       │
                         └──────────┬──────────┘
                                    │
                                    ▼
                    ┌────────────────────────────┐
                    │    Learning Orchestrator   │
                    │       / LangGraph          │
                    └──────────────┬─────────────┘
                                   │
              ┌────────────────────┼─────────────────────┐
              │                    │                     │
              ▼                    ▼                     ▼
     ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────┐
     │ Learner Modeling│  │    RAG Engine    │  │    Tutor LLM    │
     │                 │  │                  │  │                 │
     │ BKT / Mastery   │  │ Dense Retrieval │  │ Generation      │
     │ Skill Graph     │  │ Keyword Search  │  │ Explanation     │
     │ Spaced Review   │  │ Reranker        │  │ Error Analysis  │
     └────────┬────────┘  └────────┬─────────┘  └────────┬────────┘
              │                    │                     │
              └────────────────────┼─────────────────────┘
                                   │
                                   ▼
                       ┌────────────────────────┐
                       │ PostgreSQL + pgvector  │
                       │                        │
                       │ Users                  │
                       │ Skills                 │
                       │ Mastery                │
                       │ Exercises              │
                       │ Sessions               │
                       │ Errors                 │
                       │ Embeddings             │
                       └────────────┬───────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Eval / Observability│
                         │                     │
                         │ RAG Metrics         │
                         │ LLM Quality         │
                         │ Learning Metrics    │
                         │ Latency / Cost      │
                         └─────────────────────┘
```

---

# 18. Main Learning Loop

The whole project should revolve around this loop:

```text
      ┌──────────────────────────────┐
      │                              │
      ▼                              │
Understand Learner                   │
      ↓                              │
Estimate Mastery                     │
      ↓                              │
Choose Next Skill                    │
      ↓                              │
Retrieve Knowledge                   │
      ↓                              │
Generate Exercise                    │
      ↓                              │
Student Answers                      │
      ↓                              │
Diagnose Errors                      │
      ↓                              │
Update Mastery ──────────────────────┘
```

---

# 19. Project Positioning

Instead of presenting the project as:

> AI chatbot for generating English exercises.

Present it as:

> A production-oriented adaptive AI tutoring system that combines retrieval-augmented generation, learner knowledge tracing, structured error diagnosis, mastery-based recommendation, stateful AI orchestration, and quantitative evaluation to personalize English learning.

---

# 20. Recommended Technical Stack

## Frontend

```text
Next.js
TypeScript
TailwindCSS
```

## Backend

```text
Python
FastAPI
Pydantic
SQLAlchemy
Alembic
```

## AI

```text
OpenAI / Ollama
LangGraph
Sentence Transformers
Cross Encoder Reranker
```

## Retrieval

```text
PostgreSQL
pgvector
PostgreSQL Full Text Search
```

## Adaptive Learning

```text
Bayesian Knowledge Tracing
Skill Graph
Spaced Repetition
Recommendation Ranking
```

## Infrastructure

```text
Docker
Docker Compose
GitHub Actions
```

## Observability

```text
OpenTelemetry
Prometheus
Grafana
```

---

# 21. Recommended Final Goal

The project should eventually answer one central question:

> **How can an AI tutoring system identify exactly what a learner is weak at and automatically decide what the learner should study next?**

Every major technical component should support that goal:

```text
RAG
        ↓
Better learning content

Error Diagnosis
        ↓
Understand learner mistakes

Knowledge Tracing
        ↓
Estimate learner mastery

Skill Graph
        ↓
Understand prerequisite relationships

Recommendation
        ↓
Choose next learning activity

LLM
        ↓
Generate and explain content

Evaluation
        ↓
Measure whether the system actually works
```

That makes the project significantly stronger as a:

- Master’s-level software AI project
- Full-stack AI portfolio project
- GenAI / Agentic AI portfolio project
- RAG project
- Recommendation / adaptive learning project
- MLOps-oriented AI system
