"""Parsing Luma and Meetup. Pure Python, no LLM."""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

import httpx

if TYPE_CHECKING:
    from db.redis import RedisCache


class EventParser:
    """Parsing Luma and Meetup. Pure Python, no LLM."""

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
        # Check cache
        cache_key = f"events:cache:{city}:{date_from}"
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                return json.loads(cached)

        raw_events: list[dict] = []

        # Parse Luma
        luma_events = await self._parse_luma(city, lat, lon, date_from, date_to)
        raw_events.extend(luma_events)

        # Parse Meetup
        meetup_events = await self._parse_meetup(
            lat, lon, radius_km, date_from, date_to, categories
        )
        raw_events.extend(meetup_events)

        # Deduplicate
        unique = self._deduplicate(raw_events)

        # Cache for 6 hours
        if self.cache:
            await self.cache.setex(cache_key, 3600 * 6, json.dumps(unique, default=str))

        return unique

    async def _parse_luma(
        self, city: str, lat: float, lon: float, date_from: date, date_to: date
    ) -> list[dict]:
        """Call Luma discover API - returns real events with real URLs."""
        events: list[dict] = []
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    "https://api.lu.ma/discover/get-events",
                    params={
                        "pagination_limit": 20,
                        "geo_latitude": lat,
                        "geo_longitude": lon,
                    },
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "Mozilla/5.0",
                    },
                )
                if resp.status_code != 200:
                    logger.warning("Luma API status: %d", resp.status_code)
                    return []
                data = resp.json()
                # Response: {"entries": [{"event": {...}, "url": "lu.ma/xxx"}, ...]}
                entries = data.get("entries", [])
                logger.info("Luma API returned %d entries", len(entries))
                for entry in entries:
                    ev = entry.get("event", {})
                    if not ev:
                        continue
                    # Build full URL
                    slug = entry.get("url") or ev.get("url") or ""
                    if slug and not slug.startswith("http"):
                        full_url = f"https://lu.ma/{slug}"
                    elif slug.startswith("http"):
                        full_url = slug
                    else:
                        full_url = ""
                    # Parse ticket price
                    ticket_price = None
                    ticket_info = ev.get("ticket_info") or {}
                    if ticket_info.get("is_free"):
                        ticket_price = None  # free
                    elif ticket_info.get("min_price"):
                        ticket_price = float(ticket_info["min_price"]) / 100  # cents to EUR
                    # Parse datetime
                    dt_start = ev.get("start_at") or ev.get("start_time") or str(date_from)
                    events.append({
                        "source": "luma",
                        "source_id": ev.get("api_id") or ev.get("id") or slug or "",
                        "source_url": full_url,
                        "title": ev.get("name") or ev.get("title") or "",
                        "description": ev.get("description") or "",
                        "datetime_start": dt_start,
                        "location_name": (ev.get("geo_address_info") or {}).get("full_address") or "",
                        "location_city": (ev.get("geo_address_info") or {}).get("city") or city,
                        "ticket_price": ticket_price,
                        "currency": "EUR",
                        "organizer_name": (ev.get("calendar") or {}).get("name") or "",
                    })
        except Exception as e:
            logger.warning("Luma API failed: %s", e)
        return events

    async def _parse_meetup(
        self,
        lat: float,
        lon: float,
        radius_km: int,
        date_from: date,
        date_to: date,
        categories: list[str],
    ) -> list[dict]:
        """Meetup GraphQL API (api.meetup.com/gql)."""
        events: list[dict] = []
        try:
            query = """
            query($lat: Float!, $lon: Float!, $radius: Int!, $startDate: DateTime, $endDate: DateTime) {
                rankedEvents(
                    filter: {
                        lat: $lat,
                        lon: $lon,
                        radius: $radius,
                        startDateRange: $startDate,
                        endDateRange: $endDate
                    },
                    first: 50
                ) {
                    edges {
                        node {
                            id
                            title
                            description
                            dateTime
                            endTime
                            eventUrl
                            venue {
                                name
                                address
                                city
                                lat
                                lng
                            }
                            group {
                                name
                                urlname
                            }
                            feeSettings {
                                amount
                                currency
                            }
                            maxTickets
                        }
                    }
                }
            }
            """
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.meetup.com/gql",
                    json={
                        "query": query,
                        "variables": {
                            "lat": lat,
                            "lon": lon,
                            "radius": radius_km,
                            "startDate": date_from.isoformat(),
                            "endDate": date_to.isoformat(),
                        },
                    },
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    edges = (
                        data.get("data", {})
                        .get("rankedEvents", {})
                        .get("edges", [])
                    )
                    for edge in edges:
                        node = edge["node"]
                        venue = node.get("venue") or {}
                        group = node.get("group") or {}
                        fee = node.get("feeSettings") or {}
                        events.append({
                            "source": "meetup",
                            "source_id": node["id"],
                            "source_url": node.get("eventUrl", ""),
                            "title": node["title"],
                            "description": node.get("description", ""),
                            "datetime_start": node.get("dateTime", ""),
                            "datetime_end": node.get("endTime"),
                            "location_name": venue.get("name", ""),
                            "location_address": venue.get("address", ""),
                            "location_city": venue.get("city", ""),
                            "location_lat": venue.get("lat", 0.0),
                            "location_lon": venue.get("lng", 0.0),
                            "ticket_price": fee.get("amount"),
                            "currency": fee.get("currency", "EUR"),
                            "organizer_name": group.get("name", ""),
                            "organizer_url": (
                                f"https://www.meetup.com/{group['urlname']}"
                                if group.get("urlname")
                                else None
                            ),
                            "capacity": node.get("maxTickets"),
                            "food_included": False,
                        })
        except Exception:
            pass  # Meetup parsing failure is non-fatal
        return events

    def _deduplicate(self, events: list[dict]) -> list[dict]:
        """Deduplicate by (normalized_title + date + city)."""
        seen: set[tuple] = set()
        unique: list[dict] = []
        for e in events:
            key = (
                self._normalize(e["title"]),
                str(e["datetime_start"])[:10],
                e.get("location_city", ""),
            )
            if key not in seen:
                seen.add(key)
                unique.append(e)
        return unique

    def _normalize(self, title: str) -> str:
        return re.sub(r"[^a-z0-9]", "", title.lower())
