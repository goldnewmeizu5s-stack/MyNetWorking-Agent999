"""Handler for main menu button presses."""

from aiogram import F, Router
from aiogram.types import Message

router = Router()


@router.message(F.text == "🔍 Events")
async def menu_events(message: Message, **kwargs):
    from bot.handlers.events import handle_events
    await handle_events(message, **kwargs)


@router.message(F.text == "⚙️ Settings")
async def menu_settings(message: Message, **kwargs):
    from bot.handlers.settings import handle_settings
    await handle_settings(message, **kwargs)
