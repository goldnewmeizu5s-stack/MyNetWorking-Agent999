"""Direct API client - bypasses CrewAI Platform for speed."""

import json
import logging
import os
from typing import Callable, Awaitable, Optional

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

    async def run_discovery(self, raw_events: list, context: dict) -> dict:
        """Run discovery: Perplexity search + Claude scoring. ~60 seconds."""
        user_profile = context.get("user_profile", {})
        city = context.get("current_location", {}).get("city", "Tbilisi")
        interests = user_profile.get("interests", ["AI", "startups"])
        interests_str = ", ".join(interests[:3])

        # Step 1: Search via Perplexity
        logger.info("Starting Perplexity search for %s in %s", interests_str, city)
        search_results = await self._perplexity_search(
            f"upcoming networking events {interests_str} in {city} 2026"
        )

        # Step 2: Score and rank via Claude directly
        logger.info("Scoring events via Claude direct API")
        scored = await self._claude_score(
            search_results=search_results,
            raw_events=raw_events,
            user_profile=user_profile,
            city=city,
        )

        return {"output": json.dumps(scored), "status": "completed"}

    async def _perplexity_search(self, query: str) -> str:
        """Call Perplexity Sonar API directly."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._perplexity_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "sonar",
                        "messages": [{"role": "user", "content": query}],
                    },
                )
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning("Perplexity search failed: %s", e)
            return ""

    async def _claude_score(
        self,
        search_results: str,
        raw_events: list,
        user_profile: dict,
        city: str,
    ) -> dict:
        """Call Claude API directly to parse and score events."""
        interests = user_profile.get("interests", [])
        budget = user_profile.get("budget_limit_ticket", 100)

        prompt = f"""You are an event scoring assistant.

Search results about events in {city}:
{search_results[:3000]}

Pre-parsed events: {json.dumps(raw_events[:3], ensure_ascii=False)[:1000]}

User interests: {interests}
User budget: EUR{budget}

Extract and score up to 5 networking events. For each event return:
- title, datetime_start, location_name, location_city, ticket_price (null if free)
- source_url, organizer_name, event_type, description
- total_score (0-100 based on relevance to interests and budget fit)
- recommendation: "strong_recommend" if >80, "suitable" if >60, "borderline" if >40, else "skip"
- recommendation_reason (1 sentence)
- source: "perplexity"
- source_id: slugified title
- currency: "EUR"
- language: "en"

Return ONLY valid JSON object: {{"top_events": [...], "scored_events": [...]}}
No markdown, no explanation."""

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
                        "max_tokens": 2000,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                data = resp.json()
                text = data["content"][0]["text"].strip()
                # Strip markdown if present
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                return json.loads(text)
        except Exception as e:
            logger.error("Claude scoring failed: %s", e)
            return {"top_events": [], "scored_events": []}

    async def run_crew(self, inputs: dict, on_progress=None) -> dict:
        """Legacy method - used by debrief and other crews via Platform."""
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
                import asyncio

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

    async def close(self):
        pass  # No persistent client to close
