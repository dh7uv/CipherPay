from __future__ import annotations

import logging
from typing import Any

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError

from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

try:
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=1500)
    database = client[settings.mongo_db_name]
except ImportError:
    client = None
    database = None

_mongo_ready = False
_PRIMARY_KEYS = {
    "users": "_id",
    "transactions": "transaction_id",
    "alerts": "alert_id",
    "audit_logs": "log_id",
}


async def ping_database() -> bool:
    if database is None:
        return False
    try:
        await database.command("ping")
        return True
    except PyMongoError as error:
        logger.warning("MongoDB health check failed: %s", error)
        return False


async def initialize_store(store: dict[str, list[dict[str, Any]]]) -> bool:
    global _mongo_ready

    _mongo_ready = await ping_database()
    if not _mongo_ready or database is None:
        return False

    try:
        await database["users"].create_index([("email", ASCENDING)], unique=True)
        await database["transactions"].create_index([("transaction_id", ASCENDING)], unique=True)
        await database["transactions"].create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        await database["transactions"].create_index([("status", ASCENDING), ("created_at", DESCENDING)])
        await database["transactions"].create_index([("risk_score", DESCENDING)])
        await database["alerts"].create_index([("alert_id", ASCENDING)], unique=True)
        await database["alerts"].create_index([("status", ASCENDING), ("created_at", DESCENDING)])
        await database["audit_logs"].create_index([("log_id", ASCENDING)], unique=True)
        await database["audit_logs"].create_index([("actor_id", ASCENDING), ("timestamp", DESCENDING)])

        for collection_name in _PRIMARY_KEYS:
            projection = {} if collection_name == "users" else {"_id": 0}
            documents = await database[collection_name].find({}, projection).to_list(length=None)
            if documents:
                store[collection_name].clear()
                store[collection_name].extend(documents)
    except PyMongoError as error:
        _mongo_ready = False
        logger.exception("MongoDB initialization failed; using in-memory storage: %s", error)
        return False

    return True


async def persist_document(collection_name: str, document: dict[str, Any]) -> None:
    if not _mongo_ready or database is None:
        return

    primary_key = _PRIMARY_KEYS[collection_name]
    key_value = document.get(primary_key)
    if not isinstance(key_value, str) or not key_value:
        raise ValueError(f"{collection_name} document requires a non-empty {primary_key}")

    stored_document = {**document, "_id": key_value}
    await database[collection_name].replace_one({"_id": key_value}, stored_document, upsert=True)


async def update_document(
    collection_name: str,
    key_value: str,
    changes: dict[str, Any],
) -> None:
    if not _mongo_ready or database is None:
        return
    await database[collection_name].update_one(
        {"_id": key_value},
        {"$set": changes},
    )


async def get_document(collection_name: str, key_value: str) -> dict[str, Any] | None:
    if not _mongo_ready or database is None:
        return None
    document = await database[collection_name].find_one({"_id": key_value})
    if document is None:
        return None
    document.pop("_id", None)
    return document


def mongo_connected() -> bool:
    return _mongo_ready
