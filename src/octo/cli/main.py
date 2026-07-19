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


chat_app = typer.Typer(
    help="Chat with the spine (ChatGPT-style, in your terminal)", invoke_without_command=True
)
app.add_typer(chat_app, name="chat")


def _print_stream(resp: httpx.Response) -> None:
    for line in resp.iter_lines():
        if not line.startswith("data: "):
            continue
        payload = line[6:].strip()
        if payload == "[DONE]":
            typer.echo("")
            return
        try:
            chunk = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if chunk.get("error"):
            typer.echo(f"\n[error] {chunk['error']}")
            return
        if chunk.get("tool_status"):
            ts = chunk["tool_status"]
            typer.echo(f"\n[{ts['tool']}: {json.dumps(ts['args'])[:80]}]")
            typer.echo("octo > ", nl=False)
            continue
        if chunk.get("done"):
            continue
        delta = (chunk.get("choices") or [{}])[0].get("delta", {})
        if delta.get("content"):
            typer.echo(delta["content"], nl=False)


@chat_app.callback()
def chat_repl(
    ctx: typer.Context,
    conversation: str | None = typer.Option(None, "--conversation", "-c", help="resume by id"),
    persona: str | None = typer.Option(None, "--persona"),
) -> None:
    """Interactive chat. Commands inside: /new, /list, /quit."""
    if ctx.invoked_subcommand is not None:
        return
    with _client() as c:
        if conversation is None:
            r = c.post("/chat/conversations", json={"persona": persona} if persona else {})
            r.raise_for_status()
            conversation = r.json()["id"]
            typer.echo(f"(new conversation {conversation} — /new, /list, /quit)")
        while True:
            try:
                text = typer.prompt("you", prompt_suffix=" > ")
            except (KeyboardInterrupt, EOFError):
                typer.echo("\nbye")
                return
            if text.strip() == "/quit":
                return
            if text.strip() == "/new":
                conversation = c.post("/chat/conversations", json={}).json()["id"]
                typer.echo(f"(new conversation {conversation})")
                continue
            if text.strip() == "/list":
                for row in c.get("/chat/conversations").json()[:10]:
                    typer.echo(f"{row['id']}  {row['message_count']:>3} msgs  {row['title']}")
                continue
            typer.echo("octo > ", nl=False)
            with c.stream(
                "POST",
                f"/chat/conversations/{conversation}/messages",
                json={"content": text, "stream": True},
                timeout=300,
            ) as resp:
                if resp.status_code != 200:
                    resp.read()
                    typer.echo(f"[{resp.status_code}] {resp.text[:300]}")
                    continue
                _print_stream(resp)


@chat_app.command("list")
def chat_list() -> None:
    """List conversations."""
    with _client() as c:
        for row in c.get("/chat/conversations").json():
            typer.echo(
                f"{row['id']}  {row['message_count']:>3} msgs  "
                f"{row['updated_at'][:16]}  {row['title'] or '(untitled)'}"
            )


@chat_app.command("show")
def chat_show(conversation_id: str) -> None:
    """Print a conversation's messages."""
    with _client() as c:
        for m in c.get(f"/chat/conversations/{conversation_id}/messages").json():
            typer.echo(f"\n[{m['role']}]")
            typer.echo(m["content"])


@chat_app.command("usage")
def chat_usage() -> None:
    """Today's free-tier request burn."""
    with _client() as c:
        _echo(c.get("/chat/usage").json())


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
