"""Run state machine. Every status change goes through transition() — no scattered UPDATEs.

States and legal transitions per RFC-0001:

    queued -> running (claim)          running -> completed | failed
    running -> awaiting_approval       awaiting_approval -> queued (approve) | rejected
    running -> queued (lease expired)  queued | awaiting_approval -> cancelled
"""

from enum import StrEnum

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


TERMINAL = {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.REJECTED, RunStatus.CANCELLED}

ALLOWED_TRANSITIONS: set[tuple[RunStatus, RunStatus]] = {
    (RunStatus.QUEUED, RunStatus.RUNNING),
    (RunStatus.RUNNING, RunStatus.COMPLETED),
    (RunStatus.RUNNING, RunStatus.FAILED),
    (RunStatus.RUNNING, RunStatus.AWAITING_APPROVAL),
    (RunStatus.RUNNING, RunStatus.QUEUED),  # lease expiry requeue
    (RunStatus.AWAITING_APPROVAL, RunStatus.QUEUED),  # approved
    (RunStatus.AWAITING_APPROVAL, RunStatus.REJECTED),
    (RunStatus.QUEUED, RunStatus.CANCELLED),
    (RunStatus.AWAITING_APPROVAL, RunStatus.CANCELLED),
}


class IllegalTransition(Exception):
    pass


def assert_transition(from_status: RunStatus, to_status: RunStatus) -> None:
    if (from_status, to_status) not in ALLOWED_TRANSITIONS:
        raise IllegalTransition(f"{from_status} -> {to_status} is not a legal run transition")


async def transition(
    conn: AsyncConnection,
    run_id: str,
    from_status: RunStatus,
    to_status: RunStatus,
    *,
    extra_set: str = "",
    extra_params: dict | None = None,
    event_payload: dict | None = None,
) -> None:
    """Atomically move a run between states and record the audit event.

    Raises IllegalTransition if the pair is not allowed or the row was not in
    from_status (someone else got there first — callers must treat that as a conflict).
    """
    assert_transition(from_status, to_status)
    params = {"run_id": run_id, "from": from_status.value, "to": to_status.value}
    params.update(extra_params or {})
    cur = await conn.execute(
        f"UPDATE runs SET status = %(to)s{extra_set} "  # noqa: S608 - extra_set is code-owned
        "WHERE id = %(run_id)s AND status = %(from)s",
        params,
    )
    if cur.rowcount != 1:
        raise IllegalTransition(f"run {run_id} was not in {from_status} (concurrent change?)")
    await conn.execute(
        "INSERT INTO run_events (run_id, type, payload) VALUES (%s, 'status_change', %s)",
        (
            run_id,
            Jsonb({"from": from_status.value, "to": to_status.value, **(event_payload or {})}),
        ),
    )
