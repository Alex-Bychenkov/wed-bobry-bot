#!/usr/bin/env python3
"""Script to import voting data into the database."""

import sqlite3
from datetime import datetime

DB_PATH = "/opt/wed-bobry-bot/data/data.db"
CHAT_ID = -1003689265922
TARGET_DATE = "2026-01-28"

# Voting data
YES_VOTERS = [
    "Черчинцев", "Антонцев", "Пономарь", "Лычагин", "Шевцов",
    "Яворовский", "Полещук", "Ровдо", "Гречаниченко", "Чих", "Тамразов"
]

MAYBE_VOTERS = [
    "Чикинев", "Массовец", "Козлов", "Пикунов", "Морозов", "Помазенков"
]

NO_VOTERS = [
    "Быченков", "Бойцов", "Семенов"
]

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if session already exists
    cursor.execute(
        "SELECT id FROM sessions WHERE chat_id = ? AND target_date = ?",
        (CHAT_ID, TARGET_DATE)
    )
    row = cursor.fetchone()
    
    if row:
        session_id = row[0]
        print(f"✅ Found existing session: id={session_id}")
        # Reopen the session if it was closed
        cursor.execute(
            "UPDATE sessions SET is_closed = 0 WHERE id = ?",
            (session_id,)
        )
    else:
        # Create new session
        cursor.execute(
            "INSERT INTO sessions (chat_id, target_date, is_closed) VALUES (?, ?, 0)",
            (CHAT_ID, TARGET_DATE)
        )
        session_id = cursor.lastrowid
        print(f"✅ Created new session: id={session_id}")
    
    now = datetime.utcnow().isoformat()
    
    # Insert votes using negative user_ids as placeholders
    user_id_counter = -1
    
    def insert_votes(voters, status):
        nonlocal user_id_counter
        for last_name in voters:
            # Check if this person already voted (by last_name)
            cursor.execute(
                "SELECT user_id FROM responses WHERE session_id = ? AND last_name = ?",
                (session_id, last_name)
            )
            existing = cursor.fetchone()
            
            if existing:
                user_id = existing[0]
                cursor.execute(
                    """UPDATE responses SET status = ?, updated_at = ?
                       WHERE session_id = ? AND user_id = ?""",
                    (status, now, session_id, user_id)
                )
                print(f"  Updated: {last_name} -> {status}")
            else:
                cursor.execute(
                    """INSERT INTO responses (session_id, chat_id, user_id, last_name, status, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (session_id, CHAT_ID, user_id_counter, last_name, status, now)
                )
                print(f"  Inserted: {last_name} -> {status} (user_id={user_id_counter})")
                user_id_counter -= 1
    
    print("\n📝 Importing YES votes...")
    insert_votes(YES_VOTERS, "YES")
    
    print("\n📝 Importing MAYBE votes...")
    insert_votes(MAYBE_VOTERS, "MAYBE")
    
    print("\n📝 Importing NO votes...")
    insert_votes(NO_VOTERS, "NO")
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Import complete! Session ID: {session_id}")
    print(f"   Date: {TARGET_DATE}")
    print(f"   YES: {len(YES_VOTERS)}")
    print(f"   MAYBE: {len(MAYBE_VOTERS)}")
    print(f"   NO: {len(NO_VOTERS)}")

if __name__ == "__main__":
    main()
