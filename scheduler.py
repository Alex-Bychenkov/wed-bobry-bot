from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot

from config import CHAT_ID, NOTIFY_TIME, TIMEZONE
from db import close_session, get_open_session, set_pinned_message_id
from handlers import build_prompt_keyboard, ensure_list_message, ensure_session, invalidate_session_cache
from utils import parse_notify_time
from metrics import SCHEDULER_JOBS_TOTAL


async def send_daily_notification(bot: Bot) -> None:
    SCHEDULER_JOBS_TOTAL.labels(job="send_notification").inc()
    session = await ensure_session(CHAT_ID)
    if session["is_closed"]:
        return
    message = await bot.send_message(
        chat_id=CHAT_ID,
        text=(
            "Если планируешь посетить игру в среду на «Бобрах», нажми на кнопку"
        ),
        reply_markup=build_prompt_keyboard(),
    )
    # Закрепляем сообщение
    try:
        await bot.pin_chat_message(chat_id=CHAT_ID, message_id=message.message_id, disable_notification=True)
        await set_pinned_message_id(session["id"], message.message_id)
    except Exception:
        pass  # Если нет прав на закрепление — игнорируем
    await ensure_list_message(bot, session)


async def close_current_session(bot: Bot) -> None:
    SCHEDULER_JOBS_TOTAL.labels(job="close_session").inc()
    session = await get_open_session(CHAT_ID)
    if not session:
        return
    # Открепляем сообщение перед закрытием
    pinned_id = session["pinned_message_id"] if "pinned_message_id" in session else None
    if pinned_id:
        try:
            await bot.unpin_chat_message(chat_id=CHAT_ID, message_id=pinned_id)
        except Exception:
            pass  # Если нет прав или сообщение уже откреплено — игнорируем
    await close_session(session["id"])
    # Инвалидируем кэш сессии
    invalidate_session_cache(CHAT_ID)
    await bot.send_message(chat_id=CHAT_ID, text="Сессия закрыта.")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    notify_time = parse_notify_time(NOTIFY_TIME)
    # Уведомления только по средам и субботам в 11:00
    notify_trigger = CronTrigger(
        day_of_week="wed,sat",
        hour=notify_time.hour,
        minute=notify_time.minute,
    )
    scheduler.add_job(send_daily_notification, notify_trigger, args=[bot])
    # Закрытие сессии в среду в 23:30
    close_trigger = CronTrigger(day_of_week="wed", hour=23, minute=30)
    scheduler.add_job(close_current_session, close_trigger, args=[bot])
    return scheduler
