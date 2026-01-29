"""FSM state handlers (last name input, guest management)."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import CHAT_ID
from handlers.keyboard import build_team_keyboard
from metrics import CALLBACKS_TOTAL, GUESTS_ADDED_TOTAL, GUESTS_DELETED_TOTAL, PLAYERS_CURRENT, RESPONSES_TOTAL, TEAM_CHANGES_TOTAL, TEAM_SELECTIONS_TOTAL
from middleware import track_duration
from models import ResponseStatus
from services.message_service import MessageService
from services.session_service import SessionService, UserService
from utils import format_team_with_emoji


router = Router()


class LastNameState(StatesGroup):
    """FSM states for last name input."""
    waiting_last_name = State()
    waiting_team = State()  # Для выбора команды после фамилии
    waiting_guest_last_name = State()
    waiting_guest_team = State()  # Для выбора команды гостя
    waiting_delete_last_name = State()
    waiting_change_team_last_name = State()  # Для изменения команды участника
    waiting_change_team_select = State()  # Для выбора новой команды


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
    
    # Delete user message
    MessageService.schedule_delete(bot, message.chat.id, message.message_id, delay=3)
    
    # Сохраняем фамилию в state и переходим к выбору команды
    await state.set_state(LastNameState.waiting_team)
    await state.update_data(last_name=last_name)
    
    prompt_msg = await message.answer("Выбери свою команду:", reply_markup=build_team_keyboard())
    MessageService.schedule_delete(bot, prompt_msg.chat.id, prompt_msg.message_id, delay=15)


@router.callback_query(F.data.startswith("team:"), LastNameState.waiting_team)
@track_duration("team_callback")
async def team_callback(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Обработчик выбора команды для пользователя."""
    CALLBACKS_TOTAL.labels(action="team_select").inc()
    
    if callback.message.chat.id != CHAT_ID:
        await callback.answer("Этот бот работает в другой группе.")
        return
    
    team = callback.data.split(":", 1)[1]
    data = await state.get_data()
    last_name = data.get("last_name")
    pending_status = data.get("pending_status")
    
    if not last_name or not pending_status:
        await callback.answer("Произошла ошибка. Попробуй ещё раз.")
        await state.clear()
        return
    
    user_id = callback.from_user.id
    
    # Сохраняем пользователя с фамилией и командой
    await UserService.save_user_info(user_id, last_name, team)
    
    session = await SessionService.get_or_create_session(CHAT_ID)
    if session.is_closed:
        await callback.answer("Сессия закрыта.")
        await state.clear()
        return
    
    status = ResponseStatus(pending_status)
    await SessionService.add_response(session.id, CHAT_ID, user_id, last_name, status, team)
    RESPONSES_TOTAL.labels(status=pending_status).inc()
    TEAM_SELECTIONS_TOTAL.labels(team=team).inc()
    await MessageService.update_summary(bot, session)
    await update_player_metrics(session.id)
    
    await state.clear()
    
    # Удаляем сообщение с кнопками выбора команды
    await MessageService.delete_message_safe(bot, callback.message.chat.id, callback.message.message_id)
    
    # Отправляем подтверждение и удаляем его через 3 секунды
    team_display = format_team_with_emoji(team)
    confirm_msg = await callback.message.answer(f"✅ {last_name} ({team_display}) добавлен в список.")
    MessageService.schedule_delete(bot, confirm_msg.chat.id, confirm_msg.message_id, delay=3)
    
    await callback.answer()


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
        MessageService.schedule_delete(bot, error_msg.chat.id, error_msg.message_id, delay=3)
        await state.clear()
        return
    
    # Delete user message
    MessageService.schedule_delete(bot, message.chat.id, message.message_id, delay=3)
    
    # Сохраняем данные гостя в state и переходим к выбору команды
    await state.set_state(LastNameState.waiting_guest_team)
    await state.update_data(
        guest_last_name=guest_last_name,
        session_id=session.id,
        added_by_user_id=message.from_user.id
    )
    
    prompt_msg = await message.answer("Выбери команду для гостя:", reply_markup=build_team_keyboard())
    MessageService.schedule_delete(bot, prompt_msg.chat.id, prompt_msg.message_id, delay=15)


@router.callback_query(F.data.startswith("team:"), LastNameState.waiting_guest_team)
@track_duration("guest_team_callback")
async def guest_team_callback(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Обработчик выбора команды для гостя."""
    CALLBACKS_TOTAL.labels(action="guest_team_select").inc()
    
    if callback.message.chat.id != CHAT_ID:
        await callback.answer("Этот бот работает в другой группе.")
        return
    
    team = callback.data.split(":", 1)[1]
    data = await state.get_data()
    guest_last_name = data.get("guest_last_name")
    session_id = data.get("session_id")
    added_by_user_id = data.get("added_by_user_id")
    
    if not guest_last_name or not session_id:
        await callback.answer("Произошла ошибка. Попробуй ещё раз.")
        await state.clear()
        return
    
    # Создаём уникальный ID для гостя
    guest_user_id = -abs(hash(f"{guest_last_name}_{added_by_user_id}_{session_id}")) % 2147483647
    
    # Добавляем гостя в список со статусом YES и командой
    await SessionService.add_response(session_id, CHAT_ID, guest_user_id, guest_last_name, ResponseStatus.YES, team)
    RESPONSES_TOTAL.labels(status=ResponseStatus.YES.value).inc()
    GUESTS_ADDED_TOTAL.inc()
    TEAM_SELECTIONS_TOTAL.labels(team=team).inc()
    
    session = await SessionService.get_or_create_session(CHAT_ID)
    await MessageService.update_summary(bot, session)
    await update_player_metrics(session_id)
    
    await state.clear()
    
    # Удаляем сообщение с кнопками выбора команды
    await MessageService.delete_message_safe(bot, callback.message.chat.id, callback.message.message_id)
    
    # Отправляем подтверждение
    team_display = format_team_with_emoji(team)
    confirm_msg = await callback.message.answer(f"✅ Гость '{guest_last_name}' ({team_display}) добавлен в список.")
    MessageService.schedule_delete(bot, confirm_msg.chat.id, confirm_msg.message_id, delay=3)
    
    await callback.answer()


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


@router.message(LastNameState.waiting_change_team_last_name)
async def change_team_last_name_handler(message: Message, state: FSMContext, bot: Bot) -> None:
    """Обработчик ввода фамилии для изменения команды."""
    if message.chat.id != CHAT_ID:
        return
    
    if not message.text:
        error_msg = await message.answer("Пожалуйста, отправь текстовое сообщение с фамилией.")
        MessageService.schedule_delete(bot, error_msg.chat.id, error_msg.message_id, delay=10)
        return
    
    last_name_to_change = message.text.strip()
    if not last_name_to_change:
        error_msg = await message.answer("Фамилия не может быть пустой. Попробуй еще раз.")
        MessageService.schedule_delete(bot, error_msg.chat.id, error_msg.message_id, delay=10)
        return
    
    session = await SessionService.get_or_create_session(CHAT_ID)
    if session.is_closed:
        error_msg = await message.answer("Сессия закрыта.")
        MessageService.schedule_delete(bot, error_msg.chat.id, error_msg.message_id, delay=3)
        await state.clear()
        return
    
    # Удаляем сообщение пользователя с фамилией
    MessageService.schedule_delete(bot, message.chat.id, message.message_id, delay=3)
    
    # Сохраняем фамилию в state и переходим к выбору команды
    await state.set_state(LastNameState.waiting_change_team_select)
    await state.update_data(
        change_last_name=last_name_to_change,
        session_id=session.id
    )
    
    prompt_msg = await message.answer(f"Выбери новую команду для '{last_name_to_change}':", reply_markup=build_team_keyboard())
    MessageService.schedule_delete(bot, prompt_msg.chat.id, prompt_msg.message_id, delay=15)


@router.callback_query(F.data.startswith("team:"), LastNameState.waiting_change_team_select)
@track_duration("change_team_select")
async def change_team_select_callback(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Обработчик выбора новой команды для участника."""
    CALLBACKS_TOTAL.labels(action="change_team_select").inc()
    
    if callback.message.chat.id != CHAT_ID:
        await callback.answer("Этот бот работает в другой группе.")
        return
    
    new_team = callback.data.split(":", 1)[1]
    data = await state.get_data()
    change_last_name = data.get("change_last_name")
    session_id = data.get("session_id")
    
    if not change_last_name or not session_id:
        await callback.answer("Произошла ошибка. Попробуй ещё раз.")
        await state.clear()
        return
    
    # Обновляем команду участника
    updated = await SessionService.update_team(session_id, change_last_name, new_team)
    
    if updated:
        TEAM_CHANGES_TOTAL.labels(team=new_team).inc()
    
    await state.clear()
    
    # Удаляем сообщение с кнопками выбора команды
    await MessageService.delete_message_safe(bot, callback.message.chat.id, callback.message.message_id)
    
    if updated:
        session = await SessionService.get_or_create_session(CHAT_ID)
        await MessageService.update_summary(bot, session)
        await update_player_metrics(session_id)
        
        team_display = format_team_with_emoji(new_team)
        confirm_msg = await callback.message.answer(f"✅ Команда участника '{change_last_name}' изменена на {team_display}.")
    else:
        confirm_msg = await callback.message.answer(f"❌ Участник с фамилией '{change_last_name}' не найден в списке.")
    
    MessageService.schedule_delete(bot, confirm_msg.chat.id, confirm_msg.message_id, delay=5)
    
    await callback.answer()
