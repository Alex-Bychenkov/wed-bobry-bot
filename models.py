"""Data models for the bot."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional


class ResponseStatus(str, Enum):
    """Player response status."""
    YES = "YES"
    MAYBE = "MAYBE"
    NO = "NO"
    
    @classmethod
    def all(cls) -> tuple[str, ...]:
        return tuple(s.value for s in cls)


@dataclass
class User:
    """User model."""
    user_id: int
    last_name: str
    team: Optional[str] = None
    is_goalie: bool = False
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    @classmethod
    def from_row(cls, row) -> User:
        return cls(
            user_id=row["user_id"],
            last_name=row["last_name"],
            team=row["team"] if "team" in row.keys() else None,
            is_goalie=bool(row["is_goalie"]) if "is_goalie" in row.keys() and row["is_goalie"] else False,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else datetime.utcnow()
        )


@dataclass
class Session:
    """Session model."""
    id: int
    chat_id: int
    target_date: date
    is_closed: bool = False
    list_message_id: Optional[int] = None
    pinned_message_id: Optional[int] = None
    
    @classmethod
    def from_row(cls, row) -> Session:
        target_date = row["target_date"]
        if isinstance(target_date, str):
            target_date = date.fromisoformat(target_date)
        return cls(
            id=row["id"],
            chat_id=row["chat_id"],
            target_date=target_date,
            is_closed=bool(row["is_closed"]),
            list_message_id=row["list_message_id"] if "list_message_id" in row.keys() else None,
            pinned_message_id=row["pinned_message_id"] if "pinned_message_id" in row.keys() else None
        )
    
    def to_dict(self) -> dict:
        """Convert to dict for backward compatibility."""
        return {
            "id": self.id,
            "chat_id": self.chat_id,
            "target_date": self.target_date.isoformat(),
            "is_closed": int(self.is_closed),
            "list_message_id": self.list_message_id,
            "pinned_message_id": self.pinned_message_id
        }


@dataclass
class Response:
    """Player response model."""
    session_id: int
    chat_id: int
    user_id: int
    last_name: str
    status: ResponseStatus
    team: Optional[str] = None
    is_goalie: bool = False
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    @classmethod
    def from_row(cls, row) -> Response:
        return cls(
            session_id=row["session_id"] if "session_id" in row.keys() else 0,
            chat_id=row["chat_id"] if "chat_id" in row.keys() else 0,
            user_id=row["user_id"],
            last_name=row["last_name"],
            status=ResponseStatus(row["status"]),
            team=row["team"] if "team" in row.keys() else None,
            is_goalie=bool(row["is_goalie"]) if "is_goalie" in row.keys() and row["is_goalie"] else False,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else datetime.utcnow()
        )


@dataclass
class PlayerInfo:
    """Player info for summary lists."""
    last_name: str
    team: Optional[str] = None
    status: Optional[str] = None
    is_goalie: bool = False


@dataclass
class SessionSummary:
    """Session summary with player lists."""
    session: Session
    yes: list[PlayerInfo] = field(default_factory=list)
    maybe: list[PlayerInfo] = field(default_factory=list)
    no: list[PlayerInfo] = field(default_factory=list)
    
    @property
    def yes_count(self) -> int:
        return len(self.yes)
    
    @property
    def maybe_count(self) -> int:
        return len(self.maybe)
    
    @property
    def no_count(self) -> int:
        return len(self.no)
