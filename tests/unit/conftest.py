from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from octo.api.main import create_app


@contextmanager
def _client_without_db():
    """A live app whose DB pool is deliberately absent — deterministic regardless of
    whether a local Postgres happens to be running."""
    app = create_app()
    with TestClient(app) as client:
        real_pool, app.state.pool = app.state.pool, None
        try:
            yield client
        finally:
            app.state.pool = real_pool  # let lifespan close it properly


@pytest.fixture
def client_without_db():
    with _client_without_db() as client:
        yield client
