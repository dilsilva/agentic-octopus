# agentic-octopus 🐙

The spine for my agentic applications: one orchestration service every agent plugs into —
shared triggering (API + schedules, later webhooks + chat), durable run state and audit,
human approval gates, and memory. Built on FastAPI, Postgres + pgvector, and the
Claude Agent SDK. Runs locally with docker compose; designed to deploy to GCP later
without redesign.

**Start here:** [`docs/rfcs/0001-agentic-octopus-the-spine.md`](docs/rfcs/0001-agentic-octopus-the-spine.md)
(vision + design) · [`CLAUDE.md`](CLAUDE.md) (working conventions) ·
[`docs/adr/`](docs/adr/) (decisions) · [`docs/worklog.md`](docs/worklog.md) (current state).

## Quick start

```bash
cp .env.example .env          # fill in ANTHROPIC_API_KEY
make dev                      # postgres + migrations + api + worker
curl localhost:8000/healthz
```

Development: `uv sync`, then `make lint`, `make test`.

## Layout

```
agents/          # agentic applications — one dir each (agent.yaml + prompt.md)
src/octo/        # the spine: api/, worker/, cli/, queue, executor, registry
db/migrations/   # numbered SQL migrations (schema_migrations tracked)
docs/            # worklog, ADRs, RFCs — the repo's memory
skills/          # portable Claude Code skills (usable in any repo)
```

## Skills template

`skills/` contains 13 project-agnostic Claude Code skills (ADRs, RFCs, MR shaping, preflight
safety gates, secrets scanning, worklog discipline, …) that travel to any project or machine:

```bash
cd skills && ./install.sh --user          # install to ~/.claude/skills
./install.sh --project /path/to/repo      # or per-project
```

See [`skills/README.md`](skills/README.md) for the catalog and per-project adaptation guide.
