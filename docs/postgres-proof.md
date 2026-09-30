# PostgreSQL workflow proof

Run this proof against a disposable PostgreSQL 16 database using Python 3.12 and
the pinned backend requirements. The role needs permission to create schemas.
Each test migrates a randomly named schema and drops only that schema afterward.
All lock and migration cases run against PostgreSQL. The script fails when the database
URL is missing, invalid, or unreachable.

```sh
cd backend
python -m pip install -r requirements.txt
export TEST_DATABASE_URL=postgresql+asyncpg://procurement_test:procurement_test@localhost:5432/procurement_test
python scripts/prove_postgres.py
```

PowerShell uses `$env:TEST_DATABASE_URL = 'postgresql+asyncpg://...'` instead of
`export`. The script prints the server version before running the proof.

The tests verify duplicate decisions, simultaneous sibling approvals, competing
submit operations, and cancellation during approval. They hold a real parent row
lock and observe the competing backend's `pg_stat_activity` lock wait before
releasing it. The competing session has already loaded a pending ORM snapshot;
this catches locking implementations that fail to refresh cached state. Final
assertions use a separate session and inspect committed decisions, status, steps,
and audit counts.

The proof also injects a failure after routing has flushed real SQL and checks
that status, steps, and audit rows roll back together, then reuses the session for
a successful mutation. Other cases cover ownership, cross-organization approver
validation, money validation, HTTP GraphQL error codes, direct database constraints,
schema/model comparison, and downgrade/rebuild of the enum-backed schema.

## Mutation contract

Each GraphQL mutation field commits its own transaction. A failure rolls that
field back; an earlier successful field in the same operation remains committed.
The returned GraphQL types and Float amount fields remain compatible with the
existing frontend. Purchase amounts must be positive, finite, fit Numeric(12,2),
and contain at most two decimal places; invalid inputs are rejected before writes.

Request edits, submission, and cancellation require the requester or an admin in
the same organization. Decisions require the assigned approver/admin in the
request's organization and a pending request and step. Cancellation skips pending
steps. Policies require same-organization approvers/admins and supported rules.
Required request fields and policy rule values are trimmed before storage;
existing padded string rules also match after trimming.
Concurrent changes serialize on the parent request under PostgreSQL READ COMMITTED;
separate requests may proceed independently. Matching policies produce pending
steps ordered by priority; the request is approved when all steps approve.

Expected failures expose `errors[].extensions.code`: `UNAUTHENTICATED`,
`FORBIDDEN`, `NOT_FOUND`, `BAD_USER_INPUT`, or `CONFLICT`. GraphQL's own syntax/type
validation errors retain standard GraphQL behavior. Unexpected exceptions also roll back.

## Migrations

Schema creation is versioned: `0001` captures the original tables and PostgreSQL
enums; `0002` adds one decision per step, one step order per request, and finite
positive monetary bounds. Run `python -m alembic upgrade head` before starting
the app or running `python -m app.seed`. Startup and seed no longer call
`metadata.create_all`. Docker startup and setup/CI run migrations explicitly.

For an existing database created by the old `create_all` path, back it up and
verify that its schema matches revision `0001` before stamping that revision:
`python -m alembic stamp 0001`, then `python -m alembic upgrade head`. Both database
URLs must refer to the same database. Review duplicate step decisions/orders and
invalid historical amounts first. Revision `0002` intentionally fails on invalid
data and does not delete decisions or rewrite historical purchases.

The proof is generated test evidence on disposable data. It does not establish
production capacity, latency, or behavior under other transaction isolation levels.
