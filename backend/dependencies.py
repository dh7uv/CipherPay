from __future__ import annotations

from typing import Any, Dict

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings
from .database import database
from .services.redis_service import redis_service

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> Dict[str, Any]:
    return {"database": database, "users": [], "transactions": [], "alerts": [], "audit_logs": []}


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Dict[str, Any]:
    """Resolve a bearer token to an active application user."""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[settings.algorithm])
        user_id = payload.get("sub")
    except jwt.PyJWTError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from error

    user = next((item for item in request.app.state.store["users"] if item["_id"] == user_id), None)
    if user is None or user.get("status") != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is unavailable")
    rate_key = f"ratelimit:{user['_id']}:{request.url.path}"
    if redis_service.increment_with_ttl(rate_key, ttl_seconds=60) > settings.rate_limit_per_minute:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded; retry in one minute")
    return user


def require_roles(*roles: str):
    async def role_dependency(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        if user.get("role") not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return role_dependency
