"""`octo` CLI — thin client over the API. M0 ships health + db upgrade; run/approve land in M1."""

import httpx
import typer

from octo.config import settings

app = typer.Typer(help="agentic-octopus control CLI", no_args_is_help=True)


@app.command()
def health() -> None:
    """Check the API's health endpoint."""
    r = httpx.get(f"{settings.octo_api_url}/healthz", timeout=10)
    r.raise_for_status()
    typer.echo(r.json())


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
