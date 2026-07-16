---
name: rfc
description: Draft an RFC (Request for Comments) — a design proposal for feedback BEFORE significant work starts. Use for cross-team/cross-service changes, new platform capabilities, migrations, anything needing buy-in or with multiple viable designs. Invoke when the user says "RFC", "proposal", "design doc", or is about to start large work without one.
---

# RFC — design proposal for review

An RFC exists to get **feedback and buy-in before the work starts**. It is a discussion artifact;
the resulting decision gets condensed into an ADR afterwards.

## When an RFC is warranted (signal proactively)

- The change crosses team/service/repo boundaries or alters how others work (CI conventions,
  deploy paths, alerting ownership).
- Multiple viable designs exist and the wrong pick is expensive.
- The work spans weeks or touches prod-critical paths (a chat message won't carry the context).
- New platform capability (e.g. introducing an agentic workflow, new observability stack).

NOT warranted: work already covered by an accepted RFC/ADR, single-repo changes with an obvious
design, urgent incident fixes (write the retro-ADR after instead).

## Location & publishing

- Repo home: `docs/rfcs/NNNN-<slug>.md` (git versioning + greppability + agent context).
  Same numbering scheme as ADRs: `RFC-NNNN: <title>` (4-digit zero-padded) everywhere —
  markdown H1, page titles, references.
- If the team reads/comments elsewhere (wiki, Notion, Confluence), publish there on
  draft-complete and keep the repo file as a mirror — keep them in sync, don't fork content.
- Every RFC carries its **Date** (creation). No due dates — pace is the owner's.

## Shared-copy formatting (when publishing to a wiki)

- **TL;DR always first** — a callout with: the problem in one bold line, the fix in numbered
  moves, cost, and risk controls. Written for someone who will read nothing else.
- Structure for scanning: clear H2s, short paragraphs, dividers between major sections.
- Callouts for warnings/consent gates, collapsible sections for deep technical detail so the
  main flow stays light, tables only where rows are truly comparable.
- Decisions section as checkboxes so deciding is a click.
- Keep the markdown source semantically identical — wiki formatting is presentation, not content.

## Template

```markdown
# RFC-NNNN: <title — the proposal, not the problem>

- **Status:** draft | in-review | decided | rejected | superseded
- **Author:** <name>   **Date:** YYYY-MM-DD
- **Reviewers/Decider:** <see owner-decided mode below>
- **Related:** <ADRs, tickets, incidents, docs>

## Summary
The whole proposal in 3–5 sentences. A reviewer who reads only this should know what's being
proposed and what it costs.

## Problem
What hurts today, with evidence (incidents, metrics, drift findings). Why now.

## Goals / Non-goals
Bullets. Non-goals are as important — they pre-empt scope creep in review.

## Proposed design
The meat. Diagrams (mermaid) where topology matters. Cover: components touched, data/control
flow, rollout order, and what changes for each affected team/service.

## Alternatives considered
Each with an honest trade-off table or bullets, and why the proposal wins.

## Risks & mitigations
Include blast radius, rollback story, and security/IAM impact explicitly.

## Rollout plan
Phased steps, each independently safe. Mark the prod-touching steps (consent gate).

## Open questions
Numbered, so reviewers can answer by number.
```

## Style rules

- **Didactic register (default):** what/why/how structure with plain-language leads before
  technical detail. Include a short "how this works today" primer for any mechanism the design
  builds on, a one-line "why this number" for every threshold, and a glossary for terms of art.
  The RFC teaches while it proposes — the primary reader is building their mental model. Tighten
  the register only when the audience is an external/senior reviewer. (ADRs stay terse.)
- **Owner-decided mode:** when the domain is the owner's own, reviewers become
  "Decider: <owner>"; the Open Questions section becomes **Decisions** — each with options, a
  recommendation + why, and a checkbox. Other teams appear only where their code is touched,
  optionally FYI'd. Status flow: draft → decided → ADR.
- Write for the busiest reviewer: summary and goals must stand alone.
- Steel-man the alternatives — a weak alternatives section undermines trust in the proposal.
- Every prod-affecting step in the rollout plan is explicitly marked (hard rule: consent required).
- On acceptance: condense the decision into an ADR, link both ways, log in the worklog.

## Project adaptation

- **Canonical home:** repo-only, or repo + wiki mirror — decide once and note it here.
- **Decider:** name the default decider; use owner-decided mode for solo-owned domains.
