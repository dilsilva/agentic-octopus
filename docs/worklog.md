# Worklog — agentic-octopus

Cross-session log of actions and decisions, newest first. Facts live in topic docs/RFCs/ADRs;
this records what we did, decided, and parked. Conventions: skills/worklog.

## 2026-07-15

- **NEXT UP:** M1 walking skeleton, step 1 — queue/models/db + integration tests proving
  SKIP LOCKED claim semantics (sequencing in RFC-0001 rollout plan).
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
