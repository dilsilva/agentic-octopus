from octo import db


def test_upgrade_is_idempotent(migrated):
    # session fixture already applied them; a second run applies nothing
    assert db.upgrade(migrated) == []


async def test_schema_has_expected_tables(pool):
    async with pool.connection() as conn:
        rows = await (
            await conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
            )
        ).fetchall()
    tables = {r[0] for r in rows}
    assert {
        "runs",
        "run_events",
        "approvals",
        "schedules",
        "memories",
        "schema_migrations",
    } <= tables


async def test_pgvector_installed(pool):
    async with pool.connection() as conn:
        row = await (
            await conn.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        ).fetchone()
    assert row is not None
