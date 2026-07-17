"""Agent execution behind a Protocol (ADR-0002).

The spine is provider-pluggable: ClaudeSDKExecutor is the primary implementation;
an OpenRouter-style executor lands in P2.5. Tests always use FakeExecutor — the
real SDK is never called in the test suite (CLAUDE.md hard rule).
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from octo.registry import LoadedAgent

OnEvent = Callable[[str, dict[str, Any]], Awaitable[None]]


@dataclass
class ExecOutcome:
    status: Literal["completed", "failed"]
    result: str | None = None
    error: str | None = None
    cost_usd: float | None = None
    session_id: str | None = None


class AgentExecutor(Protocol):
    async def execute(
        self, run: dict[str, Any], agent: LoadedAgent, workdir: Path, on_event: OnEvent
    ) -> ExecOutcome: ...


@dataclass
class FakeExecutor:
    """Deterministic executor for tests: returns canned outcomes per agent name."""

    outcomes: dict[str, ExecOutcome] = field(default_factory=dict)
    default: ExecOutcome = field(default_factory=lambda: ExecOutcome("completed", result="fake"))
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def execute(
        self, run: dict[str, Any], agent: LoadedAgent, workdir: Path, on_event: OnEvent
    ) -> ExecOutcome:
        self.calls.append({"run_id": str(run["id"]), "agent": agent.manifest.name})
        await on_event("log", {"msg": "fake executor ran"})
        return self.outcomes.get(agent.manifest.name, self.default)


class ClaudeSDKExecutor:
    """Primary executor: headless Claude Agent SDK session (imported lazily so the
    package is only required where agents actually run)."""

    async def execute(
        self, run: dict[str, Any], agent: LoadedAgent, workdir: Path, on_event: OnEvent
    ) -> ExecOutcome:
        from claude_agent_sdk import (  # noqa: PLC0415 - lazy by design
            AssistantMessage,
            ClaudeAgentOptions,
            ResultMessage,
            TextBlock,
            ToolUseBlock,
            query,
        )

        m = agent.manifest
        options = ClaudeAgentOptions(
            system_prompt=agent.prompt,
            allowed_tools=list(m.tools),
            max_turns=m.max_turns,
            cwd=str(workdir),
            setting_sources=[],  # server runs are isolated from filesystem Claude settings
            permission_mode="bypassPermissions",  # headless: the manifest allowlist IS the gate
            **({"model": m.model} if m.model != "default" else {}),
        )
        prompt = (
            "Execute your task now. Run parameters (JSON):\n"
            f"{run.get('params') or m.params}\n"
            f"Write outputs into the current working directory."
        )
        outcome = ExecOutcome(status="failed", error="executor produced no result")
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        await on_event("message", {"text": block.text[:2000]})
                    elif isinstance(block, ToolUseBlock):
                        await on_event(
                            "tool_use", {"tool": block.name, "input": _clip(block.input)}
                        )
            elif isinstance(message, ResultMessage):
                ok = message.subtype == "success"
                outcome = ExecOutcome(
                    status="completed" if ok else "failed",
                    result=message.result if ok else None,
                    error=None if ok else f"sdk result subtype: {message.subtype}",
                    cost_usd=message.total_cost_usd,
                    session_id=message.session_id,
                )
        return outcome


class OpenRouterExecutor:
    """Provider-agnostic executor (P2.5): one-shot chat completion via OpenRouter's
    OpenAI-compatible API. v1 has no local tools — the model answers in a single
    response and the executor writes the output file itself. Pre-execution gates
    apply; mid-run gates are SDK-only (ADR-0002)."""

    async def execute(
        self, run: dict[str, Any], agent: LoadedAgent, workdir: Path, on_event: OnEvent
    ) -> ExecOutcome:
        from datetime import UTC, datetime

        import httpx

        from octo.config import settings

        if not settings.openrouter_api_key:
            return ExecOutcome(status="failed", error="OPENROUTER_API_KEY not configured")

        m = agent.manifest
        model = m.model if m.model != "default" else settings.openrouter_default_model
        # Cost guard: refuse anything that could bill until the operator opts in.
        if not model.endswith(":free") and not settings.openrouter_allow_paid:
            return ExecOutcome(
                status="failed",
                error=(
                    f"model '{model}' is not a :free variant and OPENROUTER_ALLOW_PAID "
                    "is off — refusing to run a potentially billable request"
                ),
            )
        params = run.get("params") or m.params
        user_msg = (
            "Execute your task now, in a single response. Run parameters (JSON):\n"
            f"{params}\n"
            "You have no tools in this environment: work from your knowledge, state its "
            "limits explicitly (including your knowledge cutoff), and return ONLY the "
            "final markdown document — it will be saved for you."
        )
        await on_event("log", {"executor": "openrouter", "model": model})

        async with httpx.AsyncClient(timeout=300) as client:
            r = await client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": agent.prompt},
                        {"role": "user", "content": user_msg},
                    ],
                },
            )
        if r.status_code != 200:
            return ExecOutcome(status="failed", error=f"openrouter {r.status_code}: {r.text[:500]}")
        data = r.json()
        if data.get("error"):  # OpenRouter can return 200 with an embedded error
            return ExecOutcome(
                status="failed", error=f"openrouter error: {str(data['error'])[:500]}"
            )

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        outfile = workdir / f"{m.name}-{datetime.now(UTC).strftime('%Y-%m-%d')}.md"
        outfile.write_text(content)
        await on_event("message", {"text": content[:2000]})
        return ExecOutcome(
            status="completed",
            result=(
                f"wrote {outfile.name} ({len(content)} chars, model={model}, "
                f"tokens={usage.get('total_tokens')})"
            ),
            cost_usd=0.0 if model.endswith(":free") else None,
        )


def _clip(value: Any, limit: int = 500) -> Any:
    s = str(value)
    return s if len(s) <= limit else s[:limit] + "…"


def get_executor(name: str) -> AgentExecutor:
    if name == "claude-sdk":
        return ClaudeSDKExecutor()
    if name == "openrouter":
        return OpenRouterExecutor()
    raise ValueError(f"no executor registered for '{name}'")
