"""Worker: claims runs, enforces pre-execution gates, executes via the agent's executor,
persists everything. process_once() is the testable unit; main() is the loop around it.
"""

import asyncio
import logging
import socket
import uuid
from pathlib import Path

from psycopg_pool import AsyncConnectionPool

from octo import approvals, db, queue
from octo.config import settings
from octo.executor import AgentExecutor, ExecOutcome, get_executor
from octo.models import RunStatus
from octo.registry import LoadedAgent, load_registry
from octo.telemetry import llm_span, merge_tags
from octo.worker import scheduler

log = logging.getLogger("octo.worker")

HEARTBEAT_SECONDS = 60
POLL_SECONDS = 2
SCHEDULER_SECONDS = 30


async def process_once(
    pool: AsyncConnectionPool,
    registry: dict[str, LoadedAgent],
    worker_id: str,
    executors: dict[str, AgentExecutor] | None = None,
) -> bool:
    """Claim and fully handle one run. Returns False if the queue was empty."""
    run = await queue.claim(pool, worker_id)
    if run is None:
        return False
    run_id = str(run["id"])

    agent = registry.get(run["agent"])
    if agent is None:
        await queue.finish(pool, run_id, RunStatus.FAILED, error=f"unknown agent '{run['agent']}'")
        return True

    m = agent.manifest
    # Pre-execution consent gate (ADR-0005): park until a human approves.
    if m.requires_approval and not await approvals.has_approved(pool, run_id):
        await approvals.request(
            pool, run_id, action=f"execute agent '{m.name}'", payload={"params": run["params"]}
        )
        log.info("run %s parked awaiting approval (agent=%s)", run_id, m.name)
        return True

    executor = (executors or {}).get(m.executor) or get_executor(m.executor)
    workdir = Path(m.output.dir)
    workdir.mkdir(parents=True, exist_ok=True)

    async def on_event(type_: str, payload: dict) -> None:
        await queue.record_event_pooled(pool, run_id, type_, payload)

    async def keep_lease() -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            if not await queue.heartbeat(pool, run_id, worker_id):
                log.warning("lost lease on run %s", run_id)
                return

    tags = merge_tags(
        {
            "surface": "worker",
            "agent": m.name,
            "executor": m.executor,
            "trigger": run["trigger"],
        },
        run.get("tags"),
    )
    hb = asyncio.create_task(keep_lease())
    try:
        async with llm_span(
            "agent_run", provider=m.executor, requested_model=m.model, tags=tags
        ) as obs:
            outcome = await executor.execute(run, agent, workdir, on_event)
            obs.update(actual_model=outcome.model, error=outcome.error)
    except Exception as exc:  # executor bugs must not kill the worker
        log.exception("executor crashed on run %s", run_id)
        outcome = ExecOutcome(status="failed", error=repr(exc))
    finally:
        hb.cancel()

    await queue.finish(
        pool,
        run_id,
        RunStatus.COMPLETED if outcome.status == "completed" else RunStatus.FAILED,
        result=outcome.result,
        error=outcome.error,
        cost_usd=outcome.cost_usd,
        session_id=outcome.session_id,
    )
    if outcome.model:
        tags["model"] = outcome.model
    async with pool.connection() as conn:
        from psycopg.types.json import Jsonb

        await conn.execute("UPDATE runs SET tags = %s WHERE id = %s", (Jsonb(tags), run_id))
    log.info("run %s %s (agent=%s cost=%s)", run_id, outcome.status, m.name, outcome.cost_usd)
    return True


async def scheduler_loop(pool: AsyncConnectionPool) -> None:
    while True:
        try:
            fired = await scheduler.tick(pool)
            if fired:
                log.info("scheduler enqueued %d run(s)", fired)
        except Exception:
            log.exception("scheduler tick failed")
        await asyncio.sleep(SCHEDULER_SECONDS)


async def main() -> None:
    logging.basicConfig(level=settings.log_level.upper())
    pool = await db.create_pool(settings.database_url)
    registry = load_registry(Path(settings.agents_dir))
    worker_id = f"{socket.gethostname()}-{uuid.uuid4().hex[:6]}"
    log.info("worker %s up — %d agent(s): %s", worker_id, len(registry), sorted(registry))

    sched_task = None
    if settings.scheduler_enabled:
        await scheduler.sync_from_registry(pool, registry)
        sched_task = asyncio.create_task(scheduler_loop(pool))

    try:
        while True:
            did_work = await process_once(pool, registry, worker_id)
            if not did_work:
                await queue.reap_expired(pool)
                await asyncio.sleep(POLL_SECONDS)
    finally:
        if sched_task:
            sched_task.cancel()
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
