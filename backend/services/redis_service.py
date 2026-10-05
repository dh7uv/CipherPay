from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4
from typing import Any

from ..config import get_settings

try:
    import redis
except Exception:  # pragma: no cover
    redis = None


class RedisService:
    def __init__(self) -> None:
        self._fallback: dict[str, Any] = {}
        self._client = None
        settings = get_settings()
        if redis is not None:
            try:
                self._client = redis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    password=settings.redis_password or None,
                    decode_responses=True,
                )
                self._client.ping()
            except Exception:
                self._client = None

    def increment(self, key: str, value: int = 1) -> int:
        if self._client is not None:
            return int(self._client.incr(key, value))
        self._fallback[key] = self._fallback.get(key, 0) + value
        return self._fallback[key]

    def increment_with_ttl(self, key: str, ttl_seconds: int, value: int = 1) -> int:
        """Increment a counter and ensure its fixed window expiry is set."""
        if self._client is not None:
            pipeline = self._client.pipeline()
            pipeline.incrby(key, value)
            pipeline.ttl(key)
            count, ttl = pipeline.execute()
            if ttl < 0:
                self._client.expire(key, ttl_seconds)
            return int(count)

        now = datetime.now(timezone.utc)
        counter = self._fallback.get(key, {"count": 0, "expires_at": now + timedelta(seconds=ttl_seconds)})
        if now >= counter["expires_at"]:
            counter = {"count": 0, "expires_at": now + timedelta(seconds=ttl_seconds)}
        counter["count"] += value
        self._fallback[key] = counter
        return counter["count"]

    def reset(self, key: str) -> None:
        if self._client is not None:
            self._client.delete(key)
        self._fallback.pop(key, None)

    def get(self, key: str, default=None):
        if self._client is not None:
            return self._client.get(key, default)
        return self._fallback.get(key, default)

    def connected(self) -> bool:
        return self._client is not None

    def is_suspicious_device(self, device_id: str) -> bool:
        return bool(device_id) and device_id in get_settings().suspicious_devices

    def velocity(self, key: str, window_seconds: int = 60) -> int:
        now = datetime.now(timezone.utc)
        if self._client is not None:
            bucket = f"velocity:user:{key}"
            self._client.zremrangebyscore(bucket, 0, (now - timedelta(seconds=window_seconds)).timestamp())
            self._client.zadd(bucket, {str(uuid4()): now.timestamp()})
            self._client.expire(bucket, window_seconds)
            return int(self._client.zcard(bucket))

        entries = self._fallback.setdefault(f"velocity:user:{key}", [])
        cutoff = now - timedelta(seconds=window_seconds)
        entries[:] = [item for item in entries if item > cutoff]
        entries.append(now)
        return len(entries)

    def device_activity(self, device_id: str, window_seconds: int = 86_400) -> int:
        if not device_id:
            return 0
        now = datetime.now(timezone.utc)
        bucket = f"device:activity:{device_id}"
        if self._client is not None:
            self._client.zremrangebyscore(bucket, 0, (now - timedelta(seconds=window_seconds)).timestamp())
            self._client.zadd(bucket, {str(uuid4()): now.timestamp()})
            self._client.expire(bucket, window_seconds)
            return int(self._client.zcard(bucket))
        entries = self._fallback.setdefault(bucket, [])
        cutoff = now - timedelta(seconds=window_seconds)
        entries[:] = [item for item in entries if item > cutoff]
        entries.append(now)
        return len(entries)


redis_service = RedisService()
