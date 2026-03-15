"""Handler for /events command - triggers DiscoveryCrew."""

import json
from datetime import date, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.formatters import format_event_card
from bot.keyboards import get_event_keyboard

router = Router()


@router.message(Command("events"))
async def handle_events(
    message: Message,
    crewai_client,
    context_builder,
    event_parser,
    scorer,
    db,
    crew_tracker,
):
    user_id = message.from_user.id
    await message.answer("Searching for events...")

    # 1. Build context (Python, no LLM)
    context = await context_builder.build(user_id)
    if not context.get("user_profile", {}).get("current_city"):
        await message.answer(
            "Please set your location first with /location"
        )
        return

    # 2. Parse events (Python, no LLM)
    raw_events = await event_parser.parse_all(
        city=context["current_location"]["city"],
        lat=context["current_location"]["lat"],
        lon=context["current_location"]["lon"],
        date_from=date.today(),
        date_to=date.today() + timedelta(days=14),
        categories=context["user_profile"].get("interests", []),
    )

    if not raw_events:
        await message.answer(
            "No events found in your city for the next 2 weeks."
        )
        return

    # 3. Calculate deterministic score for each (Python, no LLM)
    for event in raw_events:
        event["deterministic_score"] = scorer.calculate(
            event=event,
            profile=context["user_profile"],
            transport_cost=0,
            transport_duration_min=0,
            calendar_free=True,
        )

    # 4. Run DiscoveryCrew on CrewAI Platform (LLM: Scout + Analyst)
    result = await crew_tracker.run_and_track(
        crew_name="discovery",
        coro=crewai_client.run_discovery(raw_events, context),
        user_id=user_id,
    )

    # 5. Parse result and save to DB
    output = json.loads(result["output"])
    top_events = output.get("top_events", [])

    for event_data in top_events:
        await db.upsert_event(user_id, event_data)

    # 6. Show to user
    if not top_events:
        await message.answer("No suitable events found after analysis.")
        return

    total_filtered = output.get("total_filtered", len(raw_events))
    await message.answer(
        f"Found {total_filtered} events. Here's the top {len(top_events)}:"
    )

    for event in top_events:
        card = format_event_card(event)
        keyboard = get_event_keyboard(event["source_id"])
        await message.answer(card, reply_markup=keyboard, parse_mode="HTML")
