# ADR-0002: Python + uv/ruff/pytest with the Claude Agent SDK as execution engine

- **Status:** proposed
- **Date:** 2026-07-15
- **Deciders:** Diego
- **Related:** RFC-0001, ADR-0001

## Context

The spine needs a language and an agent execution engine. Owner background is platform/infra
(Python-adjacent). The Claude Agent SDK (`claude-agent-sdk`, PyPI, 0.2.x) provides headless
agent sessions with tools, permission modes, cost reporting, and session resume — the exact
primitives the gate design needs — and bundles the Claude Code CLI in the package.

## Decision

We will implement in Python 3.12 managed by uv (lockfile, fast installs), linted by ruff,
tested by pytest; agents execute via the Claude Agent SDK's `query()` headless API.

## Options considered

### Option A — Python + claude-agent-sdk  ← chosen
- Pros: matches owner background; mature SDK with resume + in-process MCP tools; one toolchain
  (uv) for local, CI, and Docker.
- Cons: SDK is 0.x (churn risk) — mitigated by isolating it behind an `AgentExecutor` Protocol.

### Option B — TypeScript + Agent SDK
- Pros: same SDK capabilities; better if web UIs dominate later. Rejected: no near-term UI,
  and Python fits the operator better.

### Option C — Raw Anthropic API (no Agent SDK)
- Pros: no 0.x dependency. Cons: reimplements the agentic loop, tools, and session state the
  SDK already provides. Rejected.

## Consequences

- Positive: smallest possible executor code; cost/session data for free.
- Negative: coupled to Anthropic's agent stack; acceptable — it is also the product direction.
- Follow-ups: pin `claude-agent-sdk` minor versions; executor Protocol + FakeExecutor in M1.
