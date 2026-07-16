# ADR-0006: Agents are declarative directories, not code registrations

- **Status:** accepted
- **Date:** 2026-07-15
- **Deciders:** Diego
- **Related:** RFC-0001, ADR-0002

## Context

The spine's value is measured by the cost of adding application #2..#N. If each agent requires
Python code wired into the core (routes, registries, imports), every app grows the core's
surface and blast radius.

## Decision

We will define each agent as a directory `agents/<name>/` containing `agent.yaml` (name, tools
allowlist, **executor** and **model** — provider-agnostic: `claude-sdk` is the default executor,
OpenRouter-style executors select any model dynamically once present (Diego, 2026-07-16) —
max_turns, requires_approval, default schedule, params, output dir) and `prompt.md` (system
prompt). A registry validates manifests with pydantic at startup and maps them to the chosen
executor's options (for claude-sdk: `ClaudeAgentOptions` with `setting_sources=[]` to isolate
server runs). Adding an app is two files; the core does not change.

## Options considered

### Option A — YAML manifest + prompt file  ← chosen
- Pros: two-file onboarding; diffable/reviewable like config; the tools allowlist doubles as
  the safety surface; readable by non-code tooling later (dashboard).
- Cons: expressiveness ceiling — some future agent will want logic.

### Option B — Python modules registered in code
- Pros: unlimited expressiveness. Cons: every app touches core; safety surface scattered
  through code. Rejected as the default.

## Consequences

- Positive: `agents/` is the app catalog; review of a new agent is a review of its manifest
  and prompt.
- Negative: complex agents may strain YAML — mitigated by a planned optional per-agent
  `hooks.py` escape hatch (pre/post-run callbacks), deliberately not built until needed.
- Follow-ups: M1 implements the registry; `research-brief` ships as the exemplar.
