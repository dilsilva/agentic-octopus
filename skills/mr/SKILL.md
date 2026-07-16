---
name: mr
description: Shape a Merge Request / Pull Request — title, description, scope, evidence. Use whenever creating or reviewing an MR/PR (via glab or gh), or when the user asks "open an MR/PR" / "write the MR description".
---

# MR/PR — change request conventions

An MR/PR is the unit of change AND the audit record. In a GitOps setup the description is what a
future engineer (or agent) reads to understand why live state changed. Shape it accordingly.

## Scope rules (apply before writing anything)

- **One concern per MR.** If the diff needs "and" in the title, it's probably two MRs.
- Refactors/formatting never mixed with behavior changes.
- If the change implements an RFC/ADR/ticket, link it; if it's significant and has none, signal
  that first (see /adr, /rfc) before opening the MR.

## Title

`<type>: <imperative summary>` — types: `feat` | `fix` | `chore` | `refactor` | `docs` | `ci`.
Prefix `Draft:` while not ready. Example: `fix: retag CI jobs to live runners`.

## Description template

```markdown
## What
The change, in 1–3 sentences. Plain language, not a diff narration.

## Why
The problem/motivation, with links: ticket, ADR/RFC, incident, worklog entry.

## Impact & risk
- Environments affected: dev / staging / prod (be explicit — prod changes need the user's consent to deploy)
- Blast radius if wrong, and the rollback: `helm rollback ...` / revert MR / sync to previous
- Does merging alone change live state, or only a later pipeline/sync? Say which.

## Evidence
How this was verified — commands run and their output (diff, dry-run, pipeline link, before/after).
"Tested locally" without evidence doesn't count.

## Out of scope
What this deliberately does NOT touch (pre-empts review scope creep).
```

## Process

0. Run /git-recon first — branch freshness, protected branches, and the repo's CI trigger map
   (an MR merge can BE a deploy; know that before opening it).
1. Branch from a freshly-fetched default; never commit to the default branch directly.
2. `glab mr create --draft ...` / `gh pr create --draft ...` — start as draft, fill the template.
3. Self-review the diff before requesting review: every hunk must serve the title.
4. Checks before marking ready:
   - CI runners/labels the jobs target are live — dead tags hang forever.
   - No secrets in the diff — run /secrets-check.
   - Declarative changes (helm/terraform values): dry-run diffed against live first
     (git may be drifted — verify, don't assume).
5. **Merging an MR whose pipeline deploys to prod = prod action → explicit consent first.**
6. Log significant MRs in the worklog (see /worklog).

## Project adaptation

- **Host & CLI:** GitLab/`glab` or GitHub/`gh` — detect from the remote.
- **Title convention:** if the project prefixes ticket keys (`PROJ-123:`), follow that instead.
- **Repo-specific ready checks:** add any (e.g. changelog entry, version bump, docs build).
