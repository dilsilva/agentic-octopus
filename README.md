# agentic-octopus 🐙

The **spine** for my agentic applications: one orchestration service every agent plugs
into — shared triggering (HTTP API + cron schedules), a durable Postgres-backed run queue,
human **approval gates**, a full audit trail, multi-surface **chat**, and smart model
routing across free LLMs. Built on FastAPI, Postgres + pgvector, and pluggable executors
(Claude Agent SDK, OpenRouter). Runs anywhere docker compose runs — laptop today, homelab
already, cloud later without redesign.

**Start here:**
[`docs/rfcs/0001-agentic-octopus-the-spine.md`](docs/rfcs/0001-agentic-octopus-the-spine.md) (vision + design) ·
[`CLAUDE.md`](CLAUDE.md) (working conventions) ·
[`docs/adr/`](docs/adr/) (decisions 0001–0007) ·
[`docs/worklog.md`](docs/worklog.md) (current state) ·
[`CHANGELOG.md`](CHANGELOG.md) (releases)

## What it does today

| Capability | Status |
|---|---|
| Declarative agents (`agents/<name>/agent.yaml` + `prompt.md`, zero core changes) | ✅ |
| Run queue (SKIP LOCKED claims, leases, crash recovery) + full audit trail | ✅ |
| Consent gates — a run parks until you `octo approve` (never auto-approved) | ✅ |
| Cron scheduler (DB-backed, exactly-once) — e.g. daily research brief | ✅ |
| Chat: terminal (`octo chat`), web (Open WebUI :3000), raw HTTP — one shared core | ✅ |
| Smart model router `octo/auto` — server-side failover across healthy **free** models | ✅ |
| Cost guard — non-free models refused unless explicitly opted in (`octo/claude`) | ✅ |
| Webhooks · Telegram approvals · GCP deploy · semantic memory | roadmap (RFC-0001) |

## Quick start

```bash
git clone <this repo> && cd agentic-octopus
cp .env.example .env          # fill OPENROUTER_API_KEY (free tier works)
uv sync
make dev                      # postgres + migrations + api :8000 + worker + open-webui :3000
```

Then:

```bash
uv run octo chat                       # chat in your terminal
open http://localhost:3000             # ChatGPT-style web UI (create local admin on first visit)
uv run octo run research-brief -f      # trigger an agent run and watch it
uv run octo runs                       # what happened
```

## API

Interactive documentation (Swagger UI) at **http://localhost:8000/docs** (ReDoc at
`/redoc`). The committed spec lives at [`docs/api/openapi.json`](docs/api/openapi.json)
— regenerate with `make openapi` after API changes.

- Native API: agents, runs, approvals, schedules, chat — bearer auth
  (`OCTO_API_TOKEN` admin; `OCTO_CHAT_TOKEN` chat-scoped for UIs).
- `/v1` is an **OpenAI-compatible protocol namespace**: point any OpenAI-protocol client
  (Open WebUI, SDKs) at `http://localhost:8000/v1` with the chat token.

## Layout

```
agents/          # agentic applications — one dir each (agent.yaml + prompt.md)
src/octo/        # the spine: api/, worker/, cli/, providers/, chat, queue, executor
db/migrations/   # numbered SQL migrations (append-only)
docs/            # worklog, ADRs, RFCs, api spec — the repo's memory
skills/          # portable Claude Code skills (usable in any repo — see skills/README.md)
data/            # gitignored outputs (briefs, chat workdirs)
```

## Operating notes

- `make` targets: `dev down logs psql db-migrate lint fmt test test-integration smoke backup openapi`
- Deploying elsewhere: clone, copy `.env` over SSH (never via git), optional
  `docker-compose.override.yml` for port remaps, `docker compose up -d --build`.
- Documentation contract: every significant change updates README/docs/OpenAPI/CHANGELOG
  before it ships — see [`docs/RELEASING.md`](docs/RELEASING.md).

## Philosophy

Features are core-first: every capability exists behind the API independent of any UI —
CLI, web, and future surfaces are thin clients. Safety is structural: consent gates are
schema, not convention; the cost guard is code, not discipline; live state outranks git;
everything an agent does is in the audit trail.
