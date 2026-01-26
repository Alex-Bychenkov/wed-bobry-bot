"""Keyboard builders for the bot."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def build_prompt_keyboard() -> InlineKeyboardMarkup:
    """Build the main prompt keyboard with status buttons."""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Я буду, запиши меня", callback_data="status:YES"),
        InlineKeyboardButton(text="Пока не определился", callback_data="status:MAYBE"),
        InlineKeyboardButton(text="Не смогу пойти, занят", callback_data="status:NO"),
        InlineKeyboardButton(text="➕ Добавить участника не из группы", callback_data="add_guest"),
        InlineKeyboardButton(text="➖ Удалить участника не из группы", callback_data="delete_guest"),
    )
    builder.adjust(1)
    return builder.as_markup()
