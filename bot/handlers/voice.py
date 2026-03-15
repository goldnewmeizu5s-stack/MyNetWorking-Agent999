"""Voice message handler - Whisper STT + intent routing."""

import io
import os

import httpx
from aiogram import Router
from aiogram.types import Message

from bot.keyboards import get_main_keyboard

router = Router()


@router.message(lambda m: m.voice is not None)
async def handle_voice(message: Message, bot, **kwargs):
    """Process voice messages via Whisper STT and route to intent."""
    voice = message.voice

    # Download voice file
    file = await bot.get_file(voice.file_id)
    file_data = await bot.download_file(file.file_path)

    # Transcribe via OpenAI Whisper API
    text = await _transcribe(file_data)

    if not text:
        await message.answer(
            "Sorry, couldn't understand the voice message.",
            reply_markup=get_main_keyboard(),
        )
        return

    await message.answer(f"Heard: \"{text}\"")

    # Route by intent
    text_lower = text.lower()

    if any(kw in text_lower for kw in [
        "event", "events", "meetup", "conference", "найди", "ивент", "поиск", "search",
    ]):
        from bot.handlers.events import handle_events
        await handle_events(message, **kwargs)

    elif any(kw in text_lower for kw in [
        "settings", "настройки", "профиль", "profile",
    ]):
        from bot.handlers.settings import handle_settings
        await handle_settings(message, **kwargs)

    elif any(kw in text_lower for kw in [
        "stats", "статистика", "report", "summary", "отчёт", "отчет",
    ]):
        from bot.handlers.stats import handle_stats
        await handle_stats(message, **kwargs)

    elif any(kw in text_lower for kw in [
        "challenge", "задание", "task", "челлендж",
    ]):
        from bot.handlers.challenge import handle_challenge
        await handle_challenge(message, **kwargs)

    elif any(kw in text_lower for kw in [
        "contact", "contacts", "контакты",
    ]):
        from bot.handlers.contacts import handle_contacts
        await handle_contacts(message, **kwargs)

    elif any(kw in text_lower for kw in [
        "location", "city", "город", "локация", "move",
    ]):
        from bot.handlers.settings import handle_location
        await handle_location(message, **kwargs)

    elif any(kw in text_lower for kw in [
        "debrief", "how was", "review", "как прошло",
    ]):
        from bot.handlers.debrief import handle_debrief_start
        await handle_debrief_start(message, **kwargs)

    else:
        await message.answer(
            "I didn't recognize a command. Use the buttons below:",
            reply_markup=get_main_keyboard(),
        )


async def _transcribe(file_data: io.BytesIO) -> str | None:
    """Transcribe audio using OpenAI Whisper API."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
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
    except Exception:
        pass
    return None
