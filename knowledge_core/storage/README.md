# Knowledge Core Storage V1

Knowledge Core Storage V1 persists the validated JSONL/Parquet artifacts into the
existing application persistence path instead of keeping Knowledge Core as
artifact-only data.

Local commands:

```powershell
python -m knowledge_core.storage.cli init
python -m knowledge_core.storage.cli load --twice
python -m knowledge_core.storage.cli validate
python -m knowledge_core.storage.cli inspect
```

The default database path comes from `AppConfig.sqlite_db_path`, normally
`data/sqlite/app.db`.

## Schema

The executable local schema is extended in `app/persistence/schema.sql` and adds
17 Knowledge Core tables plus 3 read views:

- `v_atomic_skills`
- `v_skill_prerequisites`
- `v_skill_assessment_summary`

The loader is idempotent for a named knowledge version. It upserts stable source
metadata/source records, clears version-scoped rows, reloads them in one
transaction, then activates the version. If any insert fails, the transaction is
rolled back and the previous active version remains intact.

## PostgreSQL Status

SQLite is the backend exercised by the current local tests. The logical
PostgreSQL port for the Knowledge Core tables and views is documented in
`app/persistence/knowledge_core_postgresql.sql` with PostgreSQL-native `JSONB`,
`BIGSERIAL`, `TIMESTAMPTZ`, and boolean columns.

Live PostgreSQL migration execution is not yet tested in this milestone because
the existing PostgreSQL repository uses an inline app-specific schema runner, not
the SQLite `schema.sql` migration source.
