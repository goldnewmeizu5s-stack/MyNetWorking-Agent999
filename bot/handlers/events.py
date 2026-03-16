"""Handler for /events command - triggers DiscoveryCrew."""
import json
import logging
from datetime import date, timedelta
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from bot.formatters import format_event_card
from bot.keyboards import get_event_keyboard, get_main_keyboard
logger = logging.getLogger(__name__)
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
    **kwargs,
):
    user_id = message.from_user.id
    await message.answer("🔍 Searching for events...")
    # 1. Build context (Python, no LLM)
    context = await context_builder.build(user_id)
    if not context.get("user_profile", {}).get("current_city"):
        await message.answer(
            "Please set your location first with /location",
            reply_markup=get_main_keyboard(),
        )
        return
    city = context["current_location"]["city"]
    # 2. Try to parse events from Luma/Meetup (Python, no LLM)
    raw_events = []
    try:
        raw_events = await event_parser.parse_all(
            city=city,
            lat=context["current_location"]["lat"],
            lon=context["current_location"]["lon"],
            date_from=date.today(),
            date_to=date.today() + timedelta(days=14),
            categories=context["user_profile"].get("interests", []),
        )
        logger.info("Parsed %d raw events from Luma/Meetup", len(raw_events))
    except Exception as e:
        logger.warning("Event parsing failed: %s", e)
    # 3. Calculate deterministic score for pre-parsed events
    for event in raw_events:
        event["deterministic_score"] = scorer.calculate(
            event=event,
            profile=context["user_profile"],
            transport_cost=0,
            transport_duration_min=0,
            calendar_free=True,
        )
    # 4. Run DiscoveryCrew on CrewAI Platform
    # Scout will SEARCH for events via Perplexity + use any pre-parsed events
    await message.answer(
        f"🤖 AI is searching for events in {city}... This may take 30-60 seconds."
    )
    try:
        result = await crew_tracker.run_and_track(
            crew_name="discovery",
            coro=crewai_client.run_discovery(raw_events, context),
            user_id=user_id,
        )
    except Exception as e:
        logger.error("CrewAI discovery failed: %s", e)
        await message.answer(
            "Sorry, event search failed. Please try again later.",
            reply_markup=get_main_keyboard(),
        )
        return
    # 5. Parse result
    try:
        result_data = result.get("result", {})
        output_str = result_data.get("output", result.get("output", "{}"))
        if isinstance(output_str, str):
            output = json.loads(output_str)
        else:
            output = output_str
        # Handle both possible response formats
        top_events = output.get("top_events", output.get("scored_events", []))
    except (json.JSONDecodeError, AttributeError, TypeError) as e:
        logger.error("Failed to parse CrewAI result: %s | raw: %s", e, str(result)[:500])
        await message.answer(
            "Found events but couldn't parse results. Please try again.",
            reply_markup=get_main_keyboard(),
        )
        return
    # 6. Save to DB
    for event_data in top_events:
        try:
            await db.upsert_event(user_id, event_data)
        except Exception as e:
            logger.warning("Failed to save event: %s", e)
    # 7. Show to user
    if not top_events:
        await message.answer(
            f"No events found in {city} for the next 2 weeks. "
            "Try changing your city with /location.",
            reply_markup=get_main_keyboard(),
        )
        return
    await message.answer(
        f"Found {len(top_events)} events in {city}:"
    )
    for event in top_events:
        card = format_event_card(event)
        source_id = event.get("source_id", event.get("title", "unknown")[:20])
        keyboard = get_event_keyboard(source_id)
        try:
            await message.answer(card, reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            # Fallback without HTML if formatting fails
            await message.answer(
                f"{event.get('title', 'Event')}\n{event.get('source_url', '')}",
                reply_markup=keyboard,
            )
