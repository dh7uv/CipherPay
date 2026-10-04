from __future__ import annotations

from typing import Any

from .config import get_settings

settings = get_settings()

try:
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(settings.mongo_uri)
    database = client[settings.mongo_db_name]
    mongo_available = True
except Exception:
    client = None
    database = None
    mongo_available = False


async def ping_database() -> bool:
    if not mongo_available or database is None:
        return False
    try:
        await database.command("ping")
        return True
    except Exception:
        return False

