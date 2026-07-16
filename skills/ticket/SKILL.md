---
name: ticket
description: Shape a work ticket/issue — problem statement, acceptance criteria, definition of done. Use when the user asks to "create a ticket/issue", when planned work has no ticket, or when breaking an RFC/epic into workable items.
---

# Ticket — shaping work items

A good ticket lets anyone on a high-ownership team (or an agent) pick up the work without a
conversation. The acceptance criteria are the contract; everything else is context.

## When to signal a ticket is needed

- Work is planned but exists only in chat/worklog — anything taking >1 hour or touching live infra.
- An RFC was accepted → break the rollout plan into tickets.
- A finding is parked "for later" — parked without a ticket = lost.
- Scope creep detected mid-task → propose splitting into a new ticket rather than growing the current one.

## Template

```markdown
# <Title: outcome-oriented, imperative — "Rotate OAuth secret", not "OAuth secret problem">

## Problem / Goal
What's wrong or missing, and why it matters — with evidence (links to worklog, docs, incidents,
metrics). One paragraph. A reader should understand the value of doing this.

## Acceptance criteria
- [ ] Each criterion is **observable and binary** — a reviewer can check it without judgment calls.
- [ ] Use concrete verification: "`kubectl get pods -n X` shows 0 restarts over 24h", not "pod is stable".
- [ ] Include the negative space: "old secret revoked and no longer works", not just "new secret works".
- [ ] 3–7 criteria. More → split the ticket. Fewer → probably not thought through.

## Scope
**In:** what this ticket covers.
**Out:** adjacent work explicitly excluded (link the ticket that covers it, or note "not ticketed").

## Definition of done (beyond the criteria)
- [ ] Docs updated (which one: reference / topic doc / runbook)
- [ ] Worklog entry appended
- [ ] If a decision was made along the way → ADR written or explicitly skipped

## Context & links
Related: ADR/RFC, MRs/PRs, prior tickets, relevant doc sections. Environment(s) affected.
Prod-touching steps flagged (consent gate).

## Size & priority
Estimate (S/M/L or hours) + why now / why this priority.
```

## Style rules

- Acceptance criteria describe **outcomes, not implementation** — leave the "how" to the assignee
  unless an ADR constrains it.
- Given/When/Then is fine for behavioral criteria; checklists for infra outcomes. Pick per criterion.
- Never write a ticket whose only criterion is "investigate X" — instead: "investigation written up
  in <doc>, with a go/no-go recommendation".

## Process

1. Draft using the template; pull evidence from the project docs rather than restating from memory.
2. Create in the project's tracker via its CLI (see Project adaptation).
3. **Draft-first rule: ALWAYS show the full ticket draft in chat and get the user's OK before
   creating it** — shared boards are team-visible. Report the created key back.
4. Cross-link: worklog entry ↔ ticket ↔ eventual MR/PR. Follow the team's commit-title
   convention for ticket keys if one exists.

## Project adaptation

- **Tracker & CLI:** e.g. Jira via `jira-cli`, GitLab issues via `glab issue create`, GitHub via
  `gh issue create`, Linear via API. Note project key, board, and how auth is fetched
  (keychain/env var — never hardcode tokens).
- **Commit-title convention:** e.g. `PROJ-123: <title>` or `NO_TICKET: <title>`.
