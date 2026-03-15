"""Handlers for /location, /interests, /budget, /settings commands."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

router = Router()


class SettingsStates(StatesGroup):
    waiting_location = State()
    waiting_interests = State()
    waiting_budget_ticket = State()
    waiting_budget_transport = State()


@router.message(Command("settings"))
async def handle_settings(message: Message, db):
    user_id = message.from_user.id
    profile = await db.get_user_profile(user_id)

    if not profile:
        await message.answer("Please run /start first to set up your profile.")
        return

    text = (
        "<b>Your Settings</b>\n\n"
        f"Name: {profile.name}\n"
        f"City: {profile.current_city}\n"
        f"Interests: {', '.join(profile.interests or [])}\n"
        f"Budget (ticket): EUR{profile.budget_limit_ticket}\n"
        f"Budget (transport): EUR{profile.budget_limit_transport}\n"
        f"Languages: {', '.join(profile.preferred_languages or ['en'])}\n"
        f"Preferred time: {profile.preferred_time or 'any'}\n\n"
        "Commands to update:\n"
        "/location - update city\n"
        "/interests - update interests\n"
        "/budget - update budget limits"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("location"))
async def handle_location(message: Message, state: FSMContext):
    await state.set_state(SettingsStates.waiting_location)
    await message.answer(
        "What city are you in? (e.g., Lisbon, Berlin, London)"
    )


@router.message(SettingsStates.waiting_location)
async def process_location(message: Message, state: FSMContext, db):
    city = message.text.strip()
    user_id = message.from_user.id

    # Geocoding would happen here in production
    await db.update_user_city(user_id, city, lat=0.0, lon=0.0)
    await state.clear()
    await message.answer(f"Location updated to {city}!")


@router.message(Command("interests"))
async def handle_interests(message: Message, state: FSMContext):
    await state.set_state(SettingsStates.waiting_interests)
    await message.answer(
        "What topics interest you?\n"
        "Separate with commas (e.g., AI, startups, SaaS, crypto, marketing)"
    )


@router.message(SettingsStates.waiting_interests)
async def process_interests(message: Message, state: FSMContext, db):
    interests = [i.strip() for i in message.text.split(",") if i.strip()]
    user_id = message.from_user.id

    await db.update_user_interests(user_id, interests)
    await state.clear()
    await message.answer(f"Interests updated: {', '.join(interests)}")


@router.message(Command("budget"))
async def handle_budget(message: Message, state: FSMContext):
    await state.set_state(SettingsStates.waiting_budget_ticket)
    await message.answer(
        "What's your max ticket price in EUR? (e.g., 50)"
    )


@router.message(SettingsStates.waiting_budget_ticket)
async def process_budget_ticket(
    message: Message, state: FSMContext
):
    try:
        amount = float(message.text.strip())
    except ValueError:
        await message.answer("Please enter a number.")
        return

    await state.update_data(budget_ticket=amount)
    await state.set_state(SettingsStates.waiting_budget_transport)
    await message.answer(
        "And max transport cost in EUR? (e.g., 20)"
    )


@router.message(SettingsStates.waiting_budget_transport)
async def process_budget_transport(
    message: Message, state: FSMContext, db
):
    try:
        amount = float(message.text.strip())
    except ValueError:
        await message.answer("Please enter a number.")
        return

    data = await state.get_data()
    user_id = message.from_user.id

    await db.update_user_budget(
        user_id,
        budget_ticket=data["budget_ticket"],
        budget_transport=amount,
    )
    await state.clear()
    await message.answer(
        f"Budget updated!\n"
        f"Ticket: EUR{data['budget_ticket']}\n"
        f"Transport: EUR{amount}"
    )
