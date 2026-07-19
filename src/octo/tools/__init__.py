"""Core-owned chat tools (ADR-0007 fast-follow): capabilities live in the spine,
available to every surface — never only inside a UI container."""

from octo.tools.web import TOOL_REGISTRY, run_tool

__all__ = ["TOOL_REGISTRY", "run_tool"]
