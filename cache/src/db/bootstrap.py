import asyncio

import asyncpg

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
"""


async def bootstrap_schema() -> None:
    conn = await asyncpg.connect(settings.DATABASE_URL)
    try:
        await conn.execute(SCHEMA_SQL)
        logger.info("Database extensions verified. Run `alembic upgrade head` for tables.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(bootstrap_schema())
