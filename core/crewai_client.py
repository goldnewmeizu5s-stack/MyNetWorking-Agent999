"""HTTP client to CrewAI Platform API for kicking off crews."""

import asyncio
import json
import logging
from typing import Callable, Awaitable, Optional

import httpx

logger = logging.getLogger(__name__)

# Progress callback type: async def callback(elapsed_sec: int) -> None
ProgressCallback = Callable[[int], Awaitable[None]]


class CrewAIClient:
    """HTTP client to CrewAI Platform deployed crew."""

    def __init__(
        self,
        base_url: str,
        bearer_token: str,
        poll_interval: int = 5,
        max_retries: int = 90,
    ):
        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token
        self.poll_interval = poll_interval
        self.max_retries = max_retries
        self.client = httpx.AsyncClient(timeout=poll_interval * max_retries + 30)
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

    async def poll_status(
        self,
        kickoff_id: str,
        on_progress: Optional[ProgressCallback] = None,
    ) -> dict:
        """Poll crew execution status until completed or failed."""
        for attempt in range(self.max_retries):
            response = await self.client.get(
                f"{self.base_url}/status/{kickoff_id}",
                headers=self._headers,
            )
            data = response.json()
            status = data.get("status", "unknown")
            logger.info("Poll %d/%d: status=%s", attempt + 1, self.max_retries, status)
            if status in ("completed", "failed", "error"):
                return data
            elapsed = (attempt + 1) * self.poll_interval
            if on_progress and elapsed % 60 == 0:
                await on_progress(elapsed)
            await asyncio.sleep(self.poll_interval)
        raise TimeoutError(
            f"Crew execution {kickoff_id} timed out after "
            f"{self.max_retries * self.poll_interval}s"
        )

    async def run_crew(
        self,
        inputs: dict,
        on_progress: Optional[ProgressCallback] = None,
    ) -> dict:
        """Kickoff and wait for result."""
        kickoff = await self.kickoff(inputs)
        kickoff_id = kickoff["kickoff_id"]
        return await self.poll_status(kickoff_id, on_progress=on_progress)

    async def run_discovery(
        self,
        raw_events: list,
        context: dict,
    ) -> dict:
        """Run discovery flow (Scout searches + Analyst scores)."""
        user_profile = context.get("user_profile", {})
        return await self.run_crew(
            {
                "raw_events": json.dumps(raw_events, ensure_ascii=False, default=str),
                "context": json.dumps(context, ensure_ascii=False, default=str),
                "debrief_data": "[]",
                "period": "",
                "event": "any",
                "existing_data": "[]",
                "user_profile": json.dumps(user_profile, ensure_ascii=False, default=str),
            },
        )

    async def close(self):
        await self.client.aclose()
