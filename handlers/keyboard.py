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
        InlineKeyboardButton(text="🥅 Я вратарь", callback_data="goalie"),
        InlineKeyboardButton(text="➕ Добавить участника не из группы", callback_data="add_guest"),
        InlineKeyboardButton(text="➖ Удалить участника не из группы", callback_data="delete_guest"),
        InlineKeyboardButton(text="🔄 Изменить команду участника", callback_data="change_team"),
    )
    builder.adjust(1)
    return builder.as_markup()


def build_team_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора команды."""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Армада 🛡️", callback_data="team:Армада"),
        InlineKeyboardButton(text="Кабаны 🐗", callback_data="team:Кабаны"),
    )
    builder.adjust(2)
    return builder.as_markup()


def build_guest_role_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора роли гостя (игрок или вратарь)."""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="🏒 Игрок", callback_data="guest_role:player"),
        InlineKeyboardButton(text="🥅 Вратарь", callback_data="guest_role:goalie"),
    )
    builder.adjust(2)
    return builder.as_markup()


def build_goalie_status_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора статуса вратаря."""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Я буду, запиши меня", callback_data="goalie_status:YES"),
        InlineKeyboardButton(text="Пока не определился", callback_data="goalie_status:MAYBE"),
        InlineKeyboardButton(text="Не смогу пойти, занят", callback_data="goalie_status:NO"),
    )
    builder.adjust(1)
    return builder.as_markup()
