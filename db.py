from __future__ import annotations

import os
from datetime import datetime, date
from typing import Optional
from contextlib import asynccontextmanager

import aiosqlite


DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "data.db")

# Connection pool для повышения производительности
_db_pool: Optional[aiosqlite.Connection] = None


async def get_db() -> aiosqlite.Connection:
    """Получить подключение к БД с оптимизированными настройками для минимального потребления памяти."""
    global _db_pool
    if _db_pool is None:
        _db_pool = await aiosqlite.connect(DB_PATH)
        _db_pool.row_factory = aiosqlite.Row
        
        # === Оптимизации SQLite для минимального потребления памяти ===
        
        # WAL режим для лучшей производительности при конкурентном доступе
        await _db_pool.execute("PRAGMA journal_mode=WAL")
        
        # NORMAL синхронизация - баланс между скоростью и надёжностью
        await _db_pool.execute("PRAGMA synchronous=NORMAL")
        
        # Ограничиваем кэш страниц (по умолчанию 2000 страниц = ~8MB)
        # Устанавливаем 500 страниц = ~2MB
        await _db_pool.execute("PRAGMA cache_size=-2000")  # -2000 = 2MB
        
        # Ограничиваем размер temp_store в памяти
        await _db_pool.execute("PRAGMA temp_store=MEMORY")
        
        # Отключаем mmap для экономии виртуальной памяти
        await _db_pool.execute("PRAGMA mmap_size=0")
        
        # Быстрый checkpoint для WAL
        await _db_pool.execute("PRAGMA wal_autocheckpoint=100")
        
        await _db_pool.commit()
    return _db_pool


@asynccontextmanager
async def db_connection():
    """Context manager для работы с БД."""
    db = await get_db()
    try:
        yield db
    finally:
        pass  # Не закрываем соединение, используем pool


async def init_db() -> None:
    # Создаем директорию для базы данных, если её нет
    os.makedirs(DB_DIR, exist_ok=True)
    async with db_connection() as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                last_name TEXT NOT NULL,
                team TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        # Индекс для быстрого поиска по user_id
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id)"
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
        # Индексы для быстрого поиска сессий
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_chat_id ON sessions(chat_id, is_closed)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_date ON sessions(chat_id, target_date)"
        )
        
        # Migration: add pinned_message_id if missing
        cursor = await db.execute("PRAGMA table_info(sessions)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "pinned_message_id" not in columns:
            await db.execute("ALTER TABLE sessions ADD COLUMN pinned_message_id INTEGER")
        
        # Migration: add team field to users table
        cursor = await db.execute("PRAGMA table_info(users)")
        user_columns = [row[1] for row in await cursor.fetchall()]
        if "team" not in user_columns:
            await db.execute("ALTER TABLE users ADD COLUMN team TEXT")
        
        # Migration: add team field to responses table
        cursor = await db.execute("PRAGMA table_info(responses)")
        response_columns = [row[1] for row in await cursor.fetchall()]
        if "team" not in response_columns:
            await db.execute("ALTER TABLE responses ADD COLUMN team TEXT")
            
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS responses (
                session_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                last_name TEXT NOT NULL,
                status TEXT NOT NULL,
                team TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (session_id, user_id)
            )
            """
        )
        # Индекс для быстрого поиска ответов по сессии
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_responses_session ON responses(session_id)"
        )
        
        await db.commit()


# Простой кэш информации о пользователях в памяти для уменьшения обращений к БД
# Максимум 100 записей, этого достаточно для небольшого бота
_user_cache: dict[int, dict] = {}
_CACHE_MAX_SIZE = 100


async def get_user_info(user_id: int) -> dict | None:
    """Получить информацию о пользователе (фамилия и команда)."""
    # Сначала проверяем кэш
    if user_id in _user_cache:
        return _user_cache[user_id]
    
    async with db_connection() as db:
        cursor = await db.execute(
            "SELECT last_name, team FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
    
    if row:
        # Добавляем в кэш
        if len(_user_cache) >= _CACHE_MAX_SIZE:
            # Удаляем первый элемент (FIFO)
            _user_cache.pop(next(iter(_user_cache)))
        user_info = {"last_name": row["last_name"], "team": row["team"]}
        _user_cache[user_id] = user_info
        return user_info
    return None


async def get_user_last_name(user_id: int) -> str | None:
    """Получить фамилию пользователя (для обратной совместимости)."""
    info = await get_user_info(user_id)
    return info["last_name"] if info else None


async def upsert_user_info(user_id: int, last_name: str, team: str) -> None:
    """Сохранить информацию о пользователе (фамилия и команда)."""
    async with db_connection() as db:
        await db.execute(
            """
            INSERT INTO users (user_id, last_name, team, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                last_name = excluded.last_name,
                team = excluded.team,
                updated_at = excluded.updated_at
            """,
            (user_id, last_name, team, datetime.utcnow().isoformat()),
        )
        await db.commit()
    
    # Обновляем кэш
    if len(_user_cache) >= _CACHE_MAX_SIZE:
        _user_cache.pop(next(iter(_user_cache)))
    _user_cache[user_id] = {"last_name": last_name, "team": team}


async def upsert_user_last_name(user_id: int, last_name: str) -> None:
    """Сохранить фамилию пользователя (для обратной совместимости)."""
    # Получаем текущую команду, если есть
    info = await get_user_info(user_id)
    team = info["team"] if info else None
    
    async with db_connection() as db:
        await db.execute(
            """
            INSERT INTO users (user_id, last_name, team, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                last_name = excluded.last_name,
                updated_at = excluded.updated_at
            """,
            (user_id, last_name, team, datetime.utcnow().isoformat()),
        )
        await db.commit()
    
    # Обновляем кэш
    if len(_user_cache) >= _CACHE_MAX_SIZE:
        _user_cache.pop(next(iter(_user_cache)))
    _user_cache[user_id] = {"last_name": last_name, "team": team}


async def get_open_session(chat_id: int) -> aiosqlite.Row | None:
    async with db_connection() as db:
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
    async with db_connection() as db:
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
    async with db_connection() as db:
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
    async with db_connection() as db:
        await db.execute(
            "UPDATE sessions SET is_closed = 1 WHERE id = ?",
            (session_id,),
        )
        await db.commit()


async def set_list_message_id(session_id: int, message_id: int | None) -> None:
    async with db_connection() as db:
        await db.execute(
            "UPDATE sessions SET list_message_id = ? WHERE id = ?",
            (message_id, session_id),
        )
        await db.commit()


async def set_pinned_message_id(session_id: int, message_id: int) -> None:
    async with db_connection() as db:
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
    team: str | None = None,
) -> None:
    async with db_connection() as db:
        await db.execute(
            """
            INSERT INTO responses (session_id, chat_id, user_id, last_name, status, team, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, user_id) DO UPDATE SET
                last_name = excluded.last_name,
                status = excluded.status,
                team = excluded.team,
                updated_at = excluded.updated_at
            """,
            (session_id, chat_id, user_id, last_name, status, team, datetime.utcnow().isoformat()),
        )
        await db.commit()


async def fetch_responses(session_id: int) -> list[aiosqlite.Row]:
    async with db_connection() as db:
        cursor = await db.execute(
            """
            SELECT user_id, last_name, status, team, updated_at
            FROM responses
            WHERE session_id = ?
            ORDER BY updated_at ASC
            """,
            (session_id,),
        )
        rows = await cursor.fetchall()
        await cursor.close()
    return list(rows)


async def delete_response_by_last_name(session_id: int, last_name: str) -> bool:
    """Удаляет участника из сессии по фамилии.
    
    Возвращает True если участник найден и удалён, False если не найден.
    """
    async with db_connection() as db:
        # Проверяем, есть ли такой участник
        cursor = await db.execute(
            """
            SELECT user_id FROM responses
            WHERE session_id = ? AND LOWER(last_name) = LOWER(?)
            """,
            (session_id, last_name),
        )
        row = await cursor.fetchone()
        await cursor.close()
        
        if not row:
            return False
        
        # Удаляем участника
        await db.execute(
            """
            DELETE FROM responses
            WHERE session_id = ? AND LOWER(last_name) = LOWER(?)
            """,
            (session_id, last_name),
        )
        await db.commit()
        return True


async def update_response_team_by_last_name(session_id: int, last_name: str, new_team: str) -> bool:
    """Обновляет команду участника по фамилии.
    
    Возвращает True если участник найден и обновлён, False если не найден.
    """
    async with db_connection() as db:
        # Проверяем, есть ли такой участник
        cursor = await db.execute(
            """
            SELECT user_id FROM responses
            WHERE session_id = ? AND LOWER(last_name) = LOWER(?)
            """,
            (session_id, last_name),
        )
        row = await cursor.fetchone()
        await cursor.close()
        
        if not row:
            return False
        
        # Обновляем команду участника
        await db.execute(
            """
            UPDATE responses
            SET team = ?, updated_at = ?
            WHERE session_id = ? AND LOWER(last_name) = LOWER(?)
            """,
            (new_team, datetime.utcnow().isoformat(), session_id, last_name),
        )
        await db.commit()
        return True
