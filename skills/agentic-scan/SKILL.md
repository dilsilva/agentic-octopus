---
name: agentic-scan
description: Evaluate a component, tool, or workflow through the agentic lens — automation opportunities, enabling interfaces, blockers. Use when the user asks "how does X fit the agentic direction", during design work (RFCs) to add the agentic perspective, or to assess a piece of the system just worked on.
---

# Agentic scan — evaluating a piece of the system

Supports the north star: steer the system agentic gradually. The output is both an assessment
AND a teaching artifact — the user is building their own mental model of the path, so explain the
*why* behind each rating, not just the verdict.

## The four-layer frame

Assess the target against the layers every agentic system needs:

1. **Actuation** — how would an agent safely *change* this?
   Best: declarative + GitOps (MR/PR = proposal, review = approval, revert = rollback).
   Worst: imperative console/CLI mutations with no record. Rate the target's current surface.
2. **Senses** — how would an agent *know* the state and the outcome of its actions?
   Metrics/alerts/logs/health endpoints it could consume; feedback latency (how fast after acting
   would an agent know it worked?). No signal = no safe autonomy.
3. **Trust boundary** — what identity/permissions would an agent need, and can they be scoped?
   Short-lived creds (e.g. workload identity / OIDC federation) vs static keys; least-privilege
   feasible? Blast radius if the agent misbehaves; where the human approval gate belongs.
4. **Context** — is the knowledge an agent needs written down and current?
   Docs, ADRs, runbooks, acceptance criteria; or does it live in someone's head?

## Output shape

For each layer: current state (1–2 sentences, concrete evidence) → gap → smallest next step.
Then close with:

- **Toil candidates:** specific recurring tasks here an agent could take over (drift detection,
  alert triage, runbook execution, MR/PR review, report generation) — ranked by value/risk ratio.
- **Autonomy ladder:** what level fits *today* — (1) agent reports, (2) agent proposes (MR/draft),
  (3) agent acts with approval, (4) agent acts autonomously with monitoring. Most components
  start at 1–2; say what would justify promotion to the next rung.
- **One-line verdict:** e.g. "GitOps-ready actuation, blind senses — fix observability before any automation here."

## Rules

- Ground every claim in the project docs or a live check — no generic "AI could help" filler.
- Gradual by design: recommend the smallest next rung, never a jump to full autonomy.
- Significant findings → relevant project doc + worklog; if the scan motivates real work, shape it
  with /ticket or /rfc.

## Project adaptation

- Nothing structural — but seed the scan with the project's actual toil list and observability
  stack once known, so verdicts stay concrete.
