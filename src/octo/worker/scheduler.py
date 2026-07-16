"""DB-driven cron scheduler. Runs as a task inside the worker (RFC-0001 decision).

tick() claims due schedule rows with FOR UPDATE SKIP LOCKED, so N workers never
double-fire the same schedule. Misses while down fire once on restart.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from croniter import croniter
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from octo.registry import LoadedAgent


def compute_next(cron_expr: str, timezone: str = "UTC") -> datetime:
    now = datetime.now(ZoneInfo(timezone))
    return croniter(cron_expr, now).get_next(datetime)


async def tick(pool: AsyncConnectionPool) -> int:
    """Fire every due, enabled schedule exactly once. Returns runs enqueued."""
    fired = 0
    async with pool.connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            "SELECT * FROM schedules WHERE enabled AND next_run_at <= now() "
            "FOR UPDATE SKIP LOCKED"
        )
        due = await cur.fetchall()
        for s in due:
            row = await (
                await conn.execute(
                    "INSERT INTO runs (agent, trigger, params, schedule_id) "
                    "VALUES (%s, 'schedule', %s, %s) RETURNING id",
                    (s["agent"], Jsonb(s["params"]), s["id"]),
                )
            ).fetchone()
            run_id = str(row[0])
            await conn.execute(
                "INSERT INTO run_events (run_id, type, payload) VALUES (%s, 'status_change', %s)",
                (run_id, Jsonb({"from": None, "to": "queued", "trigger": "schedule"})),
            )
            await conn.execute(
                "UPDATE schedules SET next_run_at = %s, last_run_at = now(), last_run_id = %s "
                "WHERE id = %s",
                (compute_next(s["cron_expr"], s["timezone"]), run_id, s["id"]),
            )
            fired += 1
    return fired


async def sync_from_registry(
    pool: AsyncConnectionPool, registry: dict[str, LoadedAgent]
) -> list[str]:
    """Upsert each manifest's default schedule. Existing rows are left untouched
    (the DB row is the operator's knob; the manifest is only the default)."""
    created: list[str] = []
    async with pool.connection() as conn:
        for name, agent in registry.items():
            expr = agent.manifest.schedule
            if not expr:
                continue
            cur = await conn.execute(
                "INSERT INTO schedules (agent, cron_expr, params, next_run_at) "
                "VALUES (%s, %s, %s, %s) ON CONFLICT (agent, cron_expr) DO NOTHING",
                (name, expr, Jsonb(agent.manifest.params), compute_next(expr)),
            )
            if cur.rowcount:
                created.append(f"{name} @ {expr}")
    return created
