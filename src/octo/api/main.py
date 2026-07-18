"""FastAPI gateway: /healthz (open) + authenticated agent/run/schedule routes."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from octo import __version__, db
from octo.api.chat_routes import router as chat_router
from octo.api.openai_compat import router as openai_router
from octo.api.routes import router
from octo.config import settings
from octo.registry import load_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tolerate a missing DB at startup so the process (and unit tests) can come up;
    # /healthz reports the truth and compose ordering handles the real world.
    try:
        app.state.pool = await db.create_pool(settings.database_url)
    except Exception:
        app.state.pool = None
    app.state.registry = load_registry(Path(settings.agents_dir))
    yield
    if app.state.pool is not None:
        await app.state.pool.close()


DESCRIPTION = """
The **spine** for personal agentic applications: one orchestration service every agent
plugs into — triggering (API + cron schedules), a durable Postgres-backed run queue,
human **approval gates**, full audit trail, and multi-surface **chat**.

### Authentication
All routes except `/healthz` require `Authorization: Bearer <token>`:

| Token | Scope |
|---|---|
| `OCTO_API_TOKEN` | admin — everything |
| `OCTO_CHAT_TOKEN` | chat surfaces only (`/chat/*`, `/v1/*`) — hand this to chat UIs |

### Model routing
`octo/auto` (the default) smart-routes across healthy **free** models with server-side
fallback. Explicit model ids are honored as-is; non-free models are refused unless the
operator opted in (`OPENROUTER_ALLOW_PAID`) or selected `octo/claude` with an Anthropic
key configured.

### Surfaces
- **Native API** (this spec): agents, runs, approvals, schedules, chat.
- **`/v1`** — OpenAI-compatible *protocol namespace* (not a version): plug in any
  OpenAI-protocol client (Open WebUI, SDKs). Plain completions; tool fields stripped.

Full design: `docs/rfcs/0001-agentic-octopus-the-spine.md` · Decisions: `docs/adr/`
"""

TAGS = [
    {"name": "system", "description": "Health and service metadata"},
    {"name": "agents", "description": "Declarative agent definitions and run triggering"},
    {"name": "runs", "description": "Run lifecycle, audit events, and approval gates"},
    {"name": "schedules", "description": "Cron schedules that enqueue runs"},
    {"name": "chat", "description": "Spine-owned conversations (stateful, all UIs share them)"},
    {"name": "openai-compat", "description": "OpenAI-protocol shim for clients like Open WebUI"},
]


def create_app() -> FastAPI:
    app = FastAPI(
        title="agentic-octopus",
        version=__version__,
        description=DESCRIPTION,
        openapi_tags=TAGS,
        lifespan=lifespan,
        contact={"name": "Diego Silva", "url": "https://gitlab.com/behold-corp/agentic-octopus"},
        license_info={"name": "Private"},
    )
    app.include_router(router)
    app.include_router(chat_router)
    app.include_router(openai_router)

    @app.get("/healthz", tags=["system"], summary="Liveness + DB reachability")
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
