"""Database access: async pool for the app, sync migration runner for `octo.db upgrade`.

Migrations are plain numbered SQL files in db/migrations/, tracked in a
schema_migrations table. No ORM, no Alembic — see ADR-0003.
"""

import sys
from pathlib import Path

import psycopg
from psycopg_pool import AsyncConnectionPool

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "db" / "migrations"


async def create_pool(database_url: str) -> AsyncConnectionPool:
    pool = AsyncConnectionPool(database_url, min_size=1, max_size=5, open=False)
    await pool.open()
    return pool


def upgrade(database_url: str) -> list[str]:
    """Apply pending migrations in filename order. Returns the versions applied."""
    applied_now: list[str] = []
    with psycopg.connect(database_url) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
        already = {r[0] for r in rows}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.stem in already:
                continue
            conn.execute(path.read_text())
            conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.stem,))
            conn.commit()
            applied_now.append(path.stem)
    return applied_now


if __name__ == "__main__":
    from octo.config import settings

    if len(sys.argv) < 2 or sys.argv[1] != "upgrade":
        print("usage: python -m octo.db upgrade", file=sys.stderr)
        raise SystemExit(2)
    applied = upgrade(settings.database_url)
    print(f"applied: {applied or 'nothing — up to date'}")
