"""Handler for /start command - simple onboarding for MVP."""

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router()


@router.message(CommandStart())
async def handle_start(message: Message, db):
    user_id = message.from_user.id
    profile = await db.get_user_profile(user_id)

    if profile and profile.onboarding_complete:
        await message.answer(
            "Welcome back! Use /events to find networking events, "
            "or /settings to update your profile."
        )
        return

    # MVP: auto-create profile with defaults
    await db.upsert_user_profile(
        user_id=user_id,
        name=message.from_user.full_name,
        current_city="Tbilisi",
        current_lat=41.7151,
        current_lon=44.8271,
        interests=["AI", "crypto", "DeFi", "startups", "B2B SaaS"],
        budget_limit_ticket=100,
        budget_limit_transport=30,
        preferred_languages=["en", "ru"],
        preferred_time="any",
        onboarding_complete=True,
    )

    await message.answer(
        "Hi! I'm your personal networking assistant.\n\n"
        "I find relevant events, score them, and help you decide what to attend.\n\n"
        f"Profile created for {message.from_user.full_name} (Tbilisi).\n"
        "Use /events to find networking events!\n"
        "Use /settings to update your profile."
    )
