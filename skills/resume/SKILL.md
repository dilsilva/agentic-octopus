---
name: resume
description: Resume project work from the worklog — load state, report where we are, continue. Use at session start when the user says "continue where we left off", "resume", "what's the status", or references the worklog.
---

# Resume — pick up where we left off

Restore full working context from the docs (the source of truth), then continue — don't rely on
conversation memory alone.

## Steps

1. Read the worklog (`docs/worklog.md`) top-down (newest first — the top entry is current state).
2. If the top entry names a current workstream doc, read that too.
3. Check for session-handoff entries: rescued artifacts, uncommitted work in scratchpad/snapshot
   dirs, and verify anything time-sensitive still holds (branches exist, files present) before
   relying on it.
4. Report back concisely:
   - Where we are (1–2 sentences).
   - **Open items in priority order** (from the worklog, updated with anything you verified changed).
   - The single recommended next action.
5. If the next action is unambiguous and non-destructive, start it. If it's a genuine fork
   (e.g. "user to pick"), present the options and wait.

## Rules

- The worklog outranks memory files and prior-session summaries when they disagree.
- Anything that looks stale (dates, counts, pipeline states) → re-verify live before acting on it.
- Read-only until direction is confirmed; hard rules apply (no prod without consent).

## Project adaptation

- **Worklog path:** default `docs/worklog.md` — keep in sync with /worklog.
