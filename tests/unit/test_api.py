from octo.config import settings

AUTH = {"Authorization": f"Bearer {settings.octo_api_token}"}


def test_healthz_is_open_and_reports_db_state(client_without_db):
    r = client_without_db.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] is False
    assert "version" in body


def test_routes_require_token(client_without_db):
    assert client_without_db.get("/agents").status_code == 401
    assert client_without_db.get("/runs").status_code == 401
    assert (
        client_without_db.get("/agents", headers={"Authorization": "Bearer wrong"}).status_code
        == 401
    )


def test_agents_listing_from_registry(client_without_db):
    r = client_without_db.get("/agents", headers=AUTH)
    assert r.status_code == 200
    names = [a["name"] for a in r.json()]
    assert "research-brief" in names
    assert "chat-assistant" in names


def test_unknown_agent_404(client_without_db):
    r = client_without_db.post("/agents/nope/run", json={"params": {}}, headers=AUTH)
    assert r.status_code == 404


def test_db_backed_routes_503_without_db(client_without_db):
    r = client_without_db.post("/agents/research-brief/run", json={"params": {}}, headers=AUTH)
    assert r.status_code == 503
