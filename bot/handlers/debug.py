"""Debug commands for admin."""
import json
import logging
import os
import time
from datetime import date, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

logger = logging.getLogger(__name__)
ADMIN_ID = 1010004170
router = Router()


@router.message(Command("debug"))
async def handle_debug(message: Message, db, **kwargs):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Admin only.")
        return

    try:
        from sqlalchemy import text

        async with db.session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT crew_name, status, duration_sec, output, created_at "
                    "FROM crew_runs ORDER BY created_at DESC LIMIT 1"
                )
            )
            row = result.first()
            if row:
                output_preview = (row[3] or "")[:2000]
                text_msg = (
                    f"<b>Last Crew Run</b>\n"
                    f"Crew: {row[0]}\n"
                    f"Status: {row[1]}\n"
                    f"Duration: {row[2]:.1f}s\n"
                    f"Time: {row[4]}\n\n"
                    f"<b>Output:</b>\n<pre>{_escape(output_preview)}</pre>"
                )
            else:
                text_msg = "No crew runs found."

        await message.answer(text_msg, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"Debug error: {e}")


@router.message(Command("clearcache"))
async def handle_clearcache(message: Message, redis=None, **kwargs):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Admin only.")
        return

    if not redis:
        await message.answer("Redis not connected.")
        return

    try:
        count = await redis.delete_by_pattern("events:cache:*")
        await message.answer(f"Cleared {count} event cache key(s).")
    except Exception as e:
        await message.answer(f"Error clearing cache: {e}")


@router.message(Command("testparsers"))
async def handle_testparsers(message: Message, db, event_parser=None, **kwargs):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Admin only.")
        return

    if not event_parser:
        await message.answer("event_parser not available.")
        return

    try:
        profile = await db.get_user_profile(message.from_user.id)
        if not profile:
            await message.answer("No profile found. Use /start first.")
            return

        city = profile.current_city
        lat = profile.current_lat
        lon = profile.current_lon

        await message.answer(
            f"Testing parsers...\n"
            f"City: {city}\nLat: {lat}\nLon: {lon}"
        )

        date_from = date.today()
        date_to = date_from + timedelta(days=14)

        # Call _parse_luma directly (bypass cache)
        t0 = time.monotonic()
        luma_events = await event_parser._parse_luma(city, lat, lon, date_from, date_to)
        luma_sec = time.monotonic() - t0

        # Call _parse_meetup directly (bypass cache)
        t0 = time.monotonic()
        meetup_events = await event_parser._parse_meetup(
            lat, lon, 15, date_from, date_to, ["networking", "tech"],
        )
        meetup_sec = time.monotonic() - t0

        # Build response
        luma_titles = [e.get("title", "?")[:50] for e in luma_events[:3]]
        meetup_titles = [e.get("title", "?")[:50] for e in meetup_events[:3]]

        text = (
            f"<b>Parser Test Results</b>\n\n"
            f"<b>Input:</b> {city} ({lat}, {lon})\n"
            f"Date range: {date_from} → {date_to}\n\n"
            f"<b>Luma:</b> {len(luma_events)} events ({luma_sec:.1f}s)\n"
            f"<b>Meetup:</b> {len(meetup_events)} events ({meetup_sec:.1f}s)\n"
            f"<b>Total:</b> {len(luma_events) + len(meetup_events)}\n\n"
        )

        if luma_titles:
            text += "<b>Luma sample:</b>\n" + "\n".join(
                f"  • {_escape(t)}" for t in luma_titles
            ) + "\n\n"

        if meetup_titles:
            text += "<b>Meetup sample:</b>\n" + "\n".join(
                f"  • {_escape(t)}" for t in meetup_titles
            ) + "\n"

        if not luma_events and not meetup_events:
            text += "⚠️ Both parsers returned 0 events. Check Railway logs."

        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.error("testparsers error: %s", e, exc_info=True)
        await message.answer(f"Error: {_escape(str(e))}", parse_mode="HTML")


@router.message(Command("env"))
async def handle_env(message: Message, **kwargs):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Admin only.")
        return

    url = os.environ.get("CREWAI_PLATFORM_URL", "NOT SET")
    has_token = "SET" if os.environ.get("CREWAI_BEARER_TOKEN") else "NOT SET"
    has_openai = "SET" if os.environ.get("OPENAI_API_KEY") else "NOT SET"
    has_db = "SET" if os.environ.get("DATABASE_URL") else "NOT SET"
    has_redis = "SET" if os.environ.get("REDIS_URL") else "NOT SET"

    text = (
        "<b>Environment</b>\n\n"
        f"CREWAI_URL: {url}\n"
        f"CREWAI_TOKEN: {has_token}\n"
        f"OPENAI_KEY: {has_openai}\n"
        f"DATABASE: {has_db}\n"
        f"REDIS: {has_redis}\n"
    )
    await message.answer(text, parse_mode="HTML")


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
