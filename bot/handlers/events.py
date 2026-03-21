"""Handler for /events command - triggers DiscoveryCrew."""
import json
import logging
import re
import traceback
import urllib.parse
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

    # 2. Try to parse events from Luma/Meetup (best-effort, non-blocking)
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
        logger.warning("Event parsing failed (non-fatal): %s", e)

    # 3. Deterministic score for pre-parsed events (fallback ranking)
    for event in raw_events:
        event["deterministic_score"] = scorer.calculate(
            event=event,
            profile=context["user_profile"],
            transport_cost=0,
            transport_duration_min=0,
            calendar_free=True,
        )
    fallback_events = sorted(
        raw_events,
        key=lambda e: e.get("deterministic_score", 0),
        reverse=True,
    )[:5]

    # 4. Run DiscoveryCrew on CrewAI Platform
    await message.answer(
        f"🤖 AI is searching for events in {city}... (~20-30 seconds)"
    )

    try:
        result = await crew_tracker.run_and_track(
            crew_name="discovery",
            coro=crewai_client.run_discovery(raw_events, context),
            user_id=user_id,
        )
    except TimeoutError as e:
        await error_forwarder.send_error("events: CrewAI timeout", e)
        if fallback_events:
            await message.answer("⏳ AI search timed out. Showing direct parsing:")
            await _show_events(message, fallback_events, city, db, user_id)
        else:
            await message.answer("⏳ AI search timed out. Try again later.", reply_markup=get_main_keyboard())
        return
    except Exception as e:
        await error_forwarder.send_error("events: CrewAI call", e)
        if fallback_events:
            await message.answer("⚠️ AI search failed. Showing direct parsing:")
            await _show_events(message, fallback_events, city, db, user_id)
        else:
            await message.answer("⚠️ Event search failed. Try again.", reply_markup=get_main_keyboard())
        return

    # 5. Log raw result for debugging (not sent to user chat)
    logger.debug(
        "CrewAI raw result: %s",
        json.dumps(result, default=str, ensure_ascii=False)[:500],
    )

    # 6. Parse result — handle multiple possible formats
    top_events = _parse_crew_result(result)

    # 6.5 Merge source_url from raw_events into scored events
    if top_events:
        top_events = _merge_urls(top_events, raw_events, city)

    if top_events is None:
        await error_forwarder.send_error(
            "events: parse result",
            ValueError("Could not parse CrewAI result"),
            extra=json.dumps(result, default=str)[:2000],
        )
        if fallback_events:
            await message.answer("⚠️ Could not parse AI results. Showing direct parsing:")
            await _show_events(message, fallback_events, city, db, user_id)
        else:
            await message.answer("⚠️ Could not parse results. Try again.", reply_markup=get_main_keyboard())
        return

    # 7. Show results
    if top_events:
        await _show_events(message, top_events, city, db, user_id)
    elif fallback_events:
        await message.answer("AI found no events. Showing direct parsing:")
        await _show_events(message, fallback_events, city, db, user_id)
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


def _normalize_title(title: str) -> str:
    """Normalize title for fuzzy matching."""
    return re.sub(r"[^a-z0-9]", "", title.lower())


def _is_valid_url(url) -> bool:
    """Check if url is a real HTTP(S) URL, not null/None/empty."""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    return url.startswith("http://") or url.startswith("https://")


def _merge_urls(scored_events: list, raw_events: list, city: str) -> list:
    """Merge source_url from raw API events into Claude-scored events.

    Claude often returns source_url=null for events found via Perplexity.
    Raw events from Luma/Meetup have verified URLs — match by title and copy.
    For unmatched events, generate a search URL as fallback.
    """
    # Build lookup: normalized_title → source_url from raw events
    url_map: dict[str, str] = {}
    for raw in raw_events:
        url = raw.get("source_url", "")
        if _is_valid_url(url):
            norm = _normalize_title(raw.get("title", ""))
            if norm:
                url_map[norm] = url

    matched = 0
    generated = 0
    for event in scored_events:
        existing_url = event.get("source_url")

        # Normalize: convert "null", None, empty to ""
        if not _is_valid_url(existing_url):
            event["source_url"] = ""

        # Try to match from raw events by title
        if not _is_valid_url(event.get("source_url")):
            norm_title = _normalize_title(event.get("title", ""))
            # Exact match
            if norm_title in url_map:
                event["source_url"] = url_map[norm_title]
                matched += 1
                continue
            # Substring match (e.g. "Web Summit" in "Web Summit 2026 Lisbon")
            for raw_norm, raw_url in url_map.items():
                if norm_title in raw_norm or raw_norm in norm_title:
                    event["source_url"] = raw_url
                    matched += 1
                    break

        # If still no URL — generate a search URL
        if not _is_valid_url(event.get("source_url")):
            title = event.get("title", "")
            loc = event.get("location_city") or city
            query = urllib.parse.quote_plus(f"{title} {loc}")
            event["source_url"] = f"https://www.google.com/search?q={query}"
            generated += 1

    logger.info(
        "URL merge: %d matched from raw, %d generated search links, %d already had URLs",
        matched, generated, len(scored_events) - matched - generated,
    )
    return scored_events


async def _show_events(message: Message, events: list, city: str, db, user_id: int):
    """Display event cards and save to DB."""
    if not events:
        await message.answer(f"No events found in {city}.", reply_markup=get_main_keyboard())
        return

    await message.answer(f"Found {len(events)} events in {city}:")
    for event in events:
        # Generate source_id FIRST before saving
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
