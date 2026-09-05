# generation_run_id Audit

Date: 2026-09-05

Goal: keep `generation_run_id` as a generation snapshot / trace identity, while
using `activity_id` as the primary business identity for learner-facing practice
activities.

## Decision

- Canonical practice identity: `activity_id`
- Generation snapshot identity: `generation_run_id`
- Practice result/report identity: `session_code`
- Legacy compatibility input: `generation_run_id` is still accepted by
  `/api/practice/score`

## Current Accepted Uses

| Area | Use | Classification |
|---|---|---|
| `GeneratedExerciseSet.generation_run_id` | Identifies generated exercise snapshot | Trace/snapshot identity |
| `LearningActivity.generation_run_id` | Link from activity to generated snapshot | Internal reference |
| Repository `get_generated_exercise_set()` | Load snapshot by generation id | Internal reference |
| Practice scoring internals | Grade against the generated snapshot | Internal reference |
| API `GeneratePracticeResponseModel.generation_run_id` | Legacy/debug response field | Compatibility |
| API `ScorePracticeRequestModel.generation_run_id` | Legacy `/api/practice/score` input | Compatibility |
| Assistant/activity metadata | Expose trace id for debugging | Observability |
| Tests | Assert compatibility and snapshot linkage | Test coverage |

## Uses To Avoid

- Do not submit new frontend practice results with `generation_run_id`.
- Do not use `generation_run_id` to identify active UI practice state.
- Do not use `generation_run_id` to accept recommendations.
- Do not use `generation_run_id` as the primary route/review identity.

## Current Canonical Paths

```text
Conversation turn:
POST /api/conversations/{conversation_id}/messages
  -> returns activity.activity_id for practice turns

Practice submission:
POST /api/activities/{activity_id}/submit

Recommendation continuation:
POST /api/recommendations/{recommendation_id}/accept
```

## Remaining Compatibility Path

```text
POST /api/practice/score
  input: generation_run_id
  behavior: resolve linked activity_id if possible, then submit canonical
```

This path can remain until all external clients have migrated.
