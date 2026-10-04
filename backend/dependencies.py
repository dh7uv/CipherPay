from __future__ import annotations

from typing import Any, Dict

from .database import database


async def get_db() -> Dict[str, Any]:
    return {"database": database, "users": [], "transactions": [], "alerts": [], "audit_logs": []}

