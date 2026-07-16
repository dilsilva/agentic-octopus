---
name: release
description: Shape a release/promotion through environments (dev→staging→prod) — sequencing, verification per stage, versioning. Use when deploying a change through the environment chain, tagging a release, or when the user says "promote this", "release", "roll this out".
---

# Release — promotion through the environment chain

## Promotion path

`dev → staging → prod`, never skipping stages for platform changes. Each stage must **soak and be
verified** before the next. prod is always last and always consent-gated.

Realities to establish per project (see /git-recon):
- Which system owns each component's deploy — CI jobs, GitOps sync (ArgoCD/Flux), or both.
  Double-ownership must be resolved or accounted for before promoting.
- How environments are expressed — per-env values files, branches, overlays. A promotion is
  usually the same artifact + the next environment's config.
- Runner/agent health — a deploy job targeting a dead runner hangs silently.

## Per-stage checklist

1. **Before:** /preflight (diff vs live, rollback, hitchhikers). Record current revision.
2. **Deploy** via the repo's own mechanism — don't bypass CI/GitOps with manual commands unless
   that IS the current mechanism (some components are maintained out-of-band; note it, don't
   fight it mid-release).
3. **Verify — observe, don't assume:** pods/services healthy over a soak period, key endpoints
   respond, GitOps app Synced+Healthy, no new alerts/log errors. Verification evidence goes in
   the MR/worklog.
4. **Soak time** proportional to blast radius: dev minutes, staging hours (or a workday for
   platform components), prod = monitored actively after deploy.
5. **Rollback rehearsed:** know the exact command per stage; a promotion without a tested rollback
   story stops at staging.

## Versioning & record

- Tag releases where the repo already tags (follow its pattern — check `git tag -l` first);
  charts/packages: bump the version in the same MR as the change.
- Changelog = the MR/PR description trail; significant releases get a worklog entry with
  revisions per environment (enables precise rollback later).

## Rules

- **prod stage: explicit in-the-moment consent. Every time. No carry-over.**
- A failed stage stops the train — fix forward or roll back, but never promote a stage that
  didn't verify clean.
- Divergence discovered mid-release (live ≠ git at the next stage) → stop, reconcile first
  (the reconcile IS the work).

## Project adaptation

- **Environment chain:** map dev/staging/prod to the project's actual names and count.
- **Deploy ownership map:** per component, which system deploys it.
- **Soak times:** set defaults per stage once real releases teach what's enough.
