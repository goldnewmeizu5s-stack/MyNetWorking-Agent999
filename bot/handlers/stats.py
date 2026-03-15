"""Handler for /stats command - local stats (no CrewAI dependency)."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("stats"))
async def handle_stats(message: Message, db):
    user_id = message.from_user.id
    await message.answer("Generating your stats...")

    try:
        stats = await db.get_basic_stats(user_id)
        budget = await db.get_budget_status(user_id)

        text = (
            "<b>Your Stats</b>\n\n"
            f"Events attended: {stats.get('total_events', 0)}\n"
            f"Total contacts: {stats.get('total_contacts', 0)}\n"
            f"Challenges completed: {stats.get('challenges_completed', 0)}\n\n"
            f"<b>Budget</b>\n"
            f"Spent this month: EUR{budget.get('spent_this_month', 0):.2f}\n"
            f"Remaining: EUR{budget.get('remaining', 0):.2f}"
        )
        await message.answer(text, parse_mode="HTML")

    except Exception:
        await message.answer("Could not load stats. Try again later.")
