from __future__ import annotations

from datetime import datetime, date

import aiosqlite


DB_PATH = "data.db"


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                last_name TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                target_date TEXT NOT NULL,
                is_closed INTEGER NOT NULL DEFAULT 0,
                list_message_id INTEGER,
                pinned_message_id INTEGER
            )
            """
        )
        # Migration: add pinned_message_id if missing
        cursor = await db.execute("PRAGMA table_info(sessions)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "pinned_message_id" not in columns:
            await db.execute("ALTER TABLE sessions ADD COLUMN pinned_message_id INTEGER")
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS responses (
                session_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                last_name TEXT NOT NULL,
                status TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (session_id, user_id)
            )
            """
        )
        await db.commit()


async def get_user_last_name(user_id: int) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT last_name FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
    return row["last_name"] if row else None


async def upsert_user_last_name(user_id: int, last_name: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, last_name, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                last_name = excluded.last_name,
                updated_at = excluded.updated_at
            """,
            (user_id, last_name, datetime.utcnow().isoformat()),
        )
        await db.commit()


async def get_open_session(chat_id: int) -> aiosqlite.Row | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM sessions
            WHERE chat_id = ? AND is_closed = 0
            ORDER BY id DESC
            LIMIT 1
            """,
            (chat_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
    return row


async def get_session_by_date(chat_id: int, target_date: date) -> aiosqlite.Row | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM sessions
            WHERE chat_id = ? AND target_date = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (chat_id, target_date.isoformat()),
        )
        row = await cursor.fetchone()
        await cursor.close()
    return row


async def create_session(chat_id: int, target_date: date) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO sessions (chat_id, target_date, is_closed)
            VALUES (?, ?, 0)
            """,
            (chat_id, target_date.isoformat()),
        )
        await db.commit()
        return cursor.lastrowid


async def close_session(session_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE sessions SET is_closed = 1 WHERE id = ?",
            (session_id,),
        )
        await db.commit()


async def set_list_message_id(session_id: int, message_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE sessions SET list_message_id = ? WHERE id = ?",
            (message_id, session_id),
        )
        await db.commit()


async def set_pinned_message_id(session_id: int, message_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE sessions SET pinned_message_id = ? WHERE id = ?",
            (message_id, session_id),
        )
        await db.commit()


async def upsert_response(
    session_id: int,
    chat_id: int,
    user_id: int,
    last_name: str,
    status: str,
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO responses (session_id, chat_id, user_id, last_name, status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, user_id) DO UPDATE SET
                last_name = excluded.last_name,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (session_id, chat_id, user_id, last_name, status, datetime.utcnow().isoformat()),
        )
        await db.commit()


async def fetch_responses(session_id: int) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT user_id, last_name, status, updated_at
            FROM responses
            WHERE session_id = ?
            ORDER BY updated_at ASC
            """,
            (session_id,),
        )
        rows = await cursor.fetchall()
        await cursor.close()
    return list(rows)
