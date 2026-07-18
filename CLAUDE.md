# agentic-octopus

The spine for all of Diego's agentic applications: one orchestration service (FastAPI + Postgres
queue + workers running the Claude Agent SDK) that every agent plugs into as a declarative
directory under `agents/`. Vision and full design: `docs/rfcs/0001-agentic-octopus-the-spine.md`.

## Architecture (6 lines)

```
trigger (API / schedule / later: webhook, chat)
  → runs row inserted (status=queued; the run row IS the queue item)
  → worker claims via FOR UPDATE SKIP LOCKED (lease + heartbeat; reaper requeues crashes)
  → executor runs the agent (AgentExecutor protocol; primary: Claude Agent SDK session with
    tools from agent.yaml allowlist + setting_sources=[]; provider-pluggable — ADR-0002)
  → events/result/cost_usd/session_id persisted (run_events = audit trail)
  → gates: requires_approval parks run in awaiting_approval until human approves (CLI/API)
```

Services (docker-compose.yml): `postgres` (pgvector), `migrate` (one-shot), `api` (:8000), `worker`.

## Conventions (wired to the skills)

- Worklog: `docs/worklog.md` (/worklog, /resume). ADRs: `docs/adr/`. RFCs: `docs/rfcs/`
  (owner-decided mode — Decider: Diego).
- Tracker: GitLab issues on `behold-corp/agentic-octopus` via `glab`. Git host: GitLab.
- Branch/commit style: `feat|fix|chore|docs|ci: imperative summary`; direct commits to `main`
  allowed while solo (protected: Maintainers) — MRs for anything worth reviewing.
- Environment chain: `local → gcp` (gcp doesn't exist yet — P4).

## Consent gate (/preflight applies)

Explicit in-the-moment consent from Diego before: any GCP mutation, enabling any schedule or
merging anything that triggers external side effects, giving an agent side-effectful tools
(email send, infra mutation, spending), and any deploy stage in CI. **Agents never approve
approvals — gates are decided by Diego only.**

## Run / test

- `make dev` (compose up), `make logs`, `make down`, `make psql`, `make db-migrate`, `make backup`
- Chat: `uv run octo chat` (terminal) or Open WebUI at `localhost:3000` (web, uses the
  scoped `OCTO_CHAT_TOKEN` — valid only on `/chat/*` + `/v1/*`, never for runs/approvals)
- `make lint` / `make fmt` / `make test` (unit) / `make test-integration` / `make smoke`
- CLI: `uv run octo health`, `uv run octo db upgrade` (M1 adds run/approve/logs/schedule)
- Local setup: `cp .env.example .env` (fill `ANTHROPIC_API_KEY`), `uv sync`.

## Hard rules

- Never commit `.env` or any credential — run /secrets-check before every commit/MR.
- New agent = new `agents/<name>/` dir (agent.yaml + prompt.md), zero core changes (ADR-0006).
- Tests never call the real SDK — use `FakeExecutor` (the SDK sits behind the `AgentExecutor`
  Protocol in `src/octo/executor.py`, M1).
- Migrations are append-only numbered files in `db/migrations/`; never edit an applied one.
- Update `docs/worklog.md` after significant work; corrections are new entries, never edits.
- **Wrap-up = documentation:** every significant change runs the checklist in
  `docs/RELEASING.md` before the final commit (CHANGELOG, `make openapi` if the API
  changed, README/CLAUDE.md currency, ADR/RFC when decisions changed).

## Glossary

**agent** declarative definition (yaml+prompt) · **run** one execution = one queue item ·
**gate** pending approval parking a run · **schedule** cron row enqueueing runs ·
**brief** research-brief output in `data/briefs/` · **spine** this service ·
**persona** agent dir used as a chat system prompt · **chat shim** `/v1` OpenAI-compat
surface for protocol clients (Open WebUI) — a protocol namespace, not an API version.
