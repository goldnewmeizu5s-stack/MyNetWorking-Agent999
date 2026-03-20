"""Handler for booking - smart registration with progressive data collection."""

import asyncio
import json
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.keyboards import get_booking_confirm_keyboard, get_main_keyboard

logger = logging.getLogger(__name__)

router = Router()

# Map common form field names/placeholders to canonical keys
FIELD_ALIASES = {
    "first name": "name",
    "first_name": "name",
    "firstname": "name",
    "last name": "last_name",
    "last_name": "last_name",
    "lastname": "last_name",
    "full name": "name",
    "your name": "name",
    "name": "name",
    "email": "email",
    "e-mail": "email",
    "email address": "email",
    "phone": "phone",
    "phone number": "phone",
    "telephone": "phone",
    "company": "company",
    "organization": "company",
    "organisation": "company",
    "company name": "company",
    "job title": "role",
    "title": "role",
    "role": "role",
    "position": "role",
    "linkedin": "linkedin_url",
    "linkedin url": "linkedin_url",
    "linkedin profile": "linkedin_url",
    "twitter": "twitter",
    "twitter handle": "twitter",
    "website": "website",
    "url": "website",
    "city": "city",
    "location": "city",
    "country": "country",
    "age": "age",
    "dietary": "dietary",
    "dietary restrictions": "dietary",
    "t-shirt size": "tshirt_size",
    "shirt size": "tshirt_size",
}


class BookingStates(StatesGroup):
    collecting_fields = State()  # Asking missing fields one by one
    waiting_brief_response = State()  # Showing brief, waiting confirm/edit
    waiting_edit = State()  # User editing a field


def _normalize_field_key(raw_key: str) -> str:
    """Map a raw form field name to a canonical key."""
    lower = raw_key.lower().strip()
    return FIELD_ALIASES.get(lower, lower.replace(" ", "_"))


def _format_brief(form_data: dict, fields: list[dict]) -> str:
    """Format registration data as a brief for user confirmation."""
    lines = ["<b>Registration Brief:</b>\n"]
    for f in fields:
        key = _normalize_field_key(f.get("key", ""))
        label = f.get("label") or f.get("placeholder") or f.get("name") or key
        value = form_data.get(key, "")
        lines.append(f"  {label}: <b>{value or '(empty)'}</b>")
    return "\n".join(lines)


@router.callback_query(F.data.startswith("book:"))
async def handle_booking(
    callback: CallbackQuery, state: FSMContext, db, **kwargs
):
    event_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    await callback.answer()

    event = await db.get_event(event_id)
    logger.info("Looking up event_id: %s, found: %s", event_id, event is not None)
    if not event:
        await callback.message.answer("Event not found.")
        return

    await callback.message.answer(
        f"Preparing registration for: {event.title}..."
    )

    # 1. Scan form fields via Playwright
    source_url = event.source_url or ""
    if source_url and source_url.startswith("http"):
        fields = await _scan_form_fields(source_url)
    else:
        fields = []
        logger.info(
            "No valid URL for event %s, using default fields", event.source_id
        )
    if not fields:
        # Fallback: assume standard Luma fields
        fields = [
            {"key": "name", "label": "Name", "name": "name", "required": True},
            {"key": "email", "label": "Email", "name": "email", "required": True},
        ]

    # 2. Get known registration data from DB
    known_data = await db.get_registration_data(user_id)

    # 3. Match fields and find missing
    form_data = {}
    missing_fields = []

    for f in fields:
        canonical = _normalize_field_key(f.get("key", ""))
        f["canonical"] = canonical
        if canonical in known_data and known_data[canonical]:
            form_data[canonical] = known_data[canonical]
        else:
            missing_fields.append(f)

    # Store state
    await state.update_data(
        event_id=event_id,
        event_url=event.source_url,
        event_source=event.source,
        event_title=event.title,
        fields=fields,
        form_data=form_data,
        missing_fields=missing_fields,
        current_missing_idx=0,
    )

    if missing_fields:
        # Ask first missing field
        await _ask_next_field(callback.message, state)
    else:
        # All fields known - show brief
        await _show_brief(callback.message, state)


async def _ask_next_field(message: Message, state: FSMContext):
    """Ask user for the next missing field."""
    data = await state.get_data()
    missing = data["missing_fields"]
    idx = data["current_missing_idx"]

    if idx >= len(missing):
        # All collected, show brief
        await _show_brief(message, state)
        return

    field = missing[idx]
    label = field.get("label") or field.get("placeholder") or field.get("key", "")

    await state.set_state(BookingStates.collecting_fields)
    await message.answer(
        f"Please provide your <b>{label}</b>:",
        parse_mode="HTML",
    )


@router.message(BookingStates.collecting_fields)
async def handle_field_response(message: Message, state: FSMContext, bot, **kwargs):
    """Handle user's answer (text or voice) for a missing field."""
    # Handle voice messages
    text = message.text
    if message.voice:
        from bot.handlers.voice import _transcribe
        file = await bot.get_file(message.voice.file_id)
        file_data = await bot.download_file(file.file_path)
        text = await _transcribe(file_data)
        if text:
            await message.answer(f"Heard: \"{text}\"")

    if not text:
        await message.answer("Couldn't understand. Please type your answer.")
        return

    data = await state.get_data()
    missing = data["missing_fields"]
    idx = data["current_missing_idx"]
    form_data = data["form_data"]

    # Save answer
    field = missing[idx]
    canonical = field.get("canonical", field.get("key", ""))
    form_data[canonical] = text.strip()

    # Move to next
    await state.update_data(
        form_data=form_data,
        current_missing_idx=idx + 1,
    )

    await _ask_next_field(message, state)


async def _show_brief(message: Message, state: FSMContext):
    """Show registration brief for confirmation."""
    data = await state.get_data()
    brief = _format_brief(data["form_data"], data["fields"])

    await state.set_state(BookingStates.waiting_brief_response)
    await message.answer(
        f"{brief}\n\nIs this correct?",
        parse_mode="HTML",
        reply_markup=get_booking_confirm_keyboard(),
    )


@router.callback_query(
    BookingStates.waiting_brief_response,
    F.data == "booking_brief:confirm",
)
async def handle_brief_confirm(
    callback: CallbackQuery, state: FSMContext, db, **kwargs
):
    """User confirmed the brief - save data and book."""
    await callback.answer()
    data = await state.get_data()
    user_id = callback.from_user.id
    form_data = data["form_data"]

    # Save all new fields to registration_data
    await db.update_registration_data(user_id, form_data)

    await callback.message.answer("Registering you now...")

    # Run Playwright booking
    event_url = data.get("event_url") or ""
    if not event_url or not event_url.startswith("http"):
        # No URL - send manual booking message
        await callback.message.answer(
            f"✅ Registration data saved!\n\n"
            f"No direct booking URL available for this event.\n"
            f"Please register manually — your details are saved for next time:\n"
            f"Name: {form_data.get('name', '')}\n"
            f"Email: {form_data.get('email', '')}",
            reply_markup=get_main_keyboard(),
        )
        await state.clear()
        return
    browser_result = await _run_browser_booking(
        source=data["event_source"],
        url=event_url,
        form_data=form_data,
    )

    event_id = data["event_id"]

    if browser_result["status"] == "confirmed":
        await callback.message.answer(
            f"Registered for {data['event_title']}!\n"
            "Will remind you 24h and 2h before.",
            reply_markup=get_main_keyboard(),
        )
        await db.update_event_status(event_id, "confirmed")

    elif browser_result["status"] == "waitlisted":
        await callback.message.answer(
            "You're on the waitlist. I'll check and notify you.",
            reply_markup=get_main_keyboard(),
        )
        await db.update_event_status(event_id, "waitlisted")

    else:
        event = await db.get_event(event_id)
        url = event.source_url if event else data["event_url"]
        await callback.message.answer(
            "Couldn't auto-register.\n"
            f"Here's the link: {url}\n"
            "Your data has been saved for next time.",
            reply_markup=get_main_keyboard(),
        )

    await state.clear()


@router.callback_query(
    BookingStates.waiting_brief_response,
    F.data == "booking_brief:edit",
)
async def handle_brief_edit(
    callback: CallbackQuery, state: FSMContext, **kwargs
):
    """User wants to edit - ask what to change."""
    await callback.answer()
    await state.set_state(BookingStates.waiting_edit)
    await callback.message.answer(
        "What would you like to change? Tell me the field and new value.\n"
        "Example: \"email: newemail@example.com\" or \"company: Acme Inc\""
    )


@router.message(BookingStates.waiting_edit)
async def handle_edit_response(message: Message, state: FSMContext, bot, **kwargs):
    """Handle user's edit (text or voice)."""
    text = message.text
    if message.voice:
        from bot.handlers.voice import _transcribe
        file = await bot.get_file(message.voice.file_id)
        file_data = await bot.download_file(file.file_path)
        text = await _transcribe(file_data)
        if text:
            await message.answer(f"Heard: \"{text}\"")

    if not text:
        await message.answer("Couldn't understand. Please type your correction.")
        return

    data = await state.get_data()
    form_data = data["form_data"]

    # Parse "field: value" or "field = value"
    updated = False
    for sep in [":", "=", " - "]:
        if sep in text:
            parts = text.split(sep, 1)
            field_name = _normalize_field_key(parts[0].strip())
            value = parts[1].strip()
            if field_name and value:
                form_data[field_name] = value
                updated = True
                break

    if not updated:
        # Try to match against known fields
        text_lower = text.lower()
        for f in data["fields"]:
            canonical = f.get("canonical", f.get("key", ""))
            label = (f.get("label") or f.get("key") or "").lower()
            if label and label in text_lower:
                # Extract value after field name mention
                idx = text_lower.index(label) + len(label)
                value = text[idx:].strip().lstrip(":=- ")
                if value:
                    form_data[canonical] = value
                    updated = True
                    break

    if updated:
        await state.update_data(form_data=form_data)
        await message.answer("Updated!")
        await _show_brief(message, state)
    else:
        await message.answer(
            "Couldn't parse that. Use format: \"field: new value\"\n"
            "Example: \"email: new@email.com\""
        )


@router.callback_query(F.data.startswith("skip:"))
async def handle_skip(callback: CallbackQuery, db, preference_learner, **kwargs):
    event_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    await callback.answer()

    event = await db.get_event(event_id)
    if event:
        await db.update_event_status(event_id, "skipped")
        await preference_learner.learn_from_skip(user_id, event.to_dict())

    await callback.message.answer(
        "Skipped. I'll keep this in mind.",
        reply_markup=get_main_keyboard(),
    )


async def _scan_form_fields(url: str) -> list[dict]:
    """Run Playwright subprocess to scan form fields."""
    try:
        params = json.dumps({"url": url})
        proc = await asyncio.create_subprocess_exec(
            "python",
            "browser/browser_worker.py",
            "--task",
            "scan_fields",
            "--params",
            params,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

        if proc.returncode == 0:
            result = json.loads(stdout.decode())
            return result.get("fields", [])
    except Exception as e:
        logger.warning("Form scan failed: %s", e)
    return []


async def _run_browser_booking(
    source: str, url: str, form_data: dict
) -> dict:
    """Run Playwright in subprocess."""
    task = "luma_book" if source == "luma" else "meetup_book"
    params = json.dumps({"url": url, "form_data": form_data})

    try:
        proc = await asyncio.create_subprocess_exec(
            "python",
            "browser/browser_worker.py",
            "--task",
            task,
            "--params",
            params,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

        if proc.returncode == 0:
            return json.loads(stdout.decode())
        else:
            return {"status": "failed", "error": stderr.decode()[:500]}
    except Exception as e:
        return {"status": "failed", "error": str(e)}
