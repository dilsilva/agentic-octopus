# ADR-0003: Postgres + pgvector is the only backing store

- **Status:** proposed
- **Date:** 2026-07-15
- **Deciders:** Diego
- **Related:** RFC-0001, ADR-0004

## Context

The spine needs a job queue, run history/audit, schedules, approvals, and (later) semantic
memory. Conventional stacks add Redis (queue) and sometimes a vector DB (memory) — three
stateful services for a system whose throughput is a handful of runs per hour, operated solo.

## Decision

We will use one Postgres (with the pgvector extension) for everything: queue via
`FOR UPDATE SKIP LOCKED`, run history, schedules, approvals, and memories with a vector column.
Raw SQL via psycopg3 and numbered .sql migrations — no ORM, no Alembic.

## Options considered

### Option A — Postgres + pgvector only  ← chosen
- Pros: one service to run/back up locally and on Cloud SQL; transactional queue+state (claim
  and status change are one commit); vectors included.
- Cons: not a "real" broker; polling instead of push. At our scale, irrelevant.

### Option B — Redis + Postgres (+ arq/celery)
- Pros: conventional, snappier dequeue. Cons: second stateful service everywhere, no
  transactional queue+state. Rejected.

### Option C — GCP-native (Pub/Sub + Firestore)
- Pros: serverless. Cons: local dev needs emulators; couples the hybrid story to GCP. Rejected.

## Consequences

- Positive: `docker compose up` = whole stack; audit + queue share transactions; semantic
  memory needs no new infra.
- Negative: single point of failure (accepted; backups); if throughput ever explodes, a broker
  migration is real work (accepted risk — evidence says it won't).
- Follow-ups: HNSW index only when semantic recall lands; Alembic only if SQL migrations hurt.
