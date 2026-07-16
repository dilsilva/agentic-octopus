---
name: git-recon
description: Before working in any repo — verify branch freshness and detect the repo's git flow (protected branches, CI triggers, MR/PR rules, conventions). Run on FIRST touch of a repo in a session, before branching/committing/pushing, or when the user asks "is this branch up to date" / "how does this repo work".
---

# Git recon — freshness + flow detection before acting

Two failure modes this prevents: (1) working on a stale branch when git may drift from live,
(2) violating a repo's flow — worst case, a push that triggers CI you didn't expect (e.g. a push
to the default branch that runs `terraform apply` or a deploy job).

Detect the host first (`git remote -v`): GitLab → `glab`, GitHub → `gh`. Commands below show the
GitLab form; use the `gh` equivalent on GitHub.

## Part 1 — Freshness (always, before any action)

1. **Know which clone you're in.** Shallow clones and scan snapshots are data layers, not dev
   surfaces. For real dev work: `git fetch --unshallow` (or a fresh full clone) — never build
   history-dependent work on a shallow snapshot.
2. `git fetch origin --prune`, then check:
   - Target branch vs `origin/<branch>`: behind/ahead counts (`git status -sb`,
     `git rev-list --left-right --count HEAD...origin/<branch>`). Behind → pull/rebase BEFORE any edit.
   - How stale is the checkout: date of last local fetch vs `origin/HEAD` tip date.
3. **Check for concurrent work:** `glab mr list` / `gh pr list` — open MRs/PRs touching the same
   files/area; recent commits by others on the target branch
   (`git log origin/<default> --since="2 weeks ago" --format='%an %s'`).
4. **Check pipeline state:** is anything running/failed on this branch right now
   (`glab ci list` / `gh run list`)? Don't push onto a red or in-flight pipeline without knowing why.
5. Resuming parked work: verify the branch still exists on origin, hasn't been force-pushed, and
   rebase onto fresh default before continuing.

## Part 2 — Flow detection (first touch of a repo)

Build a 5-line "how this repo works" picture before changing anything:

- **Default branch** (`git remote show origin`) — never assume `main`.
- **Protected branches & MR/PR rules:** `glab api "projects/:id/protected_branches"` /
  `gh api repos/{owner}/{repo}/branches/<branch>/protection`; approvals required, squash policy,
  who can merge.
- **CI trigger map — the critical one.** Read the CI config (`.gitlab-ci.yml` `workflow:rules`
  + per-job `rules`, or `.github/workflows/*` `on:` blocks) and answer explicitly: what runs on
  (a) branch push, (b) MR/PR open/update, (c) merge to default, (d) tag? Which jobs are manual?
  Which runner tags/labels (dead runners = jobs hang)?
  **Any job that deploys/applies → treat the triggering git action as a live write → /preflight.**
- **Conventions in use:** branch naming (`git branch -r` patterns), commit style
  (`git log --oneline -20`), tags/releases, CODEOWNERS, MR/PR templates.
- **Ownership:** recent committers — who to loop in.

## Output

Report a compact recon block before starting work:

```
repo: charts/example         default: main (protected, 1 approval)
branch: feat-add-user        state: exists on origin, 3 behind main → rebase needed
CI: push→lint only; MR→plan; merge to main→deploy job (DEPLOYS staging/prod ⚠ preflight); manual: prod_deploy
conventions: feat-*/fix-* branches, no squash, no MR template
concurrent: no open MRs touching helm/
```

## Rules

- Fetch is always safe; anything past fetch that mutates the remote or triggers CI is not — flag it.
- If flow and freshness conflict with the plan (e.g. rebase would retrigger a deploy pipeline),
  stop and surface the trade-off rather than picking silently.
- Cache recon per repo per session; re-verify freshness before every push, not just the first.

## Project adaptation

- Note any repos where a git action IS a deploy (merge-to-default applies infra, tag publishes) —
  list them explicitly so the CI trigger map check is never skipped there.
