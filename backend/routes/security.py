from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from ..dependencies import require_analyst
from ..services.audit_service import log_event
from ..services.crypto_service import verify_transaction_integrity
from ..services.transaction_integrity import load_transaction_for_verification

router = APIRouter()


@router.get("/audit-logs")
async def audit_logs(request: Request, _: dict[str, Any] = Depends(require_analyst)):
    return {"audit_logs": request.app.state.store["audit_logs"]}


@router.get("/integrity-check/{transaction_id}")
async def integrity_check(
    request: Request,
    transaction_id: str,
    current_user: dict[str, Any] = Depends(require_analyst),
):
    transaction = await load_transaction_for_verification(
        request.app.state.store,
        transaction_id,
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    valid = verify_transaction_integrity(transaction)
    await log_event(
        request.app.state.store,
        "INTEGRITY_CHECK",
        current_user["_id"],
        transaction_id,
        "SUCCESS" if valid else "FAILURE",
    )
    return {"transaction_id": transaction_id, "integrity_valid": valid}
