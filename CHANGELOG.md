# Changelog

All notable changes to the spine. Format: newest first, one section per release/milestone;
each entry says what changed and why it matters to an operator. Maintained per
[`docs/RELEASING.md`](docs/RELEASING.md).

## [Unreleased]

- treco local lineup: `qwen3.5:9b` removed (impractical at ~1.5 tok/s beside the
  stack); `gemma3:4b` added — fast, non-thinking, multilingual (PT-BR verified).

## 0.7.0 — 2026-07-19 · Local models: octo/local-* via Ollama (ChatProvider #3)

- **`octo/local-<name>` virtual models** route to a per-host Ollama instance
  (OpenAI-compatible API): unlimited, private, offline, $0. Opt-in per host via the
  compose `local-llm` profile + `OLLAMA_BASE_URL` in `.env`; disabled hosts refuse
  with a clear message. Installed models auto-appear in `/v1/models` (Open WebUI
  picker) as e.g. `octo/local-qwen3.5-4b`.
- **Unified routing**: `route_chat_model()` now serves every surface — `octo/claude`
  and `octo/local-*` work in `octo chat` and raw HTTP too, not just the web UI.
- Deployed on treco with `qwen3.5:4b` (daily driver, ~5-8 tok/s) and `qwen3.5:9b`
  (quality tier, ~3-7 tok/s) per the sized shortlist.

## 0.6.0 — 2026-07-19 · Request tagging + telemetry seam (ADR-0008)

- **Every model request is tagged** for data analysis: auto-derived facts (surface,
  provider, model, persona/agent, routed, trigger) merged with your categories —
  API `tags` fields, CLI `--tag k=v`, or `X-Octo-Tags` header. Dual-written:
  Postgres `tags jsonb` (GIN-indexed on messages/chat_completions/runs — SQL analysis
  with zero infra) + OTEL spans (GenAI semantic conventions) via the
  `octo/telemetry.py` seam — a no-op until `OTEL_EXPORTER_OTLP_ENDPOINT` is set.
- Langfuse (OTLP-ingesting, self-hostable) is the planned viewer on treco.

## 0.5.0 — 2026-07-19 · Core web-search tool loop + routed-model transparency

- **Chat can research (every surface)**: personas with `tools: [web_search, fetch_page]`
  get a prompted tool protocol that works with ANY model the router picks (no native
  function-calling needed — that's what free models lack). The service detects
  `TOOL_CALL`, runs DuckDuckGo search / page fetch (free, keyless), records an audit
  row (`role='tool'` + metadata), feeds results back, and loops (bounded by
  `CHAT_MAX_TOOL_CALLS`, default 2 — each round costs one free-tier request).
  Streaming hides tool rounds behind `tool_status` events and streams the final,
  cited answer. Resolves ADR-0007's "search only in Open WebUI" exception.
- **Routed-model prefix**: answers served via `octo/auto` lead with
  `` `[actual-model]` `` on both surfaces (`CHAT_SHOW_ROUTED_MODEL` to disable) —
  smart routing is no longer opaque.
- `octo chat` shows live tool activity (`[web_search: {...}]`); `/chat/usage` counts
  tool rounds toward the daily free-tier burn.

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
