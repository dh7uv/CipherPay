from __future__ import annotations

from typing import Any

try:
    import redis
except Exception:  # pragma: no cover
    redis = None


class RedisService:
    def __init__(self) -> None:
        self._fallback: dict[str, Any] = {}
        self._client = None
        if redis is not None:
            try:
                self._client = redis.Redis(host="localhost", port=6379, decode_responses=True)
                self._client.ping()
            except Exception:
                self._client = None

    def increment(self, key: str, value: int = 1) -> int:
        if self._client is not None:
            return int(self._client.incr(key, value))
        self._fallback[key] = self._fallback.get(key, 0) + value
        return self._fallback[key]

    def reset(self, key: str) -> None:
        if self._client is not None:
            self._client.delete(key)
        self._fallback.pop(key, None)

    def get(self, key: str, default=None):
        if self._client is not None:
            return self._client.get(key, default)
        return self._fallback.get(key, default)


redis_service = RedisService()
