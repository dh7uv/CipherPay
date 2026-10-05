from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi import status as http_status
from pymongo.errors import DuplicateKeyError
from pydantic import BaseModel, Field, field_validator

from ..config import get_settings
from ..database import persist_document
from ..services.audit_service import log_event
from ..services.auth_service import create_access_token, hash_password, verify_password
from ..services.redis_service import redis_service

router = APIRouter()
settings = get_settings()


class UserRegister(BaseModel):
    email: str = Field(
        min_length=3,
        max_length=254,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    password: str = Field(min_length=8, max_length=128)
    role: Literal["user"] = "user"

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: Any) -> Any:
        return value.strip().lower() if isinstance(value, str) else value


class UserLogin(BaseModel):
    email: str = Field(
        min_length=3,
        max_length=254,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: Any) -> Any:
        return value.strip().lower() if isinstance(value, str) else value


@router.post("/register")
async def register_user(request: Request, payload: UserRegister):
    store = request.app.state.store
    email = payload.email.lower().strip()
    client_host = request.client.host if request.client else "unknown"
    if not redis_service.allow_request(
        f"ratelimit:{client_host}:auth_register",
        settings.redis_rate_limit,
        settings.redis_rate_window_seconds,
    ):
        await log_event(store, "USER_REGISTERED", "unknown", client_host, "FAILURE")
        raise HTTPException(
            status_code=http_status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Account registration rate limit exceeded",
            headers={"Retry-After": str(settings.redis_rate_window_seconds)},
        )

    if not email or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(status_code=422, detail="A valid email address is required")
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
    try:
        await persist_document("users", user)
    except DuplicateKeyError as error:
        raise HTTPException(status_code=400, detail="User already exists") from error
    store["users"].append(user)
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
    email = payload.email.lower().strip()
    client_host = request.client.host if request.client else "unknown"
    rate_limit_identity = f"{client_host}\0{email}"
    email_fingerprint = hashlib.sha256(rate_limit_identity.encode("utf-8")).hexdigest()
    if not redis_service.allow_request(
        f"ratelimit:auth_login:{email_fingerprint}",
        settings.redis_rate_limit,
        settings.redis_rate_window_seconds,
    ):
        await log_event(store, "USER_LOGIN", "unknown", email, "FAILURE")
        raise HTTPException(
            status_code=http_status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Sign-in rate limit exceeded",
            headers={"Retry-After": str(settings.redis_rate_window_seconds)},
        )
    user = next((item for item in store["users"] if item["email"] == email), None)
    if not user:
        await log_event(store, "USER_LOGIN", "unknown", email, "FAILURE")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(payload.password, user["password_hash"]):
        await log_event(store, "USER_LOGIN", user["_id"], user["_id"], "FAILURE")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.get("status") != "active":
        await log_event(store, "USER_LOGIN", user["_id"], user["_id"], "FAILURE")
        raise HTTPException(status_code=403, detail="Account is suspended")

    await log_event(store, "USER_LOGIN", user["_id"], user["_id"], "SUCCESS")
    return {
        "user_id": user["_id"],
        "email": user["email"],
        "role": user["role"],
        "token": create_access_token(user["_id"]),
    }
