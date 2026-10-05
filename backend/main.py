from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import initialize_store, mongo_connected, persist_document, ping_database
from .routes.alerts import router as alerts_router
from .routes.analytics import router as analytics_router
from .routes.auth import router as auth_router
from .routes.security import router as security_router
from .routes.transactions import router as transactions_router
from .services.auth_service import hash_password
from .services.crypto_service import encrypt_value, sign_transaction
from .services.redis_service import redis_service

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await initialize_store(_.state.store)
    if settings.seed_demo_data:
        await seed_demo_data(_.state.store)
    yield


async def seed_demo_data(store: dict[str, list[dict]]):
    now = datetime.now(timezone.utc).isoformat()
    user = next(
        (
            existing for existing in store["users"]
            if existing.get("email") == "demo@cipherpay.local"
        ),
        None,
    ) or {
        "_id": "demo-user",
        "email": "demo@cipherpay.local",
        "password_hash": hash_password("demo123"),
        "role": "analyst",
        "status": "active",
        "created_at": now,
    }
    transaction_payload = {
        "transaction_id": "txn_demo_001",
        "user_id": user["_id"],
        "amount": 4800.0,
        "currency": "USD",
        "merchant": "crypto",
        "device_id": encrypt_value("dev-2048"),
        "location": encrypt_value("Berlin"),
        "status": "Under Review",
        "risk_score": 76,
        "risk_category": "High",
        "risk_reasons": ["Large transaction value", "High-risk merchant category"],
        "created_at": now,
    }
    transaction = {
        **transaction_payload,
        "integrity_hmac": sign_transaction(transaction_payload),
    }
    alert = {
        "alert_id": "alert_demo_001",
        "transaction_id": "txn_demo_001",
        "severity": "High",
        "reason": "Large transaction value; High-risk merchant category",
        "status": "Open",
        "created_at": now,
        "updated_at": now,
    }
    audit_log = {
        "log_id": "log_demo_001",
        "actor_id": user["_id"],
        "action": "USER_LOGIN",
        "resource_id": user["_id"],
        "timestamp": now,
        "outcome": "SUCCESS",
    }
    demo_documents = (
        ("users", "_id", user),
        ("transactions", "transaction_id", transaction),
        ("alerts", "alert_id", alert),
        ("audit_logs", "log_id", audit_log),
    )
    for collection_name, key, document in demo_documents:
        if not any(item.get(key) == document[key] for item in store[collection_name]):
            store[collection_name].append(document)
            await persist_document(collection_name, document)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="CipherPay transaction monitoring and fraud detection API",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.state.store = {
    "users": [],
    "transactions": [],
    "alerts": [],
    "audit_logs": [],
}

app.include_router(auth_router, prefix=f"{settings.api_v1_str}/auth", tags=["auth"])
app.include_router(transactions_router, prefix=f"{settings.api_v1_str}/transactions", tags=["transactions"])
app.include_router(alerts_router, prefix=f"{settings.api_v1_str}/alerts", tags=["alerts"])
app.include_router(analytics_router, prefix=f"{settings.api_v1_str}/analytics", tags=["analytics"])
app.include_router(security_router, prefix=f"{settings.api_v1_str}/security", tags=["security"])

frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/")
async def root():
    return {"message": "CipherPay API is live", "status": "ok", "dashboard": "/dashboard"}


@app.get("/dashboard")
async def dashboard_page():
    return FileResponse(frontend_dir / "index.html")


@app.get("/login")
async def login_page():
    return FileResponse(frontend_dir / "login.html")


@app.get(f"{settings.api_v1_str}/health")
async def healthcheck():
    return {
        "status": "ok",
        "database_connected": await ping_database() and mongo_connected(),
        "redis_connected": redis_service.connected,
        "app": settings.app_name,
    }
