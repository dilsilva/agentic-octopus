# ADR-0001: Build the spine as a single orchestration service

- **Status:** accepted
- **Date:** 2026-07-15
- **Deciders:** Diego
- **Related:** RFC-0001

## Context

Every future agentic application needs triggering, run state, consent gates, observability, and
memory. Candidate shapes: per-app scripts, an off-the-shelf workflow engine (Temporal/Prefect/
n8n), a Claude-Code-native control plane (pure config, no runtime), or one owned service.
The owner is a solo operator who wants to learn the mechanics, not operate a platform.

## Decision

We will build one orchestration service — FastAPI gateway + Postgres-backed queue + workers —
that all agentic applications plug into as declarative definitions.

## Options considered

### Option A — Single owned orchestration service  ← chosen
- Pros: plumbing solved once; consent/audit enforced by construction; full learning value;
  every piece justifiable and replaceable.
- Cons: we own the code; more upfront work than scripts or pure config.

### Option B — Per-app scripts + cron
- Pros: fastest first result. Cons: state/consent/observability re-solved per app; collapses
  by app five. Rejected: the shared spine is the whole point.

### Option C — Workflow engine (Temporal/Prefect) or n8n
- Pros: durable execution solved by others. Cons: heavy infra and concept load at solo scale;
  consent gating still custom; core logic outside git (n8n). Rejected for now.

## Consequences

- Positive: agent #2..#N are two files each; one audit trail; one place to harden.
- Negative: we maintain a service; SDK/runtime bugs are ours to debug.
- Follow-ups: RFC-0001 rollout M1 (walking skeleton); revisit Option C only if true multi-step
  DAG orchestration becomes a real need.
