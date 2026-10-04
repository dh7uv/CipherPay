from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..services.audit_service import log_event
from ..services.crypto_service import encrypt_value, sign_hmac
from ..services.fraud_engine import score_transaction

router = APIRouter()


class TransactionCreate(BaseModel):
    user_id: str
    amount: float
    currency: str = "USD"
    merchant: str
    device_id: str
    location: str


@router.post("/submit")
async def submit_transaction(request: Request, payload: TransactionCreate):
    store = request.app.state.store

    if not any(user["_id"] == payload.user_id for user in store["users"]):
        raise HTTPException(status_code=404, detail="User not found")

    risk_data = score_transaction(payload.model_dump())
    transaction_id = f"txn_{uuid4().hex[:12]}"
    transaction_payload = {
        "transaction_id": transaction_id,
        "user_id": payload.user_id,
        "amount": payload.amount,
        "currency": payload.currency,
        "merchant": payload.merchant,
        "device_id": encrypt_value(payload.device_id),
        "location": encrypt_value(payload.location),
        "status": "Under Review" if risk_data["risk_score"] >= 40 else "Approved",
        "risk_score": risk_data["risk_score"],
        "risk_category": risk_data["risk_category"],
        "risk_reasons": risk_data["risk_reasons"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    signature = sign_hmac(json.dumps(transaction_payload, sort_keys=True))
    transaction = {**transaction_payload, "integrity_hmac": signature}
    store["transactions"].append(transaction)
    log_event(store, "TRANSACTION_SUBMITTED", payload.user_id, transaction_id, "SUCCESS")

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

    return {"transaction": transaction, "risk": risk_data}


@router.get("/")
async def list_transactions(request: Request):
    return {"transactions": request.app.state.store["transactions"]}
