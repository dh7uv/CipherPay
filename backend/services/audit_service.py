from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4

from ..database import persist_document


async def log_event(store: Dict[str, List[Dict[str, Any]]], action: str, actor_id: str, resource_id: str, outcome: str) -> Dict[str, Any]:
    event = {
        "log_id": f"log_{uuid4().hex}",
        "actor_id": actor_id,
        "action": action,
        "resource_id": resource_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "outcome": outcome,
    }
    await persist_document("audit_logs", event)
    store["audit_logs"].append(event)
    return event
