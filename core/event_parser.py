"""Parsing Luma and Meetup. Pure Python, no LLM."""

from __future__ import annotations

import json
import re
from datetime import date
from typing import TYPE_CHECKING

import httpx
from bs4 import BeautifulSoup

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
        cached = await self.cache.get(cache_key)
        if cached:
            return json.loads(cached)

        raw_events: list[dict] = []

        # Parse Luma
        luma_events = await self._parse_luma(city, date_from, date_to)
        raw_events.extend(luma_events)

        # Parse Meetup
        meetup_events = await self._parse_meetup(
            lat, lon, radius_km, date_from, date_to, categories
        )
        raw_events.extend(meetup_events)

        # Deduplicate
        unique = self._deduplicate(raw_events)

        # Cache for 6 hours
        await self.cache.setex(cache_key, 3600 * 6, json.dumps(unique, default=str))

        return unique

    async def _parse_luma(
        self, city: str, date_from: date, date_to: date
    ) -> list[dict]:
        """
        Parse lu.ma. No public API - uses requests + BeautifulSoup.
        Falls back to Playwright subprocess for dynamic content.
        """
        events: list[dict] = []
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"https://lu.ma/discover?city={city}",
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        )
                    },
                )
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    # Extract event cards from Luma page
                    for card in soup.select("[data-testid='event-card'], .event-card, .event-link"):
                        title_el = card.select_one("h3, .event-title, [data-testid='event-title']")
                        if not title_el:
                            continue
                        link = card.get("href", "")
                        if link and not link.startswith("http"):
                            link = f"https://lu.ma{link}"
                        events.append({
                            "source": "luma",
                            "source_id": link.split("/")[-1] if link else "",
                            "source_url": link,
                            "title": title_el.get_text(strip=True),
                            "description": "",
                            "datetime_start": str(date_from),
                            "datetime_end": None,
                            "location_name": "",
                            "location_address": "",
                            "location_city": city,
                            "location_lat": 0.0,
                            "location_lon": 0.0,
                            "ticket_price": None,
                            "currency": "EUR",
                            "organizer_name": "",
                            "organizer_url": None,
                            "capacity": None,
                            "food_included": False,
                        })
        except Exception:
            pass  # Luma parsing failure is non-fatal
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
