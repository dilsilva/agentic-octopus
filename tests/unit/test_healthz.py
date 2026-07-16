from fastapi.testclient import TestClient

from octo.api.main import create_app


def test_healthz_up_without_db():
    """The API comes up and reports honestly even when Postgres is unreachable."""
    app = create_app()
    with TestClient(app) as client:
        r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] is False
    assert "version" in body
