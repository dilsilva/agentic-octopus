"""Consent gates as data (ADR-0005). Shared by API, CLI, and worker paths.

A pending approvals row parks its run in awaiting_approval. Deciding it moves the run
back to queued (approved — the next claim proceeds) or to rejected. Agents never call
decide(); only humans do, via API/CLI (hard rule in CLAUDE.md).
"""

from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from octo import queue
from octo.models import RunStatus, transition


async def request(
    pool: AsyncConnectionPool,
    run_id: str,
    action: str,
    payload: dict | None = None,
) -> str:
    """Create a pending approval and park the (running) run. Returns the approval id."""
    async with pool.connection() as conn:
        row = await (
            await conn.execute(
                "INSERT INTO approvals (run_id, action, payload) VALUES (%s, %s, %s) RETURNING id",
                (run_id, action, Jsonb(payload or {})),
            )
        ).fetchone()
        approval_id = str(row[0])
        await transition(
            conn,
            run_id,
            RunStatus.RUNNING,
            RunStatus.AWAITING_APPROVAL,
            extra_set=", locked_by = NULL, lease_expires_at = NULL, attempts = attempts - 1",
            event_payload={"approval_id": approval_id, "action": action},
        )
        return approval_id


async def has_approved(pool: AsyncConnectionPool, run_id: str) -> bool:
    async with pool.connection() as conn:
        row = await (
            await conn.execute(
                "SELECT 1 FROM approvals WHERE run_id = %s AND status = 'approved' LIMIT 1",
                (run_id,),
            )
        ).fetchone()
        return row is not None


async def decide(
    pool: AsyncConnectionPool,
    run_id: str,
    *,
    approved: bool,
    via: str,
    note: str | None = None,
) -> None:
    """Decide the pending approval for a run and move the run accordingly.

    Raises LookupError if the run has no pending approval.
    """
    new_status = "approved" if approved else "rejected"
    async with pool.connection() as conn:
        cur = await conn.execute(
            "UPDATE approvals SET status = %s, decided_at = now(), decided_via = %s, note = %s "
            "WHERE run_id = %s AND status = 'pending'",
            (new_status, via, note, run_id),
        )
        if cur.rowcount == 0:
            raise LookupError(f"run {run_id} has no pending approval")
        await transition(
            conn,
            run_id,
            RunStatus.AWAITING_APPROVAL,
            RunStatus.QUEUED if approved else RunStatus.REJECTED,
            extra_set="" if approved else ", finished_at = now()",
            event_payload={"decided_via": via, "note": note},
        )


async def list_for_run(pool: AsyncConnectionPool, run_id: str) -> list[dict[str, Any]]:
    async with pool.connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            "SELECT * FROM approvals WHERE run_id = %s ORDER BY requested_at", (run_id,)
        )
        return await cur.fetchall()


# re-export for callers that already import approvals
__all__ = ["request", "has_approved", "decide", "list_for_run", "queue"]
