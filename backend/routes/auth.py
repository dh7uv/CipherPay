from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..services.audit_service import log_event
from ..services.auth_service import create_access_token, hash_password, verify_password

router = APIRouter()


class UserRegister(BaseModel):
    email: str
    password: str
    role: str = "user"


class UserLogin(BaseModel):
    email: str
    password: str


@router.post("/register")
async def register_user(request: Request, payload: UserRegister):
    store = request.app.state.store
    email = payload.email.lower().strip()

    if any(user["email"] == email for user in store["users"]):
        raise HTTPException(status_code=400, detail="User already exists")

    user = {
        "_id": str(uuid4()),
        "email": email,
        "password_hash": hash_password(payload.password),
        "role": payload.role,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    store["users"].append(user)
    log_event(store, "USER_REGISTERED", user["_id"], user["_id"], "SUCCESS")

    return {
        "user_id": user["_id"],
        "email": user["email"],
        "role": user["role"],
        "token": create_access_token(user["_id"]),
    }


@router.post("/login")
async def login_user(request: Request, payload: UserLogin):
    store = request.app.state.store
    user = next((item for item in store["users"] if item["email"] == payload.email.lower().strip()), None)
    if not user:
        log_event(store, "USER_LOGIN", "unknown", payload.email, "FAILURE")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(payload.password, user["password_hash"]):
        log_event(store, "USER_LOGIN", user["_id"], user["_id"], "FAILURE")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    log_event(store, "USER_LOGIN", user["_id"], user["_id"], "SUCCESS")
    return {
        "user_id": user["_id"],
        "email": user["email"],
        "token": create_access_token(user["_id"]),
    }
