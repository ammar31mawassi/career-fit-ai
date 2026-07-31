# PostgreSQL tenant-security regression harness

This harness executes the canonical fresh-install schema and the v18-to-v22
upgrade path against an isolated stock PostgreSQL 16 container. It never reads
the repository's `DATABASE_URL` and does not expose a database port.

Prerequisites:

- Docker Engine is running.
- `postgres:16-alpine` is available locally (`docker pull postgres:16-alpine`).
- Python 3.12+ is available.

Run from the repository root:

```powershell
backend\.venv\Scripts\python.exe supabase\tests\run_postgres_security_tests.py
```

The Supabase-owned auth, storage, and pgmq objects are represented by minimal
test doubles. Application tables, foreign keys, RLS policies, grants, the
canonical schema, forward security migrations, structured-payload checks, and
workflow-state constraints execute in real
PostgreSQL. A future Supabase CLI CI job should additionally run
`supabase db reset` to cover extension packaging and platform-owned policies.
