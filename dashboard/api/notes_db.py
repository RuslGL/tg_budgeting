import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "/data/dashboard.db")


def init_notes_table() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                text TEXT NOT NULL,
                type TEXT NOT NULL,
                calendar_event_id TEXT NOT NULL DEFAULT '',
                event_date TEXT NOT NULL DEFAULT ''
            )
        """)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(notes)").fetchall()]
        if "calendar_event_id" not in cols:
            conn.execute("ALTER TABLE notes ADD COLUMN calendar_event_id TEXT NOT NULL DEFAULT ''")
        if "event_date" not in cols:
            conn.execute("ALTER TABLE notes ADD COLUMN event_date TEXT NOT NULL DEFAULT ''")
        if "event_time" not in cols:
            conn.execute("ALTER TABLE notes ADD COLUMN event_time TEXT NOT NULL DEFAULT ''")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS note_categories (
                name TEXT PRIMARY KEY,
                sort_order INTEGER NOT NULL
            )
        """)
        conn.commit()


def get_notes(category: str | None, date_from: str | None, date_to: str | None) -> list[dict]:
    query = "SELECT id, date, text, type, event_date, event_time FROM notes WHERE 1=1"
    params: list = []
    if category:
        query += " AND type = ?"
        params.append(category)
    if date_from:
        query += " AND date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND date <= ?"
        params.append(date_to)
    query += (
        " ORDER BY date DESC,"
        " CASE WHEN event_time = '' THEN '99:99' ELSE event_time END ASC,"
        " rowid DESC"
    )
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(query, params).fetchall()
    return [{"id": r[0], "date": r[1], "text": r[2], "type": r[3], "event_date": r[4] or "", "event_time": r[5] or ""} for r in rows]


def get_note_categories() -> list[str]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT name FROM note_categories ORDER BY sort_order"
        ).fetchall()
    return [r[0] for r in rows]


def insert_note_local(note_id: str, date: str, text: str, category: str, event_date: str = "", event_time: str = "") -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO notes (id, date, text, type, calendar_event_id, event_date, event_time) VALUES (?, ?, ?, ?, '', ?, ?)",
            (note_id, date, text, category, event_date, event_time),
        )
        conn.commit()


def update_note_local(note_id: str, text: str, category: str, calendar_event_id: str = "", event_date: str = "", event_time: str = "") -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE notes SET text = ?, type = ?, calendar_event_id = ?, event_date = ?, event_time = ? WHERE id = ?",
            (text, category, calendar_event_id, event_date, event_time, note_id),
        )
        conn.commit()


def delete_note_local(note_id: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()
