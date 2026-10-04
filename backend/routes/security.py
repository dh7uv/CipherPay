from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request

from ..services.audit_service import log_event
from ..services.crypto_service import verify_hmac

router = APIRouter()


@router.get("/audit-logs")
async def audit_logs(request: Request):
    return {"audit_logs": request.app.state.store["audit_logs"]}


@router.get("/integrity-check/{transaction_id}")
async def integrity_check(request: Request, transaction_id: str):
    transaction = next(
        (item for item in request.app.state.store["transactions"] if item["transaction_id"] == transaction_id),
        None,
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    payload = {
        "transaction_id": transaction["transaction_id"],
        "user_id": transaction["user_id"],
        "amount": transaction["amount"],
        "currency": transaction["currency"],
        "merchant": transaction["merchant"],
        "device_id": transaction["device_id"],
        "location": transaction["location"],
        "status": transaction["status"],
        "risk_score": transaction["risk_score"],
        "risk_category": transaction["risk_category"],
        "risk_reasons": transaction["risk_reasons"],
        "created_at": transaction["created_at"],
    }
    valid = verify_hmac(json.dumps(payload, sort_keys=True), transaction["integrity_hmac"])
    log_event(request.app.state.store, "INTEGRITY_CHECK", "system", transaction_id, "SUCCESS" if valid else "FAILURE")
    return {"transaction_id": transaction_id, "integrity_valid": valid}
