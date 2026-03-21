"""Direct API client - bypasses CrewAI Platform for speed."""

import asyncio
import json
import logging
import os
import re
from typing import Awaitable, Callable, Optional

import httpx

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int], Awaitable[None]]


class CrewAIClient:
    """Direct API client: Perplexity + Claude, no CrewAI Platform overhead."""

    def __init__(
        self,
        base_url: str,
        bearer_token: str,
        poll_interval: int = 10,
        max_retries: int = 180,
    ):
        self.base_url = base_url
        self.bearer_token = bearer_token
        self.poll_interval = poll_interval
        self.max_retries = max_retries
        self._perplexity_key = os.environ.get("PERPLEXITY_API_KEY", "")
        self._anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")

    # Matches both full URLs (https://lu.ma/...) and bare domains (lu.ma/...)
    _URL_RE = re.compile(
        r"(?:https?://)?(?:lu\.ma|(?:www\.)?meetup\.com|(?:www\.)?eventbrite\.com|ethglobal\.com)"
        r"/[\w\-/.?=&%#@!+]+"
    )

    async def run_discovery(self, raw_events: list, context: dict) -> dict:
        """Run discovery: parallel Perplexity searches + Claude scoring."""
        user_profile = context.get("user_profile", {})
        city = context.get("current_location", {}).get("city", "Tbilisi")
        interests = user_profile.get("interests", ["AI", "startups"])
        interests_str = ", ".join(interests[:3])

        logger.info("Perplexity parallel search for %s in %s", interests_str, city)

        search1, search2, search3 = await asyncio.gather(
            self._perplexity_search(
                f"upcoming networking events {interests_str} in {city} 2026"
            ),
            self._perplexity_search(
                f"tech conference meetup AI startups {city} April May June 2026"
            ),
            self._perplexity_search(
                f"meetup.com events networking {city} 2026",
                domain_filter=["meetup.com"],
            ),
        )

        # Log previews to understand Perplexity response format
        logger.info("Perplexity search1 preview: %s", search1[:500])
        logger.info("Perplexity search2 preview: %s", search2[:500])
        logger.info("Perplexity search3 preview: %s", search3[:500])

        search_results = "\n\n".join(filter(None, [search1, search2, search3]))
        logger.info("Search results: %d chars total", len(search_results))

        # Pre-extract all event URLs before sending to Claude
        # Normalize: add https:// to bare domain matches (lu.ma/..., meetup.com/...)
        raw_urls = self._URL_RE.findall(search_results)
        extracted_urls = list(dict.fromkeys(
            u if u.startswith("http") else f"https://{u}" for u in raw_urls
        ))
        logger.info("Extracted %d unique URLs from search results", len(extracted_urls))

        scored = await self._claude_score(
            search_results=search_results,
            extracted_urls=extracted_urls,
            user_profile=user_profile,
            city=city,
        )

        return {"output": json.dumps(scored), "status": "completed"}

    async def run_debrief(self, debrief_data: dict, context: dict) -> dict:
        """Calculate ROI directly without LLM."""
        event = debrief_data.get("event", {})
        contacts_count = debrief_data.get("contacts_count", 0)
        contacts_quality = debrief_data.get("contacts_quality_avg", 7.0)
        user_rating = debrief_data.get("user_rating", 5)
        actual_cost = debrief_data.get("actual_cost", 0)
        forecast_cost = event.get("total_estimated_cost", 0)

        divisor = actual_cost if actual_cost > 0 else 0.5
        roi_score = round(
            (contacts_count * contacts_quality * user_rating) / divisor, 2
        )

        if forecast_cost and forecast_cost > 0:
            diff_pct = round((actual_cost - forecast_cost) / forecast_cost * 100)
            sign = "+" if diff_pct > 0 else ""
            comparison = (
                f"Forecast: EUR{forecast_cost:.2f}, "
                f"actual: EUR{actual_cost:.2f} ({sign}{diff_pct}%)"
            )
        else:
            comparison = f"Actual cost: EUR{actual_cost:.2f}"

        return {
            "output": json.dumps({
                "roi_score": roi_score,
                "comparison_to_forecast": comparison,
                "contacts_count": contacts_count,
                "event_id": debrief_data.get("event_id", ""),
                "actual_cost": actual_cost,
                "contacts_quality_avg": contacts_quality,
                "user_rating": user_rating,
            }),
            "status": "completed",
        }

    async def _perplexity_search(
        self, query: str, domain_filter: list[str] | None = None
    ) -> str:
        """Call Perplexity Sonar API directly."""
        try:
            payload: dict = {
                "model": "sonar",
                "messages": [{"role": "user", "content": query}],
            }
            if domain_filter:
                payload["search_domain_filter"] = domain_filter

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._perplexity_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning("Perplexity search failed: %s", e)
            return ""

    async def _claude_score(
        self,
        search_results: str,
        extracted_urls: list[str],
        user_profile: dict,
        city: str,
    ) -> dict:
        """Call Claude API directly to parse and score events."""
        interests = user_profile.get("interests", [])
        budget = user_profile.get("budget_limit_ticket", 100)

        urls_block = "\n".join(f"  - {u}" for u in extracted_urls) if extracted_urls else "  (none found)"

        prompt = f"""You are an event discovery and scoring assistant.

Search results about networking events in {city}:
{search_results[:6000]}

EXTRACTED URLs (pre-extracted from search results — this is the ONLY source of truth for URLs):
{urls_block}

User interests: {interests}
User budget limit: EUR{budget} per ticket

Your task: extract and score up to 8 networking events from the search results.

For each event provide these exact fields:
- title: event name as string
- datetime_start: date string "YYYY-MM-DD" or null if unknown
- location_name: venue name as string or null
- location_city: city name as string (always fill this)
- ticket_price: price as number like 25.0, or null if free
- source_url: Use URLs ONLY from the EXTRACTED URLs list above. Match each event to the most relevant URL from that list. Do not invent or guess URLs. If no URL from the list matches this event, set source_url to null.
- organizer_name: organizer as string or null
- event_type: one of "conference", "meetup", "workshop", "networking_dinner", "other"
- description: 1-2 sentence description
- total_score: integer 0-100 based on relevance to user interests and budget fit
- recommendation: exactly "strong_recommend" if score>=80, "suitable" if score>=60, "borderline" if score>=40, "skip" otherwise
- recommendation_reason: one sentence explaining the score
- source: "luma" if source_url contains "lu.ma", "meetup" if "meetup.com", "eventbrite" if "eventbrite.com", otherwise "perplexity"
- source_id: URL-friendly slug of the title (lowercase, hyphens, no spaces, max 40 chars)
- currency: always "EUR"
- language: "en" or detected language code

Scoring guide:
- 80-100: directly matches user interests, within budget, confirmed real event
- 60-79: partially matches interests or slightly over budget
- 40-59: tangentially related or significantly over budget
- 0-39: irrelevant to user interests

Return ONLY a valid JSON object with this exact structure (no markdown, no code blocks, no explanation):
{{"top_events": [list of up to 8 best events], "scored_events": [same list]}}"""

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self._anthropic_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 8096,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                data = resp.json()
                text = data["content"][0]["text"].strip()
                logger.info("Claude raw response length: %d", len(text))

                # Strip markdown fences if present
                if "```" in text:
                    for part in text.split("```"):
                        part = part.strip()
                        if part.startswith("json"):
                            part = part[4:].strip()
                        if part.startswith("{"):
                            text = part
                            break

                # Find first complete JSON object via brace matching
                start = text.find("{")
                if start == -1:
                    logger.error("No JSON object found in Claude response")
                    return {"top_events": [], "scored_events": []}

                depth = 0
                end = -1
                for i, ch in enumerate(text[start:], start):
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break

                if end == -1:
                    logger.error(
                        "Unterminated JSON in Claude response, length=%d", len(text)
                    )
                    return {"top_events": [], "scored_events": []}

                result = json.loads(text[start:end])
                logger.info(
                    "Parsed %d top_events", len(result.get("top_events", []))
                )
                return result
        except Exception as e:
            logger.error("Claude scoring failed: %s", e, exc_info=True)
            return {"top_events": [], "scored_events": []}

    async def find_event_url(self, event_title: str, city: str) -> str | None:
        """Search for event registration URL at booking time."""
        clean_title = re.sub(r"\s*\([^)]*\)", "", event_title).strip()
        words = clean_title.split()
        short_title = " ".join(words[:5])
        logger.info("Searching URL for: '%s' (from '%s')", short_title, event_title)

        url_pattern = re.compile(
            r"https?://(?:lu\.ma|(?:www\.)?meetup\.com|(?:www\.)?eventbrite\.com)"
            r"/[\w\-/]+"
        )

        # Attempt 1: domain-filtered search with 5-word title
        r1 = await self._perplexity_search(
            f"{short_title} {city} event 2026",
            domain_filter=["lu.ma", "meetup.com", "eventbrite.com"],
        )
        urls = url_pattern.findall(r1)
        if urls:
            logger.info("Found URL (attempt 1): %s", urls[0])
            return urls[0]

        # Attempt 2: broader search without domain filter
        r2 = await self._perplexity_search(
            f"{short_title} {city} registration 2026"
        )
        urls = url_pattern.findall(r2)
        if urls:
            logger.info("Found URL (attempt 2): %s", urls[0])
            return urls[0]

        # Attempt 3: ultra-short 3-word title
        if len(words) > 3:
            ultra_short = " ".join(words[:3])
            r3 = await self._perplexity_search(
                f"{ultra_short} {city} 2026",
                domain_filter=["lu.ma", "meetup.com", "eventbrite.com"],
            )
            urls = url_pattern.findall(r3)
            if urls:
                logger.info("Found URL (attempt 3): %s", urls[0])
                return urls[0]

        logger.warning("No URL found for '%s' after 3 attempts", event_title)
        return None

    async def run_crew(self, inputs: dict, on_progress: Optional[ProgressCallback] = None) -> dict:
        """Legacy method — calls CrewAI Platform for weekly report."""
        if not self.base_url or not self.bearer_token:
            logger.warning("CrewAI Platform not configured, skipping")
            return {"output": "{}", "status": "skipped"}

        async with httpx.AsyncClient(timeout=1800) as client:
            resp = await client.post(
                f"{self.base_url}/kickoff",
                headers={
                    "Authorization": f"Bearer {self.bearer_token}",
                    "Content-Type": "application/json",
                },
                json={"inputs": inputs},
            )
            resp.raise_for_status()
            kickoff_id = resp.json()["kickoff_id"]

            for attempt in range(self.max_retries):
                await asyncio.sleep(self.poll_interval)
                status_resp = await client.get(
                    f"{self.base_url}/status/{kickoff_id}",
                    headers={"Authorization": f"Bearer {self.bearer_token}"},
                )
                data = status_resp.json()
                status = data.get("status", "unknown")
                logger.info("Poll %d/%d: %s", attempt + 1, self.max_retries, status)
                if status in ("completed", "failed", "error"):
                    return data

            raise TimeoutError(f"Crew {kickoff_id} timed out")

    async def run_weekly_report(self, context: dict, period: str) -> dict:
        """Run weekly report via CrewAI Platform."""
        return await self.run_crew({
            "raw_events": "[]",
            "context": json.dumps(context, ensure_ascii=False, default=str),
            "debrief_data": "[]",
            "period": period,
            "event": "any",
            "existing_data": "[]",
            "user_profile": json.dumps(
                context.get("user_profile", {}), ensure_ascii=False, default=str
            ),
        })

    async def close(self) -> None:
        pass  # No persistent client to close
