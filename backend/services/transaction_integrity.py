from __future__ import annotations

from typing import Any

from ..database import get_document, mongo_connected


async def load_transaction_for_verification(
    store: dict[str, list[dict[str, Any]]],
    transaction_id: str,
) -> dict[str, Any] | None:
    if mongo_connected():
        return await get_document("transactions", transaction_id)
    return next(
        (
            item for item in store["transactions"]
            if item["transaction_id"] == transaction_id
        ),
        None,
    )
