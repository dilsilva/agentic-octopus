# ADR-0005: Approval gates are a durable run-state primitive

- **Status:** accepted
- **Date:** 2026-07-15
- **Deciders:** Diego
- **Related:** RFC-0001, skills/preflight (the philosophy being encoded)

## Context

The operator's standing discipline (/preflight skill) requires explicit, in-the-moment human
consent before side-effectful actions. Agents will eventually send emails, mutate infra, spend
money. Consent must survive process restarts and work from any frontend (CLI today, chat
buttons later) — it cannot be "the process blocks waiting for input".

## Decision

We will model consent as data: an `approvals` table plus the `awaiting_approval` run state.
A parked run resumes when its approval row is approved (re-queued; mid-run gates resume the SDK
session via its stored `session_id`). Approving happens through the API (`POST /runs/{id}/approve`)
or CLI; future chat buttons call the same endpoint.

## Options considered

### Option A — Durable state + approvals table  ← chosen
- Pros: survives restarts; auditable (who/when/via/note); frontend-agnostic; two tiers
  (pre-execution now, mid-run via SDK session resume later) on the same rows.
- Cons: slightly more machinery than blocking.

### Option B — Process blocks awaiting input
- Pros: trivial. Cons: dies with the process; ties up a worker; no audit. Rejected.

### Option C — No gates until needed
- Pros: nothing to build now. Cons: gates are core safety philosophy; bolting them on under
  pressure produces Option B. Rejected.

## Consequences

- Positive: safety gate is enforced by the schema, not by convention; full consent audit trail.
- Negative: gated runs add a queue round-trip (accepted — consent latency is human anyway).
- Follow-ups: M1 implements pre-execution gates; P2 adds mid-run `request_approval` tool +
  session resume. Hard rule (CLAUDE.md): no agent may approve an approval.
