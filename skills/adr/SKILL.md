---
name: adr
description: Draft an Architecture Decision Record. Use when a decision is significant and hard to reverse — technology/tooling choice, architectural pattern, security/IAM model, ownership boundary, deprecation. Also invoke when the user says "ADR", "decision record", or asks to document a decision already made.
---

# ADR — Architecture Decision Record

Shape a decision record that a future engineer (or agent) can read and understand **why** the
project is the way it is, without asking anyone.

## When an ADR is warranted (signal proactively)

- The decision is **hard or costly to reverse** (schema, cloud service choice, auth model, network topology).
- Two+ credible options exist and the choice constrains future work.
- Someone will ask "why did we do it this way?" in 6 months.
- An incident or drift revealed an implicit decision that was never written down (retro-ADR — these are legitimate and valuable).

NOT warranted: reversible implementation details, style choices, anything a linter could decide.

## Location & numbering

- Repo-scoped decision → `docs/adr/NNNN-<slug>.md` in that repo (create the dir on first use).
- Org/platform-wide → the project's canonical decision home (wiki, Notion, Confluence — see
  Project adaptation) + a repo mirror for greppability and agent context.
- `NNNN` = zero-padded 4-digit sequence within that location. Check existing files first.
- Titles are ALWAYS `ADR-NNNN: <title>` — in the markdown H1 and anywhere referenced.
- Every ADR carries its **Date** (creation). No due dates.

## Template

```markdown
# ADR-NNNN: <Decision as a short assertive sentence, e.g. "Use ArgoCD as the sole deploy path">

- **Status:** proposed | accepted | superseded by [NNNN] | deprecated
- **Date:** YYYY-MM-DD
- **Deciders:** <names — the owner + whoever must agree>
- **Related:** <RFC / ticket / MR-PR / incident links>

## Context
What forces are at play — technical, organizational, migration, cost. State the facts that
make this decision necessary. 2–4 paragraphs max. Facts, not advocacy.

## Decision
"We will <decision>." One paragraph. Unambiguous, active voice.

## Options considered
### Option A — <name>  ← chosen
Pros / cons, in bullets.
### Option B — <name>
Pros / cons. Why rejected — one honest sentence.

## Consequences
- Positive: what this enables.
- Negative: what we accept/give up (be honest — every real decision has costs).
- Follow-ups: concrete actions this creates (tickets to open, docs to update).
```

## Style rules

- Decision-first title: a reader scanning filenames should learn the decisions.
- Honest negative consequences — an ADR with no downsides listed wasn't thought through.
- Immutable once accepted: changes of mind → new ADR that supersedes, never edit history.
- Keep it under ~1 page. If it needs more, the design discussion belongs in an RFC (link it).

## Process

1. Confirm scope (repo vs org-wide) and check the next number.
2. Draft with the user's input; if options weren't discussed, propose the credible alternatives yourself.
3. Status starts `proposed`. Only mark `accepted` when the user says so.
4. Log the ADR's creation in the worklog (see /worklog).

## Project adaptation

- **ADR directory:** default `docs/adr/`; change if the project has an existing convention.
- **Canonical home:** if decisions live in a wiki/Notion/Confluence, publish there and keep the
  repo file as a mirror; note the two-way link convention.
- **Deciders:** name the default decider(s) for this project.
