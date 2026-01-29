"""Callback query handlers (button presses)."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from config import CHAT_ID
from db import get_user_info
from handlers.keyboard import build_team_keyboard
from metrics import CALLBACKS_TOTAL, GUESTS_ADDED_TOTAL, PLAYERS_CURRENT, RESPONSES_TOTAL
from middleware import is_chat_admin, track_duration
from models import ResponseStatus
from services.message_service import MessageService
from services.session_service import SessionService

from handlers.states import LastNameState


router = Router()


async def update_player_metrics(session_id: int) -> None:
    """Update Prometheus player count metrics."""
    counts = await SessionService.get_player_counts(session_id)
    for status, count in counts.items():
        PLAYERS_CURRENT.labels(status=status).set(count)


@router.callback_query(F.data.startswith("status:"))
@track_duration("status_callback")
async def status_callback(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Handle status selection callback."""
    CALLBACKS_TOTAL.labels(action="status").inc()
    
    if callback.message.chat.id != CHAT_ID:
        await callback.answer("Этот бот работает в другой группе.")
        return
    
    status_str = callback.data.split(":", 1)[1]
    if status_str not in ResponseStatus.all():
        await callback.answer("Неизвестный статус.")
        return
    
    status = ResponseStatus(status_str)
    user_id = callback.from_user.id
    user_info = await get_user_info(user_id)
    
    # Если нет фамилии - запрашиваем фамилию
    if not user_info:
        await state.set_state(LastNameState.waiting_last_name)
        await state.update_data(pending_status=status.value)
        prompt_msg = await callback.message.answer("Пожалуйста, отправь свою фамилию.")
        MessageService.schedule_delete(bot, prompt_msg.chat.id, prompt_msg.message_id, delay=15)
        await callback.answer()
        return
    
    last_name = user_info["last_name"]
    team = user_info.get("team")
    
    # Если нет команды - запрашиваем команду
    if not team:
        await state.set_state(LastNameState.waiting_team)
        await state.update_data(pending_status=status.value, last_name=last_name)
        prompt_msg = await callback.message.answer("Выбери свою команду:", reply_markup=build_team_keyboard())
        MessageService.schedule_delete(bot, prompt_msg.chat.id, prompt_msg.message_id, delay=15)
        await callback.answer()
        return
    
    session = await SessionService.get_or_create_session(CHAT_ID)
    if session.is_closed:
        await callback.answer("Сессия закрыта.")
        return
    
    await SessionService.add_response(session.id, CHAT_ID, user_id, last_name, status, team)
    RESPONSES_TOTAL.labels(status=status.value).inc()
    
    await MessageService.update_summary(bot, session)
    await update_player_metrics(session.id)
    
    await callback.answer()  # Silent answer


@router.callback_query(F.data == "add_guest")
@track_duration("add_guest")
async def add_guest_callback(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Handle 'Add guest' button press."""
    CALLBACKS_TOTAL.labels(action="add_guest").inc()
    
    if callback.message.chat.id != CHAT_ID:
        await callback.answer("Этот бот работает в другой группе.")
        return
    
    session = await SessionService.get_or_create_session(CHAT_ID)
    if session.is_closed:
        await callback.answer("Сессия закрыта.")
        return
    
    if not await is_chat_admin(bot, callback.message.chat.id, callback.from_user.id):
        await callback.answer("Только администраторы могут добавлять гостей.", show_alert=True)
        return
    
    await state.set_state(LastNameState.waiting_guest_last_name)
    prompt_msg = await callback.message.answer("Введите фамилию участника, который придёт с вами:")
    MessageService.schedule_delete(bot, prompt_msg.chat.id, prompt_msg.message_id, delay=15)
    await callback.answer()


@router.callback_query(F.data == "delete_guest")
@track_duration("delete_guest")
async def delete_guest_callback(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Handle 'Delete guest' button press."""
    CALLBACKS_TOTAL.labels(action="delete_guest").inc()
    
    if callback.message.chat.id != CHAT_ID:
        await callback.answer("Этот бот работает в другой группе.")
        return
    
    session = await SessionService.get_or_create_session(CHAT_ID)
    if session.is_closed:
        await callback.answer("Сессия закрыта.")
        return
    
    if not await is_chat_admin(bot, callback.message.chat.id, callback.from_user.id):
        await callback.answer("Только администраторы могут удалять участников.", show_alert=True)
        return
    
    await state.set_state(LastNameState.waiting_delete_last_name)
    prompt_msg = await callback.message.answer("Введите фамилию участника, которого нужно удалить из списка:")
    MessageService.schedule_delete(bot, prompt_msg.chat.id, prompt_msg.message_id, delay=15)
    await callback.answer()


@router.callback_query(F.data == "change_team")
@track_duration("change_team")
async def change_team_callback(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Handle 'Change team' button press."""
    CALLBACKS_TOTAL.labels(action="change_team").inc()
    
    if callback.message.chat.id != CHAT_ID:
        await callback.answer("Этот бот работает в другой группе.")
        return
    
    session = await SessionService.get_or_create_session(CHAT_ID)
    if session.is_closed:
        await callback.answer("Сессия закрыта.")
        return
    
    if not await is_chat_admin(bot, callback.message.chat.id, callback.from_user.id):
        await callback.answer("Только администраторы могут изменять команду участников.", show_alert=True)
        return
    
    await state.set_state(LastNameState.waiting_change_team_last_name)
    prompt_msg = await callback.message.answer("Введите фамилию участника, которому нужно изменить команду:")
    MessageService.schedule_delete(bot, prompt_msg.chat.id, prompt_msg.message_id, delay=15)
    await callback.answer()
