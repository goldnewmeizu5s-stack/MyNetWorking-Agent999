"""Debug commands for admin."""
import json
import logging
import os

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
