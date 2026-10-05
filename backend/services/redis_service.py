from __future__ import annotations

import hashlib
import logging
import threading
import time
from typing import Any

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

try:
    import redis
except ImportError:  # pragma: no cover
    redis = None


class RedisService:
    def __init__(self) -> None:
        self._fallback: dict[str, Any] = {}
        self._fallback_lock = threading.Lock()
        self._last_fallback_cleanup = 0.0
        self._client = None
        self._connected = False
        if redis is not None:
            try:
                self._client = redis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    password=settings.redis_password or None,
                    decode_responses=True,
                    socket_connect_timeout=1,
                    socket_timeout=1,
                )
                self._client.ping()
                self._connected = True
            except redis.RedisError as error:
                logger.warning("Redis unavailable; using in-memory fraud tracking: %s", error)
                self._client = None

    @property
    def connected(self) -> bool:
        return self._connected

    def _disable_client(self, error: Exception) -> None:
        logger.warning("Redis request failed; falling back to in-memory tracking: %s", error)
        self._client = None
        self._connected = False

    def record_transaction(
        self,
        user_id: str,
        device_id: str,
        transaction_id: str,
        timestamp: float | None = None,
    ) -> dict[str, int]:
        now = time.time() if timestamp is None else timestamp
        velocity_key = f"velocity:user:{user_id}"
        device_fingerprint = hashlib.sha256(device_id.encode("utf-8")).hexdigest()
        device_key = f"device:activity:{device_fingerprint}"

        if self._client is not None:
            try:
                pipeline = self._client.pipeline()
                pipeline.zremrangebyscore(velocity_key, "-inf", now - 3600)
                pipeline.zremrangebyscore(device_key, "-inf", now - 86400)
                pipeline.zcard(velocity_key)
                pipeline.zcard(device_key)
                counts = pipeline.execute()
                velocity_count, device_count = int(counts[2]), int(counts[3])
                pipeline = self._client.pipeline()
                pipeline.zadd(velocity_key, {transaction_id: now})
                pipeline.expire(velocity_key, 3600)
                pipeline.zadd(device_key, {transaction_id: now})
                pipeline.expire(device_key, 86400)
                pipeline.execute()
                return {"velocity_count": velocity_count, "device_activity_count": device_count}
            except redis.RedisError as error:
                self._disable_client(error)

        with self._fallback_lock:
            velocity_count = self._fallback_add(velocity_key, transaction_id, now, 3600)
            device_count = self._fallback_add(device_key, transaction_id, now, 86400)
        return {"velocity_count": velocity_count, "device_activity_count": device_count}

    def _fallback_add(self, key: str, member: str, now: float, window: int) -> int:
        entries: dict[str, float] = self._fallback.setdefault(key, {})
        earliest = now - window
        expired = [entry for entry, score in entries.items() if score <= earliest]
        for entry in expired:
            del entries[entry]
        previous_count = len(entries)
        entries[member] = now
        return previous_count

    def _prune_fallback(self, now: float) -> None:
        if now - self._last_fallback_cleanup < 60:
            return
        self._last_fallback_cleanup = now

        for key, value in list(self._fallback.items()):
            if key.startswith("ratelimit:") and isinstance(value, dict):
                if value.get("expires_at", now) <= now:
                    self._fallback.pop(key, None)
                continue

            if key.startswith("velocity:user:"):
                window = 3600
            elif key.startswith("device:activity:"):
                window = 86400
            else:
                continue

            if isinstance(value, dict):
                earliest = now - window
                for member, score in list(value.items()):
                    if score <= earliest:
                        value.pop(member, None)
                if not value:
                    self._fallback.pop(key, None)

    def allow_request(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        if limit < 1 or window_seconds < 1:
            raise ValueError("Rate limit and window must be positive")

        if self._client is not None:
            try:
                pipeline = self._client.pipeline()
                pipeline.incr(key)
                pipeline.expire(key, window_seconds, nx=True)
                count, _ = pipeline.execute()
                return int(count) <= limit
            except redis.RedisError as error:
                self._disable_client(error)

        with self._fallback_lock:
            self._prune_fallback(now)
            entry = self._fallback.get(key)
            if entry is None or entry["expires_at"] <= now:
                entry = {"count": 0, "expires_at": now + window_seconds}
                self._fallback[key] = entry
            entry["count"] += 1
            return entry["count"] <= limit

    def increment(self, key: str, value: int = 1) -> int:
        if self._client is not None:
            try:
                return int(self._client.incr(key, value))
            except redis.RedisError as error:
                self._disable_client(error)
        now = time.time()
        with self._fallback_lock:
            self._prune_fallback(now)
            self._fallback[key] = int(self._fallback.get(key, 0)) + value
            return self._fallback[key]

    def reset(self, key: str) -> None:
        if self._client is not None:
            try:
                self._client.delete(key)
            except redis.RedisError as error:
                self._disable_client(error)
        with self._fallback_lock:
            self._fallback.pop(key, None)

    def get(self, key: str, default=None):
        if self._client is not None:
            try:
                return self._client.get(key, default)
            except redis.RedisError as error:
                self._disable_client(error)
        return self._fallback.get(key, default)


redis_service = RedisService()
