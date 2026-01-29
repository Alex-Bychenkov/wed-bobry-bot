"""Session management service."""
from __future__ import annotations

import time
from datetime import date
from typing import Optional

from config import CHAT_ID, TIMEZONE
from db import (
    close_session,
    create_session,
    fetch_responses,
    get_open_session,
    get_session_by_date,
    get_user_info,
    get_user_last_name,
    set_list_message_id,
    set_pinned_message_id,
    upsert_response,
    upsert_user_info,
    upsert_user_last_name,
    delete_response_by_last_name,
    update_response_team_by_last_name,
)
from models import PlayerInfo, Response, ResponseStatus, Session, SessionSummary
from utils import format_summary_message, get_now, next_wednesday


class SessionService:
    """Service for managing sessions and responses."""
    
    # Session cache
    _cache: dict[int, Session] = {}
    _cache_time: dict[int, float] = {}
    _CACHE_TTL = 60  # seconds
    
    @classmethod
    async def get_or_create_session(cls, chat_id: int, force_refresh: bool = False) -> Session:
        """Get current session or create a new one."""
        now = get_now(TIMEZONE)
        target_date = next_wednesday(now)
        
        # Check cache
        if not force_refresh and chat_id in cls._cache:
            cached = cls._cache[chat_id]
            cache_time = cls._cache_time.get(chat_id, 0)
            if (time.time() - cache_time < cls._CACHE_TTL and 
                cached.target_date == target_date and
                not cached.is_closed):
                return cached
        
        # Get from DB
        open_session = await get_open_session(chat_id)
        if open_session and open_session["is_closed"] == 0:
            if open_session["target_date"] == target_date.isoformat():
                session = Session.from_row(open_session)
                cls._update_cache(chat_id, session)
                return session
            await close_session(open_session["id"])
            cls.invalidate_cache(chat_id)
        
        # Check for existing session with same date
        existing = await get_session_by_date(chat_id, target_date)
        if existing and existing["is_closed"] == 0:
            session = Session.from_row(existing)
            cls._update_cache(chat_id, session)
            return session
        
        # Create new session
        session_id = await create_session(chat_id, target_date)
        session = Session(
            id=session_id,
            chat_id=chat_id,
            target_date=target_date,
            is_closed=False
        )
        cls._update_cache(chat_id, session)
        return session
    
    @classmethod
    def _update_cache(cls, chat_id: int, session: Session) -> None:
        """Update session cache."""
        cls._cache[chat_id] = session
        cls._cache_time[chat_id] = time.time()
    
    @classmethod
    def invalidate_cache(cls, chat_id: int) -> None:
        """Invalidate session cache."""
        cls._cache.pop(chat_id, None)
        cls._cache_time.pop(chat_id, None)
    
    @classmethod
    async def close_session(cls, session_id: int) -> None:
        """Close a session."""
        await close_session(session_id)
    
    @classmethod
    async def get_open_session(cls, chat_id: int) -> Optional[Session]:
        """Get open session for chat."""
        row = await get_open_session(chat_id)
        if row:
            return Session.from_row(row)
        return None
    
    @classmethod
    async def update_list_message_id(cls, session_id: int, message_id: Optional[int]) -> None:
        """Update list message ID for session."""
        await set_list_message_id(session_id, message_id)
    
    @classmethod
    async def update_pinned_message_id(cls, session_id: int, message_id: int) -> None:
        """Update pinned message ID for session."""
        await set_pinned_message_id(session_id, message_id)
    
    @classmethod
    async def add_response(
        cls,
        session_id: int,
        chat_id: int,
        user_id: int,
        last_name: str,
        status: ResponseStatus,
        team: str | None = None,
        is_goalie: bool = False
    ) -> None:
        """Add or update player response."""
        await upsert_response(session_id, chat_id, user_id, last_name, status.value, team, is_goalie)
    
    @classmethod
    async def delete_response(cls, session_id: int, last_name: str) -> bool:
        """Delete response by last name."""
        return await delete_response_by_last_name(session_id, last_name)
    
    @classmethod
    async def update_team(cls, session_id: int, last_name: str, new_team: str) -> bool:
        """Update team for a response by last name."""
        return await update_response_team_by_last_name(session_id, last_name, new_team)
    
    @classmethod
    async def get_responses(cls, session_id: int) -> list[Response]:
        """Get all responses for session."""
        rows = await fetch_responses(session_id)
        return [Response.from_row(row) for row in rows]
    
    @classmethod
    async def get_session_summary(cls, session: Session) -> SessionSummary:
        """Get session summary with categorized responses."""
        responses = await cls.get_responses(session.id)
        
        summary = SessionSummary(session=session)
        for resp in responses:
            player = PlayerInfo(
                last_name=resp.last_name,
                team=resp.team,
                status=resp.status.value,
                is_goalie=resp.is_goalie
            )
            if resp.status == ResponseStatus.YES:
                summary.yes.append(player)
            elif resp.status == ResponseStatus.MAYBE:
                summary.maybe.append(player)
            elif resp.status == ResponseStatus.NO:
                summary.no.append(player)
        
        return summary
    
    @classmethod
    async def format_summary_text(cls, session: Session) -> str:
        """Format session summary as text."""
        summary = await cls.get_session_summary(session)
        return format_summary_message(
            target_date=session.target_date,
            yes=summary.yes,
            maybe=summary.maybe,
            no=summary.no
        )
    
    @classmethod
    async def get_player_counts(cls, session_id: int) -> dict[str, int]:
        """Get player counts by status."""
        responses = await cls.get_responses(session_id)
        counts = {"YES": 0, "MAYBE": 0, "NO": 0}
        for resp in responses:
            if resp.status.value in counts:
                counts[resp.status.value] += 1
        return counts


class UserService:
    """Service for user management."""
    
    @classmethod
    async def get_last_name(cls, user_id: int) -> Optional[str]:
        """Get user's last name."""
        return await get_user_last_name(user_id)
    
    @classmethod
    async def get_info(cls, user_id: int) -> Optional[dict]:
        """Get user's info (last_name and team)."""
        return await get_user_info(user_id)
    
    @classmethod
    async def save_last_name(cls, user_id: int, last_name: str) -> None:
        """Save user's last name."""
        await upsert_user_last_name(user_id, last_name)
    
    @classmethod
    async def save_user_info(cls, user_id: int, last_name: str, team: str, is_goalie: bool = False) -> None:
        """Save user's info (last_name, team, is_goalie)."""
        await upsert_user_info(user_id, last_name, team, is_goalie)
