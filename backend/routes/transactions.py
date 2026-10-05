from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..dependencies import get_current_user, require_roles
from ..database import persist_document
from ..services.audit_service import log_event
from ..services.crypto_service import canonical_transaction_payload, decrypt_value, encrypt_value, sign_hmac, verify_transaction_hmac
from ..services.fraud_engine import score_transaction

router = APIRouter()


class TransactionCreate(BaseModel):
    user_id: str | None = None
    amount: float = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    merchant: str = Field(min_length=1, max_length=120)
    device_id: str = ""
    location: str = ""


@router.post("")
@router.post("/submit", include_in_schema=False)
async def submit_transaction(
    request: Request,
    payload: TransactionCreate,
    current_user: dict = Depends(get_current_user),
):
    store = request.app.state.store
    if current_user["role"] == "guest":
        raise HTTPException(status_code=403, detail="Guest sessions are read-only")
    owner_id = payload.user_id or current_user["_id"]

    if owner_id != current_user["_id"] and current_user["role"] != "analyst":
        raise HTTPException(status_code=403, detail="You can only submit transactions for your own account")
    if not any(user["_id"] == owner_id for user in store["users"]):
        raise HTTPException(status_code=404, detail="User not found")

    risk_data = score_transaction({**payload.model_dump(), "user_id": owner_id})
    transaction_id = f"txn_{uuid4().hex[:12]}"
    transaction_payload = {
        "transaction_id": transaction_id,
        "user_id": owner_id,
        "amount": payload.amount,
        "currency": payload.currency,
        "merchant": payload.merchant,
        "encrypted_fields": {
            "device_id": encrypt_value(payload.device_id),
            "location": encrypt_value(payload.location),
        },
        "status": "Declined" if risk_data["risk_score"] >= 90 else "Under Review" if risk_data["risk_score"] >= 40 else "Approved",
        "risk_score": risk_data["risk_score"],
        "risk_category": risk_data["risk_category"],
        "risk_reasons": risk_data["risk_reasons"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    signature = sign_hmac(canonical_transaction_payload(transaction_payload))
    transaction = {**transaction_payload, "integrity_hmac": signature}
    store["transactions"].append(transaction)
    await persist_document("transactions", transaction)
    await log_event(store, "TRANSACTION_SUBMITTED", current_user["_id"], transaction_id, "SUCCESS")

    if risk_data["risk_category"] in {"High", "Medium"}:
        alert = {
            "alert_id": f"alert_{uuid4().hex[:10]}",
            "transaction_id": transaction_id,
            "severity": "High" if risk_data["risk_category"] == "High" else "Medium",
            "reason": "; ".join(risk_data["risk_reasons"]),
            "status": "Open",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        store["alerts"].append(alert)
        await persist_document("fraud_alerts", alert)

    return {"transaction": transaction, "risk": risk_data}


@router.get("")
@router.get("/")
async def list_transactions(
    request: Request,
    status: str | None = None,
    risk_category: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    transactions = request.app.state.store["transactions"]
    visible = transactions if current_user["role"] in {"analyst", "guest"} else [item for item in transactions if item["user_id"] == current_user["_id"]]
    if status:
        visible = [item for item in visible if item["status"] == status]
    if risk_category:
        visible = [item for item in visible if item["risk_category"] == risk_category]
    ordered = list(reversed(visible))
    start = (page - 1) * page_size
    return {"transactions": ordered[start : start + page_size], "total": len(ordered), "page": page, "page_size": page_size}


@router.get("/{transaction_id}/details")
async def transaction_details(request: Request, transaction_id: str, analyst: dict = Depends(require_roles("analyst", "guest"))):
    transaction = next((item for item in request.app.state.store["transactions"] if item["transaction_id"] == transaction_id), None)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    encrypted_fields = transaction.get("encrypted_fields", {})
    if not encrypted_fields:
        encrypted_fields = {key: transaction.get(key) for key in ("device_id", "location") if transaction.get(key)}
    sensitive_metadata = {}
    for field_name, encrypted_value in encrypted_fields.items():
        try:
            sensitive_metadata[field_name] = decrypt_value(encrypted_value) if encrypted_value else "Not provided"
        except Exception:
            sensitive_metadata[field_name] = "Unavailable"
    await log_event(request.app.state.store, "TRANSACTION_INSPECTED", analyst["_id"], transaction_id, "SUCCESS")
    return {"transaction": transaction, "sensitive_metadata": sensitive_metadata}


@router.get("/{transaction_id}")
async def get_transaction(request: Request, transaction_id: str, current_user: dict = Depends(get_current_user)):
    transaction = next((item for item in request.app.state.store["transactions"] if item["transaction_id"] == transaction_id), None)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if current_user["role"] != "analyst" and transaction["user_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return transaction


@router.post("/{transaction_id}/verify-integrity")
async def verify_integrity(
    request: Request,
    transaction_id: str,
    analyst: dict = Depends(require_roles("analyst", "guest")),
):
    transaction = next((item for item in request.app.state.store["transactions"] if item["transaction_id"] == transaction_id), None)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    valid = verify_transaction_hmac(transaction)
    await log_event(request.app.state.store, "INTEGRITY_CHECK", analyst["_id"], transaction_id, "SUCCESS" if valid else "FAILURE")
    return {"transaction_id": transaction_id, "integrity_valid": valid}
