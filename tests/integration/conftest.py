"""Integration tests run against real Postgres+pgvector: TEST_DATABASE_URL if set
(GitLab CI services), otherwise a throwaway testcontainer."""

import os

import pytest
import pytest_asyncio

from octo import db


@pytest.fixture(scope="session")
def database_url():
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        yield url
        return
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("pgvector/pgvector:pg16") as pg:
        yield pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")


@pytest.fixture(scope="session")
def migrated(database_url):
    db.upgrade(database_url)
    return database_url


@pytest_asyncio.fixture
async def pool(migrated):
    p = await db.create_pool(migrated)
    async with p.connection() as conn:
        await conn.execute(
            "TRUNCATE run_events, approvals, runs, schedules, memories RESTART IDENTITY CASCADE"
        )
    yield p
    await p.close()
