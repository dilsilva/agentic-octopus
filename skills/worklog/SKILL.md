---
name: worklog
description: Append a properly-shaped entry to the project worklog (actions/decisions log), or write a session handoff. Use after completing significant work, making a decision, parking something, or when the user says "log this", "update the worklog", or ends a session ("handoff", "wrapping up").
---

# Worklog — appending entries

`docs/worklog.md` is the cross-session source of truth for actions and decisions. Project *facts*
go in the topic docs; the worklog records **what we did, decided, and parked**, newest first.

## Entry conventions

- Entries go under today's `## YYYY-MM-DD` heading (create it at the top if absent); newest
  bullets first within the day.
- One bullet per action/decision, bold lead-in: `- **<What happened>:** detail...`
- Every entry must be actionable for a future session: exact names (repo, branch, MR/PR number,
  namespace, revision), what state things were left in, and what's still pending.
- Decisions include the *why* in one clause. Parked work says what would resume it.
- Prefixes in use: `🔒` security-sensitive, **HARD RULE** for standing rules, **PARKED** for
  deliberately stopped work, **NEXT UP** for the queued workstream.
- Cross-reference instead of duplicating: link topic docs, MRs/PRs, tickets.

## Session handoff variant

When ending a session or switching machines/accounts, write a `**SESSION HANDOFF.**` entry at the top:
1. How to resume (which docs to read, in what order).
2. Where uncommitted/rescued artifacts live (scratchpad paths die with the session — move
   anything needed to a durable path in the repo first, then reference that path).
3. **Open items in priority order**, numbered.

## Hygiene while you're in the file

- If a fact you're logging supersedes an older entry's claim, don't edit history — the new entry
  states the correction.
- If the entry records project facts that belong in a topic doc, put them there and link — the
  worklog bullet stays one line.

## Project adaptation

- **Worklog path:** default `docs/worklog.md` — keep in sync with /resume.
- **Topic docs:** list the project's topic docs so facts have a destination.
