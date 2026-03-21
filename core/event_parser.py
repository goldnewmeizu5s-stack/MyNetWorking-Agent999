"""Parsing Luma and Meetup. Pure Python, no LLM."""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import TYPE_CHECKING

import httpx
from bs4 import BeautifulSoup

if TYPE_CHECKING:
    from db.redis import RedisCache

logger = logging.getLogger(__name__)


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
        cache_key = f"events:cache:{city}:{date_from}"
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                return json.loads(cached)

        raw_events: list[dict] = []

        luma_events = await self._parse_luma(city, lat, lon, date_from, date_to)
        raw_events.extend(luma_events)

        meetup_events = await self._parse_meetup(
            lat, lon, radius_km, date_from, date_to, categories
        )
        raw_events.extend(meetup_events)

        unique = self._deduplicate(raw_events)

        if self.cache:
            await self.cache.setex(
                cache_key, 3600 * 6, json.dumps(unique, default=str)
            )

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
                        "pagination_limit": 30,
                        "geo_latitude": lat,
                        "geo_longitude": lon,
                    },
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "Mozilla/5.0",
                    },
                )

                logger.info(
                    "Luma API response: status=%d, body[:200]=%s",
                    resp.status_code,
                    resp.text[:200],
                )

                if resp.status_code in (401, 403):
                    logger.warning(
                        "Luma API %d, trying fallback endpoint", resp.status_code
                    )
                    resp = await client.get(
                        "https://lu.ma/api/v2/event/get-events-for-discover",
                        params={
                            "pagination_limit": 30,
                            "geo_latitude": lat,
                            "geo_longitude": lon,
                        },
                        headers={
                            "Accept": "application/json",
                            "User-Agent": "Mozilla/5.0",
                        },
                    )
                    logger.info(
                        "Luma fallback response: status=%d, body[:200]=%s",
                        resp.status_code,
                        resp.text[:200],
                    )

                if resp.status_code != 200:
                    logger.warning("Luma API final status: %d", resp.status_code)
                    return []

                try:
                    data = resp.json()
                except json.JSONDecodeError as je:
                    logger.error(
                        "Luma API returned non-JSON: %s | body[:300]=%s",
                        je,
                        resp.text[:300],
                    )
                    return []

                # Log raw structure to diagnose response shape in Railway logs
                logger.info(
                    "Luma API raw top-level keys: %s | sample: %s",
                    list(data.keys()),
                    str(data)[:300],
                )

                # Luma response can vary — try all known shapes
                entries = (
                    data.get("entries")
                    or data.get("events")
                    or (data.get("data") or {}).get("entries")
                    or (data.get("data") or {}).get("events")
                    or []
                )

                logger.info("Luma API: %d entries found", len(entries))

                for entry in entries:
                    if not isinstance(entry, dict):
                        continue

                    # entry shape A: {"event": {...}, "url": "slug"}
                    # entry shape B: flat event object
                    ev = entry.get("event") or {}
                    if not ev:
                        if entry.get("name") or entry.get("title"):
                            ev = entry
                        else:
                            continue

                    title = ev.get("name") or ev.get("title") or ""
                    if not title:
                        continue

                    # URL slug: prefer entry-level, fall back to event-level
                    slug = (
                        entry.get("url")
                        or ev.get("url")
                        or ev.get("slug")
                        or ev.get("api_id")
                        or ev.get("id")
                        or ""
                    )
                    if slug and not slug.startswith("http"):
                        full_url = f"https://lu.ma/{slug}"
                    elif slug.startswith("http"):
                        full_url = slug
                    else:
                        full_url = ""

                    source_id = (
                        ev.get("api_id")
                        or ev.get("id")
                        or slug
                        or ""
                    )

                    # Ticket price
                    ticket_price = None
                    ticket_info = ev.get("ticket_info") or {}
                    if not ticket_info.get("is_free") and ticket_info.get("min_price"):
                        try:
                            ticket_price = float(ticket_info["min_price"]) / 100
                        except (TypeError, ValueError):
                            ticket_price = None

                    dt_start = (
                        ev.get("start_at")
                        or ev.get("start_time")
                        or str(date_from)
                    )

                    geo = ev.get("geo_address_info") or {}

                    events.append({
                        "source": "luma",
                        "source_id": source_id,
                        "source_url": full_url,
                        "title": title,
                        "description": ev.get("description") or "",
                        "datetime_start": dt_start,
                        "location_name": geo.get("full_address") or "",
                        "location_city": geo.get("city") or city,
                        "ticket_price": ticket_price,
                        "currency": "EUR",
                        "organizer_name": (ev.get("calendar") or {}).get("name") or "",
                    })
        except Exception as e:
            logger.warning("Luma API failed: %s", e, exc_info=True)

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
        """Two-level Meetup parser: GraphQL → HTML fallback."""
        keyword = " ".join(categories[:2]) if categories else "networking"
        events = await self._meetup_graphql(lat, lon, radius_km, keyword)
        if not events:
            logger.info("Meetup GraphQL empty, trying HTML fallback")
            events = await self._meetup_html(lat, lon, keyword)
        logger.info("Meetup returned %d events total", len(events))
        return events

    async def _meetup_graphql(
        self, lat: float, lon: float, radius_km: int, keyword: str
    ) -> list[dict]:
        """keywordSearch — works without OAuth for public events."""
        query = """
        query($query: String!, $lat: Float!, $lon: Float!, $radius: Int!) {
          keywordSearch(
            filter: {
              query: $query
              lat: $lat
              lon: $lon
              radius: $radius
              source: EVENTS
            }
            first: 20
          ) {
            edges {
              node {
                result {
                  ... on Event {
                    id
                    title
                    dateTime
                    endTime
                    eventUrl
                    description
                    isOnline
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
          }
        }
        """
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    "https://api.meetup.com/gql",
                    json={
                        "query": query,
                        "variables": {
                            "query": keyword,
                            "lat": lat,
                            "lon": lon,
                            "radius": radius_km,
                        },
                    },
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                )
                if resp.status_code != 200:
                    logger.warning("Meetup GraphQL status: %d", resp.status_code)
                    return []

                data = resp.json()
                edges = (
                    data.get("data", {})
                    .get("keywordSearch", {})
                    .get("edges", [])
                )
                return [
                    self._meetup_node_to_event(e["node"]["result"])
                    for e in edges
                    if e.get("node", {}).get("result", {}).get("id")
                ]
        except Exception as e:
            logger.warning("Meetup GraphQL failed: %s", e)
            return []

    async def _meetup_html(
        self, lat: float, lon: float, keyword: str
    ) -> list[dict]:
        """Fallback: scrape meetup.com/find, extract JSON-LD."""
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    "https://www.meetup.com/find/events/",
                    params={
                        "allMeetups": "true",
                        "lat": lat,
                        "lon": lon,
                        "radius": 25,
                        "keywords": keyword,
                    },
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                        ),
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                )
                if resp.status_code != 200:
                    logger.warning("Meetup HTML status: %d", resp.status_code)
                    return []

                soup = BeautifulSoup(resp.text, "html.parser")
                events = []

                # Primary: JSON-LD embedded in page
                for script in soup.find_all("script", type="application/ld+json"):
                    try:
                        data = json.loads(script.string or "")
                        items = (
                            data.get("@graph", [data])
                            if isinstance(data, dict)
                            else data
                        )
                        for item in items:
                            if item.get("@type") == "Event":
                                ev = self._jsonld_to_event(item)
                                if ev:
                                    events.append(ev)
                    except (json.JSONDecodeError, AttributeError):
                        continue

                # Secondary: anchor tags fallback
                if not events:
                    for a in soup.select("a[data-event-id], a[href*='/events/']"):
                        href = a.get("href", "")
                        if "meetup.com" not in href and href.startswith("/"):
                            href = f"https://www.meetup.com{href}"
                        title_el = a.select_one(
                            "h3, h2, [class*='title'], [class*='name']"
                        )
                        if title_el and href:
                            events.append({
                                "source": "meetup",
                                "source_id": href.rstrip("/").split("/")[-1],
                                "source_url": href,
                                "title": title_el.get_text(strip=True),
                                "description": "",
                                "datetime_start": str(date.today()),
                                "location_city": "",
                                "ticket_price": None,
                                "currency": "EUR",
                            })

                logger.info("Meetup HTML parsed %d events", len(events))
                return events[:15]
        except Exception as e:
            logger.warning("Meetup HTML scraping failed: %s", e)
            return []

    def _meetup_node_to_event(self, node: dict) -> dict:
        """Convert Meetup GraphQL node to internal event format."""
        venue = node.get("venue") or {}
        group = node.get("group") or {}
        fee = node.get("feeSettings") or {}
        url = node.get("eventUrl", "")
        return {
            "source": "meetup",
            "source_id": node.get("id", ""),
            "source_url": url,
            "title": node.get("title", ""),
            "description": (node.get("description") or "")[:500],
            "datetime_start": node.get("dateTime", ""),
            "datetime_end": node.get("endTime"),
            "location_name": venue.get("name", ""),
            "location_city": venue.get("city", ""),
            "location_lat": venue.get("lat", 0.0),
            "location_lon": venue.get("lng", 0.0),
            "ticket_price": (
                float(fee["amount"]) / 100 if fee.get("amount") else None
            ),
            "currency": fee.get("currency", "EUR"),
            "organizer_name": group.get("name", ""),
            "organizer_url": (
                f"https://www.meetup.com/{group['urlname']}"
                if group.get("urlname")
                else None
            ),
        }

    def _jsonld_to_event(self, item: dict) -> dict | None:
        """Convert JSON-LD Event to internal format."""
        url = item.get("url", "")
        title = item.get("name", "")
        if not title or not url:
            return None

        location = item.get("location") or {}
        offers = item.get("offers") or [{}]
        if isinstance(offers, dict):
            offers = [offers]
        price = offers[0].get("price") if offers else None

        return {
            "source": "meetup",
            "source_id": url.rstrip("/").split("/")[-1],
            "source_url": url,
            "title": title,
            "description": item.get("description", "")[:500],
            "datetime_start": item.get("startDate", ""),
            "datetime_end": item.get("endDate"),
            "location_name": location.get("name", ""),
            "location_city": (
                (location.get("address") or {}).get("addressLocality", "")
            ),
            "ticket_price": float(price) if price else None,
            "currency": offers[0].get("priceCurrency", "EUR") if offers else "EUR",
            "organizer_name": (item.get("organizer") or {}).get("name", ""),
        }

    def _deduplicate(self, events: list[dict]) -> list[dict]:
        """Deduplicate by (normalized_title + date + city)."""
        seen: set[tuple] = set()
        unique: list[dict] = []
        for e in events:
            key = (
                self._normalize(e.get("title", "")),
                str(e.get("datetime_start", ""))[:10],
                e.get("location_city", ""),
            )
            if key not in seen:
                seen.add(key)
                unique.append(e)
        return unique

    def _normalize(self, title: str) -> str:
        return re.sub(r"[^a-z0-9]", "", title.lower())
