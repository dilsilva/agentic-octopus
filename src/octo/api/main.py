"""FastAPI gateway. M0 ships /healthz only; run/approval/schedule routes land in M1."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from octo import __version__, db
from octo.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tolerate a missing DB at startup so the process (and unit tests) can come up;
    # /healthz reports the truth and compose ordering handles the real world.
    try:
        app.state.pool = await db.create_pool(settings.database_url)
    except Exception:
        app.state.pool = None
    yield
    if app.state.pool is not None:
        await app.state.pool.close()


def create_app() -> FastAPI:
    app = FastAPI(title="agentic-octopus", version=__version__, lifespan=lifespan)

    @app.get("/healthz")
    async def healthz():
        db_ok = False
        if app.state.pool is not None:
            try:
                async with app.state.pool.connection() as conn:
                    await conn.execute("SELECT 1")
                db_ok = True
            except Exception:
                db_ok = False
        return {"status": "ok", "version": __version__, "env": settings.octo_env, "db": db_ok}

    return app


app = create_app()
