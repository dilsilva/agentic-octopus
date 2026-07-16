from contextlib import contextmanager

from fastapi.testclient import TestClient

from octo.api.main import create_app
from octo.config import settings

AUTH = {"Authorization": f"Bearer {settings.octo_api_token}"}


@contextmanager
def client_without_db():
    """A live app whose DB pool is deliberately absent — deterministic regardless of
    whether a local Postgres happens to be running."""
    app = create_app()
    with TestClient(app) as client:
        real_pool, app.state.pool = app.state.pool, None
        try:
            yield client
        finally:
            app.state.pool = real_pool  # let lifespan close it properly


def test_healthz_is_open_and_reports_db_state():
    with client_without_db() as client:
        r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] is False
    assert "version" in body


def test_routes_require_token():
    with client_without_db() as client:
        assert client.get("/agents").status_code == 401
        assert client.get("/runs").status_code == 401
        assert client.get("/agents", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_agents_listing_from_registry():
    with client_without_db() as client:
        r = client.get("/agents", headers=AUTH)
    assert r.status_code == 200
    names = [a["name"] for a in r.json()]
    assert "research-brief" in names


def test_unknown_agent_404():
    with client_without_db() as client:
        r = client.post("/agents/nope/run", json={"params": {}}, headers=AUTH)
    assert r.status_code == 404


def test_db_backed_routes_503_without_db():
    with client_without_db() as client:
        r = client.post("/agents/research-brief/run", json={"params": {}}, headers=AUTH)
    assert r.status_code == 503
