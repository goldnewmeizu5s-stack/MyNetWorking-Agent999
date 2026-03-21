"""Nominatim geocoding helper."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


async def geocode_city(city: str) -> tuple[float, float] | None:
    """Return (lat, lon) for a city name via OSM Nominatim, or None on failure."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": city, "format": "json", "limit": 1},
                headers={"User-Agent": "PlanetNineBot/1.0"},
            )
            if resp.status_code == 200:
                results = resp.json()
                if results:
                    return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        logger.warning("Geocoding failed for %s: %s", city, e)
    return None
