import json
import logging
import os
import sqlite3
import uuid

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
CALENDAR_CATEGORIES = [c.strip().lower() for c in os.getenv("CALENDAR_CATEGORIES", "Календарь").split(",") if c.strip()]

logger = logging.getLogger(__name__)


def _calendar_event_body(event_date: str, text: str, event_time: str = "") -> dict:
    time_str = event_time or "09:00"
    h, m = map(int, time_str.split(":"))
    end_m = m + 30
    end_h = (h + end_m // 60) % 24
    end_m = end_m % 60
    end_str = f"{end_h:02d}:{end_m:02d}"
    summary = f"{time_str} — {text[:97]}" if event_time else text[:100]
    return {
        "summary": summary,
        "start": {"dateTime": f"{event_date}T{time_str}:00", "timeZone": "Europe/Moscow"},
        "end": {"dateTime": f"{event_date}T{end_str}:00", "timeZone": "Europe/Moscow"},
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 0}],
        },
    }


def _create_calendar_event(event_date: str, text: str, event_time: str = "") -> str:
    creds = Credentials.from_service_account_info(GOOGLE_CREDENTIALS, scopes=SCOPES)
    service = build("calendar", "v3", credentials=creds)
    event = _calendar_event_body(event_date, text, event_time)
    result = service.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=event).execute()
    return result["id"]


def _update_calendar_event(event_id: str, event_date: str, text: str, event_time: str = "") -> None:
    creds = Credentials.from_service_account_info(GOOGLE_CREDENTIALS, scopes=SCOPES)
    service = build("calendar", "v3", credentials=creds)
    event = _calendar_event_body(event_date, text, event_time)
    service.events().update(calendarId=GOOGLE_CALENDAR_ID, eventId=event_id, body=event).execute()


def _delete_calendar_event(event_id: str) -> None:
    creds = Credentials.from_service_account_info(GOOGLE_CREDENTIALS, scopes=SCOPES)
    service = build("calendar", "v3", credentials=creds)
    service.events().delete(calendarId=GOOGLE_CALENDAR_ID, eventId=event_id).execute()


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
        event_time = row[6].strip() if len(row) > 6 else ""
        if not note_id or not date:
            continue
        records.append((note_id, date, text, type_, calendar_event_id, event_date, event_time))

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM notes")
        conn.executemany(
            "INSERT OR REPLACE INTO notes (id, date, text, type, calendar_event_id, event_date, event_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
            records,
        )
        conn.commit()

    logger.debug("Notes sync: inserted %d rows", len(records))
    return len(records)


def sync_note_categories() -> int:
    creds = Credentials.from_service_account_info(GOOGLE_CREDENTIALS, scopes=SCOPES)
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SPREADSHEET_ID).worksheet("notes_categories")
    names = [row[0].strip() for row in ws.get_all_values() if row and row[0].strip()]

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM note_categories")
        conn.executemany(
            "INSERT INTO note_categories (name, sort_order) VALUES (?, ?)",
            [(name, i) for i, name in enumerate(names)],
        )
        conn.commit()
    return len(names)


def create_note_in_sheets(date: str, text: str, category: str, event_date: str = "", event_time: str = "") -> str:
    note_id = str(uuid.uuid4())
    calendar_event_id = ""
    if event_date and category.strip().lower() in CALENDAR_CATEGORIES and GOOGLE_CALENDAR_ID:
        try:
            calendar_event_id = _create_calendar_event(event_date, text, event_time)
        except Exception as e:
            logger.error("Calendar event creation failed: %s", e)

    creds = Credentials.from_service_account_info(GOOGLE_CREDENTIALS, scopes=SCOPES)
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SPREADSHEET_ID).worksheet("notes")
    ws.append_row([note_id, date, text, category, calendar_event_id, event_date, event_time])
    return note_id


def delete_note_from_sheets(note_id: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT calendar_event_id FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
    calendar_event_id = row[0] if row else ""

    if calendar_event_id and GOOGLE_CALENDAR_ID:
        try:
            _delete_calendar_event(calendar_event_id)
        except Exception as e:
            logger.error("Calendar delete error: %s", e)

    creds = Credentials.from_service_account_info(GOOGLE_CREDENTIALS, scopes=SCOPES)
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SPREADSHEET_ID).worksheet("notes")
    cell = ws.find(note_id)
    if cell:
        ws.delete_rows(cell.row)


def update_note_in_sheets(note_id: str, text: str, category: str, event_date: str = "", event_time: str = "") -> str:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT calendar_event_id FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
    old_calendar_event_id = row[0] if row and row[0] else ""

    wants_calendar = bool(event_date) and category.strip().lower() in CALENDAR_CATEGORIES and bool(GOOGLE_CALENDAR_ID)
    calendar_event_id = old_calendar_event_id

    try:
        if old_calendar_event_id and wants_calendar:
            _update_calendar_event(old_calendar_event_id, event_date, text, event_time)
        elif old_calendar_event_id and not wants_calendar:
            _delete_calendar_event(old_calendar_event_id)
            calendar_event_id = ""
        elif not old_calendar_event_id and wants_calendar:
            calendar_event_id = _create_calendar_event(event_date, text, event_time)
    except Exception as e:
        logger.error("Calendar update error: %s", e)

    creds = Credentials.from_service_account_info(GOOGLE_CREDENTIALS, scopes=SCOPES)
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SPREADSHEET_ID).worksheet("notes")
    cell = ws.find(note_id)
    if cell:
        ws.update(f"C{cell.row}:G{cell.row}", [[text, category, calendar_event_id, event_date, event_time]])
    return calendar_event_id
