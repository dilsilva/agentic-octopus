# Changelog

All notable changes to the spine. Format: newest first, one section per release/milestone;
each entry says what changed and why it matters to an operator. Maintained per
[`docs/RELEASING.md`](docs/RELEASING.md).

## [Unreleased]

## 0.4.0 — 2026-07-18 · Smart routing, octo/claude, first remote deployment

- **`octo/auto` smart router**: virtual model that expands to OpenRouter's native
  `models` fallback array (max 3 — API limit) of probed healthy `:free` models;
  server-side failover in a single request, so congested/dead free models no longer
  break chat. Default model everywhere.
- **`octo/claude` virtual model**: Anthropic Messages API provider behind the
  `ChatProvider` protocol. Listed only when a real `ANTHROPIC_API_KEY` is configured —
  selecting it is the explicit paid opt-in; everything else stays under the `:free` guard.
- **Streaming robustness**: upstream provider errors mid-stream now surface as readable
  SSE error events instead of severed connections; `/v1` strips tool fields (plain-
  completions contract) so tool-injecting clients (Open WebUI) work with any model.
- **First remote deployment**: full stack on `treco` (ARM64 homelab) over Tailscale.
- **OpenAPI documentation**: tagged/described spec with working auth in Swagger UI
  (`/docs`); committed spec at `docs/api/openapi.json`; `make openapi`.

## 0.3.0 — 2026-07-17 · Chat as a spine capability (ADR-0007)

- Spine-owned conversations/messages in Postgres; three thin clients: `octo chat`
  (terminal REPL), Open WebUI (pinned container, `:3000`), raw HTTP.
- `ChatProvider` protocol (providers are pluggable); token-budget sliding context
  window; human-readable free-tier quota errors; truncated-on-disconnect persistence.
- Scoped `OCTO_CHAT_TOKEN`: chat UIs can converse but never drive agents/approvals.
- Personas are declarative agent dirs (`agents/chat-assistant/`).

## 0.2.0 — 2026-07-17 · OpenRouter executor + cost guard (P2.5)

- Second executor: OpenRouter free-tier models run agents at $0 (no Anthropic key
  needed); `research-brief` produced its first real briefs.
- Hard cost guard: non-`:free` models refused unless `OPENROUTER_ALLOW_PAID` is set.

## 0.1.0 — 2026-07-16 · M1 walking skeleton

- Postgres run queue (`FOR UPDATE SKIP LOCKED`, leases, reaper), guarded run state
  machine, append-only `run_events` audit.
- Consent gates as durable data (ADR-0005): `awaiting_approval` + approve/reject via
  API/CLI with decided_via/note audit.
- DB-backed cron scheduler (exactly-once under concurrent workers), declarative agent
  registry (ADR-0006), `AgentExecutor` protocol with Claude SDK + Fake executors,
  full API with bearer auth, `octo` CLI.

## 0.0.1 — 2026-07-15 · Foundation (M0)

- Vision RFC-0001; founding ADRs 0001–0006 (service shape, Python+SDK, Postgres+pgvector
  only, hybrid containers, approval gates, declarative agents).
- Runnable scaffold: compose stack (pgvector, migrations, api, worker), CI (lint+test,
  no deploys), portable Claude Code skills under `skills/`.
