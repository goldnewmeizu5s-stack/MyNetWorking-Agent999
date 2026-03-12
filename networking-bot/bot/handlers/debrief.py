"""Handler for /debrief command - triggers DebriefCrew."""

import json

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.keyboards import get_rating_keyboard

router = Router()


class DebriefStates(StatesGroup):
    waiting_rating = State()
    waiting_contacts = State()
    waiting_cost_confirm = State()


@router.message(Command("debrief"))
async def handle_debrief_start(message: Message, state: FSMContext, db):
    user_id = message.from_user.id

    # Find the most recent confirmed event
    recent_event = await db.get_most_recent_confirmed_event(user_id)
    if not recent_event:
        await message.answer("No recent events to debrief. Attend an event first!")
        return

    await state.update_data(event_id=str(recent_event.event_id))
    await state.set_state(DebriefStates.waiting_rating)

    await message.answer(
        f"How was '{recent_event.title}'? Rate 1-10:",
        reply_markup=get_rating_keyboard(),
    )


@router.callback_query(
    DebriefStates.waiting_rating, F.data.startswith("rate:")
)
async def handle_rating(
    callback: CallbackQuery, state: FSMContext
):
    rating = int(callback.data.split(":")[1])
    await callback.answer()
    await state.update_data(rating=rating)
    await state.set_state(DebriefStates.waiting_contacts)

    await callback.message.answer(
        "Who did you meet? (text or voice)\n"
        "Format: Name (Role, Company)"
    )


@router.message(DebriefStates.waiting_contacts)
async def handle_contacts(
    message: Message,
    state: FSMContext,
    crewai_client,
    context_builder,
    db,
    preference_learner,
):
    user_id = message.from_user.id
    data = await state.get_data()
    event_id = data["event_id"]
    rating = data["rating"]

    contacts_text = message.text or ""

    # Parse contacts from text
    contacts = _parse_contacts(contacts_text)

    event = await db.get_event(event_id)
    if not event:
        await message.answer("Event not found.")
        await state.clear()
        return

    # Build debrief data
    debrief_data = {
        "event_id": event_id,
        "event": event.to_dict(),
        "user_rating": rating,
        "contacts": contacts,
        "actual_cost": event.total_estimated_cost or 0,
        "contacts_count": len(contacts),
        "contacts_quality_avg": 7.0,  # default, can be refined
    }

    # Build context and run DebriefCrew
    context = await context_builder.build(user_id)

    try:
        result = await crewai_client.run_debrief(debrief_data, context)
        output = json.loads(result["output"])

        # Save result to DB
        await db.create_event_result(
            event_id=event_id,
            user_id=user_id,
            contacts_made=contacts,
            user_rating=rating,
            actual_cost=debrief_data["actual_cost"],
            roi_score=output.get("roi_score", 0),
        )

        # Learn from debrief
        await preference_learner.learn_from_debrief(
            user_id, event.to_dict(), rating
        )

        # Format response
        roi = output.get("roi_score", 0)
        comparison = output.get("comparison_to_forecast", "")
        text = (
            f"ROI: {roi:.1f}\n"
            f"{comparison}\n"
            f"Contacts: {len(contacts)}\n"
        )

        challenge_eval = output.get("challenge_evaluation")
        if challenge_eval:
            text += f"\nChallenge: {challenge_eval.get('status', 'N/A')}"
            feedback = challenge_eval.get("feedback", "")
            if feedback:
                text += f"\n{feedback}"

        await message.answer(text)

    except Exception:
        await message.answer(
            "Something went wrong with the debrief analysis. "
            "Your data has been saved though."
        )

    await state.clear()


def _parse_contacts(text: str) -> list[dict]:
    """Parse contacts from user text input."""
    contacts = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # Try to parse "Name (Role, Company)" format
        if "(" in line and ")" in line:
            name_part = line[: line.index("(")].strip()
            details = line[line.index("(") + 1 : line.index(")")].strip()
            parts = [p.strip() for p in details.split(",")]
            contact = {"name": name_part}
            if len(parts) >= 2:
                contact["role"] = parts[0]
                contact["company"] = parts[1]
            elif len(parts) == 1:
                contact["company"] = parts[0]
            contacts.append(contact)
        else:
            contacts.append({"name": line})
    return contacts
