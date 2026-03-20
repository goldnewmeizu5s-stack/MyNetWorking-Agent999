"""Voice message handler - Whisper STT + intent routing."""

import io
import logging
import os

import httpx
from aiogram import Router
from aiogram.types import Message

from bot.keyboards import get_main_keyboard

router = Router()
logger = logging.getLogger(__name__)

INTENT_EVENTS = ["event", "events", "meetup", "conference",
                 "найди", "ивент", "поиск", "search", "show"]
INTENT_LOCATION = ["location", "city", "город", "локация", "move", "переезд"]
INTENT_SETTINGS = ["settings", "настройки", "профиль", "profile", "budget"]
INTENT_STATS = ["stats", "статистика", "report", "summary", "отчёт", "roi"]
INTENT_CHALLENGE = ["challenge", "задание", "task", "челлендж"]
INTENT_CONTACTS = ["contact", "contacts", "контакты", "познакомился"]
INTENT_DEBRIEF = ["debrief", "how was", "review", "как прошло", "итог"]


@router.message(lambda m: m.voice is not None)
async def handle_voice(message: Message, bot, **kwargs):
    """Process voice messages via Whisper STT and route to intent."""
    await message.answer("🎤 Processing voice...")

    file = await bot.get_file(message.voice.file_id)
    file_data = await bot.download_file(file.file_path)

    text = await _transcribe(file_data)

    if not text:
        await message.answer(
            "Sorry, couldn't understand. Please try again or use buttons below.",
            reply_markup=get_main_keyboard(),
        )
        return

    await message.answer(f'🎤 Heard: "{text}"')

    text_lower = text.lower()

    if any(kw in text_lower for kw in INTENT_EVENTS):
        from bot.handlers.events import handle_events
        await handle_events(message, **kwargs)

    elif any(kw in text_lower for kw in INTENT_DEBRIEF):
        from bot.handlers.debrief import handle_debrief_start
        await handle_debrief_start(message, **kwargs)

    elif any(kw in text_lower for kw in INTENT_LOCATION):
        from bot.handlers.settings import handle_location
        await handle_location(message, **kwargs)

    elif any(kw in text_lower for kw in INTENT_STATS):
        from bot.handlers.stats import handle_stats
        await handle_stats(message, **kwargs)

    elif any(kw in text_lower for kw in INTENT_CHALLENGE):
        from bot.handlers.challenge import handle_challenge
        await handle_challenge(message, **kwargs)

    elif any(kw in text_lower for kw in INTENT_CONTACTS):
        from bot.handlers.contacts import handle_contacts
        await handle_contacts(message, **kwargs)

    elif any(kw in text_lower for kw in INTENT_SETTINGS):
        from bot.handlers.settings import handle_settings
        await handle_settings(message, **kwargs)

    else:
        await message.answer(
            "I heard you but wasn't sure what to do. Use buttons below:",
            reply_markup=get_main_keyboard(),
        )


async def _transcribe(file_data: io.BytesIO) -> str | None:
    """Transcribe audio using OpenAI Whisper API."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not set - voice disabled")
        return None

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": ("voice.ogg", file_data, "audio/ogg")},
                data={"model": "whisper-1"},
            )
            if resp.status_code == 200:
                return resp.json().get("text")
            logger.error("Whisper API error: %s %s", resp.status_code, resp.text)
    except Exception as e:
        logger.error("Whisper transcription failed: %s", e)
    return None
