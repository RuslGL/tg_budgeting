import json
import logging
import os
import sqlite3
from datetime import date

import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
DB_PATH = os.getenv("DB_PATH", "/data/dashboard.db")
SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
GOOGLE_CREDENTIALS = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])

logger = logging.getLogger(__name__)


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                category TEXT NOT NULL,
                type TEXT NOT NULL,
                amount REAL NOT NULL,
                author TEXT NOT NULL DEFAULT ''
            )
        """)
        try:
            conn.execute("ALTER TABLE transactions ADD COLUMN author TEXT NOT NULL DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # column already exists
        conn.commit()


def _prev_month_start() -> str:
    today = date.today()
    if today.month == 1:
        return date(today.year - 1, 12, 1).isoformat()
    return date(today.year, today.month - 1, 1).isoformat()


def run_sync() -> int:
    creds = Credentials.from_service_account_info(GOOGLE_CREDENTIALS, scopes=SCOPES)
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SPREADSHEET_ID).worksheet("raw")
    rows = ws.get_all_values()[1:]  # skip header row

    cutoff = _prev_month_start()

    fresh = []
    for row in rows:
        if len(row) < 4:
            continue
        d, category, type_, amount_str = row[0], row[1], row[2], row[3]
        author = row[5] if len(row) > 5 else ""
        if not d or d < cutoff:
            continue
        try:
            amount = float(amount_str)
        except ValueError:
            continue
        fresh.append((d, category, type_, amount, author))

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM transactions WHERE date >= ?", (cutoff,))
        conn.executemany(
            "INSERT INTO transactions (date, category, type, amount, author) VALUES (?, ?, ?, ?, ?)",
            fresh,
        )
        conn.commit()

    logger.info("Sync: deleted rows >= %s, inserted %d rows", cutoff, len(fresh))
    return len(fresh)
