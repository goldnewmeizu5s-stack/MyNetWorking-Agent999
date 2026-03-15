"""HTTP client to CrewAI Platform API for kicking off crews."""

import asyncio
import json
import logging

import httpx

logger = logging.getLogger(__name__)


class CrewAIClient:
    """HTTP client to CrewAI Platform deployed crew."""

    def __init__(self, base_url: str, bearer_token: str):
        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token
        self.client = httpx.AsyncClient(timeout=180)
        self._headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
        }

    async def kickoff(self, inputs: dict) -> dict:
        """Kickoff the deployed crew with given inputs."""
        logger.info("CrewAI kickoff with inputs: %s", list(inputs.keys()))
        response = await self.client.post(
            f"{self.base_url}/kickoff",
            headers=self._headers,
            json={"inputs": inputs},
        )
        response.raise_for_status()
        data = response.json()
        logger.info("Kickoff started: %s", data.get("kickoff_id"))
        return data

    async def poll_status(self, kickoff_id: str, poll_interval: int = 3, max_retries: int = 60) -> dict:
        """Poll crew execution status until completed or failed."""
        for attempt in range(max_retries):
            response = await self.client.get(
                f"{self.base_url}/status/{kickoff_id}",
                headers=self._headers,
            )
            data = response.json()
            status = data.get("status", "unknown")
            logger.info("Poll %d: status=%s", attempt + 1, status)
            if status in ("completed", "failed", "error"):
                return data
            await asyncio.sleep(poll_interval)
        raise TimeoutError(f"Crew execution {kickoff_id} timed out after {max_retries * poll_interval}s")

    async def run_crew(self, inputs: dict) -> dict:
        """Kickoff and wait for result."""
        kickoff = await self.kickoff(inputs)
        kickoff_id = kickoff["kickoff_id"]
        return await self.poll_status(kickoff_id)

    async def run_discovery(self, raw_events: list, context: dict) -> dict:
        """Run discovery flow (Scout + Analyst)."""
        return await self.run_crew({
            "raw_events": json.dumps(raw_events, ensure_ascii=False),
            "context": json.dumps(context, ensure_ascii=False),
            "debrief_data": "[]",
            "period": "",
            "event": "any",
            "existing_data": "[]",
            "user_profile": json.dumps(context.get("user_profile", {}), ensure_ascii=False),
        })

    async def close(self):
        await self.client.aclose()
