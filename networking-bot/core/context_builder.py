"""Builds context packet from PostgreSQL/Redis. No LLM."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from db.postgres import Database
    from db.redis import RedisCache


class ContextBuilder:
    """Assembles context packet from DB. No LLM."""

    def __init__(self, db: Database, redis: RedisCache):
        self.db = db
        self.redis = redis

    async def build(self, user_id: int) -> dict:
        profile = await self.db.get_user_profile(user_id)
        recent_events = await self.db.get_recent_events(user_id, limit=5)
        active_challenges = await self.db.get_active_challenges(user_id)
        preferences = await self.db.get_learned_preferences(user_id)
        budget_status = await self.db.get_budget_status(user_id)
        conversation_summary = await self.db.get_conversation_summary(user_id)
        challenge_count = await self.db.get_completed_challenge_count(user_id)

        # Determine level by completed challenge count
        if challenge_count < 5:
            user_level = "beginner"
        elif challenge_count < 20:
            user_level = "intermediate"
        else:
            user_level = "advanced"

        return {
            "user_profile": profile.to_dict() if profile else {},
            "current_location": {
                "city": profile.current_city if profile else "",
                "lat": profile.current_lat if profile else 0,
                "lon": profile.current_lon if profile else 0,
            },
            "planned_moves": (
                profile.planned_locations if profile and profile.planned_locations else []
            ),
            "recent_events": [e.to_dict() for e in recent_events],
            "active_challenges": [c.to_dict() for c in active_challenges],
            "used_methodology_ids": await self.db.get_used_methodology_ids(user_id),
            "learned_preferences": preferences,
            "conversation_summary": conversation_summary,
            "budget_status": budget_status,
            "user_level": user_level,
            "challenge_count": challenge_count,
        }
