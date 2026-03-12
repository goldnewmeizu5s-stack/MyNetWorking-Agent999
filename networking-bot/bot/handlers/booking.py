"""Handler for booking callbacks - triggers BookingCrew + Playwright."""

import asyncio
import json

from aiogram import F, Router
from aiogram.types import CallbackQuery

router = Router()


@router.callback_query(F.data.startswith("book:"))
async def handle_booking(
    callback: CallbackQuery, crewai_client, context_builder, db
):
    event_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    await callback.answer()
    await callback.message.answer("Booking...")

    # 1. Build context
    context = await context_builder.build(user_id)
    event = await db.get_event(event_id)
    user_profile = await db.get_user_profile(user_id)

    if not event:
        await callback.message.answer("Event not found.")
        return

    # 2. Run BookingCrew on CrewAI Platform
    crew_result = await crewai_client.run_booking(
        event=event.to_dict(),
        user_profile=user_profile.to_dict(),
        context=context,
    )
    booking_data = json.loads(crew_result["output"])

    # 3. Check: are additional fields needed?
    if booking_data.get("status") == "missing_fields":
        missing = booking_data.get("missing_fields", [])
        await callback.message.answer(
            "I need additional information:\n"
            + "\n".join(f"{i+1}. {f}?" for i, f in enumerate(missing))
        )
        return

    # 4. Run Playwright for actual registration (subprocess on Railway)
    booking_instruction = booking_data.get("booking_instruction", {})
    browser_result = await _run_browser_booking(
        source=event.source,
        url=event.source_url,
        form_data=booking_instruction,
    )

    # 5. Result to user
    if browser_result["status"] == "confirmed":
        challenge = booking_data.get("challenge", {})
        text = (
            "Registered you!\n"
            "Added to Google Calendar\n"
            "Will remind you 24h and 2h before\n\n"
        )
        if challenge:
            text += (
                f"Challenge for this event:\n"
                f"'{challenge.get('description', '')}'\n\n"
                f"Success metrics:\n"
            )
            for m in challenge.get("success_metrics", []):
                text += f"- {m}\n"

        await callback.message.answer(text)
        await db.update_event_status(event_id, "confirmed")

    elif browser_result["status"] == "waitlisted":
        await callback.message.answer(
            "You're on the waitlist. "
            "I'll check status every 6 hours and notify you."
        )
        await db.update_event_status(event_id, "waitlisted")

    else:
        await callback.message.answer(
            "Couldn't auto-register.\n"
            f"Here's the link: {event.source_url}\n"
            "Let me know when you've registered."
        )


@router.callback_query(F.data.startswith("skip:"))
async def handle_skip(callback: CallbackQuery, db, preference_learner):
    event_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    await callback.answer()

    event = await db.get_event(event_id)
    if event:
        await db.update_event_status(event_id, "skipped")
        await preference_learner.learn_from_skip(user_id, event.to_dict())

    await callback.message.answer("Skipped. I'll keep this in mind.")


async def _run_browser_booking(
    source: str, url: str, form_data: dict
) -> dict:
    """Run Playwright in subprocess."""
    task = "luma_book" if source == "luma" else "meetup_book"
    params = json.dumps({"url": url, "form_data": form_data})

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
