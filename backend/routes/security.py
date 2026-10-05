from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from ..dependencies import require_roles
from ..services.audit_service import log_event
from ..services.crypto_service import verify_transaction_hmac

router = APIRouter()


@router.get("/audit-logs")
async def audit_logs(request: Request, _: dict = Depends(require_roles("analyst", "guest"))):
    logs = request.app.state.store["audit_logs"]
    return {"audit_logs": list(reversed(logs)), "total": len(logs)}


@router.get("/integrity-check/{transaction_id}")
async def integrity_check(request: Request, transaction_id: str, analyst: dict = Depends(require_roles("analyst", "guest"))):
    transaction = next(
        (item for item in request.app.state.store["transactions"] if item["transaction_id"] == transaction_id),
        None,
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    valid = verify_transaction_hmac(transaction)
    await log_event(request.app.state.store, "INTEGRITY_CHECK", analyst["_id"], transaction_id, "SUCCESS" if valid else "FAILURE")
    return {"transaction_id": transaction_id, "integrity_valid": valid}
