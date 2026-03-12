"""Monitoring all crew runs."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from db.postgres import Database


class CrewTracker:
    """Monitoring all crew runs."""

    def __init__(self, db: Database):
        self.db = db

    async def run_and_track(
        self, crew_name: str, coro: Any, user_id: int
    ) -> dict:
        start = time.time()
        try:
            result = await coro
            duration = time.time() - start
            await self._log(
                crew_name,
                user_id,
                duration,
                "success",
                json.dumps(result, default=str)[:5000],
            )
            return result
        except Exception as e:
            duration = time.time() - start
            await self._log(
                crew_name, user_id, duration, "error", str(e)[:5000]
            )
            raise

    async def _log(
        self,
        crew_name: str,
        user_id: int,
        duration: float,
        status: str,
        output: str,
    ) -> None:
        await self.db.log_crew_run(
            crew_name=crew_name,
            user_id=user_id,
            duration_sec=duration,
            status=status,
            output=output,
        )
