from octo.telemetry import llm_span, merge_tags, parse_tags_header


def test_merge_tags_manual_wins_and_coerces():
    merged = merge_tags(
        {"surface": "native", "routed": True, "skip_me": None},
        {"surface": "cli", "topic": 42},
    )
    assert merged["surface"] == "cli"  # manual wins
    assert merged["routed"] == "True"  # coerced to string
    assert merged["topic"] == "42"
    assert "skip_me" not in merged  # None dropped


def test_merge_tags_truncates():
    merged = merge_tags({}, {"k" * 100: "v" * 500})
    key = next(iter(merged))
    assert len(key) == 64
    assert len(merged[key]) == 200


def test_parse_tags_header():
    assert parse_tags_header("a=1,topic=infra research, b = x ") == {
        "a": "1",
        "topic": "infra research",
        "b": "x",
    }
    assert parse_tags_header(None) == {}
    assert parse_tags_header("garbage-no-equals,=novalue") == {}


async def test_llm_span_is_noop_without_endpoint():
    # settings.otel_exporter_otlp_endpoint defaults to "" — span must cost nothing
    async with llm_span("chat", provider="p", requested_model="m", tags={"a": "b"}) as obs:
        obs.update(actual_model="x", prompt_tokens=1)
    assert obs["actual_model"] == "x"  # obs is usable either way
