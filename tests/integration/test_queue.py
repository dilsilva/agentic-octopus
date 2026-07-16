"""The SKIP LOCKED proof — the property the whole spine sits on."""

import asyncio

from octo import queue
from octo.models import RunStatus


async def test_claim_returns_none_on_empty_queue(pool):
    assert await queue.claim(pool, "w1") is None


async def test_fifo_claim_and_finish(pool):
    first = await queue.enqueue(pool, "research-brief")
    second = await queue.enqueue(pool, "research-brief")
    run = await queue.claim(pool, "w1")
    assert str(run["id"]) == first
    assert run["status"] == "running"
    assert run["attempts"] == 1
    await queue.finish(pool, first, RunStatus.COMPLETED, result="done", cost_usd=0.01)
    done = await queue.get_run(pool, first)
    assert done["status"] == "completed"
    assert done["result"] == "done"
    assert done["finished_at"] is not None
    # audit trail exists for the full lifecycle
    events = await queue.list_events(pool, first)
    changes = [e["payload"]["to"] for e in events if e["type"] == "status_change"]
    assert changes == ["queued", "running", "completed"]
    # second run untouched
    assert (await queue.get_run(pool, second))["status"] == "queued"


async def test_concurrent_claims_never_collide(pool):
    ids = {await queue.enqueue(pool, "research-brief") for _ in range(5)}
    claimed = await asyncio.gather(*(queue.claim(pool, f"w{i}") for i in range(8)))
    got = [str(r["id"]) for r in claimed if r is not None]
    assert len(got) == 5, "exactly the 5 queued runs are claimed"
    assert len(set(got)) == 5, "no run claimed twice"
    assert set(got) == ids
    assert claimed.count(None) == 3, "excess claimers get None, never a duplicate"


async def test_lease_expiry_requeues_then_fails(pool):
    run_id = await queue.enqueue(pool, "research-brief", max_attempts=2)
    # claim with an instantly-expired lease (simulates a crashed worker)
    run = await queue.claim(pool, "w1", lease_minutes=0)
    assert str(run["id"]) == run_id
    assert await queue.reap_expired(pool) == 1
    assert (await queue.get_run(pool, run_id))["status"] == "queued"
    # second crash exhausts attempts -> failed
    await queue.claim(pool, "w1", lease_minutes=0)
    assert await queue.reap_expired(pool) == 1
    dead = await queue.get_run(pool, run_id)
    assert dead["status"] == "failed"
    assert "lease expired" in dead["error"]


async def test_heartbeat_only_works_for_owner(pool):
    run_id = await queue.enqueue(pool, "research-brief")
    await queue.claim(pool, "w1")
    assert await queue.heartbeat(pool, run_id, "w1") is True
    assert await queue.heartbeat(pool, run_id, "intruder") is False
