import sqlite3
from pathlib import Path
from uuid import uuid4


DB_PATH = Path(__file__).resolve().parent / "chat_memory.db"


def init_chat_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()

def get_or_create_session_id(session_id):
    if session_id:
        return session_id

    return str(uuid4())



def save_message(session_id, role, content):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, role, content)
    )
    conn.commit()
    conn.close()


def get_messages(session_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY id ASC",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    messages = []
    for role, content in rows:
        messages.append({"role": role, "content": content})
    return messages
