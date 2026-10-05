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


INDEXES: dict[str, list[tuple[Any, dict[str, Any]]]] = {
    "users": [([("email", 1)], {"unique": True})],
    "transactions": [
        ([("user_id", 1), ("created_at", -1)], {}),
        ([("status", 1), ("created_at", -1)], {}),
        ([("risk_score", -1)], {}),
        ([("transaction_id", 1)], {"unique": True}),
    ],
    "fraud_alerts": [
        ([("transaction_id", 1)], {}),
        ([("status", 1), ("created_at", -1)], {}),
        ([("alert_id", 1)], {"unique": True}),
    ],
    "audit_logs": [
        ([("actor_id", 1), ("timestamp", -1)], {}),
        ([("timestamp", -1)], {}),
    ],
}


async def create_indexes() -> bool:
    if not await ping_database() or database is None:
        return False
    for collection_name, indexes in INDEXES.items():
        collection = database[collection_name]
        for fields, options in indexes:
            await collection.create_index(fields, **options)
    return True


async def hydrate_store(store: dict[str, list[dict[str, Any]]]) -> bool:
    """Load MongoDB documents into the application cache when MongoDB is available."""
    if not await ping_database() or database is None:
        return False
    mapping = {"users": "users", "transactions": "transactions", "alerts": "fraud_alerts", "audit_logs": "audit_logs"}
    for store_name, collection_name in mapping.items():
        documents = await database[collection_name].find({}).to_list(length=None)
        for document in documents:
            document.pop("_id", None) if store_name != "users" else None
        store[store_name] = documents
    return True


async def persist_document(collection_name: str, document: dict[str, Any]) -> None:
    """Upsert a document in MongoDB; local mode intentionally remains dependency-free."""
    if database is None or not await ping_database():
        return
    identifiers = {
        "users": "_id",
        "transactions": "transaction_id",
        "fraud_alerts": "alert_id",
        "audit_logs": "log_id",
    }
    key = identifiers[collection_name]
    await database[collection_name].replace_one({key: document[key]}, document, upsert=True)
    try:
        await database.command("ping")
        return True
    except Exception:
        return False
