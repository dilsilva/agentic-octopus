---
name: refresh-data
description: Refresh the project's data layer (repo clones, scan results, drift reports, live-state snapshots) and reconcile the docs with what changed. Use when data is stale (>1 week old), before a major analysis, or when the user says "refresh the data", "rescan", "update the snapshots".
---

# Refresh data — data layer + doc reconciliation

The analysis docs are only as good as the data under them. This refreshes the project's data
layer (whatever snapshots/exports/scans it maintains), then surfaces what changed so the docs
stay truthful.

> This skill is a frame — the concrete data sources are per-project. Fill the Project adaptation
> section the first time you use it in a new project.

## Steps

1. **Baseline first.** Note current timestamps and key counts of every data artifact (repo count,
   drift findings, snapshot dates) so the delta is measurable.
2. **Refresh each source** using the project's own refresh mechanism (clone/fetch scripts,
   scanners, cloud asset exports, cluster state exports). Preserve existing filenames and naming
   schemes — downstream docs and scripts depend on them.
3. **Everything read-only.** Exports, list/describe, fetches. If a refresh step seems to need a
   mutation, something is wrong — stop.
4. **Diff vs baseline.** Report what changed: new/archived repos, status changes
   (dormant→live matters most), new/resolved drift, health changes, workload deltas — anything
   the worklog is tracking.
5. **Reconcile docs.** Material changes → update the affected topic docs (numbers, statuses) and
   append a worklog entry summarizing the refresh delta. Non-material → worklog one-liner
   ("data refreshed, no material delta").

## Rules

- Long-running steps (mass cloning, asset exports) → run in background, continue other work.
- Never edit scan/diff script semantics silently to make output match expectations — fix data,
  or flag the discrepancy.
- Docs record *corrections* explicitly when new data contradicts old claims — don't silently
  overwrite previously-verified numbers.

## Project adaptation (fill in per project)

- **Data artifacts & locations:** list each (e.g. `repos/_manifest.json`, `scan_results.json`,
  `drift.json`, `livestate/` exports) and the command/script that refreshes it.
- **Staleness threshold:** default 1 week; tighten for fast-moving systems.
- **Docs to reconcile:** which topic docs consume this data.
