"""API routes. Thin: business logic lives in queue.py / approvals.py / scheduler.py
so the worker and CLI share it."""

from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from octo import approvals, queue
from octo.api.auth import require_token
from octo.models import IllegalTransition
from octo.worker import scheduler

router = APIRouter(dependencies=[Depends(require_token)])


def _pool(request: Request):
    pool = request.app.state.pool
    if pool is None:
        raise HTTPException(status_code=503, detail="database unavailable")
    return pool


# --- agents ---------------------------------------------------------------


@router.get("/agents", tags=["agents"], summary="List registered agents")
async def list_agents(request: Request):
    registry = request.app.state.registry
    return [
        {
            "name": a.manifest.name,
            "description": a.manifest.description,
            "executor": a.manifest.executor,
            "model": a.manifest.model,
            "requires_approval": a.manifest.requires_approval,
            "schedule": a.manifest.schedule,
        }
        for a in registry.values()
    ]


class RunRequest(BaseModel):
    params: dict = {}


@router.post(
    "/agents/{name}/run", status_code=202, tags=["agents"], summary="Enqueue a run for an agent"
)
async def run_agent(name: str, body: RunRequest, request: Request):
    if name not in request.app.state.registry:
        raise HTTPException(status_code=404, detail=f"unknown agent '{name}'")
    run_id = await queue.enqueue(_pool(request), name, trigger="api", params=body.params)
    return {"run_id": run_id, "status": "queued"}


# --- runs -----------------------------------------------------------------


@router.get("/runs", tags=["runs"], summary="List recent runs")
async def list_runs(
    request: Request, status: str | None = None, agent: str | None = None, limit: int = 50
):
    return await queue.list_runs(_pool(request), status=status, agent=agent, limit=min(limit, 500))


@router.get("/runs/{run_id}", tags=["runs"], summary="Get one run")
async def get_run(run_id: str, request: Request):
    run = await queue.get_run(_pool(request), run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@router.get("/runs/{run_id}/events", tags=["runs"], summary="Run audit trail (events)")
async def get_run_events(run_id: str, request: Request):
    return await queue.list_events(_pool(request), run_id)


class DecisionRequest(BaseModel):
    note: str | None = None


@router.post("/runs/{run_id}/approve", tags=["runs"], summary="Approve a gated run")
async def approve_run(run_id: str, body: DecisionRequest, request: Request):
    return await _decide(request, run_id, approved=True, note=body.note)


@router.post("/runs/{run_id}/reject", tags=["runs"], summary="Reject a gated run")
async def reject_run(run_id: str, body: DecisionRequest, request: Request):
    return await _decide(request, run_id, approved=False, note=body.note)


async def _decide(request: Request, run_id: str, *, approved: bool, note: str | None):
    try:
        await approvals.decide(_pool(request), run_id, approved=approved, via="api", note=note)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"run_id": run_id, "decision": "approved" if approved else "rejected"}


# --- schedules --------------------------------------------------------------


@router.get("/schedules", tags=["schedules"], summary="List schedules")
async def list_schedules(request: Request):
    async with _pool(request).connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute("SELECT * FROM schedules ORDER BY agent, cron_expr")
        return await cur.fetchall()


class ScheduleRequest(BaseModel):
    agent: str
    cron_expr: str
    timezone: str = "UTC"
    params: dict = {}


@router.post("/schedules", status_code=201, tags=["schedules"], summary="Create/enable a schedule")
async def create_schedule(body: ScheduleRequest, request: Request):
    if body.agent not in request.app.state.registry:
        raise HTTPException(status_code=404, detail=f"unknown agent '{body.agent}'")
    from croniter import croniter

    if not croniter.is_valid(body.cron_expr):
        raise HTTPException(status_code=422, detail=f"invalid cron expression {body.cron_expr!r}")
    async with _pool(request).connection() as conn:
        row = await (
            await conn.execute(
                "INSERT INTO schedules (agent, cron_expr, timezone, params, next_run_at) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (agent, cron_expr) DO UPDATE SET enabled = true "
                "RETURNING id",
                (
                    body.agent,
                    body.cron_expr,
                    body.timezone,
                    Jsonb(body.params),
                    scheduler.compute_next(body.cron_expr, body.timezone),
                ),
            )
        ).fetchone()
    return {"schedule_id": str(row[0])}


@router.post(
    "/schedules/sync", tags=["schedules"], summary="Upsert default schedules from agent manifests"
)
async def sync_schedules(request: Request):
    created = await scheduler.sync_from_registry(_pool(request), request.app.state.registry)
    return {"created": created}


@router.post(
    "/schedules/{schedule_id}/toggle", tags=["schedules"], summary="Enable/disable a schedule"
)
async def toggle_schedule(schedule_id: str, request: Request):
    async with _pool(request).connection() as conn:
        row = await (
            await conn.execute(
                "UPDATE schedules SET enabled = NOT enabled WHERE id = %s RETURNING enabled",
                (schedule_id,),
            )
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="schedule not found")
    return {"schedule_id": schedule_id, "enabled": row[0]}
