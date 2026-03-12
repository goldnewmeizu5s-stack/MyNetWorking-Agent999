"""APScheduler cron jobs for automated tasks."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

if TYPE_CHECKING:
    from core.context_builder import ContextBuilder
    from core.crewai_client import CrewAIClient
    from core.event_parser import EventParser
    from core.deterministic_scorer import DeterministicScorer
    from db.postgres import Database
    from db.redis import RedisCache

logger = logging.getLogger(__name__)


class SchedulerManager:
    """Manages all cron jobs."""

    def __init__(
        self,
        db: Database,
        redis: RedisCache,
        crewai_client: CrewAIClient,
        context_builder: ContextBuilder,
        event_parser: EventParser,
        scorer: DeterministicScorer,
        bot=None,
    ):
        self.db = db
        self.redis = redis
        self.crewai_client = crewai_client
        self.context_builder = context_builder
        self.event_parser = event_parser
        self.scorer = scorer
        self.bot = bot
        self.scheduler = AsyncIOScheduler()

    def start(self):
        """Register and start all cron jobs."""
        # Discovery - every 12 hours
        self.scheduler.add_job(
            self.run_discovery_cron,
            CronTrigger(hour="8,20", minute=0),
            id="discovery_cron",
        )

        # Check waitlists - every 6 hours
        self.scheduler.add_job(
            self.check_waitlists,
            IntervalTrigger(hours=6),
            id="waitlist_check",
        )

        # Reminders - every hour
        self.scheduler.add_job(
            self.send_reminders,
            IntervalTrigger(hours=1),
            id="reminders",
        )

        # Debrief prompt - every hour
        self.scheduler.add_job(
            self.prompt_debrief,
            IntervalTrigger(hours=1),
            id="debrief_prompt",
        )

        # Weekly report - Sunday 20:00
        self.scheduler.add_job(
            self.send_weekly_report,
            CronTrigger(day_of_week="sun", hour=20),
            id="weekly_report",
        )

        self.scheduler.start()
        logger.info("Scheduler started with all cron jobs")

    def stop(self):
        self.scheduler.shutdown()

    async def run_discovery_cron(self):
        """Run event discovery for all active users."""
        logger.info("Running discovery cron job")
        users = await self.db.get_all_active_users()
        for user in users:
            try:
                context = await self.context_builder.build(user.user_id)
                raw_events = await self.event_parser.parse_all(
                    city=context["current_location"]["city"],
                    lat=context["current_location"]["lat"],
                    lon=context["current_location"]["lon"],
                    date_from=date.today(),
                    date_to=date.today() + timedelta(days=14),
                    categories=context["user_profile"].get("interests", []),
                )
                for event in raw_events:
                    event["deterministic_score"] = self.scorer.calculate(
                        event=event,
                        profile=context["user_profile"],
                        transport_cost=0,
                        transport_duration_min=0,
                        calendar_free=True,
                    )
                if raw_events:
                    result = await self.crewai_client.run_discovery(
                        raw_events, context
                    )
                    output = json.loads(result["output"])
                    for event_data in output.get("top_events", []):
                        await self.db.upsert_event(user.user_id, event_data)
            except Exception:
                logger.exception(
                    f"Discovery cron failed for user {user.user_id}"
                )

    async def check_waitlists(self):
        """Check waitlist status for pending events."""
        logger.info("Checking waitlists")
        # Implementation: re-check Luma/Meetup pages for waitlisted events

    async def send_reminders(self):
        """Send reminders for upcoming events (24h and 2h before)."""
        logger.info("Checking reminders")
        if not self.bot:
            return
        now = datetime.utcnow()
        # 24h reminder
        target_24h = now + timedelta(hours=24)
        # 2h reminder
        target_2h = now + timedelta(hours=2)
        # Implementation: query events near these times and send messages

    async def prompt_debrief(self):
        """Prompt users for debrief 2 hours after event ends."""
        logger.info("Checking debrief prompts")
        if not self.bot:
            return
        now = datetime.utcnow()
        target = now - timedelta(hours=2)
        # Implementation: find events that ended ~2h ago and prompt debrief

    async def send_weekly_report(self):
        """Send weekly report to all active users."""
        logger.info("Sending weekly reports")
        users = await self.db.get_all_active_users()
        for user in users:
            try:
                context = await self.context_builder.build(user.user_id)
                today = date.today()
                week_start = today - timedelta(days=today.weekday())
                period = f"{week_start.isoformat()} to {today.isoformat()}"

                result = await self.crewai_client.run_weekly_report(
                    context, period
                )
                output = json.loads(result["output"])

                if self.bot:
                    from bot.formatters import format_weekly_report

                    text = format_weekly_report(output)
                    await self.bot.send_message(user.user_id, text, parse_mode="HTML")
            except Exception:
                logger.exception(
                    f"Weekly report failed for user {user.user_id}"
                )
