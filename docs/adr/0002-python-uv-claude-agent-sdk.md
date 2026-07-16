# ADR-0002: Python + uv/ruff/pytest with the Claude Agent SDK as primary execution engine

- **Status:** accepted
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
tested by pytest. Agents execute through an `AgentExecutor` protocol whose **primary**
implementation is the Claude Agent SDK's `query()` headless API. The spine is deliberately
NOT Claude-only (Diego, 2026-07-16): alternative executors (e.g. OpenRouter/LiteLLM-backed)
plug in beside it, selected per agent via the manifest's `executor`/`model` fields, so any
model can be used dynamically.

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

### Option D — Provider-agnostic engine only (OpenRouter/LiteLLM as THE engine)
- Pros: maximum model freedom everywhere. Cons: loses the SDK's built-in tools, permission
  modes, and session resume — the exact primitives gates and audit depend on; those would be
  reimplemented per provider. Rejected as the primary, adopted as a pluggable secondary.

## Consequences

- Positive: smallest possible executor code; cost/session data for free; model freedom
  preserved by construction (the protocol, not the SDK, is the contract).
- Negative: coupled to Anthropic's agent stack for the primary path; alternative executors get
  weaker guarantees — mid-run gate resume is SDK-specific, so non-SDK executors support
  pre-execution gates only until they implement their own pause/resume.
- Follow-ups: pin `claude-agent-sdk` minor versions; executor Protocol + FakeExecutor in M1;
  OpenRouter executor as its own rollout phase (RFC-0001).
