# ADR-0008: Observability via OTEL behind a seam; tags dual-written to Postgres

- **Status:** accepted
- **Date:** 2026-07-19
- **Deciders:** Diego
- **Related:** ADR-0007, RFC-0001

## Context

Diego wants every model request (OpenRouter and Anthropic alike) tagged/labeled for
future data analysis, injected "through a library" for maintainability, with OTEL or
equivalent on the horizon. Options: hand-rolled tags only; OpenTelemetry now with a
generic viewer later; or standing up an LLM-native platform (Langfuse) immediately.

## Decision

We will route all request observability through one seam — `src/octo/telemetry.py`,
the only module that knows OpenTelemetry exists. Every model request gets:
1. a **tags dict** (auto-derived system facts: surface, provider, model, persona/agent,
   routed, trigger — merged with caller categories from API `tags` fields, CLI `--tag`,
   or the `X-Octo-Tags` header; manual wins) **persisted to Postgres** (`tags jsonb` +
   GIN indexes on messages / chat_completions / runs) so SQL analysis needs zero infra;
2. an **OTEL span** following the GenAI semantic conventions (`gen_ai.*` attributes,
   tags as `octo.tag.*`) — a no-op unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set.

Langfuse (self-hostable, ingests OTLP) is the intended viewer, deployed on treco in a
later phase; swapping or adding backends is a change to the seam file only.

## Options considered

### Option A — OTEL + DB tags behind a seam, Langfuse later  ← chosen
- Pros: standard data shape from day one; SQL analysis immediately; no service to
  operate before the data justifies it; LLM-native analytics available when wanted.
- Cons: two write paths (span + row) — mitigated: both fed from the same merged dict.

### Option B — Hand-rolled tags only
- Pros: least code. Cons: rebuilds tracing/correlation later; never OTEL-compatible
  without rework. Rejected.

### Option C — Langfuse from day one
- Pros: most capability today. Cons: another stateful service before any analysis
  exists; still needs the same seam. Rejected as premature — it's the natural P-later.

## Consequences

- Positive: `SELECT tags->>'model', count(*) FROM chat_completions GROUP BY 1` works
  today; the same data streams to any OTLP backend tomorrow; per-request categories
  (`--tag topic=x`) enable Diego's analysis workflows.
- Negative: streaming chat spans are not yet emitted (only tags persisted) — the span
  would outlive the generator awkwardly; acceptable v1 gap, revisit with Langfuse.
- Follow-ups: deploy Langfuse on treco + set OTLP endpoint; metrics (request counters)
  when a collector exists; propagate trace context into run_events.
