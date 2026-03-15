"""Inline keyboard builders for Telegram bot."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_event_keyboard(source_id: str) -> InlineKeyboardMarkup:
    """Keyboard for event card: Details, Book, Skip."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Details", callback_data=f"details:{source_id}"
                ),
                InlineKeyboardButton(
                    text="Book", callback_data=f"book:{source_id}"
                ),
                InlineKeyboardButton(
                    text="Skip", callback_data=f"skip:{source_id}"
                ),
            ]
        ]
    )


def get_rating_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for debrief rating 1-10."""
    buttons = []
    row = []
    for i in range(1, 11):
        row.append(
            InlineKeyboardButton(text=str(i), callback_data=f"rate:{i}")
        )
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    """Yes/No confirmation keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Yes", callback_data="confirm:yes"),
                InlineKeyboardButton(text="No", callback_data="confirm:no"),
            ]
        ]
    )


def get_debrief_cost_keyboard(estimated_cost: float) -> InlineKeyboardMarkup:
    """Keyboard to confirm or update actual costs."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Yes (EUR{estimated_cost:.2f})",
                    callback_data="cost:confirm",
                ),
                InlineKeyboardButton(
                    text="No, different", callback_data="cost:update"
                ),
            ]
        ]
    )
