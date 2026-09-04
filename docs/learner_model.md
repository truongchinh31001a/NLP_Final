# Learner Model

The adaptive core tracks mastery at skill level, not only at topic level.

## Skill Identity

Each generated or seed exercise carries:

- `topic`, for example `tenses` or `passive_voice`.
- `skill`, for example `grammar` or `vocabulary`.
- `subtopic`, for example `past_simple_finished_time`.
- `error_tag`, for example `wrong_tense`.

The skill graph maps this metadata to a stable skill id:

```text
grammar.tenses.past_simple_finished_time
grammar.passive_voice.present_simple_passive
vocabulary.vocabulary.collocations
```

Default taxonomy lives in `app/learner/skill_graph.py`. Unknown subtopics are
accepted as auto-discovered skills so LLM-generated metadata can still be stored.

## Bayesian Knowledge Tracing

Every submitted answer becomes a binary observation for one skill:

```text
prior mastery -> correct/incorrect observation -> posterior mastery
```

The BKT implementation is in `app/learner/knowledge_tracing.py`. The SQLite
repository stores:

- Current mastery in `user_skill_mastery`.
- Observation history in `user_skill_mastery_history`.
- Error frequencies and recent difficulty history for each skill.
- `next_review_at` for spaced review.

## Structured Error Diagnosis

Before the mastery update is saved, each answer is converted into an
`AnswerDiagnosis`:

```text
exercise + selected answer
  -> correctness
  -> error_type
  -> skill_id
  -> subtype
  -> severity
  -> mastery_impact
```

The current diagnosis service is deterministic and metadata-aware. It uses the
exercise `error_tag`, `topic`, `skill`, and `subtopic` to classify mistakes such
as `verb_tense`, `auxiliary`, `voice`, `agreement`, or `vocabulary_meaning`.

SQLite stores answer-level diagnosis records in `answer_diagnoses`, linked to
the original user answer and session exercise. These records make review
feedback more specific and give the adaptive engine a cleaner signal than only
session-level score.

## Recommendation

The recommendation service ranks the next practice target using:

- Skills missed in the latest submitted exercise set.
- Structured diagnosis from the latest answers.
- Existing mastery probability.
- Prerequisite readiness from the skill graph.
- Session score as a fallback signal.

This keeps the learner close to the actual weak skill instead of switching topic
based only on one session-level percentage.
