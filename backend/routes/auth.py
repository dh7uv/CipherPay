from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from ..services.audit_service import log_event
from ..services.auth_service import create_access_token, hash_password, verify_password
from ..database import persist_document

router = APIRouter()


class UserRegister(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    role: Literal["user"] = "user"

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("A valid email address is required")
        return normalized


class UserLogin(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


@router.post("/guest")
async def guest_login(request: Request):
    store = request.app.state.store
    guest_id = "guest-viewer"
    guest = next((item for item in store["users"] if item["_id"] == guest_id), None)
    if guest is None:
        guest = {
            "_id": guest_id,
            "email": "guest@cryptaguard.local",
            "password_hash": "",
            "role": "guest",
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        store["users"].append(guest)
    await log_event(store, "GUEST_SESSION_STARTED", guest_id, guest_id, "SUCCESS")
    return {
        "user_id": guest_id,
        "email": guest["email"],
        "role": guest["role"],
        "token": create_access_token(guest_id),
        "read_only": True,
    }


@router.post("/register")
async def register_user(request: Request, payload: UserRegister):
    store = request.app.state.store
    email = payload.email

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
    await persist_document("users", user)
    await log_event(store, "USER_REGISTERED", user["_id"], user["_id"], "SUCCESS")

    return {
        "user_id": user["_id"],
        "email": user["email"],
        "role": user["role"],
        "token": create_access_token(user["_id"]),
    }


@router.post("/login")
async def login_user(request: Request, payload: UserLogin):
    store = request.app.state.store
    user = next((item for item in store["users"] if item["email"] == payload.email), None)
    if not user:
        await log_event(store, "USER_LOGIN", "unknown", payload.email, "FAILURE")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(payload.password, user["password_hash"]):
        await log_event(store, "USER_LOGIN", user["_id"], user["_id"], "FAILURE")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    await log_event(store, "USER_LOGIN", user["_id"], user["_id"], "SUCCESS")
    return {
        "user_id": user["_id"],
        "email": user["email"],
        "role": user["role"],
        "token": create_access_token(user["_id"]),
    }
