"""Full consent-gate round-trip through the real worker logic with a fake executor."""

from pathlib import Path

import pytest

from octo import approvals, queue
from octo.executor import FakeExecutor
from octo.registry import load_registry
from octo.worker.main import process_once


@pytest.fixture
def gated_registry(tmp_path: Path):
    d = tmp_path / "gated-agent"
    d.mkdir()
    (d / "agent.yaml").write_text(
        "name: gated-agent\nrequires_approval: true\noutput:\n  dir: " + str(tmp_path / "out")
    )
    (d / "prompt.md").write_text("pretend to do something side-effectful")
    return load_registry(tmp_path)


async def test_gate_approve_resumes_and_completes(pool, gated_registry):
    fake = FakeExecutor()
    run_id = await queue.enqueue(pool, "gated-agent")

    # first claim parks the run at the gate — executor must NOT be called
    assert await process_once(pool, gated_registry, "w1", executors={"claude-sdk": fake}) is True
    assert (await queue.get_run(pool, run_id))["status"] == "awaiting_approval"
    assert fake.calls == []
    pending = await approvals.list_for_run(pool, run_id)
    assert len(pending) == 1 and pending[0]["status"] == "pending"

    # human approves -> requeued -> next claim executes
    await approvals.decide(pool, run_id, approved=True, via="cli", note="looks safe")
    assert (await queue.get_run(pool, run_id))["status"] == "queued"
    assert await process_once(pool, gated_registry, "w1", executors={"claude-sdk": fake}) is True
    final = await queue.get_run(pool, run_id)
    assert final["status"] == "completed"
    assert fake.calls == [{"run_id": run_id, "agent": "gated-agent"}]

    decided = (await approvals.list_for_run(pool, run_id))[0]
    assert decided["status"] == "approved"
    assert decided["decided_via"] == "cli"
    assert decided["note"] == "looks safe"


async def test_gate_reject_never_executes(pool, gated_registry):
    fake = FakeExecutor()
    run_id = await queue.enqueue(pool, "gated-agent")
    await process_once(pool, gated_registry, "w1", executors={"claude-sdk": fake})
    await approvals.decide(pool, run_id, approved=False, via="api", note="nope")
    final = await queue.get_run(pool, run_id)
    assert final["status"] == "rejected"
    assert final["finished_at"] is not None
    assert fake.calls == []


async def test_double_decision_is_an_error(pool, gated_registry):
    run_id = await queue.enqueue(pool, "gated-agent")
    await process_once(pool, gated_registry, "w1", executors={"claude-sdk": FakeExecutor()})
    await approvals.decide(pool, run_id, approved=True, via="cli")
    with pytest.raises(LookupError):
        await approvals.decide(pool, run_id, approved=True, via="cli")


async def test_ungated_agent_runs_straight_through(pool, tmp_path):
    d = tmp_path / "open-agent"
    d.mkdir()
    (d / "agent.yaml").write_text("name: open-agent\noutput:\n  dir: " + str(tmp_path / "out"))
    (d / "prompt.md").write_text("harmless")
    registry = load_registry(tmp_path)
    fake = FakeExecutor()
    run_id = await queue.enqueue(pool, "open-agent")
    assert await process_once(pool, registry, "w1", executors={"claude-sdk": fake}) is True
    assert (await queue.get_run(pool, run_id))["status"] == "completed"
    assert len(fake.calls) == 1


async def test_unknown_agent_fails_cleanly(pool, gated_registry):
    run_id = await queue.enqueue(pool, "ghost-agent")
    assert await process_once(pool, gated_registry, "w1") is True
    final = await queue.get_run(pool, run_id)
    assert final["status"] == "failed"
    assert "unknown agent" in final["error"]
