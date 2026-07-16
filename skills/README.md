# Skill templates

Portable, project-agnostic Claude Code skills for platform/infra work. Genericized from a
real engagement so they carry the working discipline (safety gates, evidence rules, doc
conventions) without any client-specific details.

## The set

| Skill | Purpose |
|---|---|
| `adr` | Architecture Decision Records — template, numbering, immutability rules |
| `agentic-scan` | Assess a component through the agentic lens (actuation/senses/trust/context) |
| `git-recon` | Branch freshness + repo flow detection before touching any repo |
| `mr` | MR/PR conventions — scope, title, description template, evidence |
| `postmortem` | Blameless incident write-ups with mandatory detection-gap section |
| `preflight` | Safety checklist before any write to live systems; prod consent gate |
| `refresh-data` | Refresh the project's data layer and reconcile docs (frame — customize per project) |
| `release` | Promotion through the environment chain with per-stage verification |
| `resume` | Restore working context from the worklog at session start |
| `rfc` | Design proposals for feedback before work starts; owner-decided mode |
| `secrets-check` | Scan diffs/repos for committed secrets; safe handling order |
| `ticket` | Work items with binary acceptance criteria; draft-first rule |
| `worklog` | Cross-session actions/decisions log + session handoffs |

They interlock: `/mr` invokes `/git-recon` and `/secrets-check`; `/preflight` gates anything
`/release` or `/mr` arms; everything significant lands in `/worklog`, which `/resume` reads back.

## Install

```bash
# user-level (all projects on this machine):
./install.sh --user

# project-level (one repo; commits with the project):
./install.sh --project /path/to/repo

# a subset:
./install.sh --user adr rfc worklog
```

User-level installs to `~/.claude/skills/`; project-level to `<repo>/.claude/skills/`.
Existing skills are never overwritten unless you pass `--force`.

## Adapting to a new project

Each skill ends with a **Project adaptation** section listing exactly what to customize.
On first use in a new project, walk through:

1. **Paths** — worklog (`docs/worklog.md`), ADRs (`docs/adr/`), RFCs (`docs/rfcs/`),
   postmortems (`docs/postmortems/`). Keep the defaults unless the project has conventions.
2. **Git host** — skills auto-detect GitLab (`glab`) vs GitHub (`gh`) from the remote.
3. **Tracker** — fill in `/ticket`'s destination (Jira/GitLab issues/GitHub issues/Linear),
   project key, and auth mechanism.
4. **Environment chain** — map `dev → staging → prod` in `/preflight` and `/release` to the
   project's real environment names; decide where the consent gate sits.
5. **Data layer** — `/refresh-data` is a frame; list the project's actual data artifacts and
   refresh commands, or skip installing it if the project has none.
6. **Canonical doc homes** — if the team reads RFCs/ADRs in a wiki (Notion/Confluence), note
   the publish-there-mirror-here convention in `/rfc` and `/adr`.

Record the choices in the project's `CLAUDE.md` so every session picks them up.

## Hard rules baked in (keep them)

- **Prod anywhere in the blast radius → explicit, in-the-moment user consent. No carry-over.**
- Live state outranks git; diff against live before any declarative apply.
- Secrets found in history are compromised — rotation is the fix, removal is not.
- Blameless postmortems: causes are systems/processes, never people.
- Draft-first for anything team-visible (tickets, MRs to shared boards).
