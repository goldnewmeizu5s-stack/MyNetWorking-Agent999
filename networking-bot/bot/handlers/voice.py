"""Voice message handler - Whisper STT + intent routing."""

import io
import os

import httpx
from aiogram import Router
from aiogram.types import Message

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
        await message.answer("Sorry, couldn't understand the voice message.")
        return

    # Route by intent
    text_lower = text.lower()

    if any(kw in text_lower for kw in ["event", "meetup", "conference"]):
        await message.answer(f"Heard: '{text}'\nUse /events to search for events.")
    elif any(kw in text_lower for kw in ["debrief", "how was", "review"]):
        await message.answer(f"Heard: '{text}'\nUse /debrief to review your last event.")
    elif any(kw in text_lower for kw in ["location", "city", "move"]):
        await message.answer(f"Heard: '{text}'\nUse /location to update your city.")
    elif any(kw in text_lower for kw in ["stats", "report", "summary"]):
        await message.answer(f"Heard: '{text}'\nUse /stats to see your weekly report.")
    elif any(kw in text_lower for kw in ["challenge", "task"]):
        await message.answer(f"Heard: '{text}'\nUse /challenge to see your current challenge.")
    else:
        await message.answer(
            f"Heard: '{text}'\n\n"
            "Available commands:\n"
            "/events - find events\n"
            "/debrief - review last event\n"
            "/stats - weekly stats\n"
            "/challenge - current challenge\n"
            "/settings - your profile"
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
