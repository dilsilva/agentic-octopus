# Worklog — agentic-octopus

Cross-session log of actions and decisions, newest first. Facts live in topic docs/RFCs/ADRs;
this records what we did, decided, and parked. Conventions: skills/worklog.

## 2026-07-18

- **Docs overhaul + documentation contract (v0.4.0):** README rewritten to current
  reality (capability table, chat surfaces, API section); `CHANGELOG.md` created and
  back-filled 0.0.1→0.4.0; **HARD RULE** established in `docs/RELEASING.md` + CLAUDE.md —
  every significant change runs the wrap-up checklist (CHANGELOG, `make openapi` when the
  API changes, README/CLAUDE.md currency, ADR/RFC, worklog) before the final commit.
  OpenAPI made first-class: tagged + described routes, HTTPBearer security scheme
  (Authorize button works in `/docs`), rich API description, committed spec at
  `docs/api/openapi.json` via `make openapi`. Version synced to 0.4.0.
- **Repo mirrored to GitHub:** private `github.com/dilsilva/agentic-octopus` added as
  `github` remote beside GitLab `origin`; push both on wrap-up.
- **🎉 Spine deployed on treco (homelab, ARM64 RK3588 / Ubuntu 20.04):** clone at
  `~/apps/agentic-octopus` via read-only GitLab deploy key (id 21224058, key on
  treco `~/.ssh/id_ed25519`); `.env` copied over SSH (never via git). Open WebUI
  remapped to **:3002** through an untracked `docker-compose.override.yml`
  (3000 is homepage on that box; 3001 uptime-kuma). Full stack verified: healthz
  OK, migrations applied, `octo/auto` live chat served by nemotron at $0, Open
  WebUI answering 200 over Tailscale (`http://treco.leopard-barley.ts.net:3002`
  — first visit creates the admin account). To update treco: `cd
  ~/apps/agentic-octopus && git pull && docker compose up -d --build`.
- **octo/claude virtual model shipped (commits fc90dbb, 6506150 → main):**
  `AnthropicChatProvider` (src/octo/providers/claude.py) speaks the ChatProvider
  protocol but calls the Anthropic Messages API via the official SDK — system
  folding, sampling params stripped (Opus 4.8 rejects them), adaptive thinking,
  refusal→content_filter, synthesized OpenAI SSE. New `route_chat_model()` seam
  in providers/base.py does per-model routing + billing policy: octo/claude
  requires a real `ANTHROPIC_API_KEY` (`.env.example` placeholder detected and
  ignored) — selecting it IS the paid opt-in; other models stay on the :free
  guard. Appears in /v1/models (Open WebUI picker) only when the key is set;
  default model `claude-opus-4-8` via `ANTHROPIC_DEFAULT_MODEL`
  (claude-haiku-4-5 = budget option). 63/63 unit tests.
- **Smart router fixed + verified live — OpenRouter caps the `models` fallback array
  at 3:** `octo/auto` was sending all 5 preferred candidates and every request 400'd
  (`'models' array must have 3 items or fewer`) before any model was tried. Root cause
  found by probing the API directly; `router_candidates()` now capped at
  `MAX_FALLBACK_MODELS = 3` (extras in `OPENROUTER_PREFERRED_MODELS` stay as warm
  spares to promote). Verified end-to-end through the `/v1` shim, stream and
  non-stream, served by `nvidia/nemotron-3-super-120b-a12b:free` at $0 — server-side
  failover confirmed working (an earlier probe was served by `gemma-4-26b` when
  nemotron was congested, same single request). Cap regression test added (52/52
  unit); api + worker containers rebuilt with the fix.
- **Fix — streaming errors no longer kill the connection:** Open WebUI showed
  `TransferEncodingError` when a model errored mid-stream (root cause: OpenRouter 404/429
  for models with no live endpoint raised inside the SSE generator AFTER HTTP 200 was
  committed). Providers now raise typed `ProviderError`; both SSE surfaces catch all
  exceptions and emit a readable `data: {"error": ...}` + `[DONE]` instead of dying;
  native non-stream maps provider errors to 502. Regression test added (68/68). Note:
  some `:free` models (e.g. dolphin-venice) are flaky/demand-throttled on OpenRouter —
  pick stable ones (nemotron default works) when a model errors.

## 2026-07-17

- **NEXT UP:** fast-follows from ADR-0007 — core web-search tool loop for chat (removes
  the Open WebUI capability exception), rolling summarization — or P2 (webhooks +
  mid-run gates). Still pending: $10 OpenRouter top-up consideration, OpenRouter key
  rotation (pasted into a chat session).
- **Chat capability shipped (ADR-0007, plan reviewed by independent agent — 11 findings
  incorporated):** conversations/messages spine-owned (migration 0002: CASCADE, tool
  role + metadata reserved for tool loop, summary reserved for summarization);
  `ChatProvider` protocol + OpenRouter provider #1 (executor refactored onto it, tests
  unchanged); chat service with token-budget sliding window, human-readable 429 quota
  mapping, streaming with truncated-on-disconnect persistence; native `/chat` API (one
  SSE dialect = OpenAI chunks); `/v1` shim for protocol clients (metadata-only logging);
  scoped `OCTO_CHAT_TOKEN` (chat surfaces only — Open WebUI never holds admin); personas
  as agent dirs (`agents/chat-assistant/`); `octo chat` REPL/list/show/usage; Open WebUI
  v0.10.2 pinned in compose with title/tag/follow-up generation disabled (free-tier quota
  protection) + api healthcheck gating its startup; `make backup`. 67/67 tests.
- **Memory saved:** Diego's core-first principle (features UI-independent, UIs thin
  clients) → `features-core-first` in session memory.
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
