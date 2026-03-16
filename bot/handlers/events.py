"""Handler for /events command - triggers DiscoveryCrew."""
import json
import logging
import traceback
from datetime import date, timedelta
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from bot.formatters import format_event_card
from bot.keyboards import get_event_keyboard, get_main_keyboard
logger = logging.getLogger(__name__)
MAX_TG_MSG = 4096


def _escape(text: str) -> str:
    """Escape HTML special chars for Telegram <pre> blocks."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def _show_events(message: Message, events: list, city: str, db, user_id: int):
    """Display event cards to the user and save to DB."""
    if not events:
        await message.answer(
            f"No events found in {city} for the next 2 weeks. "
            "Try changing your city with /location.",
            reply_markup=get_main_keyboard(),
        )
        return
    await message.answer(f"Found {len(events)} events in {city}:")
    for event in events:
        # Save to DB
        try:
            await db.upsert_event(user_id, event)
        except Exception as e:
            logger.warning("Failed to save event: %s", e)
        # Show card
        card = format_event_card(event)
        source_id = event.get("source_id", event.get("title", "unknown")[:20])
        keyboard = get_event_keyboard(source_id)
        try:
            await message.answer(card, reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            await message.answer(
                f"{event.get('title', 'Event')}\n{event.get('source_url', '')}",
                reply_markup=keyboard,
            )


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
    # Sort pre-parsed events by deterministic score (fallback ranking)
    fallback_events = sorted(
        raw_events,
        key=lambda e: e.get("deterministic_score", 0),
        reverse=True,
    )[:5]
    # 4. Run DiscoveryCrew on CrewAI Platform
    # Scout will SEARCH for events via Perplexity + use any pre-parsed events
    await message.answer(
        f"🤖 AI is searching for events in {city}... This may take 2-5 minutes."
    )
    progress_messages = [
        "⏳ Still searching... analyzing event details.",
        "⏳ Scoring and ranking events for you...",
        "⏳ Almost done, finalizing results...",
    ]
    progress_idx = 0

    async def _on_progress(elapsed_sec: int):
        nonlocal progress_idx
        if progress_idx < len(progress_messages):
            await message.answer(progress_messages[progress_idx])
            progress_idx += 1

    try:
        result = await crew_tracker.run_and_track(
            crew_name="discovery",
            coro=crewai_client.run_discovery(
                raw_events, context, on_progress=_on_progress
            ),
            user_id=user_id,
        )
    except TimeoutError as e:
        logger.error("CrewAI discovery timed out: %s", e)
        if fallback_events:
            await message.answer(
                "⏳ AI scoring timed out, but here are events from Luma/Meetup "
                "sorted by basic matching:"
            )
            await _show_events(message, fallback_events, city, db, user_id)
        else:
            await message.answer(
                "⏳ The AI search took too long and timed out.\n\n"
                "Please try again with /events.",
            )
        return
    except Exception as e:
        tb = traceback.format_exc()
        logger.error("CrewAI discovery failed: %s\n%s", e, tb)
        if fallback_events:
            await message.answer(
                "⚠️ AI scoring failed, but here are events from Luma/Meetup "
                "sorted by basic matching:"
            )
            await _show_events(message, fallback_events, city, db, user_id)
        else:
            await message.answer(
                "⚠️ Something went wrong while searching for events. "
                "Please try again later.",
            )
        return
    # 5. Check crew status and parse result
    crew_status = result.get("status", "unknown")
    if crew_status in ("failed", "error"):
        raw_preview = str(result)[:2000]
        logger.error("CrewAI returned status=%s: %s", crew_status, raw_preview)
        if fallback_events:
            await message.answer(
                "⚠️ AI scoring returned an error, showing events from Luma/Meetup:"
            )
            await _show_events(message, fallback_events, city, db, user_id)
        else:
            await message.answer(
                "⚠️ Event search failed. Please try again later.",
            )
        return

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
        tb = traceback.format_exc()
        raw_preview = str(result)[:1500]
        logger.error("Failed to parse CrewAI result: %s\n%s\nraw: %s", e, tb, raw_preview)
        if fallback_events:
            await message.answer(
                "⚠️ Could not parse AI results, showing events from Luma/Meetup:"
            )
            await _show_events(message, fallback_events, city, db, user_id)
        else:
            await message.answer(
                "⚠️ Could not parse event results. Please try again.",
            )
        return
    # 6. Show results (prefer crew results, fallback to pre-parsed)
    if top_events:
        await _show_events(message, top_events, city, db, user_id)
    elif fallback_events:
        await message.answer(
            "AI found no additional events. Here are events from Luma/Meetup:"
        )
        await _show_events(message, fallback_events, city, db, user_id)
    else:
        await message.answer(
            f"No events found in {city} for the next 2 weeks. "
            "Try changing your city with /location.",
            reply_markup=get_main_keyboard(),
        )
