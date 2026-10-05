from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..database import update_document
from ..dependencies import require_analyst
from ..services.audit_service import log_event

router = APIRouter()


class AlertReview(BaseModel):
    status: Literal["Open", "Under Investigation", "Resolved", "Dismissed"]


@router.get("/")
async def list_alerts(request: Request, _: dict[str, Any] = Depends(require_analyst)):
    return {"alerts": request.app.state.store["alerts"]}


async def _update_alert(
    request: Request,
    alert_id: str,
    new_status: str,
    current_user: dict[str, Any],
):
    store = request.app.state.store
    alert = next((item for item in store["alerts"] if item["alert_id"] == alert_id), None)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    updated_at = datetime.now(timezone.utc).isoformat()
    await update_document("alerts", alert_id, {"status": new_status, "updated_at": updated_at})
    alert["status"] = new_status
    alert["updated_at"] = updated_at
    await log_event(store, "ALERT_UPDATED", current_user["_id"], alert_id, "SUCCESS")
    return {"message": "Alert status updated", "alert": alert}


@router.patch("/{alert_id}")
async def review_alert(
    request: Request,
    alert_id: str,
    payload: AlertReview,
    current_user: dict[str, Any] = Depends(require_analyst),
):
    return await _update_alert(request, alert_id, payload.status, current_user)


@router.patch("/{alert_id}/resolve")
async def resolve_alert(
    request: Request,
    alert_id: str,
    current_user: dict[str, Any] = Depends(require_analyst),
):
    return await _update_alert(request, alert_id, "Resolved", current_user)
