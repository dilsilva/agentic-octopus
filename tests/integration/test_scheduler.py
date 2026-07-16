import asyncio
from pathlib import Path

from octo.registry import load_registry
from octo.worker import scheduler

REPO_AGENTS = Path(__file__).resolve().parents[2] / "agents"


async def test_sync_upserts_manifest_schedules_once(pool):
    registry = load_registry(REPO_AGENTS)
    created = await scheduler.sync_from_registry(pool, registry)
    assert any("research-brief" in c for c in created)
    assert await scheduler.sync_from_registry(pool, registry) == []  # idempotent


async def test_due_schedule_fires_exactly_once(pool):
    async with pool.connection() as conn:
        await conn.execute(
            "INSERT INTO schedules (agent, cron_expr, next_run_at) "
            "VALUES ('research-brief', '* * * * *', now() - interval '1 minute')"
        )
    # concurrent ticks (two workers) must not double-fire
    fired = await asyncio.gather(scheduler.tick(pool), scheduler.tick(pool))
    assert sum(fired) == 1
    async with pool.connection() as conn:
        row = await (await conn.execute("SELECT count(*), min(trigger) FROM runs")).fetchone()
    assert row[0] == 1 and row[1] == "schedule"
    # next_run_at advanced into the future -> immediate re-tick fires nothing
    assert await scheduler.tick(pool) == 0


async def test_disabled_schedule_never_fires(pool):
    async with pool.connection() as conn:
        await conn.execute(
            "INSERT INTO schedules (agent, cron_expr, enabled, next_run_at) "
            "VALUES ('research-brief', '* * * * *', false, now() - interval '1 minute')"
        )
    assert await scheduler.tick(pool) == 0
