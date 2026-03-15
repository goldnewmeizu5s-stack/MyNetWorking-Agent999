"""Learns user preferences from event interactions. No LLM."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from db.postgres import Database


class PreferenceLearner:
    """Rule-based preference learning from user behavior."""

    def __init__(self, db: Database):
        self.db = db

    async def learn_from_booking(self, user_id: int, event: dict) -> None:
        """Update preferences when user books an event."""
        # Learn event type preference
        if event.get("event_type"):
            await self._update_preference(
                user_id, "type", event["event_type"], delta=0.1
            )

        # Learn time preference
        if event.get("datetime_start"):
            hour = self._extract_hour(event["datetime_start"])
            time_slot = self._hour_to_slot(hour)
            await self._update_preference(
                user_id, "time", time_slot, delta=0.1
            )

        # Learn price preference
        price = event.get("ticket_price") or 0
        if price == 0:
            await self._update_preference(
                user_id, "price", "free", delta=0.05
            )
        elif price <= 10:
            await self._update_preference(
                user_id, "price", "cheap", delta=0.05
            )

        # Learn topic preferences from categories
        for cat in event.get("categories", []):
            await self._update_preference(
                user_id, "topic", cat.lower(), delta=0.1
            )

        # Learn language preference
        lang = event.get("language") or event.get("detected_language")
        if lang:
            await self._update_preference(
                user_id, "language", lang.lower(), delta=0.05
            )

    async def learn_from_skip(self, user_id: int, event: dict) -> None:
        """Update preferences when user skips an event."""
        if event.get("event_type"):
            await self._update_preference(
                user_id, "type", event["event_type"], delta=-0.05
            )

    async def learn_from_debrief(
        self, user_id: int, event: dict, rating: int
    ) -> None:
        """Update preferences from debrief rating."""
        if rating >= 7:
            delta = 0.15
        elif rating >= 5:
            delta = 0.05
        else:
            delta = -0.1

        if event.get("event_type"):
            await self._update_preference(
                user_id, "type", event["event_type"], delta=delta
            )

    async def _update_preference(
        self,
        user_id: int,
        pref_type: str,
        pref_value: str,
        delta: float,
    ) -> None:
        """Upsert a preference with confidence adjustment."""
        existing = await self.db.get_preference(user_id, pref_type, pref_value)
        if existing:
            new_confidence = max(0.0, min(1.0, existing["confidence"] + delta))
            new_count = existing["evidence_count"] + 1
            await self.db.update_preference(
                existing["preference_id"],
                confidence=new_confidence,
                evidence_count=new_count,
            )
        else:
            await self.db.create_preference(
                user_id=user_id,
                preference_type=pref_type,
                preference_value=pref_value,
                confidence=max(0.0, min(1.0, 0.3 + delta)),
            )

    def _extract_hour(self, datetime_str: str) -> int:
        """Extract hour from ISO datetime string."""
        try:
            if "T" in str(datetime_str):
                time_part = str(datetime_str).split("T")[1]
                return int(time_part.split(":")[0])
        except (IndexError, ValueError):
            pass
        return 12  # default to noon

    def _hour_to_slot(self, hour: int) -> str:
        if hour < 12:
            return "morning"
        elif hour < 17:
            return "afternoon"
        else:
            return "evening"
