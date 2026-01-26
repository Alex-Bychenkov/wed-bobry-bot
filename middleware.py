"""Middleware and decorators for handlers."""
from __future__ import annotations

import time
import functools
import logging
from typing import Any, Callable, Awaitable, Optional

from aiogram import Bot
from aiogram.types import Message, CallbackQuery

from config import ADMIN_IDS, CHAT_ID
from metrics import REQUEST_DURATION, ERRORS_TOTAL


async def is_chat_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Check if user is admin in the chat."""
    if user_id in ADMIN_IDS:
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in {"administrator", "creator"}
    except Exception as e:
        logging.warning(f"Failed to check admin status: {e}")
        return False


def track_duration(handler_name: str):
    """Decorator to track handler execution duration."""
    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                REQUEST_DURATION.labels(handler=handler_name).observe(time.time() - start_time)
        return wrapper
    return decorator


def require_target_chat(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Decorator to check if message/callback is from target chat."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        # Find message or callback in args
        message: Optional[Message] = None
        callback: Optional[CallbackQuery] = None
        
        for arg in args:
            if isinstance(arg, Message):
                message = arg
                break
            elif isinstance(arg, CallbackQuery):
                callback = arg
                break
        
        chat_id = None
        if message:
            chat_id = message.chat.id
        elif callback and callback.message:
            chat_id = callback.message.chat.id
        
        if chat_id != CHAT_ID:
            if callback:
                await callback.answer("Этот бот работает в другой группе.")
            return None
        
        return await func(*args, **kwargs)
    return wrapper


def require_admin(error_message: str = "Команда доступна только администраторам."):
    """Decorator to check if user is admin."""
    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            from services.message_service import MessageService
            
            # Find message/callback and bot in args/kwargs
            message: Optional[Message] = None
            callback: Optional[CallbackQuery] = None
            bot: Optional[Bot] = kwargs.get("bot")
            
            for arg in args:
                if isinstance(arg, Message):
                    message = arg
                elif isinstance(arg, CallbackQuery):
                    callback = arg
                elif isinstance(arg, Bot):
                    bot = arg
            
            if not bot:
                return await func(*args, **kwargs)
            
            chat_id = None
            user_id = None
            
            if message:
                chat_id = message.chat.id
                user_id = message.from_user.id if message.from_user else None
            elif callback:
                chat_id = callback.message.chat.id if callback.message else None
                user_id = callback.from_user.id
            
            if not chat_id or not user_id:
                return await func(*args, **kwargs)
            
            if not await is_chat_admin(bot, chat_id, user_id):
                if message:
                    error_msg = await message.answer(error_message)
                    MessageService.schedule_delete(bot, error_msg.chat.id, error_msg.message_id, delay=5)
                elif callback:
                    await callback.answer(error_message, show_alert=True)
                return None
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def auto_delete_command(delay: int = 3):
    """Decorator to auto-delete command message."""
    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            from services.message_service import MessageService
            
            message: Optional[Message] = None
            bot: Optional[Bot] = kwargs.get("bot")
            
            for arg in args:
                if isinstance(arg, Message):
                    message = arg
                elif isinstance(arg, Bot):
                    bot = arg
            
            if message and bot:
                MessageService.schedule_delete(bot, message.chat.id, message.message_id, delay=delay)
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator
