"""Scheduler for periodic tasks (notifications, session closing)."""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot

from config import CHAT_ID, NOTIFY_TIME, TIMEZONE
from handlers.keyboard import build_prompt_keyboard
from metrics import SCHEDULER_JOBS_TOTAL
from services.message_service import MessageService
from services.session_service import SessionService
from utils import parse_notify_time


async def send_daily_notification(bot: Bot) -> None:
    """Send daily notification to the chat."""
    SCHEDULER_JOBS_TOTAL.labels(job="send_notification").inc()
    
    session = await SessionService.get_or_create_session(CHAT_ID)
    if session.is_closed:
        return
    
    # Delete previous pinned message (with buttons) if exists
    if session.pinned_message_id:
        await MessageService.unpin_message_safe(bot, CHAT_ID, session.pinned_message_id)
        await MessageService.delete_message_safe(bot, CHAT_ID, session.pinned_message_id)
    
    # Delete previous list message if exists
    if session.list_message_id:
        await MessageService.delete_message_safe(bot, CHAT_ID, session.list_message_id)
        await SessionService.update_list_message_id(session.id, None)
        SessionService.invalidate_cache(CHAT_ID)
    
    # Send new message with buttons
    message = await bot.send_message(
        chat_id=CHAT_ID,
        text="Если планируешь посетить игру в среду на «Бобрах», нажми на кнопку",
        reply_markup=build_prompt_keyboard(),
    )
    
    # Pin message
    try:
        await bot.pin_chat_message(
            chat_id=CHAT_ID,
            message_id=message.message_id,
            disable_notification=True
        )
        await SessionService.update_pinned_message_id(session.id, message.message_id)
    except Exception:
        pass  # Ignore if no permissions to pin
    
    await MessageService.ensure_list_message(bot, session)


async def close_current_session(bot: Bot) -> None:
    """Close the current session."""
    SCHEDULER_JOBS_TOTAL.labels(job="close_session").inc()
    
    session = await SessionService.get_open_session(CHAT_ID)
    if not session:
        return
    
    # Unpin message before closing
    if session.pinned_message_id:
        await MessageService.unpin_message_safe(bot, CHAT_ID, session.pinned_message_id)
    
    await SessionService.close_session(session.id)
    SessionService.invalidate_cache(CHAT_ID)
    
    msg = await bot.send_message(chat_id=CHAT_ID, text="Сессия закрыта.")
    # Удаляем сообщение через 3 секунды
    MessageService.schedule_delete(bot, CHAT_ID, msg.message_id, delay=3)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Set up and return the scheduler with all jobs."""
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    notify_time = parse_notify_time(NOTIFY_TIME)
    
    # Notifications on Wednesdays and Saturdays
    notify_trigger = CronTrigger(
        day_of_week="wed,sat",
        hour=notify_time.hour,
        minute=notify_time.minute,
    )
    scheduler.add_job(send_daily_notification, notify_trigger, args=[bot])
    
    # Close session on Wednesday at 23:30
    close_trigger = CronTrigger(day_of_week="wed", hour=23, minute=30)
    scheduler.add_job(close_current_session, close_trigger, args=[bot])
    
    return scheduler
