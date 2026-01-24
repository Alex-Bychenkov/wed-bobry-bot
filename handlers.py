from __future__ import annotations

import logging
from datetime import date

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import ADMIN_IDS, CHAT_ID, TIMEZONE
from db import (
    close_session,
    create_session,
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


class LastNameState(StatesGroup):
    waiting_last_name = State()


def build_prompt_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Я буду, запиши меня", callback_data="status:YES"),
        InlineKeyboardButton(text="Пока не определился", callback_data="status:MAYBE"),
        InlineKeyboardButton(text="Не смогу пойти, занят", callback_data="status:NO"),
    )
    builder.adjust(1)
    return builder.as_markup()


async def ensure_session(chat_id: int) -> dict:
    now = get_now(TIMEZONE)
    target_date = next_wednesday(now)
    open_session = await get_open_session(chat_id)
    if open_session and open_session["is_closed"] == 0:
        if open_session["target_date"] == target_date.isoformat():
            return dict(open_session)
        await close_session(open_session["id"])
    session = await get_session_by_date(chat_id, target_date)
    if session and session["is_closed"] == 0:
        return dict(session)
    session_id = await create_session(chat_id, target_date)
    return {
        "id": session_id,
        "chat_id": chat_id,
        "target_date": target_date.isoformat(),
        "is_closed": 0,
        "list_message_id": None,
    }


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
        except Exception as e:
            # Если сообщение не найдено или другое исключение, создаем новое
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
async def cmd_start(message: Message) -> None:
    text = (
        "Привет! Нажми кнопку под сообщением бота и выбери статус.\n"
        "Если фамилия еще не сохранена, бот попросит ее один раз."
    )
    await message.answer(text, reply_markup=build_prompt_keyboard())


@router.message(Command("status"))
async def cmd_status(message: Message, bot: Bot) -> None:
    session = await ensure_session(CHAT_ID)
    summary = await build_summary_text(session)
    await ensure_list_message(bot, session)
    await message.answer(summary, reply_markup=build_prompt_keyboard())


@router.message(Command("reset"))
async def cmd_reset(message: Message, bot: Bot) -> None:
    if message.chat.id != CHAT_ID:
        return
    if not await is_admin(bot, message.chat.id, message.from_user.id):
        await message.answer("Команда доступна только администраторам.")
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
        await close_session(open_session["id"])
    session = await ensure_session(CHAT_ID)
    await ensure_list_message(bot, session)
    await message.answer("Сессия сброшена.")


@router.message(Command("close"))
async def cmd_close(message: Message, bot: Bot) -> None:
    if message.chat.id != CHAT_ID:
        return
    if not await is_admin(bot, message.chat.id, message.from_user.id):
        await message.answer("Команда доступна только администраторам.")
        return
    open_session = await get_open_session(CHAT_ID)
    if not open_session:
        await message.answer("Нет активной сессии.")
        return
    # Открепляем сообщение
    pinned_id = open_session["pinned_message_id"] if "pinned_message_id" in open_session else None
    if pinned_id:
        try:
            await bot.unpin_chat_message(chat_id=CHAT_ID, message_id=pinned_id)
        except Exception:
            pass
    await close_session(open_session["id"])
    await message.answer("Сессия закрыта.")


@router.callback_query(F.data.startswith("status:"))
async def status_callback(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
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
        await callback.message.answer("Пожалуйста, отправь свою фамилию.")
        await callback.answer()
        return
    session = await ensure_session(CHAT_ID)
    if session["is_closed"]:
        await callback.answer("Сессия закрыта.")
        return
    await upsert_response(session["id"], CHAT_ID, user_id, last_name, status)
    await update_summary(bot, session)
    await callback.answer()  # Без текста - действие скрыто от других участников


@router.message(LastNameState.waiting_last_name)
async def last_name_handler(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.chat.id != CHAT_ID:
        return
    last_name = message.text.strip()
    if not last_name:
        await message.answer("Фамилия не может быть пустой. Попробуй еще раз.")
        return
    data = await state.get_data()
    pending_status = data.get("pending_status")
    if not pending_status:
        await message.answer("Не удалось определить статус. Нажми кнопку еще раз.")
        await state.clear()
        return
    await upsert_user_last_name(message.from_user.id, last_name)
    session = await ensure_session(CHAT_ID)
    if session["is_closed"]:
        await message.answer("Сессия закрыта.")
        await state.clear()
        return
    await upsert_response(session["id"], CHAT_ID, message.from_user.id, last_name, pending_status)
    await update_summary(bot, session)
    await state.clear()
    await message.answer("Фамилия сохранена и статус обновлен.")
