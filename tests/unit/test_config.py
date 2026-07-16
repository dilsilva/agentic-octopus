from octo.config import Settings


def test_defaults_are_local_and_safe(monkeypatch):
    for var in ("DATABASE_URL", "OCTO_ENV", "OCTO_API_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    s = Settings(_env_file=None)
    assert s.octo_env == "local"
    assert s.database_url.startswith("postgresql://")
    assert s.scheduler_enabled is True


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("OCTO_ENV", "gcp")
    monkeypatch.setenv("WORKER_CONCURRENCY", "4")
    s = Settings(_env_file=None)
    assert s.octo_env == "gcp"
    assert s.worker_concurrency == 4
