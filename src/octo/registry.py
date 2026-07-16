"""Agent registry (ADR-0006): agents/<name>/agent.yaml + prompt.md, validated at startup.

The filesystem is authoritative — there is no agents table. The manifest's `executor`
field selects the AgentExecutor implementation (ADR-0002: provider-pluggable).
"""

from dataclasses import dataclass
from pathlib import Path

import yaml
from croniter import croniter
from pydantic import BaseModel, Field, field_validator

KNOWN_EXECUTORS = {"claude-sdk"}  # P2.5 adds "openrouter"


class OutputSpec(BaseModel):
    dir: str = "data"


class AgentManifest(BaseModel):
    name: str
    description: str = ""
    tools: list[str] = Field(default_factory=list)
    executor: str = "claude-sdk"
    model: str = "default"
    max_turns: int = 30
    requires_approval: bool = False
    schedule: str | None = None
    params: dict = Field(default_factory=dict)
    output: OutputSpec = Field(default_factory=OutputSpec)

    @field_validator("executor")
    @classmethod
    def executor_known(cls, v: str) -> str:
        if v not in KNOWN_EXECUTORS:
            raise ValueError(f"unknown executor '{v}' (known: {sorted(KNOWN_EXECUTORS)})")
        return v

    @field_validator("schedule")
    @classmethod
    def schedule_is_valid_cron(cls, v: str | None) -> str | None:
        if v is not None and not croniter.is_valid(v):
            raise ValueError(f"invalid cron expression: {v!r}")
        return v


@dataclass(frozen=True)
class LoadedAgent:
    manifest: AgentManifest
    prompt: str
    path: Path


def load_registry(agents_dir: Path) -> dict[str, LoadedAgent]:
    """Load and validate every agent directory. Raises on any invalid manifest —
    a broken agent definition should fail startup loudly, not at claim time."""
    registry: dict[str, LoadedAgent] = {}
    if not agents_dir.is_dir():
        return registry
    for agent_dir in sorted(p for p in agents_dir.iterdir() if p.is_dir()):
        manifest_path = agent_dir / "agent.yaml"
        prompt_path = agent_dir / "prompt.md"
        if not manifest_path.is_file():
            continue  # not an agent dir
        manifest = AgentManifest.model_validate(yaml.safe_load(manifest_path.read_text()))
        if manifest.name != agent_dir.name:
            raise ValueError(
                f"agent name '{manifest.name}' does not match directory '{agent_dir.name}'"
            )
        if not prompt_path.is_file():
            raise ValueError(f"agent '{manifest.name}' is missing prompt.md")
        registry[manifest.name] = LoadedAgent(
            manifest=manifest, prompt=prompt_path.read_text(), path=agent_dir
        )
    return registry
