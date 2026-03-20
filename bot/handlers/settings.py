"""Handlers for /location, /interests, /budget, /settings commands."""

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot.keyboards import get_main_keyboard

logger = logging.getLogger(__name__)
router = Router()


class SettingsStates(StatesGroup):
    waiting_location = State()
    waiting_interests = State()
    waiting_budget_ticket = State()
    waiting_budget_transport = State()


@router.message(Command("settings"))
async def handle_settings(message: Message, db, **kwargs):
    user_id = message.from_user.id
    profile = await db.get_user_profile(user_id)

    if not profile:
        await message.answer(
            "Please run /start first to set up your profile.",
            reply_markup=get_main_keyboard(),
        )
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
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())


@router.message(Command("location"))
async def handle_location(message: Message, state: FSMContext, **kwargs):
    await state.set_state(SettingsStates.waiting_location)
    await message.answer(
        "What city are you in? (e.g., Lisbon, Berlin, London)"
    )


@router.message(SettingsStates.waiting_location)
async def process_location(message: Message, state: FSMContext, db, **kwargs):
    city = message.text.strip()
    user_id = message.from_user.id

    # Geocode city using OpenStreetMap Nominatim (free, no API key)
    lat, lon = 0.0, 0.0
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": city, "format": "json", "limit": 1},
                headers={"User-Agent": "PlanetNineBot/1.0"},
            )
            if resp.status_code == 200:
                results = resp.json()
                if results:
                    lat = float(results[0]["lat"])
                    lon = float(results[0]["lon"])
                    # Use the official city name from geocoder
                    city = results[0].get("display_name", city).split(",")[0].strip()
    except Exception as e:
        logger.warning("Geocoding failed for %s: %s", city, e)
    await db.update_user_city(user_id, city, lat=lat, lon=lon)
    await state.clear()

    location_info = f"📍 {city}"
    if lat != 0.0:
        location_info += f" ({lat:.2f}, {lon:.2f})"

    await message.answer(
        f"Location updated to {location_info}!",
        reply_markup=get_main_keyboard(),
    )


@router.message(Command("interests"))
async def handle_interests(message: Message, state: FSMContext, **kwargs):
    await state.set_state(SettingsStates.waiting_interests)
    await message.answer(
        "What topics interest you?\n"
        "Separate with commas (e.g., AI, startups, SaaS, crypto, marketing)"
    )


@router.message(SettingsStates.waiting_interests)
async def process_interests(message: Message, state: FSMContext, db, **kwargs):
    interests = [i.strip() for i in message.text.split(",") if i.strip()]
    user_id = message.from_user.id

    await db.update_user_interests(user_id, interests)
    await state.clear()
    await message.answer(
        f"Interests updated: {', '.join(interests)}",
        reply_markup=get_main_keyboard(),
    )


@router.message(Command("budget"))
async def handle_budget(message: Message, state: FSMContext, **kwargs):
    await state.set_state(SettingsStates.waiting_budget_ticket)
    await message.answer(
        "What's your max ticket price in EUR? (e.g., 50)"
    )


@router.message(SettingsStates.waiting_budget_ticket)
async def process_budget_ticket(
    message: Message, state: FSMContext, **kwargs
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
    message: Message, state: FSMContext, db, **kwargs
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
        f"Transport: EUR{amount}",
        reply_markup=get_main_keyboard(),
    )
