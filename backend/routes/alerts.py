from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request

from ..dependencies import require_roles
from ..database import persist_document
from ..services.audit_service import log_event

router = APIRouter()


class AlertUpdate(BaseModel):
    status: str


@router.get("")
@router.get("/", include_in_schema=False)
async def list_alerts(request: Request, _: dict = Depends(require_roles("analyst", "guest"))):
    alerts = request.app.state.store["alerts"]
    return {"alerts": list(reversed(alerts)), "total": len(alerts), "open": sum(item["status"] == "Open" for item in alerts)}


@router.patch("/{alert_id}/resolve")
async def resolve_alert(request: Request, alert_id: str, analyst: dict = Depends(require_roles("analyst"))):
    store = request.app.state.store
    alert = next((item for item in store["alerts"] if item["alert_id"] == alert_id), None)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert["status"] = "Resolved"
    alert["updated_at"] = datetime.now(timezone.utc).isoformat()
    await persist_document("fraud_alerts", alert)
    await log_event(store, "ALERT_UPDATED", analyst["_id"], alert_id, "SUCCESS")
    return {"message": "Alert resolved", "alert": alert}


@router.patch("/{alert_id}")
async def update_alert(request: Request, alert_id: str, payload: AlertUpdate, analyst: dict = Depends(require_roles("analyst"))):
    allowed = {"Open", "Under Investigation", "Resolved", "Dismissed"}
    if payload.status not in allowed:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {', '.join(sorted(allowed))}")
    alert = next((item for item in request.app.state.store["alerts"] if item["alert_id"] == alert_id), None)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert["status"] = payload.status
    alert["updated_at"] = datetime.now(timezone.utc).isoformat()
    await persist_document("fraud_alerts", alert)
    await log_event(request.app.state.store, "ALERT_UPDATED", analyst["_id"], alert_id, "SUCCESS")
    return {"alert": alert}
