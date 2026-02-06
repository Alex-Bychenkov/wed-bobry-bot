"""Command handlers (/start, /status, /reset, /close)."""
from __future__ import annotations

from aiogram import Bot, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from config import CHAT_ID
from metrics import COMMANDS_TOTAL
from middleware import (
    auto_delete_command,
    is_chat_admin,
    require_target_chat,
    track_duration,
)
from models import Session
from services.message_service import MessageService
from services.session_service import SessionService

from handlers.keyboard import build_prompt_keyboard


router = Router()


@router.message(CommandStart())
@track_duration("start")
@auto_delete_command(delay=3)
async def cmd_start(message: Message, bot: Bot) -> None:
    """Handle /start command - show main menu."""
    COMMANDS_TOTAL.labels(command="start").inc()
    
    chat_id = message.chat.id
    
    # Delete previous /start message
    old_message_id = MessageService.get_last_start_message(chat_id)
    if old_message_id:
        await MessageService.delete_message_safe(bot, chat_id, old_message_id)
    
    text = (
        "Привет! Нажми кнопку под сообщением бота и выбери статус.\n"
        "Если фамилия еще не сохранена, бот попросит ее один раз."
    )
    new_message = await message.answer(text, reply_markup=build_prompt_keyboard())
    
    MessageService.set_last_start_message(chat_id, new_message.message_id)


@router.message(Command("status"))
@track_duration("status")
@auto_delete_command(delay=3)
async def cmd_status(message: Message, bot: Bot) -> None:
    """Handle /status command - show current list."""
    COMMANDS_TOTAL.labels(command="status").inc()
    
    chat_id = message.chat.id
    
    # Delete previous /start or /status message with buttons
    old_message_id = MessageService.get_last_start_message(chat_id)
    if old_message_id:
        await MessageService.delete_message_safe(bot, chat_id, old_message_id)
    
    # Force refresh session from DB
    SessionService.invalidate_cache(CHAT_ID)
    session = await SessionService.get_or_create_session(CHAT_ID, force_refresh=True)
    
    # Also get fresh data directly from DB
    fresh_session = await SessionService.get_open_session(CHAT_ID)
    list_message_id = fresh_session.list_message_id if fresh_session else session.list_message_id
    
    # Delete previous list message
    if list_message_id:
        await MessageService.delete_message_safe(bot, CHAT_ID, list_message_id)
        await SessionService.update_list_message_id(session.id, None)
        session.list_message_id = None
        SessionService.invalidate_cache(CHAT_ID)
    
    # Create new prompt message with buttons
    text = (
        "Привет! Нажми кнопку под сообщением бота и выбери статус.\n"
        "Если фамилия еще не сохранена, бот попросит ее один раз."
    )
    new_message = await message.answer(text, reply_markup=build_prompt_keyboard())
    MessageService.set_last_start_message(chat_id, new_message.message_id)
    
    # Create new list message
    await MessageService.ensure_list_message(bot, session)
    
    # Invalidate cache with new list_message_id
    SessionService.invalidate_cache(CHAT_ID)


@router.message(Command("reset"))
@track_duration("reset")
@auto_delete_command(delay=3)
async def cmd_reset(message: Message, bot: Bot) -> None:
    """Handle /reset command (admin only) - reset session."""
    COMMANDS_TOTAL.labels(command="reset").inc()
    
    if message.chat.id != CHAT_ID:
        return
    
    if not await is_chat_admin(bot, message.chat.id, message.from_user.id):
        error_msg = await message.answer("Команда доступна только администраторам.")
        MessageService.schedule_delete(bot, error_msg.chat.id, error_msg.message_id, delay=5)
        return
    
    open_session = await SessionService.get_open_session(CHAT_ID)
    if open_session:
        # Unpin and delete old messages
        if open_session.pinned_message_id:
            await MessageService.unpin_message_safe(bot, CHAT_ID, open_session.pinned_message_id)
        if open_session.list_message_id:
            await MessageService.delete_message_safe(bot, CHAT_ID, open_session.list_message_id)
        
        await SessionService.close_session(open_session.id)
        SessionService.invalidate_cache(CHAT_ID)
    
    session = await SessionService.get_or_create_session(CHAT_ID, force_refresh=True)
    await MessageService.ensure_list_message(bot, session)
    
    confirm_msg = await message.answer("Сессия сброшена.")
    MessageService.schedule_delete(bot, confirm_msg.chat.id, confirm_msg.message_id, delay=3)


@router.message(Command("close"))
@track_duration("close")
@auto_delete_command(delay=3)
async def cmd_close(message: Message, bot: Bot) -> None:
    """Handle /close command (admin only) - close current session."""
    COMMANDS_TOTAL.labels(command="close").inc()
    
    if message.chat.id != CHAT_ID:
        return
    
    if not await is_chat_admin(bot, message.chat.id, message.from_user.id):
        error_msg = await message.answer("Команда доступна только администраторам.")
        MessageService.schedule_delete(bot, error_msg.chat.id, error_msg.message_id, delay=5)
        return
    
    open_session = await SessionService.get_open_session(CHAT_ID)
    if not open_session:
        error_msg = await message.answer("Нет активной сессии.")
        MessageService.schedule_delete(bot, error_msg.chat.id, error_msg.message_id, delay=5)
        return
    
    # Unpin message before closing
    if open_session.pinned_message_id:
        await MessageService.unpin_message_safe(bot, CHAT_ID, open_session.pinned_message_id)
    
    await SessionService.close_session(open_session.id)
    SessionService.invalidate_cache(CHAT_ID)
    
    confirm_msg = await message.answer("Сессия закрыта.")
    MessageService.schedule_delete(bot, confirm_msg.chat.id, confirm_msg.message_id, delay=3)
