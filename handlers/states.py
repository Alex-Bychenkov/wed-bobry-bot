"""FSM state handlers (last name input, guest management)."""
from __future__ import annotations

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from config import CHAT_ID
from metrics import GUESTS_ADDED_TOTAL, GUESTS_DELETED_TOTAL, PLAYERS_CURRENT, RESPONSES_TOTAL
from models import ResponseStatus
from services.message_service import MessageService
from services.session_service import SessionService, UserService


router = Router()


class LastNameState(StatesGroup):
    """FSM states for last name input."""
    waiting_last_name = State()
    waiting_guest_last_name = State()
    waiting_delete_last_name = State()


async def update_player_metrics(session_id: int) -> None:
    """Update Prometheus player count metrics."""
    counts = await SessionService.get_player_counts(session_id)
    for status, count in counts.items():
        PLAYERS_CURRENT.labels(status=status).set(count)


@router.message(LastNameState.waiting_last_name)
async def last_name_handler(message: Message, state: FSMContext, bot: Bot) -> None:
    """Handle user's last name input."""
    if message.chat.id != CHAT_ID:
        return
    
    if not message.text:
        error_msg = await message.answer("Пожалуйста, отправь текстовое сообщение с фамилией.")
        MessageService.schedule_delete(bot, error_msg.chat.id, error_msg.message_id, delay=10)
        return
    
    last_name = message.text.strip()
    if not last_name:
        error_msg = await message.answer("Фамилия не может быть пустой. Попробуй еще раз.")
        MessageService.schedule_delete(bot, error_msg.chat.id, error_msg.message_id, delay=10)
        return
    
    data = await state.get_data()
    pending_status = data.get("pending_status")
    if not pending_status:
        error_msg = await message.answer("Не удалось определить статус. Нажми кнопку еще раз.")
        MessageService.schedule_delete(bot, error_msg.chat.id, error_msg.message_id, delay=10)
        await state.clear()
        return
    
    # Save user's last name
    await UserService.save_last_name(message.from_user.id, last_name)
    
    session = await SessionService.get_or_create_session(CHAT_ID)
    if session.is_closed:
        error_msg = await message.answer("Сессия закрыта.")
        MessageService.schedule_delete(bot, error_msg.chat.id, error_msg.message_id, delay=10)
        await state.clear()
        return
    
    status = ResponseStatus(pending_status)
    await SessionService.add_response(session.id, CHAT_ID, message.from_user.id, last_name, status)
    await MessageService.update_summary(bot, session)
    await update_player_metrics(session.id)
    
    await state.clear()
    
    # Delete user message
    MessageService.schedule_delete(bot, message.chat.id, message.message_id, delay=3)
    
    # Send confirmation
    confirm_msg = await message.answer("Фамилия сохранена и статус обновлен.")
    MessageService.schedule_delete(bot, confirm_msg.chat.id, confirm_msg.message_id, delay=3)


@router.message(LastNameState.waiting_guest_last_name)
async def guest_last_name_handler(message: Message, state: FSMContext, bot: Bot) -> None:
    """Handle guest last name input."""
    if message.chat.id != CHAT_ID:
        return
    
    if not message.text:
        error_msg = await message.answer("Пожалуйста, отправь текстовое сообщение с фамилией.")
        MessageService.schedule_delete(bot, error_msg.chat.id, error_msg.message_id, delay=10)
        return
    
    guest_last_name = message.text.strip()
    if not guest_last_name:
        error_msg = await message.answer("Фамилия не может быть пустой. Попробуй еще раз.")
        MessageService.schedule_delete(bot, error_msg.chat.id, error_msg.message_id, delay=10)
        return
    
    session = await SessionService.get_or_create_session(CHAT_ID)
    if session.is_closed:
        error_msg = await message.answer("Сессия закрыта.")
        MessageService.schedule_delete(bot, error_msg.chat.id, error_msg.message_id, delay=10)
        await state.clear()
        return
    
    # Generate unique guest ID
    guest_user_id = -abs(hash(f"{guest_last_name}_{message.from_user.id}_{session.id}")) % 2147483647
    
    # Add guest with YES status
    await SessionService.add_response(session.id, CHAT_ID, guest_user_id, guest_last_name, ResponseStatus.YES)
    RESPONSES_TOTAL.labels(status=ResponseStatus.YES.value).inc()
    GUESTS_ADDED_TOTAL.inc()
    
    await MessageService.update_summary(bot, session)
    await update_player_metrics(session.id)
    
    await state.clear()
    
    # Delete user message
    MessageService.schedule_delete(bot, message.chat.id, message.message_id, delay=3)
    
    # Send confirmation
    confirm_msg = await message.answer(f"✅ Участник '{guest_last_name}' добавлен в список.")
    MessageService.schedule_delete(bot, confirm_msg.chat.id, confirm_msg.message_id, delay=3)


@router.message(LastNameState.waiting_delete_last_name)
async def delete_last_name_handler(message: Message, state: FSMContext, bot: Bot) -> None:
    """Handle last name input for deletion."""
    if message.chat.id != CHAT_ID:
        return
    
    if not message.text:
        error_msg = await message.answer("Пожалуйста, отправь текстовое сообщение с фамилией.")
        MessageService.schedule_delete(bot, error_msg.chat.id, error_msg.message_id, delay=10)
        return
    
    last_name_to_delete = message.text.strip()
    if not last_name_to_delete:
        error_msg = await message.answer("Фамилия не может быть пустой. Попробуй еще раз.")
        MessageService.schedule_delete(bot, error_msg.chat.id, error_msg.message_id, delay=10)
        return
    
    session = await SessionService.get_or_create_session(CHAT_ID)
    if session.is_closed:
        error_msg = await message.answer("Сессия закрыта.")
        MessageService.schedule_delete(bot, error_msg.chat.id, error_msg.message_id, delay=10)
        await state.clear()
        return
    
    # Delete response by last name
    deleted = await SessionService.delete_response(session.id, last_name_to_delete)
    
    await state.clear()
    
    # Delete user message
    MessageService.schedule_delete(bot, message.chat.id, message.message_id, delay=3)
    
    if deleted:
        GUESTS_DELETED_TOTAL.inc()
        await MessageService.update_summary(bot, session)
        await update_player_metrics(session.id)
        confirm_msg = await message.answer(f"✅ Участник '{last_name_to_delete}' удалён из списка.")
    else:
        confirm_msg = await message.answer(f"❌ Участник с фамилией '{last_name_to_delete}' не найден в списке.")
    
    MessageService.schedule_delete(bot, confirm_msg.chat.id, confirm_msg.message_id, delay=5)
