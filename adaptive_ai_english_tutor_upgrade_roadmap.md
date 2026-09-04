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

---

# 2. Main Problems in the Current Version

| Current component | Current limitation | Recommended upgrade |
|---|---|---|
| KeywordHashEmbeddings | Not true semantic embeddings | Real embedding model |
| Chroma retrieval | Basic vector retrieval | Hybrid retrieval + reranker |
| RecommendationService | Mostly score thresholds | Adaptive recommendation engine |
| Personalization | Latest score can dominate learner state | Persistent mastery model |
| LearningAgent | Fixed orchestration workflow | Stateful bounded agent |
| Review | Basic review + LLM support | Structured error diagnosis |
| SQLite | Suitable for demo | PostgreSQL |
| Tests | Limited coverage | Unit + integration + AI evaluation |
| GitHub repo | Academic-project style | Portfolio-quality repository |

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

| Priority | Upgrade | Value |
|---|---|---|
| P0 | Root README + architecture documentation | ⭐⭐⭐ |
| P0 | Real embedding model | ⭐⭐⭐⭐⭐ |
| P0 | Skill taxonomy | ⭐⭐⭐⭐⭐ |
| P0 | Exercise-skill tagging | ⭐⭐⭐⭐⭐ |
| P0 | Learner mastery model | ⭐⭐⭐⭐⭐ |
| P1 | Error diagnosis engine | ⭐⭐⭐⭐⭐ |
| P1 | Adaptive recommendation engine | ⭐⭐⭐⭐⭐ |
| P1 | Hybrid RAG | ⭐⭐⭐⭐ |
| P1 | Reranker | ⭐⭐⭐⭐ |
| P1 | Evaluation framework | ⭐⭐⭐⭐⭐ |
| P2 | LangGraph orchestration | ⭐⭐⭐⭐ |
| P2 | PostgreSQL + pgvector | ⭐⭐⭐⭐ |
| P2 | Authentication + multi-user | ⭐⭐⭐ |
| P2 | OpenTelemetry | ⭐⭐⭐⭐ |
| P2 | CI/CD + regression evaluation | ⭐⭐⭐⭐ |
| P3 | Speech-to-text | ⭐⭐⭐ |
| P3 | Text-to-speech | ⭐⭐⭐ |
| P3 | Free conversation tutor | ⭐⭐⭐ |
| P3 | Kubernetes / scaling | ⭐⭐ |

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

# 16. Suggested Development Phases

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
