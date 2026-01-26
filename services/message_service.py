"""Message management service."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from models import Session
from services.session_service import SessionService


class MessageService:
    """Service for managing bot messages."""
    
    # Track last /start message per chat
    _last_start_messages: dict[int, int] = {}
    
    @classmethod
    async def delete_message_later(
        cls,
        bot: Bot,
        chat_id: int,
        message_id: int,
        delay: int = 5
    ) -> None:
        """Delete a message after specified delay (in seconds)."""
        await asyncio.sleep(delay)
        try:
            await bot.delete_message(chat_id, message_id)
        except Exception:
            pass  # Ignore deletion errors
    
    @classmethod
    def schedule_delete(
        cls,
        bot: Bot,
        chat_id: int,
        message_id: int,
        delay: int = 5
    ) -> None:
        """Schedule message deletion as a background task."""
        asyncio.create_task(cls.delete_message_later(bot, chat_id, message_id, delay))
    
    @classmethod
    async def delete_message_safe(cls, bot: Bot, chat_id: int, message_id: int) -> bool:
        """Safely delete a message, returning True if successful."""
        try:
            await bot.delete_message(chat_id, message_id)
            return True
        except Exception:
            return False
    
    @classmethod
    async def unpin_message_safe(cls, bot: Bot, chat_id: int, message_id: int) -> bool:
        """Safely unpin a message, returning True if successful."""
        try:
            await bot.unpin_chat_message(chat_id=chat_id, message_id=message_id)
            return True
        except Exception:
            return False
    
    @classmethod
    def get_last_start_message(cls, chat_id: int) -> Optional[int]:
        """Get last /start message ID for chat."""
        return cls._last_start_messages.get(chat_id)
    
    @classmethod
    def set_last_start_message(cls, chat_id: int, message_id: int) -> None:
        """Set last /start message ID for chat."""
        cls._last_start_messages[chat_id] = message_id
    
    @classmethod
    async def ensure_list_message(cls, bot: Bot, session: Session) -> None:
        """Ensure list message exists and is up-to-date."""
        text = await SessionService.format_summary_text(session)
        
        if session.list_message_id:
            try:
                await bot.edit_message_text(
                    text=text,
                    chat_id=session.chat_id,
                    message_id=session.list_message_id,
                )
                return
            except TelegramBadRequest as e:
                if "message is not modified" in str(e):
                    return
                logging.warning(f"Failed to edit message {session.list_message_id}: {e}")
            except Exception as e:
                logging.warning(f"Failed to edit message {session.list_message_id}: {e}")
        
        # Create new list message
        message = await bot.send_message(chat_id=session.chat_id, text=text)
        await SessionService.update_list_message_id(session.id, message.message_id)
        session.list_message_id = message.message_id
    
    @classmethod
    async def update_summary(cls, bot: Bot, session: Session) -> None:
        """Update summary message with fresh data from DB."""
        from db import get_session_by_date
        
        # Reload session from DB to get current list_message_id
        fresh_session = await get_session_by_date(session.chat_id, session.target_date)
        if fresh_session and not fresh_session["is_closed"]:
            session = Session.from_row(fresh_session)
        
        await cls.ensure_list_message(bot, session)
