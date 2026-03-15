"""Redis cache layer using aioredis."""

from __future__ import annotations

import redis.asyncio as aioredis


class RedisCache:
    """Async Redis cache wrapper."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._redis: aioredis.Redis | None = None

    async def connect(self) -> None:
        self._redis = aioredis.from_url(
            self.redis_url, decode_responses=True
        )

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()

    async def get(self, key: str) -> str | None:
        if not self._redis:
            return None
        return await self._redis.get(key)

    async def set(self, key: str, value: str) -> None:
        if self._redis:
            await self._redis.set(key, value)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        if self._redis:
            await self._redis.setex(key, ttl, value)

    async def delete(self, key: str) -> None:
        if self._redis:
            await self._redis.delete(key)
