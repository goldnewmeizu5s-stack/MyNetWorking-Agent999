"""Handler for main menu button presses."""

from aiogram import F, Router
from aiogram.types import Message

router = Router()


@router.message(F.text == "🔍 Events")
async def menu_events(message: Message, **kwargs):
    from bot.handlers.events import handle_events
    await handle_events(message, **kwargs)


@router.message(F.text == "📍 Location")
async def menu_location(message: Message, **kwargs):
    from bot.handlers.settings import handle_location
    await handle_location(message, **kwargs)


@router.message(F.text == "⚙️ Settings")
async def menu_settings(message: Message, **kwargs):
    from bot.handlers.settings import handle_settings
    await handle_settings(message, **kwargs)


@router.message(F.text == "📊 Stats")
async def menu_stats(message: Message, **kwargs):
    from bot.handlers.stats import handle_stats
    await handle_stats(message, **kwargs)


@router.message(F.text == "🎯 Challenge")
async def menu_challenge(message: Message, **kwargs):
    from bot.handlers.challenge import handle_challenge
    await handle_challenge(message, **kwargs)


@router.message(F.text == "📇 Contacts")
async def menu_contacts(message: Message, **kwargs):
    from bot.handlers.contacts import handle_contacts
    await handle_contacts(message, **kwargs)
