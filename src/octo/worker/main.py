"""Worker process. M0 stub: connects to the DB and idles so the compose stack is complete.

M1 replaces the loop body with: claim run via FOR UPDATE SKIP LOCKED -> load agent
definition -> execute via Claude Agent SDK -> persist events/result -> handle gates.
See docs/rfcs/0001-agentic-octopus-the-spine.md §M1 design.
"""

import asyncio
import logging

from octo import db
from octo.config import settings

log = logging.getLogger("octo.worker")


async def run() -> None:
    logging.basicConfig(level=settings.log_level.upper())
    pool = await db.create_pool(settings.database_url)
    log.info(
        "worker up (M0 stub — no executor yet); scheduler_enabled=%s", settings.scheduler_enabled
    )
    try:
        while True:
            async with pool.connection() as conn:
                await conn.execute("SELECT 1")
            await asyncio.sleep(30)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(run())
