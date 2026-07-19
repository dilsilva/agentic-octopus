# ADR-0007: Chat is a spine capability; UIs are thin clients (Open WebUI bought, not built)

- **Status:** accepted
- **Date:** 2026-07-17
- **Deciders:** Diego
- **Related:** RFC-0001, ADR-0002 (provider seam), ADR-0006 (personas as agent dirs)

## Context

Diego wants a ChatGPT-like chat for daily research, usable from terminal, browser, and raw
HTTP — his explicit principle: capabilities live in the core independent of any UI, with
UIs coupled on top. Building a web chat UI from scratch is undifferentiated work when
mature OSS (Open WebUI) exists.

## Decision

Chat is implemented as a spine capability: conversations/messages live in the spine's
Postgres, a chat service + native API expose it, and every surface is a thin client —
`octo chat` (CLI), raw HTTP, and **Open WebUI** (adopted, version-pinned container) via an
OpenAI-compatible `/v1` shim. Personas are declarative agent directories (ADR-0006);
providers sit behind a `ChatProvider` protocol (ADR-0002); the `:free` cost guard applies
on every surface. A scoped `OCTO_CHAT_TOKEN` (valid only on `/chat/*` + `/v1/*`) is what
chat UIs receive — they can converse but not drive agents.

## Options considered

### Option A — Core capability + bought UI (Open WebUI)  ← chosen
- Pros: capability UI-independent (CLI/HTTP/web share tables and guard); ChatGPT-grade UI
  for free; one endpoint of shim code.
- Cons: dependency on an upstream OSS project; two conversation stores (below).

### Option B — Build our own web UI
- Pros: single store, full control. Cons: weeks of undifferentiated frontend work at the
  cost of actual platform phases. Rejected.

### Option C — Open WebUI straight to OpenRouter (no spine)
- Pros: zero code. Cons: no cost guard, no audit, capability lives outside the spine —
  violates the core-first principle. Rejected.

## Consequences

- Positive: chat from terminal, browser, or curl against the same core; free-of-charge
  guaranteed by the shared guard; scoping pattern established for P3 (Telegram).
- Negative — **explicit accepted trade-offs:**
  1. Open WebUI keeps its own conversation history inside its volume; those chats are NOT
     in the spine's Postgres (only request metadata via `chat_completions`). P5 semantic
     memory will see native-chat history only.
  2. ~~Open WebUI's built-in web search is a *temporary UI-side capability exception*~~
     **Resolved 2026-07-19 (v0.5.0):** the core tool loop shipped (prompted protocol in
     `chat.py` + `octo/tools/`); every surface now has web search. Open WebUI's own
     search toggle is redundant for native-model use and may be disabled.
  3. `/v1` is a protocol namespace (OpenAI-compat), NOT a version of our API — native
     routes stay unversioned; never mint a `/v2`.
- Follow-ups: core web-search tool loop; rolling summarization into
  `conversations.summary`; Ollama as ChatProvider #2 (containerized — run-anywhere, not
  Mac-bound).
