"""PostgreSQL database layer using SQLAlchemy + asyncpg."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from models.challenge import Challenge
from models.crew_run import CrewRun
from models.event import Event, EventResult
from models.user import Base, UserProfile


class Database:
    """Async PostgreSQL database operations."""

    def __init__(self, database_url: str):
        # Convert postgres:// to postgresql+asyncpg://
        if database_url.startswith("postgres://"):
            database_url = database_url.replace(
                "postgres://", "postgresql+asyncpg://", 1
            )
        elif database_url.startswith("postgresql://"):
            database_url = database_url.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )

        self.engine = create_async_engine(database_url, echo=False)
        self.session_factory = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init_db(self):
        """Create all tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self):
        await self.engine.dispose()

    # -- User operations --

    async def get_user_profile(self, user_id: int) -> UserProfile | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(UserProfile).where(UserProfile.user_id == user_id)
            )
            return result.scalar_one_or_none()

    async def upsert_user_profile(self, user_id: int, **kwargs) -> None:
        async with self.session_factory() as session:
            existing = await session.get(UserProfile, user_id)
            if existing:
                for key, value in kwargs.items():
                    if hasattr(existing, key) and value is not None:
                        setattr(existing, key, value)
            else:
                profile = UserProfile(user_id=user_id, **kwargs)
                session.add(profile)
            await session.commit()

    async def update_user_city(
        self, user_id: int, city: str, lat: float, lon: float
    ) -> None:
        async with self.session_factory() as session:
            await session.execute(
                update(UserProfile)
                .where(UserProfile.user_id == user_id)
                .values(
                    current_city=city,
                    current_lat=lat,
                    current_lon=lon,
                )
            )
            await session.commit()

    async def update_user_interests(
        self, user_id: int, interests: list[str]
    ) -> None:
        async with self.session_factory() as session:
            await session.execute(
                update(UserProfile)
                .where(UserProfile.user_id == user_id)
                .values(interests=interests)
            )
            await session.commit()

    async def update_user_budget(
        self, user_id: int, budget_ticket: float, budget_transport: float
    ) -> None:
        async with self.session_factory() as session:
            await session.execute(
                update(UserProfile)
                .where(UserProfile.user_id == user_id)
                .values(
                    budget_limit_ticket=budget_ticket,
                    budget_limit_transport=budget_transport,
                )
            )
            await session.commit()

    # -- Event operations --

    async def get_event(self, event_id: str) -> Event | None:
        async with self.session_factory() as session:
            # Try by source_id first, then by event_id
            result = await session.execute(
                select(Event).where(Event.source_id == event_id)
            )
            event = result.scalar_one_or_none()
            if not event:
                try:
                    uid = uuid.UUID(event_id)
                    result = await session.execute(
                        select(Event).where(Event.event_id == uid)
                    )
                    event = result.scalar_one_or_none()
                except ValueError:
                    pass
            return event

    async def upsert_event(self, user_id: int, event_data: dict) -> None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Event).where(
                    Event.user_id == user_id,
                    Event.source_id == event_data.get("source_id", ""),
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                for key, value in event_data.items():
                    if hasattr(existing, key) and value is not None:
                        setattr(existing, key, value)
            else:
                # Parse datetime if string
                dt_start = event_data.get("datetime_start")
                if isinstance(dt_start, str):
                    try:
                        dt_start = datetime.fromisoformat(dt_start)
                    except ValueError:
                        dt_start = datetime.now()

                event = Event(
                    user_id=user_id,
                    source=event_data.get("source", "other"),
                    source_id=event_data.get("source_id", ""),
                    source_url=event_data.get("source_url", ""),
                    title=event_data.get("title", ""),
                    description=event_data.get("description"),
                    datetime_start=dt_start,
                    location_name=event_data.get("location_name"),
                    location_city=event_data.get("location_city"),
                    ticket_price=event_data.get("ticket_price"),
                    total_score=event_data.get("total_score", 0),
                    deterministic_score=event_data.get("deterministic_score", 0),
                    semantic_score=event_data.get("semantic_score", 0),
                    recommendation=event_data.get("recommendation"),
                    recommendation_reason=event_data.get("recommendation_reason"),
                    event_type=event_data.get("event_type"),
                    language=event_data.get("language"),
                    transport_cost=event_data.get("transport_cost"),
                    transport_duration_min=event_data.get("transport_duration_min"),
                    total_estimated_cost=event_data.get("total_estimated_cost"),
                )
                session.add(event)
            await session.commit()

    async def update_event_status(
        self, event_id: str, status: str
    ) -> None:
        async with self.session_factory() as session:
            await session.execute(
                update(Event)
                .where(Event.source_id == event_id)
                .values(status=status)
            )
            await session.commit()

    async def get_recent_events(
        self, user_id: int, limit: int = 5
    ) -> list[Event]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Event)
                .where(Event.user_id == user_id)
                .order_by(Event.datetime_start.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def get_most_recent_confirmed_event(
        self, user_id: int
    ) -> Event | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Event)
                .where(
                    Event.user_id == user_id,
                    Event.status == "confirmed",
                )
                .order_by(Event.datetime_start.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    # -- Challenge operations --

    async def get_active_challenges(
        self, user_id: int
    ) -> list[Challenge]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Challenge)
                .where(
                    Challenge.user_id == user_id,
                    Challenge.status == "assigned",
                )
                .order_by(Challenge.created_at.desc())
            )
            return list(result.scalars().all())

    async def get_completed_challenge_count(
        self, user_id: int
    ) -> int:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Challenge)
                .where(
                    Challenge.user_id == user_id,
                    Challenge.status == "completed",
                )
            )
            return len(list(result.scalars().all()))

    async def get_used_methodology_ids(
        self, user_id: int
    ) -> list[int]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Challenge.methodology_id)
                .where(Challenge.user_id == user_id)
                .distinct()
            )
            return [r for r in result.scalars().all() if r is not None]

    # -- Event Result operations --

    async def create_event_result(
        self,
        event_id: str,
        user_id: int,
        contacts_made: list[dict],
        user_rating: int,
        actual_cost: float,
        roi_score: float,
    ) -> None:
        async with self.session_factory() as session:
            # Get the Event UUID
            event = await self.get_event(event_id)
            event_uuid = event.event_id if event else None

            result = EventResult(
                event_id=event_uuid,
                user_id=user_id,
                contacts_made=contacts_made,
                user_rating=user_rating,
                actual_cost=actual_cost,
                roi_score=roi_score,
            )
            session.add(result)
            await session.commit()

    async def get_all_contacts(self, user_id: int) -> list[dict]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(EventResult, Event)
                .join(Event, EventResult.event_id == Event.event_id)
                .where(EventResult.user_id == user_id)
                .order_by(EventResult.created_at.desc())
            )
            contacts = []
            for event_result, event in result.all():
                for contact in event_result.contacts_made or []:
                    contact["event_title"] = event.title
                    contacts.append(contact)
            return contacts

    # -- Preferences --

    async def get_learned_preferences(self, user_id: int) -> list[dict]:
        async with self.session_factory() as session:
            from sqlalchemy import text

            result = await session.execute(
                text(
                    "SELECT preference_type, preference_value, confidence "
                    "FROM learned_preferences "
                    "WHERE user_id = :uid ORDER BY confidence DESC"
                ),
                {"uid": user_id},
            )
            return [
                {
                    "type": row[0],
                    "value": row[1],
                    "confidence": row[2],
                }
                for row in result.all()
            ]

    async def get_preference(
        self, user_id: int, pref_type: str, pref_value: str
    ) -> dict | None:
        async with self.session_factory() as session:
            from sqlalchemy import text

            result = await session.execute(
                text(
                    "SELECT preference_id, confidence, evidence_count "
                    "FROM learned_preferences "
                    "WHERE user_id = :uid AND preference_type = :pt "
                    "AND preference_value = :pv"
                ),
                {"uid": user_id, "pt": pref_type, "pv": pref_value},
            )
            row = result.first()
            if row:
                return {
                    "preference_id": row[0],
                    "confidence": row[1],
                    "evidence_count": row[2],
                }
            return None

    async def update_preference(
        self,
        preference_id: int,
        confidence: float,
        evidence_count: int,
    ) -> None:
        async with self.session_factory() as session:
            from sqlalchemy import text

            await session.execute(
                text(
                    "UPDATE learned_preferences "
                    "SET confidence = :c, evidence_count = :ec, "
                    "updated_at = NOW() "
                    "WHERE preference_id = :pid"
                ),
                {"c": confidence, "ec": evidence_count, "pid": preference_id},
            )
            await session.commit()

    async def create_preference(
        self,
        user_id: int,
        preference_type: str,
        preference_value: str,
        confidence: float,
    ) -> None:
        async with self.session_factory() as session:
            from sqlalchemy import text

            await session.execute(
                text(
                    "INSERT INTO learned_preferences "
                    "(user_id, preference_type, preference_value, confidence) "
                    "VALUES (:uid, :pt, :pv, :c)"
                ),
                {
                    "uid": user_id,
                    "pt": preference_type,
                    "pv": preference_value,
                    "c": confidence,
                },
            )
            await session.commit()

    # -- Crew runs --

    async def log_crew_run(
        self,
        crew_name: str,
        user_id: int,
        duration_sec: float,
        status: str,
        output: str,
    ) -> None:
        async with self.session_factory() as session:
            run = CrewRun(
                crew_name=crew_name,
                user_id=user_id,
                duration_sec=duration_sec,
                status=status,
                output=output,
            )
            session.add(run)
            await session.commit()

    # -- Stats --

    async def get_budget_status(self, user_id: int) -> dict:
        async with self.session_factory() as session:
            from sqlalchemy import text

            result = await session.execute(
                text(
                    "SELECT COALESCE(SUM(total_estimated_cost), 0) "
                    "FROM events WHERE user_id = :uid AND status = 'confirmed' "
                    "AND datetime_start >= date_trunc('month', CURRENT_DATE)"
                ),
                {"uid": user_id},
            )
            spent = result.scalar() or 0
            profile = await self.get_user_profile(user_id)
            budget = (
                (profile.budget_limit_ticket or 50)
                + (profile.budget_limit_transport or 20)
            ) * 4  # Monthly estimate

            return {
                "spent_this_month": float(spent),
                "estimated_monthly_budget": budget,
                "remaining": budget - float(spent),
            }

    async def get_conversation_summary(self, user_id: int) -> str:
        return ""  # Placeholder for conversation memory

    async def get_basic_stats(self, user_id: int) -> dict:
        async with self.session_factory() as session:
            from sqlalchemy import func as sqlfunc, text

            # Total confirmed events
            events_result = await session.execute(
                select(sqlfunc.count(Event.event_id)).where(
                    Event.user_id == user_id,
                    Event.status == "confirmed",
                )
            )
            total_events = events_result.scalar() or 0

            # Total contacts
            contacts_result = await session.execute(
                text(
                    "SELECT COALESCE(SUM(jsonb_array_length(contacts_made)), 0) "
                    "FROM event_results WHERE user_id = :uid"
                ),
                {"uid": user_id},
            )
            total_contacts = contacts_result.scalar() or 0

            # Challenges completed
            challenges_result = await session.execute(
                select(sqlfunc.count(Challenge.challenge_id)).where(
                    Challenge.user_id == user_id,
                    Challenge.status == "completed",
                )
            )
            challenges_completed = challenges_result.scalar() or 0

            return {
                "total_events": total_events,
                "total_contacts": total_contacts,
                "challenges_completed": challenges_completed,
            }

    async def get_all_active_users(self) -> list[UserProfile]:
        """Get all users with completed onboarding."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(UserProfile).where(
                    UserProfile.onboarding_complete.is_(True)
                )
            )
            return list(result.scalars().all())
