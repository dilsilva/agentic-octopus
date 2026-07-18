# Releasing & documentation contract

Standing rule (Diego, 2026-07-18): **no significant change ships with stale docs.**
"Significant" = new capability, changed API surface, changed operational procedure,
or a decision worth remembering. Typo-level fixes are exempt.

## The wrap-up checklist

Run this at the end of every significant piece of work, before the final commit/push:

1. **CHANGELOG.md** — add/extend the entry (what changed + why an operator cares).
   Bump the version section when the change is a coherent release; otherwise it
   accumulates under `[Unreleased]`.
2. **OpenAPI** — if any route/schema/auth changed: `make openapi` and commit the
   regenerated `docs/api/openapi.json`. Sanity-check `http://localhost:8000/docs`.
3. **README.md** — capability table, quick start, and layout still true?
4. **CLAUDE.md** — conventions/architecture/glossary still true? (Keep it lean —
   it loads every session.)
5. **docs/worklog.md** — entry per /worklog conventions (always, this one is not
   optional even for small changes).
6. **ADR/RFC** — if a decision was made or reversed: new ADR (or amend a `proposed`
   one); update the RFC's rollout/phase status.
7. **Version** — `pyproject.toml` version bump when cutting a CHANGELOG release
   section (keep them in sync).

## Who runs it

Whoever wraps the work — human or agent. For Claude Code sessions this checklist is
wired into CLAUDE.md's hard rules; "wrap up" / "ship it" implies running it.

## Release flow (when a milestone lands)

1. Checklist above, with a fresh CHANGELOG version section (semver-ish: minor per
   milestone, patch for fixes).
2. `uv run pytest tests/unit tests/integration -q` + `make lint` green.
3. /secrets-check on the diff.
4. Commit `feat|fix|docs: ...`, push, CI green.
5. Deployed hosts (e.g. treco): `git pull && docker compose up -d --build`, then
   `make smoke` there.
