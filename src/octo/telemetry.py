"""Telemetry seam (ADR-0008) — the ONLY module that knows OpenTelemetry exists.

Every model request gets:
- a tags dict (auto-derived + caller-supplied) persisted to Postgres by the caller, and
- an OTEL span following the GenAI semantic conventions (gen_ai.*) — a no-op unless
  OTEL_EXPORTER_OTLP_ENDPOINT is configured, so local runs cost nothing.

Swapping/adding backends (Langfuse ingests OTLP) is a change to THIS file only.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from octo.config import settings

log = logging.getLogger("octo.telemetry")

_initialized = False
_tracer = None


def _get_tracer():
    """Lazy init: real OTLP tracer when an endpoint is configured, no-op otherwise."""
    global _initialized, _tracer
    if _initialized:
        return _tracer
    _initialized = True
    if not settings.otel_exporter_otlp_endpoint:
        _tracer = None
        return None
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(
            resource=Resource.create({"service.name": settings.otel_service_name})
        )
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=f"{settings.otel_exporter_otlp_endpoint}/v1/traces")
            )
        )
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("octo")
        log.info("telemetry: OTLP export to %s", settings.otel_exporter_otlp_endpoint)
    except Exception:
        log.exception("telemetry init failed — continuing without OTEL")
        _tracer = None
    return _tracer


def merge_tags(auto: dict[str, Any], manual: dict[str, Any] | None) -> dict[str, str]:
    """Auto-derived system facts + caller categories; manual wins on collision.
    Values coerced to short strings (tags are labels, not payloads)."""
    merged = {**auto, **(manual or {})}
    return {str(k)[:64]: str(v)[:200] for k, v in merged.items() if v is not None}


def parse_tags_header(raw: str | None) -> dict[str, str]:
    """X-Octo-Tags: 'k=v,k2=v2' (lenient; bad pairs skipped)."""
    tags: dict[str, str] = {}
    if not raw:
        return tags
    for pair in raw.split(","):
        k, sep, v = pair.partition("=")
        if sep and k.strip():
            tags[k.strip()] = v.strip()
    return tags


@asynccontextmanager
async def llm_span(
    operation: str,  # e.g. "chat", "chat_stream", "agent_run", "openai_compat"
    *,
    provider: str,
    requested_model: str,
    tags: dict[str, str],
) -> AsyncIterator[dict[str, Any]]:
    """Wraps one model request. Yields a mutable `obs` dict the caller fills in
    (actual_model, prompt_tokens, completion_tokens, tool_rounds, error) — recorded
    as GenAI-convention span attributes on exit."""
    obs: dict[str, Any] = {}
    tracer = _get_tracer()
    if tracer is None:
        yield obs
        return
    with tracer.start_as_current_span(f"octo.{operation}") as span:
        span.set_attribute("gen_ai.system", provider)
        span.set_attribute("gen_ai.request.model", requested_model)
        for k, v in tags.items():
            span.set_attribute(f"octo.tag.{k}", v)
        try:
            yield obs
        except Exception as exc:
            span.set_attribute("error.type", type(exc).__name__)
            raise
        finally:
            if obs.get("actual_model"):
                span.set_attribute("gen_ai.response.model", obs["actual_model"])
            if obs.get("prompt_tokens") is not None:
                span.set_attribute("gen_ai.usage.input_tokens", obs["prompt_tokens"])
            if obs.get("completion_tokens") is not None:
                span.set_attribute("gen_ai.usage.output_tokens", obs["completion_tokens"])
            if obs.get("tool_rounds"):
                span.set_attribute("octo.tool_rounds", obs["tool_rounds"])
            if obs.get("error"):
                span.set_attribute("error.type", str(obs["error"])[:200])
