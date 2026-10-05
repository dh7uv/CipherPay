from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import create_indexes, hydrate_store, ping_database, persist_document
from .routes.alerts import router as alerts_router
from .routes.analytics import router as analytics_router
from .routes.auth import router as auth_router
from .routes.security import router as security_router
from .routes.transactions import router as transactions_router
from .services.auth_service import hash_password
from .services.crypto_service import canonical_transaction_payload, sign_hmac
from .services.crypto_service import encrypt_value
from .services.redis_service import redis_service

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    _.state.mongo_connected = await create_indexes()
    if _.state.mongo_connected:
        await hydrate_store(_.state.store)
    if not _.state.store["users"]:
        _.state.store["users"] = [{
            "_id": "demo-user",
            "email": "demo@cipherpay.local",
            "password_hash": hash_password("demo123"),
            "role": "analyst",
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }]
        _.state.store["transactions"] = [{
            "transaction_id": "txn_demo_001",
            "user_id": "demo-user",
            "amount": 4800.0,
            "currency": "USD",
            "merchant": "crypto",
            "encrypted_fields": {
                "device_id": encrypt_value("dev-2048"),
                "location": encrypt_value("Berlin"),
            },
            "status": "Under Review",
            "risk_score": 76,
            "risk_category": "High",
            "risk_reasons": ["Large transaction value", "High-risk merchant category"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }]
        _.state.store["transactions"][0]["integrity_hmac"] = sign_hmac(canonical_transaction_payload(_.state.store["transactions"][0]))
        _.state.store["alerts"] = [{
            "alert_id": "alert_demo_001",
            "transaction_id": "txn_demo_001",
            "severity": "High",
            "reason": "Large transaction value; High-risk merchant category",
            "status": "Open",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }]
        _.state.store["audit_logs"] = [{
            "log_id": "log_demo_001",
            "actor_id": "demo-user",
            "action": "USER_LOGIN",
            "resource_id": "demo-user",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "outcome": "SUCCESS",
        }]
        for user in _.state.store["users"]:
            await persist_document("users", user)
        for transaction in _.state.store["transactions"]:
            await persist_document("transactions", transaction)
        for alert in _.state.store["alerts"]:
            await persist_document("fraud_alerts", alert)
        for event in _.state.store["audit_logs"]:
            await persist_document("audit_logs", event)
    elif not any(user["_id"] == "demo-user" for user in _.state.store["users"]):
        # Keep a predictable analyst account available for the local demonstration
        # without overwriting users that were created before the lifespan started.
        demo_user = {
            "_id": "demo-user",
            "email": "demo@cipherpay.local",
            "password_hash": hash_password("demo123"),
            "role": "analyst",
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _.state.store["users"].append(demo_user)
        await persist_document("users", demo_user)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="CryptaGuard transaction monitoring and fraud detection API",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    return {"message": "CryptaGuard API is live", "status": "ok", "dashboard": "/dashboard"}


@app.get("/dashboard")
async def dashboard_page():
    return FileResponse(frontend_dir / "index.html")


@app.get("/login")
async def login_page():
    return FileResponse(frontend_dir / "login.html")


@app.get(f"{settings.api_v1_str}/health")
async def healthcheck():
    db_status = await ping_database()
    return {
        "status": "ok",
        "database_connected": db_status,
        "redis_connected": redis_service.connected(),
        "app": settings.app_name,
    }
