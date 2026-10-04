from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from ..services.audit_service import log_event

router = APIRouter()


@router.get("/")
async def list_alerts(request: Request):
    return {"alerts": request.app.state.store["alerts"]}


@router.patch("/{alert_id}/resolve")
async def resolve_alert(request: Request, alert_id: str):
    store = request.app.state.store
    alert = next((item for item in store["alerts"] if item["alert_id"] == alert_id), None)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert["status"] = "Resolved"
    alert["updated_at"] = datetime.now(timezone.utc).isoformat()
    log_event(store, "ALERT_UPDATED", "system", alert_id, "SUCCESS")
    return {"message": "Alert resolved", "alert": alert}
