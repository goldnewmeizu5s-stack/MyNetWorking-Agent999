"""Handler for /start command - triggers OnboardingCrew."""

import json

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router()


@router.message(CommandStart())
async def handle_start(message: Message, crewai_client, db):
    user_id = message.from_user.id

    # Check if user already onboarded
    profile = await db.get_user_profile(user_id)
    if profile and profile.onboarding_complete:
        await message.answer(
            "Welcome back! Use /events to find networking events, "
            "or /settings to update your profile."
        )
        return

    await message.answer(
        "Hi! I'm your personal networking assistant.\n\n"
        "I find relevant events, help you register, "
        "generate networking challenges, and track your ROI.\n\n"
        "Let's set up your profile first. This will take about a minute."
    )

    # Kick off OnboardingCrew
    try:
        existing_data = {}
        if profile:
            existing_data = profile.to_dict()

        result = await crewai_client.run_onboarding(existing_data)
        output = json.loads(result["output"])

        # Save profile to DB
        await db.upsert_user_profile(
            user_id=user_id,
            name=output.get("name", message.from_user.full_name),
            current_city=output.get("current_city", ""),
            current_lat=output.get("current_lat", 0),
            current_lon=output.get("current_lon", 0),
            interests=output.get("interests", []),
            budget_limit_ticket=output.get("budget_limit_ticket", 50),
            budget_limit_transport=output.get("budget_limit_transport", 20),
            email=output.get("email"),
            linkedin_url=output.get("linkedin_url"),
            company=output.get("company"),
            role=output.get("role"),
            preferred_languages=output.get("preferred_languages", ["en"]),
            preferred_time=output.get("preferred_time", "any"),
            planned_locations=output.get("planned_locations"),
            onboarding_complete=True,
        )

        await message.answer(
            "Profile saved! Here's what I know:\n\n"
            f"Name: {output.get('name', 'N/A')}\n"
            f"City: {output.get('current_city', 'N/A')}\n"
            f"Interests: {', '.join(output.get('interests', []))}\n"
            f"Budget (ticket): EUR{output.get('budget_limit_ticket', 50)}\n"
            f"Budget (transport): EUR{output.get('budget_limit_transport', 20)}\n\n"
            "Use /events to find events near you!"
        )
    except Exception as e:
        await message.answer(
            "Something went wrong during onboarding. "
            "Please try again with /start or set up manually with /settings."
        )
