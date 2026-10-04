from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


def log_event(store: Dict[str, List[Dict[str, Any]]], action: str, actor_id: str, resource_id: str, outcome: str) -> Dict[str, Any]:
    event = {
        "log_id": f"log_{len(store['audit_logs']) + 1}",
        "actor_id": actor_id,
        "action": action,
        "resource_id": resource_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "outcome": outcome,
    }
    store["audit_logs"].append(event)
    return event
