import json
import logging
import os
import sqlite3

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar",
]
DB_PATH = os.getenv("DB_PATH", "/data/dashboard.db")
SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
GOOGLE_CREDENTIALS = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "")

logger = logging.getLogger(__name__)


def run_notes_sync() -> int:
    creds = Credentials.from_service_account_info(GOOGLE_CREDENTIALS, scopes=SCOPES)
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SPREADSHEET_ID).worksheet("notes")
    rows = ws.get_all_values()

    records = []
    for row in rows:
        if len(row) < 4 or not row[0].strip():
            continue
        note_id = row[0].strip()
        date = row[1].strip()
        text = row[2].strip()
        type_ = row[3].strip()
        calendar_event_id = row[4].strip() if len(row) > 4 else ""
        event_date = row[5].strip() if len(row) > 5 else ""
        if not note_id or not date:
            continue
        records.append((note_id, date, text, type_, calendar_event_id, event_date))

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM notes")
        conn.executemany(
            "INSERT OR REPLACE INTO notes (id, date, text, type, calendar_event_id, event_date) VALUES (?, ?, ?, ?, ?, ?)",
            records,
        )
        conn.commit()

    logger.debug("Notes sync: inserted %d rows", len(records))
    return len(records)


def delete_note_from_sheets(note_id: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT calendar_event_id FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
    calendar_event_id = row[0] if row else ""

    if calendar_event_id and GOOGLE_CALENDAR_ID:
        try:
            creds = Credentials.from_service_account_info(GOOGLE_CREDENTIALS, scopes=SCOPES)
            service = build("calendar", "v3", credentials=creds)
            service.events().delete(calendarId=GOOGLE_CALENDAR_ID, eventId=calendar_event_id).execute()
        except Exception as e:
            logger.error("Calendar delete error: %s", e)

    creds = Credentials.from_service_account_info(GOOGLE_CREDENTIALS, scopes=SCOPES)
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SPREADSHEET_ID).worksheet("notes")
    cell = ws.find(note_id)
    if cell:
        ws.delete_rows(cell.row)
