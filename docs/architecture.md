# Architecture Ownership

This document is the current backend ownership map after the platform refactor.
It is intentionally boring: the goal is clear module boundaries without a
rewrite into microservices, event sourcing, Kafka, or a full multi-agent system.

## HTTP API Layer

- `app/api/main.py` owns FastAPI app bootstrap, middleware, CORS, tracing setup,
  health, auth token, debug, ops, and legacy compatibility endpoints.
- `app/api/routes/conversations.py` owns canonical conversation endpoints:
  create/list/get conversation and send learner messages.
- `app/api/routes/activities.py` owns canonical activity endpoints: read,
  submit, and review by `activity_id`.
- `app/api/routes/learners.py` owns canonical learner query/update endpoints:
  profile, mastery, progress, and recommendations.
- `app/api/routes/recommendations.py` owns recommendation list and accept
  routes.
- `app/api/dependencies.py` owns shared HTTP helpers: auth checks, payload
  builders, profile update normalization, debug snapshots, and compatibility
  headers. It reads `api_main.pipeline` dynamically so existing tests and dev
  overrides still work.
- `app/api/schemas.py` owns request/response Pydantic models only.

HTTP modules should translate request/response shapes and call services. They
should not own learning rules, grading, retrieval, or recommendation policy.

## Domain Services

- `app/conversation/router.py` owns intent routing and slot extraction.
- `app/conversation/service.py` owns turn orchestration and capability dispatch.
- `app/activities/` owns learning activity lifecycle. New activity work should
  use this plural package; do not add a parallel `app/activity/` package.
- `app/agent/learning_agent.py` owns the bounded practice generation/scoring
  pipeline for practice-like activities.
- `app/agent/workflow_graph.py` owns a static orchestration/debug graph. It is
  LangGraph-compatible for inspection and future experiments, but conversation
  routing does not depend on LangGraph at runtime.
- Guardrail: conversation routing does not depend on LangGraph at runtime.
- `app/learner/` owns the skill graph, BKT mastery updates, and review schedule.
- `app/personalization/` owns plan selection from learner state.
- `app/retrieval/` owns knowledge loading, embeddings, sparse/dense/hybrid
  retrieval, pgvector/Chroma adapters, and reranking.
- `app/generation/` owns exercise generation, fallback seed generation, and
  validation.
- `app/diagnosis/` owns answer-level error classification.
- `app/recommendation/` owns next-activity ranking and evidence.
- `app/review/` owns review explanations over submitted activities.
- `app/tutor/` owns natural-language tutor responses and grounded explanation
  fallbacks.
- `app/persistence/` owns repository interfaces and in-memory, SQLite, and
  PostgreSQL implementations.
- `app/observability/` owns metrics and OpenTelemetry setup.

Domain services should not import FastAPI route modules. Cross-module data
should pass through schemas/dataclasses and repository/service interfaces.

## Cleanup Rules

- Split route modules gradually when `app/api/main.py` grows again.
- Keep canonical platform vocabulary: conversation, activity, learner,
  recommendation.
- Keep `generation_run_id` as trace/debug/legacy compatibility identity, not the
  business identity for practice.
- Keep `LearningWorkflowGraph` as a debug/orchestration view unless a future
  phase explicitly converts runtime execution to LangGraph.
- Keep deployment in one FastAPI backend for this project phase; avoid
  microservice boundaries until there is a real operational need.
