"""The Postgres-backed run queue (ADR-0003). A run row IS the queue item.

All functions take an open AsyncConnectionPool. Claiming uses FOR UPDATE SKIP LOCKED so
N workers never take the same run; leases + the reaper make crashed workers safe.
"""

from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from octo.models import RunStatus, transition

DEFAULT_LEASE_MINUTES = 15


async def enqueue(
    pool: AsyncConnectionPool,
    agent: str,
    *,
    trigger: str = "api",
    params: dict | None = None,
    schedule_id: str | None = None,
    max_attempts: int = 1,
    tags: dict | None = None,
) -> str:
    async with pool.connection() as conn:
        row = await (
            await conn.execute(
                "INSERT INTO runs (agent, trigger, params, schedule_id, max_attempts, tags) "
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (agent, trigger, Jsonb(params or {}), schedule_id, max_attempts, Jsonb(tags or {})),
            )
        ).fetchone()
        run_id = str(row[0])
        await conn.execute(
            "INSERT INTO run_events (run_id, type, payload) VALUES (%s, 'status_change', %s)",
            (run_id, Jsonb({"from": None, "to": "queued", "trigger": trigger})),
        )
        return run_id


async def claim(
    pool: AsyncConnectionPool,
    worker_id: str,
    lease_minutes: int = DEFAULT_LEASE_MINUTES,
) -> dict[str, Any] | None:
    """Atomically claim the oldest available queued run. None if the queue is empty."""
    async with pool.connection() as conn:
        # row_factory goes on the cursor, never the pooled connection (it would leak
        # into unrelated queries when the connection is reused)
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            """
            UPDATE runs SET status = 'running', locked_by = %(worker)s,
                   attempts = attempts + 1,
                   started_at = COALESCE(started_at, now()),
                   lease_expires_at = now() + make_interval(mins => %(lease)s)
            WHERE id = (SELECT id FROM runs
                        WHERE status = 'queued' AND available_at <= now()
                        ORDER BY created_at LIMIT 1
                        FOR UPDATE SKIP LOCKED)
            RETURNING *
            """,
            {"worker": worker_id, "lease": lease_minutes},
        )
        run = await cur.fetchone()
        if run is None:
            return None
        await conn.execute(
            "INSERT INTO run_events (run_id, type, payload) VALUES (%s, 'status_change', %s)",
            (run["id"], Jsonb({"from": "queued", "to": "running", "worker": worker_id})),
        )
        return run


async def heartbeat(
    pool: AsyncConnectionPool,
    run_id: str,
    worker_id: str,
    lease_minutes: int = DEFAULT_LEASE_MINUTES,
) -> bool:
    """Extend the lease on a running run. False if we no longer own it."""
    async with pool.connection() as conn:
        cur = await conn.execute(
            "UPDATE runs SET lease_expires_at = now() + make_interval(mins => %s) "
            "WHERE id = %s AND status = 'running' AND locked_by = %s",
            (lease_minutes, run_id, worker_id),
        )
        return cur.rowcount == 1


async def finish(
    pool: AsyncConnectionPool,
    run_id: str,
    status: RunStatus,
    *,
    result: str | None = None,
    error: str | None = None,
    cost_usd: float | None = None,
    session_id: str | None = None,
) -> None:
    assert status in (RunStatus.COMPLETED, RunStatus.FAILED)
    async with pool.connection() as conn:
        await transition(
            conn,
            run_id,
            RunStatus.RUNNING,
            status,
            extra_set=(
                ", result = %(result)s, error = %(error)s, cost_usd = %(cost_usd)s, "
                "session_id = COALESCE(%(session_id)s, session_id), "
                "finished_at = now(), locked_by = NULL, lease_expires_at = NULL"
            ),
            extra_params={
                "result": result,
                "error": error,
                "cost_usd": cost_usd,
                "session_id": session_id,
            },
            event_payload={"error": error} if error else None,
        )


async def park_awaiting_approval(pool: AsyncConnectionPool, run_id: str) -> None:
    async with pool.connection() as conn:
        await transition(
            conn,
            run_id,
            RunStatus.RUNNING,
            RunStatus.AWAITING_APPROVAL,
            extra_set=", locked_by = NULL, lease_expires_at = NULL, attempts = attempts - 1",
        )


async def reap_expired(pool: AsyncConnectionPool) -> int:
    """Requeue running runs whose lease expired (crashed worker); fail them once
    attempts are exhausted. Returns how many rows were touched."""
    async with pool.connection() as conn:
        requeued = await conn.execute(
            """
            WITH expired AS (
                SELECT id FROM runs
                WHERE status = 'running' AND lease_expires_at < now()
                      AND attempts < max_attempts
                FOR UPDATE SKIP LOCKED
            )
            UPDATE runs SET status = 'queued', locked_by = NULL, lease_expires_at = NULL
            FROM expired WHERE runs.id = expired.id
            RETURNING runs.id
            """
        )
        requeued_ids = [str(r[0]) for r in await requeued.fetchall()]
        failed = await conn.execute(
            """
            WITH dead AS (
                SELECT id FROM runs
                WHERE status = 'running' AND lease_expires_at < now()
                      AND attempts >= max_attempts
                FOR UPDATE SKIP LOCKED
            )
            UPDATE runs SET status = 'failed', error = 'lease expired; attempts exhausted',
                   locked_by = NULL, lease_expires_at = NULL, finished_at = now()
            FROM dead WHERE runs.id = dead.id
            RETURNING runs.id
            """
        )
        failed_ids = [str(r[0]) for r in await failed.fetchall()]
        for rid in requeued_ids:
            await record_event(
                conn,
                rid,
                "status_change",
                {"from": "running", "to": "queued", "reason": "lease_expired"},
            )
        for rid in failed_ids:
            await record_event(
                conn,
                rid,
                "status_change",
                {"from": "running", "to": "failed", "reason": "lease_expired"},
            )
        return len(requeued_ids) + len(failed_ids)


async def record_event(conn, run_id: str, type_: str, payload: dict) -> None:
    await conn.execute(
        "INSERT INTO run_events (run_id, type, payload) VALUES (%s, %s, %s)",
        (run_id, type_, Jsonb(payload)),
    )


async def record_event_pooled(
    pool: AsyncConnectionPool, run_id: str, type_: str, payload: dict
) -> None:
    async with pool.connection() as conn:
        await record_event(conn, run_id, type_, payload)


async def get_run(pool: AsyncConnectionPool, run_id: str) -> dict[str, Any] | None:
    async with pool.connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute("SELECT * FROM runs WHERE id = %s", (run_id,))
        return await cur.fetchone()


async def list_runs(
    pool: AsyncConnectionPool,
    *,
    status: str | None = None,
    agent: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    async with pool.connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            "SELECT * FROM runs "
            "WHERE (%(status)s::text IS NULL OR status = %(status)s) "
            "  AND (%(agent)s::text IS NULL OR agent = %(agent)s) "
            "ORDER BY created_at DESC LIMIT %(limit)s",
            {"status": status, "agent": agent, "limit": limit},
        )
        return await cur.fetchall()


async def list_events(pool: AsyncConnectionPool, run_id: str) -> list[dict[str, Any]]:
    async with pool.connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            "SELECT id, ts, type, payload FROM run_events WHERE run_id = %s ORDER BY id",
            (run_id,),
        )
        return await cur.fetchall()
