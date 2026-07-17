# Worklog — agentic-octopus

Cross-session log of actions and decisions, newest first. Facts live in topic docs/RFCs/ADRs;
this records what we did, decided, and parked. Conventions: skills/worklog.

## 2026-07-17

- **NEXT UP:** P2 per RFC-0001 (webhooks + mid-run gates) or first additional agent —
  Diego to pick. Also consider: $10 OpenRouter top-up (unlocks 1000 req/day + `:online`
  search-grounded models for a fresher brief), and rotating the OpenRouter key (it was
  pasted into a chat session).
- **🎉 FIRST SUCCESSFUL AGENT RUN through the spine:** `research-brief` via OpenRouter free
  tier — run 1abe64f7 `completed` in 16s, cost $0.00, model
  `nvidia/nemotron-3-super-120b-a12b:free`, output `data/briefs/research-brief-2026-07-17.md`.
  Brief correctly self-labels knowledge-cutoff limits (no web tools in executor v1).
- **P2.5 OpenRouterExecutor shipped (pulled forward — Diego has no Anthropic key):**
  one-shot chat completion, executor writes the output file, `:free` models → cost 0.0;
  registry accepts `executor: openrouter`; default model via `OPENROUTER_DEFAULT_MODEL`
  (currently nemotron-3-super). `research-brief` manifest switched claude-sdk → openrouter.
  5 new unit tests (respx-mocked; success/default-model/429/embedded-error/missing-key).
  🔒 `OPENROUTER_API_KEY` lives in `.env` only (gitignored, verified).

## 2026-07-16

- **M1 walking skeleton complete:** queue (SKIP LOCKED claim/lease/reaper), run state machine
  with guarded transitions, agent registry, `AgentExecutor` protocol (ClaudeSDK + Fake), full
  API (runs/approve/reject/schedules + bearer auth), worker loop with pre-execution gates,
  DB scheduler (exactly-once tick), `octo` CLI. 39/39 tests (16 integration on real pgvector).
  **Live evidence:** run pipeline verified via CLI (queued→running→failed on placeholder API
  key, cause captured in run_events); consent gate verified live both ways (reject → rejected
  without execution; approve → requeued → executed, note + decided_via audited). Schedule
  synced from manifest, next fire 2026-07-17 07:00 UTC. Real SDK success blocked only on a
  real `ANTHROPIC_API_KEY` in `.env` (placeholder present).
- **Bug caught by integration tests:** psycopg pooled connections had `row_factory` mutated
  connection-wide, leaking dict rows into tuple-indexing code — fixed by scoping row_factory
  to cursors. The kind of bug that would have surfaced as a flaky worker.
- **ADRs 0001–0006 accepted by Diego; 0002/0006 amended:** the spine is NOT Claude-only —
  execution sits behind the `AgentExecutor` protocol, manifests carry `executor`/`model`,
  OpenRouter-style executor planned as P2.5 (why: model freedom / dynamic provider choice).
  RFC-0001 flipped to decided.
- **M0 CI green:** pipeline #1 (lint+unit) succeeded on gitlab.com.

## 2026-07-15

- **M0 foundation committed:** repo repurposed as the spine for all agentic applications.
  RFC-0001 drafted (vision + full M1 technical design); ADRs 0001–0006 `proposed` (service
  shape, Python+SDK, Postgres+pgvector single store, hybrid runtime, approval gates,
  declarative agents) — Diego to flip to `accepted`. Scaffold: pyproject (uv), Dockerfile,
  compose (postgres+migrate+api+worker stub), schema `db/migrations/0001_init.sql`, healthz
  API, `octo` CLI stub, unit tests, `.gitlab-ci.yml` (lint+unit; integration job armed for M1;
  no deploys). Exemplar agent `agents/research-brief/` (not executable until M1).
- **Decision — repo scope:** agentic-octopus = spine + portable skills templates (`skills/`
  stays, installable via `skills/install.sh`); why: one repo to clone on any new machine.
- **Skills migrated:** `~/.claude/skills` now runs the generic templates from this repo
  (7bridges-specific versions removed; `refresh-estate` superseded by `refresh-data`).
