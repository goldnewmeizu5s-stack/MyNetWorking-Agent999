"""Handler for /events command - triggers DiscoveryCrew."""
import json
import logging
import traceback
import urllib.parse
from datetime import date, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

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
    error_forwarder,
    **kwargs,
):
    user_id = message.from_user.id
    await message.answer("🔍 Searching for events...")

    # 1. Build context
    try:
        context = await context_builder.build(user_id)
    except Exception as e:
        await error_forwarder.send_error("events: build context", e)
        await message.answer("Error loading profile. Try /start first.", reply_markup=get_main_keyboard())
        return

    if not context.get("user_profile", {}).get("current_city"):
        await message.answer(
            "Please set your location first with /location",
            reply_markup=get_main_keyboard(),
        )
        return

    city = context["current_location"]["city"]

    # 2. Run DiscoveryCrew (Perplexity + Claude — single source of truth)
    await message.answer(
        f"🤖 AI is searching for events in {city}... (~20-30 seconds)"
    )

    try:
        result = await crew_tracker.run_and_track(
            crew_name="discovery",
            coro=crewai_client.run_discovery([], context),
            user_id=user_id,
        )
    except TimeoutError as e:
        await error_forwarder.send_error("events: CrewAI timeout", e)
        await message.answer("⏳ AI search timed out. Try again later.", reply_markup=get_main_keyboard())
        return
    except Exception as e:
        await error_forwarder.send_error("events: CrewAI call", e)
        await message.answer("⚠️ Event search failed. Try again.", reply_markup=get_main_keyboard())
        return

    # 3. Log raw result for debugging (not sent to user chat)
    logger.debug(
        "CrewAI raw result: %s",
        json.dumps(result, default=str, ensure_ascii=False)[:500],
    )

    # 4. Parse result — handle multiple possible formats
    top_events = _parse_crew_result(result)

    if top_events is None:
        await error_forwarder.send_error(
            "events: parse result",
            ValueError("Could not parse CrewAI result"),
            extra=json.dumps(result, default=str)[:2000],
        )
        await message.answer("⚠️ Could not parse results. Try again.", reply_markup=get_main_keyboard())
        return

    # 5. Show results
    if top_events:
        await _show_events(message, top_events, city, db, user_id)
    else:
        await message.answer(
            f"No events found in {city}. Try /location to change city.",
            reply_markup=get_main_keyboard(),
        )


def _parse_crew_result(result: dict) -> list | None:
    """Parse discovery result. Supports direct Claude format and legacy Platform format."""
    try:
        # Primary format from direct Claude call:
        # {"output": "{\"top_events\": [...]}", "status": "completed"}
        output = result.get("output")

        # Parse output if it's a JSON string
        if isinstance(output, str) and output.strip():
            try:
                output = json.loads(output)
            except json.JSONDecodeError:
                logger.error("Failed to parse output JSON: %s", output[:200])
                return None

        # Extract events list from dict
        if isinstance(output, dict):
            for key in ("top_events", "scored_events", "events"):
                events = output.get(key)
                if isinstance(events, list) and events:
                    logger.info("Found %d events under key '%s'", len(events), key)
                    return events

        # Output is already a list
        if isinstance(output, list) and output:
            return output

        logger.warning("No events found in result: %s", str(result)[:200])
        return None
    except Exception as e:
        logger.error("_parse_crew_result failed: %s", e, exc_info=True)
        return None


async def _show_events(message: Message, events: list, city: str, db, user_id: int):
    """Display event cards and save to DB."""
    if not events:
        await message.answer(f"No events found in {city}.", reply_markup=get_main_keyboard())
        return

    await message.answer(f"Found {len(events)} events in {city}:")
    for event in events:
        # Generate source_id FIRST before saving
        import re
        source_id = event.get("source_id") or ""
        if not source_id:
            source_id = re.sub(
                r"[^a-z0-9-]", "",
                event.get("title", "unknown").lower().replace(" ", "-")
            )[:40]
        event["source_id"] = source_id
        try:
            await db.upsert_event(user_id, event)
        except Exception as e:
            logger.warning("Failed to save event %s: %s", source_id, e)
        card = format_event_card(event)
        keyboard = get_event_keyboard(source_id)
        try:
            await message.answer(card, reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            title = event.get("title", "Event")
            url = event.get("source_url", "")
            await message.answer(f"{title}\n{url}", reply_markup=keyboard)


@router.callback_query(F.data.startswith("details:"))
async def handle_event_details(callback: CallbackQuery, db, **kwargs):
    """Show full event details from DB."""
    source_id = callback.data.split(":", 1)[1]
    event = await db.get_event(source_id)

    if not event:
        await callback.answer("Event not found", show_alert=True)
        return

    # Build detailed card
    lines = [f"<b>{event.title}</b>"]

    if event.description and str(event.description) not in ("None", ""):
        lines.append(f"\n{event.description}")

    if event.datetime_start:
        dt_str = event.datetime_start.strftime("%A, %d %B %Y %H:%M")
        lines.append(f"\n📅 <b>Date:</b> {dt_str}")

    if event.event_type and str(event.event_type) not in ("None", ""):
        lines.append(f"🏷 <b>Type:</b> {event.event_type}")

    if event.organizer_name and str(event.organizer_name) not in ("None", ""):
        lines.append(f"👤 <b>Organizer:</b> {event.organizer_name}")

    location_parts = []
    if event.location_name and str(event.location_name) not in ("None", ""):
        location_parts.append(event.location_name)
    if event.location_address and str(event.location_address) not in ("None", ""):
        location_parts.append(event.location_address)
    if event.location_city and str(event.location_city) not in ("None", ""):
        location_parts.append(event.location_city)
    if location_parts:
        lines.append(f"📍 <b>Location:</b> {', '.join(location_parts)}")

    if event.ticket_price is not None:
        currency = event.currency or "EUR"
        if event.ticket_price == 0:
            lines.append("🎟 <b>Price:</b> Free")
        else:
            lines.append(f"🎟 <b>Price:</b> {currency}{event.ticket_price:.0f}")

    if event.transport_cost and float(event.transport_cost) > 0:
        transport = f"🚌 <b>Transport:</b> €{float(event.transport_cost):.2f}"
        if event.transport_duration_min and int(event.transport_duration_min) > 0:
            transport += f" (~{event.transport_duration_min} min)"
        lines.append(transport)

    if event.total_estimated_cost and float(event.total_estimated_cost) > 0:
        lines.append(f"💰 <b>Total est. cost:</b> €{float(event.total_estimated_cost):.2f}")

    if event.language and str(event.language) not in ("None", ""):
        lines.append(f"🗣 <b>Language:</b> {event.language.upper()}")

    if event.capacity and int(event.capacity) > 0:
        lines.append(f"👥 <b>Capacity:</b> {event.capacity}")

    if event.total_score:
        lines.append(f"\n⭐️ <b>Score:</b> {event.total_score:.0f}/100")

    if event.recommendation_reason and str(event.recommendation_reason) not in ("None", ""):
        lines.append(f"💡 {event.recommendation_reason}")

    if event.source_url and str(event.source_url) not in ("None", ""):
        lines.append(f"\n🔗 <a href='{event.source_url}'>Event page</a>")
    else:
        search_q = urllib.parse.quote_plus(f"{event.title} {event.location_city or ''} 2026".strip())
        lines.append(f"\n🔍 <a href='https://www.google.com/search?q={search_q}'>Search on Google</a>")

    text = "\n".join(lines)
    keyboard = get_event_keyboard(source_id)

    try:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        await callback.message.answer(f"{event.title}\n{event.source_url or ''}", reply_markup=keyboard)

    await callback.answer()
