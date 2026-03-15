"""Handler for /challenge command - shows current challenge from DB."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("challenge"))
async def handle_challenge(message: Message, db):
    user_id = message.from_user.id

    active = await db.get_active_challenges(user_id)

    if not active:
        await message.answer(
            "No active challenges. Book an event to get a personalized challenge!"
        )
        return

    for ch in active:
        text = (
            f"<b>Challenge: {ch.methodology_name}</b>\n"
            f"Difficulty: {ch.difficulty}\n\n"
            f"{ch.description}\n\n"
            f"<b>Success Metrics:</b>\n"
        )
        for m in ch.success_metrics or []:
            text += f"- {m}\n"

        text += "\n<b>Tips:</b>\n"
        for t in ch.tips or []:
            text += f"- {t}\n"

        if ch.progress_note:
            text += f"\n{ch.progress_note}"

        await message.answer(text, parse_mode="HTML")
