"""Event parser stub — Luma/Meetup APIs unavailable from Railway IP."""

from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from db.redis import RedisCache

logger = logging.getLogger(__name__)


class EventParser:
    """Stub: direct API parsing disabled. Events come from Perplexity + Claude."""

    def __init__(self, redis_cache: RedisCache):
        self.cache = redis_cache

    async def parse_all(
        self,
        city: str,
        lat: float,
        lon: float,
        date_from: date,
        date_to: date,
        categories: list[str],
        radius_km: int = 15,
    ) -> list[dict]:
        # Luma/Meetup APIs unavailable from Railway IP.
        # All event discovery goes through Perplexity + Claude.
        return []
