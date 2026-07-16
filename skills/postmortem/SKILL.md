---
name: postmortem
description: Write a blameless incident postmortem — timeline, root cause, contributing factors, actions. Use after any incident (self-inflicted included), near-miss, or when the user says "postmortem", "write up what happened", "incident review".
---

# Postmortem — blameless incident write-up

A postmortem converts an incident into (a) prevention work and (b) taught knowledge. Blameless
means causes are systems/processes, never people — "the reviewer missed it" is banned; "nothing
forced a diff against live before apply" is the correct form.

## When

- Any unexpected impact to a live environment (including self-inflicted, including non-prod).
- Near-misses — caught before impact but only by luck. These are cheaper lessons, same template.
- Retroactively for significant past incidents when patterns repeat.

## Location

`docs/postmortems/YYYY-MM-DD-<slug>.md` (create dir on first use). Log in the worklog.

## Template

```markdown
# YYYY-MM-DD — <what broke, plainly>

- **Severity:** SEV1 (prod user impact) | SEV2 (prod degraded/at risk) | SEV3 (non-prod/near-miss)
- **Duration:** detection → resolution. **Author:** … **Status:** draft | reviewed

## Summary
3–5 sentences: what happened, impact, how it was resolved. Readable standalone.

## Timeline (UTC)
| Time | Event |
Include: first cause event, detection (HOW did we notice — an alert? luck?), key decisions, resolution.

## Root cause
The mechanism, precisely. Ask "why" until you reach a system/process condition, not an action.

## Contributing factors
The conditions that let it happen and made it worse (drift, missing alert, stale docs, no dry-run
gate). Usually more valuable than the root cause itself.

## What went well / what didn't
Honest bullets — include tooling and process, not just the fix.

## Detection gap
Would we have known without a human watching? If detection was luck → that's an alerting ticket.

## Actions
| Action | Type (prevent/detect/mitigate) | Ticket | Owner |
Every action gets a ticket (/ticket) or an explicit "accepted risk, not doing" — no orphan intentions.
Decisions exposed by the incident → retro-ADR (/adr).
```

## Rules

- Write within a day or two while memory is fresh; mark `draft` until reviewed.
- The "detection gap" section is mandatory — it feeds the observability workstream directly.

## Project adaptation

- **Location:** default `docs/postmortems/`; use the org's incident home if one exists.
- **Severity scale:** map to the org's existing SEV/P-level scheme if it has one.
