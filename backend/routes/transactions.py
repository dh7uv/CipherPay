from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from ..config import get_settings
from ..database import persist_document, update_document
from ..dependencies import get_current_user
from ..services.audit_service import log_event
from ..services.crypto_service import encrypt_value, sign_transaction, verify_transaction_integrity
from ..services.fraud_engine import score_transaction
from ..services.redis_service import redis_service
from ..services.transaction_integrity import load_transaction_for_verification

router = APIRouter()
settings = get_settings()


class TransactionCreate(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    amount: float = Field(gt=0, allow_inf_nan=False)
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    merchant: str = Field(min_length=1, max_length=120)
    device_id: str = Field(min_length=1, max_length=128)
    location: str = Field(min_length=1, max_length=120)


class TransactionDecision(BaseModel):
    decision: Literal["Approved", "Declined"]


@router.post("/submit")
async def submit_transaction(
    request: Request,
    payload: TransactionCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    store = request.app.state.store

    if current_user["role"] != "analyst" and payload.user_id != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Users can only submit their own transactions")

    if not any(user["_id"] == payload.user_id for user in store["users"]):
        raise HTTPException(status_code=404, detail="User not found")

    rate_limit_key = f"ratelimit:{current_user['_id']}:transactions_submit"
    if not redis_service.allow_request(
        rate_limit_key,
        settings.redis_rate_limit,
        settings.redis_rate_window_seconds,
    ):
        await log_event(store, "TRANSACTION_SUBMITTED", current_user["_id"], "", "FAILURE")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Transaction submission rate limit exceeded",
            headers={"Retry-After": str(settings.redis_rate_window_seconds)},
        )

    transaction_id = f"txn_{uuid4().hex[:12]}"
    activity = redis_service.record_transaction(
        payload.user_id,
        payload.device_id,
        transaction_id,
    )
    risk_data = score_transaction(
        payload.model_dump(),
        velocity_count=activity["velocity_count"],
        device_activity_count=activity["device_activity_count"],
    )
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
    signature = sign_transaction(transaction_payload)
    transaction = {**transaction_payload, "integrity_hmac": signature}
    await persist_document("transactions", transaction)
    store["transactions"].append(transaction)
    await log_event(store, "TRANSACTION_SUBMITTED", payload.user_id, transaction_id, "SUCCESS")

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
        await persist_document("alerts", alert)
        store["alerts"].append(alert)

    return {"transaction": transaction, "risk": risk_data}


@router.get("/")
async def list_transactions(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
    risk_category: str | None = Query(default=None, pattern="^(Low|Medium|High)$"),
    transaction_status: str | None = Query(default=None, alias="status"),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    transactions = list(reversed(request.app.state.store["transactions"]))
    if current_user["role"] != "analyst":
        transactions = [item for item in transactions if item["user_id"] == current_user["_id"]]
    if risk_category:
        transactions = [item for item in transactions if item["risk_category"] == risk_category]
    if transaction_status:
        transactions = [item for item in transactions if item["status"] == transaction_status]
    total = len(transactions)
    return {"transactions": transactions[skip:skip + limit], "total": total, "limit": limit, "skip": skip}


@router.get("/{transaction_id}")
async def get_transaction(
    request: Request,
    transaction_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    transaction = await load_transaction_for_verification(
        request.app.state.store,
        transaction_id,
    )
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if current_user["role"] != "analyst" and transaction["user_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="You can only access your own transactions")
    return {"transaction": transaction}


@router.post("/{transaction_id}/verify-integrity")
async def verify_transaction(
    request: Request,
    transaction_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    if current_user["role"] != "analyst":
        raise HTTPException(status_code=403, detail="Analyst access required")
    transaction = await load_transaction_for_verification(
        request.app.state.store,
        transaction_id,
    )
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    valid = verify_transaction_integrity(transaction)
    await log_event(
        request.app.state.store,
        "INTEGRITY_CHECK",
        current_user["_id"],
        transaction_id,
        "SUCCESS" if valid else "FAILURE",
    )
    if valid:
        verified_at = datetime.now(timezone.utc).isoformat()
        transaction.update(
            integrity_status="Verified",
            integrity_verified_at=verified_at,
            integrity_verified_by=current_user["_id"],
        )
        transaction["integrity_hmac"] = sign_transaction(transaction)
        await update_document(
            "transactions",
            transaction_id,
            {
                "integrity_status": transaction["integrity_status"],
                "integrity_verified_at": verified_at,
                "integrity_verified_by": current_user["_id"],
                "integrity_hmac": transaction["integrity_hmac"],
            },
        )
        stored_transaction = next(
            (
                item for item in request.app.state.store["transactions"]
                if item.get("transaction_id") == transaction_id
            ),
            None,
        )
        if stored_transaction is not None:
            stored_transaction.update(transaction)

    manual_review_available = (
        valid
        and transaction.get("status") == "Under Review"
    )
    return {
        "transaction_id": transaction_id,
        "integrity_valid": valid,
        "integrity_status": "Verified" if valid else "Failed",
        "manual_review_available": manual_review_available,
    }


@router.post("/{transaction_id}/decision")
async def decide_transaction(
    request: Request,
    transaction_id: str,
    payload: TransactionDecision,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    if current_user["role"] != "analyst":
        raise HTTPException(status_code=403, detail="Analyst access required")

    store = request.app.state.store
    transaction = await load_transaction_for_verification(store, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if not verify_transaction_integrity(transaction):
        raise HTTPException(
            status_code=409,
            detail="Transaction integrity check failed; manual decision is not allowed",
        )
    if (
        transaction.get("integrity_status") != "Verified"
        or transaction.get("status") != "Under Review"
    ):
        raise HTTPException(
            status_code=409,
            detail="Only verified transactions under review can be manually decided",
        )

    decided_at = datetime.now(timezone.utc).isoformat()
    transaction.update(
        status=payload.decision,
        reviewed_at=decided_at,
        reviewed_by=current_user["_id"],
    )
    transaction["integrity_hmac"] = sign_transaction(transaction)
    await update_document(
        "transactions",
        transaction_id,
        {
            "status": payload.decision,
            "reviewed_at": decided_at,
            "reviewed_by": current_user["_id"],
            "integrity_hmac": transaction["integrity_hmac"],
        },
    )

    stored_transaction = next(
        (
            item for item in store["transactions"]
            if item.get("transaction_id") == transaction_id
        ),
        None,
    )
    if stored_transaction is not None:
        stored_transaction.update(transaction)

    await log_event(
        store,
        f"TRANSACTION_{payload.decision.upper()}",
        current_user["_id"],
        transaction_id,
        "SUCCESS",
    )
    return {"transaction": transaction}
