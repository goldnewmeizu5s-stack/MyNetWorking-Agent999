"""HTTP client to CrewAI Platform API for kicking off crews."""

import asyncio
import json

import httpx


class CrewAIClient:
    """HTTP client to CrewAI Platform API for kicking off crews."""

    def __init__(self, base_url: str, bearer_token: str):
        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token
        self.client = httpx.AsyncClient(timeout=120)

    async def _kickoff(self, crew_id: str, inputs: dict) -> dict:
        """Start a crew on CrewAI Platform."""
        response = await self.client.post(
            f"{self.base_url}/v1/crews/{crew_id}/kickoff",
            headers={
                "Authorization": f"Bearer {self.bearer_token}",
                "Content-Type": "application/json",
            },
            json={"inputs": inputs},
        )
        response.raise_for_status()
        return response.json()

    async def _poll_status(self, kickoff_id: str) -> dict:
        """Poll crew execution status."""
        while True:
            response = await self.client.get(
                f"{self.base_url}/v1/kickoffs/{kickoff_id}/status",
                headers={"Authorization": f"Bearer {self.bearer_token}"},
            )
            data = response.json()
            if data["status"] in ("completed", "failed", "error"):
                return data
            await asyncio.sleep(2)

    async def run_discovery(self, raw_events: list, context: dict) -> dict:
        """Run DiscoveryCrew."""
        kickoff = await self._kickoff(
            "discovery_crew",
            {
                "raw_events": json.dumps(raw_events, ensure_ascii=False),
                "context": json.dumps(context, ensure_ascii=False),
            },
        )
        return await self._poll_status(kickoff["kickoff_id"])

    async def run_booking(
        self, event: dict, user_profile: dict, context: dict
    ) -> dict:
        """Run BookingCrew."""
        kickoff = await self._kickoff(
            "booking_crew",
            {
                "event": json.dumps(event, ensure_ascii=False),
                "user_profile": json.dumps(user_profile, ensure_ascii=False),
                "context": json.dumps(context, ensure_ascii=False),
            },
        )
        return await self._poll_status(kickoff["kickoff_id"])

    async def run_debrief(self, debrief_data: dict, context: dict) -> dict:
        """Run DebriefCrew."""
        kickoff = await self._kickoff(
            "debrief_crew",
            {
                "debrief_data": json.dumps(debrief_data, ensure_ascii=False),
                "context": json.dumps(context, ensure_ascii=False),
            },
        )
        return await self._poll_status(kickoff["kickoff_id"])

    async def run_onboarding(self, existing_data: dict) -> dict:
        """Run OnboardingCrew."""
        kickoff = await self._kickoff(
            "onboarding_crew",
            {
                "existing_data": json.dumps(existing_data, ensure_ascii=False),
            },
        )
        return await self._poll_status(kickoff["kickoff_id"])

    async def run_weekly_report(self, context: dict, period: str) -> dict:
        """Run WeeklyReportCrew."""
        kickoff = await self._kickoff(
            "weekly_report_crew",
            {
                "context": json.dumps(context, ensure_ascii=False),
                "period": period,
            },
        )
        return await self._poll_status(kickoff["kickoff_id"])

    async def close(self):
        await self.client.aclose()
