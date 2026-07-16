"""`octo` CLI — thin httpx client over the API (except `db upgrade`, which is direct)."""

import json
import time

import httpx
import typer

from octo.config import settings

app = typer.Typer(help="agentic-octopus control CLI", no_args_is_help=True)

TERMINAL_STATES = {"completed", "failed", "rejected", "cancelled"}


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=settings.octo_api_url,
        headers={"Authorization": f"Bearer {settings.octo_api_token}"},
        timeout=30,
    )


def _echo(data) -> None:
    typer.echo(json.dumps(data, indent=2, default=str))


@app.command()
def health() -> None:
    """Check the API's health endpoint."""
    r = httpx.get(f"{settings.octo_api_url}/healthz", timeout=10)
    r.raise_for_status()
    _echo(r.json())


@app.command()
def agents() -> None:
    """List registered agents."""
    with _client() as c:
        r = c.get("/agents")
        r.raise_for_status()
        _echo(r.json())


@app.command()
def run(
    agent: str,
    param: list[str] = typer.Option([], "--param", "-p", help="k=v, repeatable"),
    follow: bool = typer.Option(False, "--follow", "-f", help="poll until the run finishes"),
) -> None:
    """Trigger an agent run."""
    params = {}
    for p in param:
        k, _, v = p.partition("=")
        params[k] = v
    with _client() as c:
        r = c.post(f"/agents/{agent}/run", json={"params": params})
        r.raise_for_status()
        run_id = r.json()["run_id"]
        typer.echo(f"run_id: {run_id}")
        if not follow:
            return
        last = None
        while True:
            status = c.get(f"/runs/{run_id}").json()["status"]
            if status != last:
                typer.echo(f"status: {status}")
                last = status
            if status in TERMINAL_STATES:
                _echo(c.get(f"/runs/{run_id}").json())
                return
            if status == "awaiting_approval":
                typer.echo(f"→ approve with: octo approve {run_id}")
            time.sleep(2)


@app.command()
def runs(
    status: str | None = typer.Option(None),
    agent: str | None = typer.Option(None),
    limit: int = typer.Option(20),
) -> None:
    """List recent runs."""
    with _client() as c:
        r = c.get(
            "/runs",
            params={
                k: v
                for k, v in {"status": status, "agent": agent, "limit": limit}.items()
                if v is not None
            },
        )
        r.raise_for_status()
        for row in r.json():
            typer.echo(
                f"{row['id']}  {row['agent']:<20} {row['status']:<18} "
                f"{row['trigger']:<8} {row['created_at']}"
            )


@app.command()
def status(run_id: str) -> None:
    """Show one run."""
    with _client() as c:
        r = c.get(f"/runs/{run_id}")
        r.raise_for_status()
        _echo(r.json())


@app.command()
def logs(run_id: str) -> None:
    """Print a run's event stream (audit trail)."""
    with _client() as c:
        r = c.get(f"/runs/{run_id}/events")
        r.raise_for_status()
        for ev in r.json():
            typer.echo(f"{ev['ts']}  {ev['type']:<14} {json.dumps(ev['payload'], default=str)}")


@app.command()
def approve(run_id: str, note: str | None = typer.Option(None)) -> None:
    """Approve a run parked at a consent gate."""
    with _client() as c:
        r = c.post(f"/runs/{run_id}/approve", json={"note": note})
        r.raise_for_status()
        _echo(r.json())


@app.command()
def reject(run_id: str, note: str | None = typer.Option(None)) -> None:
    """Reject a run parked at a consent gate."""
    with _client() as c:
        r = c.post(f"/runs/{run_id}/reject", json={"note": note})
        r.raise_for_status()
        _echo(r.json())


schedule_app = typer.Typer(help="Manage schedules")
app.add_typer(schedule_app, name="schedule")


@schedule_app.command("list")
def schedule_list() -> None:
    with _client() as c:
        r = c.get("/schedules")
        r.raise_for_status()
        for s in r.json():
            state = "on " if s["enabled"] else "off"
            typer.echo(
                f"{s['id']}  [{state}] {s['agent']:<20} {s['cron_expr']:<15} "
                f"next={s['next_run_at']}"
            )


@schedule_app.command("sync")
def schedule_sync() -> None:
    """Upsert default schedules from agent manifests."""
    with _client() as c:
        r = c.post("/schedules/sync")
        r.raise_for_status()
        _echo(r.json())


@schedule_app.command("toggle")
def schedule_toggle(schedule_id: str) -> None:
    with _client() as c:
        r = c.post(f"/schedules/{schedule_id}/toggle")
        r.raise_for_status()
        _echo(r.json())


db_app = typer.Typer(help="Database operations (talks to the DB directly, not the API)")
app.add_typer(db_app, name="db")


@db_app.command()
def upgrade() -> None:
    """Apply pending migrations."""
    from octo import db as _db

    applied = _db.upgrade(settings.database_url)
    typer.echo(f"applied: {applied or 'nothing — up to date'}")


if __name__ == "__main__":
    app()
