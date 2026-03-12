"""Redis cache wrapper for API responses."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from db.redis import RedisCache


class CacheManager:
    """Redis-based cache for external API responses."""

    def __init__(self, redis: RedisCache):
        self.redis = redis

    async def get_transport(
        self, origin: str, dest: str, date_str: str
    ) -> dict | None:
        key = f"transport:{origin}:{dest}:{date_str}"
        data = await self.redis.get(key)
        return json.loads(data) if data else None

    async def set_transport(
        self, origin: str, dest: str, date_str: str, data: dict
    ) -> None:
        key = f"transport:{origin}:{dest}:{date_str}"
        await self.redis.setex(key, 3600 * 6, json.dumps(data))

    async def get_currency(self, from_cur: str, to_cur: str) -> float | None:
        key = f"currency:{from_cur}:{to_cur}"
        data = await self.redis.get(key)
        return float(data) if data else None

    async def set_currency(
        self, from_cur: str, to_cur: str, rate: float
    ) -> None:
        key = f"currency:{from_cur}:{to_cur}"
        await self.redis.setex(key, 3600 * 24, str(rate))

    async def get_user_location(self, user_id: int) -> dict | None:
        key = f"user:{user_id}:location"
        data = await self.redis.get(key)
        return json.loads(data) if data else None

    async def set_user_location(
        self, user_id: int, location: dict
    ) -> None:
        key = f"user:{user_id}:location"
        await self.redis.set(key, json.dumps(location))
