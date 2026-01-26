from __future__ import annotations

import asyncio
import logging
import time
from datetime import date

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from metrics import (
    CALLBACKS_TOTAL,
    COMMANDS_TOTAL,
    ERRORS_TOTAL,
    GUESTS_ADDED_TOTAL,
    GUESTS_DELETED_TOTAL,
    PLAYERS_CURRENT,
    REQUEST_DURATION,
    RESPONSES_TOTAL,
)


async def delete_message_later(bot: Bot, chat_id: int, message_id: int, delay: int = 5) -> None:
    """Удаляет сообщение через указанное время (в секундах)."""
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass  # Если не удалось удалить — игнорируем

from config import ADMIN_IDS, CHAT_ID, TIMEZONE
from db import (
    close_session,
    create_session,
    delete_response_by_last_name,
    fetch_responses,
    get_open_session,
    get_session_by_date,
    get_user_last_name,
    set_list_message_id,
    upsert_response,
    upsert_user_last_name,
)
from utils import (
    ALL_STATUSES,
    STATUS_MAYBE,
    STATUS_NO,
    STATUS_YES,
    format_summary_message,
    get_now,
    next_wednesday,
)


router = Router()

# Хранит ID последнего сообщения /start для каждого чата
_last_start_message: dict[int, int] = {}

# Кэш текущей сессии для уменьшения обращений к БД
_session_cache: dict[int, dict] = {}
_session_cache_time: dict[int, float] = {}
_SESSION_CACHE_TTL = 60  # секунд


async def update_player_metrics(session_id: int) -> None:
    """Update player count metrics for the current session."""
    rows = await fetch_responses(session_id)
    counts = {"YES": 0, "MAYBE": 0, "NO": 0}
    for row in rows:
        status = row["status"]
        if status in counts:
            counts[status] += 1
    for status, count in counts.items():
        PLAYERS_CURRENT.labels(status=status).set(count)


class LastNameState(StatesGroup):
    waiting_last_name = State()
    waiting_guest_last_name = State()  # Для добавления гостя
    waiting_delete_last_name = State()  # Для удаления участника


def build_prompt_keyboard() -> InlineKeyboardMarkup:
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


async def ensure_session(chat_id: int, force_refresh: bool = False) -> dict:
    """Получить или создать сессию с кэшированием."""
    now = get_now(TIMEZONE)
    target_date = next_wednesday(now)
    cache_key = chat_id
    
    # Проверяем кэш (если не форсируем обновление)
    if not force_refresh and cache_key in _session_cache:
        cached = _session_cache[cache_key]
        cache_time = _session_cache_time.get(cache_key, 0)
        # Проверяем TTL и актуальность даты
        if (time.time() - cache_time < _SESSION_CACHE_TTL and 
            cached.get("target_date") == target_date.isoformat() and
            not cached.get("is_closed")):
            return cached
    
    open_session = await get_open_session(chat_id)
    if open_session and open_session["is_closed"] == 0:
        if open_session["target_date"] == target_date.isoformat():
            result = dict(open_session)
            _session_cache[cache_key] = result
            _session_cache_time[cache_key] = time.time()
            return result
        await close_session(open_session["id"])
        # Инвалидируем кэш
        _session_cache.pop(cache_key, None)
        
    session = await get_session_by_date(chat_id, target_date)
    if session and session["is_closed"] == 0:
        result = dict(session)
        _session_cache[cache_key] = result
        _session_cache_time[cache_key] = time.time()
        return result
        
    session_id = await create_session(chat_id, target_date)
    result = {
        "id": session_id,
        "chat_id": chat_id,
        "target_date": target_date.isoformat(),
        "is_closed": 0,
        "list_message_id": None,
    }
    _session_cache[cache_key] = result
    _session_cache_time[cache_key] = time.time()
    return result


def invalidate_session_cache(chat_id: int) -> None:
    """Инвалидировать кэш сессии."""
    _session_cache.pop(chat_id, None)
    _session_cache_time.pop(chat_id, None)


async def build_summary_text(session: dict) -> str:
    rows = await fetch_responses(session["id"])
    yes = []
    maybe = []
    no = []
    for row in rows:
        label = f'{row["last_name"]} — {row["status"]}'
        if row["status"] == STATUS_YES:
            yes.append(label)
        elif row["status"] == STATUS_MAYBE:
            maybe.append(label)
        elif row["status"] == STATUS_NO:
            no.append(label)
    target_date = session["target_date"]
    if isinstance(target_date, str):
        target_date = date.fromisoformat(target_date)
    return format_summary_message(target_date=target_date, yes=yes, maybe=maybe, no=no)


async def ensure_list_message(bot: Bot, session: dict) -> None:
    from aiogram.exceptions import TelegramBadRequest
    
    text = await build_summary_text(session)
    list_message_id = session.get("list_message_id")
    if list_message_id:
        try:
            await bot.edit_message_text(
                text=text,
                chat_id=session["chat_id"],
                message_id=list_message_id,
            )
            return
        except TelegramBadRequest as e:
            # Если текст не изменился — это нормально, не создаём новое сообщение
            if "message is not modified" in str(e):
                return
            # Если сообщение удалено или другая ошибка — создаём новое
            logging.warning(f"Не удалось отредактировать сообщение {list_message_id}: {e}")
        except Exception as e:
            logging.warning(f"Не удалось отредактировать сообщение {list_message_id}: {e}")
    # Создаем новое сообщение со списком
    message = await bot.send_message(chat_id=session["chat_id"], text=text)
    await set_list_message_id(session["id"], message.message_id)
    session["list_message_id"] = message.message_id


async def update_summary(bot: Bot, session: dict) -> None:
    # Перезагружаем сессию из базы, чтобы получить актуальный list_message_id
    # Используем get_session_by_date для точного поиска по дате
    target_date = session["target_date"]
    if isinstance(target_date, str):
        target_date = date.fromisoformat(target_date)
    fresh_session = await get_session_by_date(session["chat_id"], target_date)
    if fresh_session and not fresh_session["is_closed"]:
        session = dict(fresh_session)
    await ensure_list_message(bot, session)


async def is_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    member = await bot.get_chat_member(chat_id, user_id)
    return member.status in {"administrator", "creator"}


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    start_time = time.time()
    COMMANDS_TOTAL.labels(command="start").inc()
    
    chat_id = message.chat.id
    
    # Удаляем сообщение с командой через 3 секунды
    asyncio.create_task(delete_message_later(bot, chat_id, message.message_id, delay=3))
    
    # Удаляем ТОЛЬКО предыдущее сообщение от /start (с кнопками)
    old_message_id = _last_start_message.get(chat_id)
    if old_message_id:
        try:
            await bot.delete_message(chat_id, old_message_id)
        except Exception:
            pass
    
    text = (
        "Привет! Нажми кнопку под сообщением бота и выбери статус.\n"
        "Если фамилия еще не сохранена, бот попросит ее один раз."
    )
    new_message = await message.answer(text, reply_markup=build_prompt_keyboard())
    
    # Сохраняем ID нового сообщения (оно будет удалено при следующем вызове /start)
    _last_start_message[chat_id] = new_message.message_id
    
    REQUEST_DURATION.labels(handler="start").observe(time.time() - start_time)


@router.message(Command("status"))
async def cmd_status(message: Message, bot: Bot) -> None:
    start_time = time.time()
    COMMANDS_TOTAL.labels(command="status").inc()
    
    # Удаляем сообщение с командой через 3 секунды
    asyncio.create_task(delete_message_later(bot, message.chat.id, message.message_id, delay=3))
    
    # Получаем свежую сессию из БД (force_refresh=True), чтобы иметь актуальный list_message_id
    invalidate_session_cache(CHAT_ID)
    session = await ensure_session(CHAT_ID, force_refresh=True)
    
    # Также получаем данные напрямую из БД для надёжности
    fresh_session = await get_open_session(CHAT_ID)
    if fresh_session:
        list_message_id = fresh_session["list_message_id"] if "list_message_id" in fresh_session.keys() else None
    else:
        list_message_id = session.get("list_message_id")
    
    # Удаляем ТОЛЬКО предыдущее сообщение со списком (от /status)
    if list_message_id:
        try:
            await bot.delete_message(CHAT_ID, list_message_id)
        except Exception:
            pass
        # Сбрасываем ID, чтобы создать новое сообщение
        await set_list_message_id(session["id"], None)
        session["list_message_id"] = None
        # Обновляем кэш
        invalidate_session_cache(CHAT_ID)
    
    # Создаём новое сообщение со списком
    await ensure_list_message(bot, session)
    
    # Обновляем кэш с новым list_message_id
    invalidate_session_cache(CHAT_ID)
    
    REQUEST_DURATION.labels(handler="status").observe(time.time() - start_time)


@router.message(Command("reset"))
async def cmd_reset(message: Message, bot: Bot) -> None:
    start_time = time.time()
    COMMANDS_TOTAL.labels(command="reset").inc()
    
    # Удаляем сообщение с командой через 3 секунды
    asyncio.create_task(delete_message_later(bot, message.chat.id, message.message_id, delay=3))
    
    if message.chat.id != CHAT_ID:
        return
    if not await is_admin(bot, message.chat.id, message.from_user.id):
        error_msg = await message.answer("Команда доступна только администраторам.")
        asyncio.create_task(delete_message_later(bot, error_msg.chat.id, error_msg.message_id, delay=5))
        return
    open_session = await get_open_session(CHAT_ID)
    if open_session:
        # Открепляем сообщение перед сбросом
        pinned_id = open_session["pinned_message_id"] if "pinned_message_id" in open_session else None
        if pinned_id:
            try:
                await bot.unpin_chat_message(chat_id=CHAT_ID, message_id=pinned_id)
            except Exception:
                pass
        # Удаляем старое сообщение со списком
        list_message_id = open_session["list_message_id"] if "list_message_id" in open_session else None
        if list_message_id:
            try:
                await bot.delete_message(CHAT_ID, list_message_id)
            except Exception:
                pass
        await close_session(open_session["id"])
        # Инвалидируем кэш сессии
        invalidate_session_cache(CHAT_ID)
    session = await ensure_session(CHAT_ID, force_refresh=True)
    await ensure_list_message(bot, session)
    confirm_msg = await message.answer("Сессия сброшена.")
    asyncio.create_task(delete_message_later(bot, confirm_msg.chat.id, confirm_msg.message_id, delay=3))
    
    REQUEST_DURATION.labels(handler="reset").observe(time.time() - start_time)


@router.message(Command("close"))
async def cmd_close(message: Message, bot: Bot) -> None:
    start_time = time.time()
    COMMANDS_TOTAL.labels(command="close").inc()
    
    # Удаляем сообщение с командой через 3 секунды
    asyncio.create_task(delete_message_later(bot, message.chat.id, message.message_id, delay=3))
    
    if message.chat.id != CHAT_ID:
        return
    if not await is_admin(bot, message.chat.id, message.from_user.id):
        error_msg = await message.answer("Команда доступна только администраторам.")
        asyncio.create_task(delete_message_later(bot, error_msg.chat.id, error_msg.message_id, delay=5))
        return
    open_session = await get_open_session(CHAT_ID)
    if not open_session:
        error_msg = await message.answer("Нет активной сессии.")
        asyncio.create_task(delete_message_later(bot, error_msg.chat.id, error_msg.message_id, delay=5))
        return
    # Открепляем сообщение
    pinned_id = open_session["pinned_message_id"] if "pinned_message_id" in open_session else None
    if pinned_id:
        try:
            await bot.unpin_chat_message(chat_id=CHAT_ID, message_id=pinned_id)
        except Exception:
            pass
    await close_session(open_session["id"])
    # Инвалидируем кэш сессии
    invalidate_session_cache(CHAT_ID)
    confirm_msg = await message.answer("Сессия закрыта.")
    asyncio.create_task(delete_message_later(bot, confirm_msg.chat.id, confirm_msg.message_id, delay=3))
    
    REQUEST_DURATION.labels(handler="close").observe(time.time() - start_time)


@router.callback_query(F.data.startswith("status:"))
async def status_callback(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    start_time = time.time()
    CALLBACKS_TOTAL.labels(action="status").inc()
    
    if callback.message.chat.id != CHAT_ID:
        await callback.answer("Этот бот работает в другой группе.")
        return
    status = callback.data.split(":", 1)[1]
    if status not in ALL_STATUSES:
        await callback.answer("Неизвестный статус.")
        return
    user_id = callback.from_user.id
    last_name = await get_user_last_name(user_id)
    if not last_name:
        await state.set_state(LastNameState.waiting_last_name)
        await state.update_data(pending_status=status)
        prompt_msg = await callback.message.answer("Пожалуйста, отправь свою фамилию.")
        # Удаляем сообщение через 15 секунд
        asyncio.create_task(delete_message_later(bot, prompt_msg.chat.id, prompt_msg.message_id, delay=15))
        await callback.answer()
        REQUEST_DURATION.labels(handler="status_callback").observe(time.time() - start_time)
        return
    session = await ensure_session(CHAT_ID)
    if session["is_closed"]:
        await callback.answer("Сессия закрыта.")
        return
    await upsert_response(session["id"], CHAT_ID, user_id, last_name, status)
    RESPONSES_TOTAL.labels(status=status).inc()
    await update_summary(bot, session)
    
    # Update player counts
    await update_player_metrics(session["id"])
    
    await callback.answer()  # Без текста - действие скрыто от других участников
    
    REQUEST_DURATION.labels(handler="status_callback").observe(time.time() - start_time)


@router.callback_query(F.data == "add_guest")
async def add_guest_callback(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Обработчик кнопки 'Добавить участника не из группы'."""
    start_time = time.time()
    CALLBACKS_TOTAL.labels(action="add_guest").inc()
    
    if callback.message.chat.id != CHAT_ID:
        await callback.answer("Этот бот работает в другой группе.")
        return
    
    session = await ensure_session(CHAT_ID)
    if session["is_closed"]:
        await callback.answer("Сессия закрыта.")
        return
    
    # Проверяем, является ли пользователь администратором
    if not await is_admin(bot, callback.message.chat.id, callback.from_user.id):
        await callback.answer("Только администраторы могут добавлять гостей.", show_alert=True)
        return
    
    await state.set_state(LastNameState.waiting_guest_last_name)
    prompt_msg = await callback.message.answer("Введите фамилию участника, который придёт с вами:")
    # Удаляем сообщение через 15 секунд
    asyncio.create_task(delete_message_later(bot, prompt_msg.chat.id, prompt_msg.message_id, delay=15))
    await callback.answer()
    
    REQUEST_DURATION.labels(handler="add_guest").observe(time.time() - start_time)


@router.message(LastNameState.waiting_last_name)
async def last_name_handler(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.chat.id != CHAT_ID:
        return
    if not message.text:
        error_msg = await message.answer("Пожалуйста, отправь текстовое сообщение с фамилией.")
        asyncio.create_task(delete_message_later(bot, error_msg.chat.id, error_msg.message_id, delay=10))
        return
    last_name = message.text.strip()
    if not last_name:
        error_msg = await message.answer("Фамилия не может быть пустой. Попробуй еще раз.")
        asyncio.create_task(delete_message_later(bot, error_msg.chat.id, error_msg.message_id, delay=10))
        return
    data = await state.get_data()
    pending_status = data.get("pending_status")
    if not pending_status:
        error_msg = await message.answer("Не удалось определить статус. Нажми кнопку еще раз.")
        asyncio.create_task(delete_message_later(bot, error_msg.chat.id, error_msg.message_id, delay=10))
        await state.clear()
        return
    await upsert_user_last_name(message.from_user.id, last_name)
    session = await ensure_session(CHAT_ID)
    if session["is_closed"]:
        error_msg = await message.answer("Сессия закрыта.")
        asyncio.create_task(delete_message_later(bot, error_msg.chat.id, error_msg.message_id, delay=10))
        await state.clear()
        return
    await upsert_response(session["id"], CHAT_ID, message.from_user.id, last_name, pending_status)
    await update_summary(bot, session)
    
    # Update player counts
    await update_player_metrics(session["id"])
    
    await state.clear()
    # Удаляем сообщение пользователя с фамилией
    asyncio.create_task(delete_message_later(bot, message.chat.id, message.message_id, delay=3))
    # Отправляем подтверждение и удаляем его через 3 секунды
    confirm_msg = await message.answer("Фамилия сохранена и статус обновлен.")
    asyncio.create_task(delete_message_later(bot, confirm_msg.chat.id, confirm_msg.message_id, delay=3))


@router.message(LastNameState.waiting_guest_last_name)
async def guest_last_name_handler(message: Message, state: FSMContext, bot: Bot) -> None:
    """Обработчик ввода фамилии гостя (не из группы)."""
    if message.chat.id != CHAT_ID:
        return
    if not message.text:
        error_msg = await message.answer("Пожалуйста, отправь текстовое сообщение с фамилией.")
        asyncio.create_task(delete_message_later(bot, error_msg.chat.id, error_msg.message_id, delay=10))
        return
    
    guest_last_name = message.text.strip()
    if not guest_last_name:
        error_msg = await message.answer("Фамилия не может быть пустой. Попробуй еще раз.")
        asyncio.create_task(delete_message_later(bot, error_msg.chat.id, error_msg.message_id, delay=10))
        return
    
    session = await ensure_session(CHAT_ID)
    if session["is_closed"]:
        error_msg = await message.answer("Сессия закрыта.")
        asyncio.create_task(delete_message_later(bot, error_msg.chat.id, error_msg.message_id, delay=10))
        await state.clear()
        return
    
    # Создаём уникальный ID для гостя (отрицательное число на основе хэша)
    guest_user_id = -abs(hash(f"{guest_last_name}_{message.from_user.id}_{session['id']}")) % 2147483647
    
    # Добавляем гостя в список со статусом YES
    await upsert_response(session["id"], CHAT_ID, guest_user_id, guest_last_name, STATUS_YES)
    RESPONSES_TOTAL.labels(status=STATUS_YES).inc()
    GUESTS_ADDED_TOTAL.inc()
    await update_summary(bot, session)
    
    # Update player counts
    await update_player_metrics(session["id"])
    
    await state.clear()
    
    # Удаляем сообщение пользователя с фамилией
    asyncio.create_task(delete_message_later(bot, message.chat.id, message.message_id, delay=3))
    
    # Отправляем подтверждение и удаляем его через 3 секунды
    confirm_msg = await message.answer(f"✅ Участник '{guest_last_name}' добавлен в список.")
    asyncio.create_task(delete_message_later(bot, confirm_msg.chat.id, confirm_msg.message_id, delay=3))


@router.callback_query(F.data == "delete_guest")
async def delete_guest_callback(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Обработчик кнопки 'Удалить участника не из группы'."""
    start_time = time.time()
    CALLBACKS_TOTAL.labels(action="delete_guest").inc()
    
    if callback.message.chat.id != CHAT_ID:
        await callback.answer("Этот бот работает в другой группе.")
        return
    
    session = await ensure_session(CHAT_ID)
    if session["is_closed"]:
        await callback.answer("Сессия закрыта.")
        return
    
    # Проверяем, является ли пользователь администратором
    if not await is_admin(bot, callback.message.chat.id, callback.from_user.id):
        await callback.answer("Только администраторы могут удалять участников.", show_alert=True)
        return
    
    await state.set_state(LastNameState.waiting_delete_last_name)
    prompt_msg = await callback.message.answer("Введите фамилию участника, которого нужно удалить из списка:")
    # Удаляем сообщение через 15 секунд
    asyncio.create_task(delete_message_later(bot, prompt_msg.chat.id, prompt_msg.message_id, delay=15))
    await callback.answer()
    
    REQUEST_DURATION.labels(handler="delete_guest").observe(time.time() - start_time)


@router.message(LastNameState.waiting_delete_last_name)
async def delete_last_name_handler(message: Message, state: FSMContext, bot: Bot) -> None:
    """Обработчик ввода фамилии для удаления участника."""
    if message.chat.id != CHAT_ID:
        return
    if not message.text:
        error_msg = await message.answer("Пожалуйста, отправь текстовое сообщение с фамилией.")
        asyncio.create_task(delete_message_later(bot, error_msg.chat.id, error_msg.message_id, delay=10))
        return
    
    last_name_to_delete = message.text.strip()
    if not last_name_to_delete:
        error_msg = await message.answer("Фамилия не может быть пустой. Попробуй еще раз.")
        asyncio.create_task(delete_message_later(bot, error_msg.chat.id, error_msg.message_id, delay=10))
        return
    
    session = await ensure_session(CHAT_ID)
    if session["is_closed"]:
        error_msg = await message.answer("Сессия закрыта.")
        asyncio.create_task(delete_message_later(bot, error_msg.chat.id, error_msg.message_id, delay=10))
        await state.clear()
        return
    
    # Удаляем участника по фамилии
    deleted = await delete_response_by_last_name(session["id"], last_name_to_delete)
    
    await state.clear()
    
    # Удаляем сообщение пользователя с фамилией
    asyncio.create_task(delete_message_later(bot, message.chat.id, message.message_id, delay=3))
    
    if deleted:
        # Обновляем метрику удалённых гостей
        GUESTS_DELETED_TOTAL.inc()
        
        # Обновляем список
        await update_summary(bot, session)
        
        # Update player counts
        await update_player_metrics(session["id"])
        
        confirm_msg = await message.answer(f"✅ Участник '{last_name_to_delete}' удалён из списка.")
    else:
        confirm_msg = await message.answer(f"❌ Участник с фамилией '{last_name_to_delete}' не найден в списке.")
    
    asyncio.create_task(delete_message_later(bot, confirm_msg.chat.id, confirm_msg.message_id, delay=5))
