"""Handler for /stats command - triggers WeeklyReportCrew."""

import json
from datetime import date, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("stats"))
async def handle_stats(
    message: Message, crewai_client, context_builder, crew_tracker, db
):
    user_id = message.from_user.id
    await message.answer("Generating your stats report...")

    context = await context_builder.build(user_id)

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    period = f"{week_start.isoformat()} to {today.isoformat()}"

    try:
        result = await crew_tracker.run_and_track(
            crew_name="weekly_report",
            coro=crewai_client.run_weekly_report(context, period),
            user_id=user_id,
        )
        output = json.loads(result["output"])

        text = (
            f"<b>Weekly Stats ({period})</b>\n\n"
            f"Events attended: {output.get('total_events', 0)}\n"
            f"Total spent: EUR{output.get('total_spent', 0):.2f}\n"
            f"Average ROI: {output.get('avg_roi', 0):.1f}\n"
            f"Best event type: {output.get('best_event_type', 'N/A')}\n"
            f"New contacts: {output.get('contacts_total', 0)}\n"
            f"Challenges: {output.get('challenges_completed', 0)}/{output.get('challenges_assigned', 0)}\n"
            f"Trend: {output.get('trend', 'N/A')} {output.get('trend_detail', '')}\n\n"
            f"Recommendation: {output.get('recommendation_next_week', '')}"
        )
        await message.answer(text, parse_mode="HTML")

    except Exception:
        # Fallback to local stats
        stats = await db.get_basic_stats(user_id)
        text = (
            "<b>Quick Stats</b>\n\n"
            f"Events attended: {stats.get('total_events', 0)}\n"
            f"Total contacts: {stats.get('total_contacts', 0)}\n"
            f"Challenges completed: {stats.get('challenges_completed', 0)}"
        )
        await message.answer(text, parse_mode="HTML")
