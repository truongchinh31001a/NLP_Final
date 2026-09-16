# Knowledge Repository V1

Knowledge Repository V1 is a read-only persistence abstraction over the
persisted Knowledge Core tables. It does not perform adaptive sequencing,
mastery estimation, exercise generation, or LLM calls.

Usage:

```python
from knowledge_core.repository import open_knowledge_repositories

with open_knowledge_repositories() as repos:
    skill = repos.nodes.get_by_canonical_id("grammar.present_simple.affirmative")
    snapshot = repos.queries.get_skill_snapshot(skill.canonical_id)
```

## Version Handling

Every version-scoped query accepts `version=None`, a version name, a version id,
or a `KnowledgeVersionReadModel`. `None` resolves to the single active version.
If no active version exists, `KnowledgeVersionNotFoundError` is raised. If more
than one active version exists, `KnowledgeIntegrityError` is raised.

## Query Strategy

Repositories receive one SQLite connection through `KnowledgeRepositorySession`,
so callers can keep read consistency across a group of queries. List operations
return `[]` for no rows; get operations raise `KnowledgeNotFoundError`.

Taxonomy ancestor/descendant queries use recursive CTEs supported by SQLite and
straightforward to port to PostgreSQL. Transitive prerequisite/unlock traversal
is implemented in repository code using repeated indexed direct-edge lookups;
this keeps behavior deterministic across SQLite and PostgreSQL syntax variants.
The V1 graph is small, so the performance tradeoff is acceptable for this
milestone.

## PostgreSQL Status

The read models and repository interfaces are database-neutral. The concrete V1
implementation is tested against the local SQLite backend. PostgreSQL-compatible
DDL exists in `app/persistence/knowledge_core_postgresql.sql`, but a live
PostgreSQL repository adapter has not been executed in this milestone.
