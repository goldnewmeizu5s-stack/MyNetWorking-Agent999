"""Handler for /contacts command - shows contacts from DB."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("contacts"))
async def handle_contacts(message: Message, db):
    user_id = message.from_user.id

    contacts = await db.get_all_contacts(user_id)

    if not contacts:
        await message.answer(
            "No contacts yet. Attend some events and do a /debrief!"
        )
        return

    text = "<b>Your Networking Contacts</b>\n\n"
    for i, contact in enumerate(contacts, 1):
        name = contact.get("name", "Unknown")
        company = contact.get("company", "")
        role = contact.get("role", "")
        event_title = contact.get("event_title", "")

        line = f"{i}. <b>{name}</b>"
        if role and company:
            line += f" - {role}, {company}"
        elif company:
            line += f" - {company}"
        if event_title:
            line += f"\n   (met at: {event_title})"
        text += line + "\n"

    await message.answer(text, parse_mode="HTML")
