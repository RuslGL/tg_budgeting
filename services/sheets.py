import logging
import time
import uuid
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

import config

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar",
]

_client: Optional[gspread.Client] = None
_categories_cache: Optional[list[str]] = None
_category_types: dict[str, str] = {}
_categories_cached_at: float = 0
_note_categories_cache: Optional[list[str]] = None
_note_categories_cached_at: float = 0
CACHE_TTL = 600  # 10 minutes


def _get_client() -> gspread.Client:
    global _client
    if _client is None:
        creds = Credentials.from_service_account_info(config.GOOGLE_CREDENTIALS, scopes=SCOPES)
        _client = gspread.authorize(creds)
    return _client


def _refresh_categories() -> None:
    global _categories_cache, _category_types, _categories_cached_at
    client = _get_client()
    sheet = client.open_by_key(config.SPREADSHEET_ID)
    ws = sheet.worksheet(config.CATEGORIES_SHEET)
    rows = ws.get_all_values()
    # First row is header: categorie, type
    _categories_cache = []
    _category_types = {}
    for row in rows[1:]:
        if row and row[0].strip():
            name = row[0].strip()
            type_ = row[1].strip() if len(row) > 1 else ""
            _categories_cache.append(name)
            _category_types[name] = type_
    _categories_cached_at = time.time()


def _ensure_cache() -> None:
    if _categories_cache is None or time.time() - _categories_cached_at >= CACHE_TTL:
        _refresh_categories()


def get_categories() -> list[str]:
    _ensure_cache()
    return _categories_cache


def get_category_type(category: str) -> str:
    _ensure_cache()
    return _category_types.get(category, "")


def get_note_categories() -> list[str]:
    global _note_categories_cache, _note_categories_cached_at
    if _note_categories_cache is None or time.time() - _note_categories_cached_at >= CACHE_TTL:
        client = _get_client()
        sheet = client.open_by_key(config.SPREADSHEET_ID)
        ws = sheet.worksheet("notes_categories")
        rows = ws.get_all_values()
        _note_categories_cache = [row[0].strip() for row in rows if row and row[0].strip()]
        _note_categories_cached_at = time.time()
    return _note_categories_cache


def _create_calendar_event(event_date: str, text: str) -> str:
    logger.info("Creating calendar event: date=%s text=%s calendarId=%s", event_date, text[:50], config.GOOGLE_CALENDAR_ID)
    creds = Credentials.from_service_account_info(config.GOOGLE_CREDENTIALS, scopes=SCOPES)
    service = build("calendar", "v3", credentials=creds)
    event = {
        "summary": text[:100],
        "start": {"date": event_date},
        "end": {"date": event_date},
    }
    result = service.events().insert(calendarId=config.GOOGLE_CALENDAR_ID, body=event).execute()
    logger.info("Calendar event created: id=%s", result.get("id"))
    return result["id"]


def append_note(date: str, text: str, category: str, event_date: Optional[str] = None) -> str:
    note_id = str(uuid.uuid4())
    calendar_event_id = ""
    logger.info(
        "append_note: category=%s event_date=%s CALENDAR_CATEGORIES=%s GOOGLE_CALENDAR_ID=%s",
        category, event_date, config.CALENDAR_CATEGORIES, bool(config.GOOGLE_CALENDAR_ID),
    )
    if (
        event_date
        and category in config.CALENDAR_CATEGORIES
        and config.GOOGLE_CALENDAR_ID
    ):
        try:
            calendar_event_id = _create_calendar_event(event_date, text)
        except Exception as e:
            logger.error("Calendar event creation failed: %s", e)
    client = _get_client()
    sheet = client.open_by_key(config.SPREADSHEET_ID)
    ws = sheet.worksheet("notes")
    ws.append_row([note_id, date, text, category, calendar_event_id])
    return note_id


def delete_note(note_id: str) -> None:
    client = _get_client()
    sheet = client.open_by_key(config.SPREADSHEET_ID)
    ws = sheet.worksheet("notes")
    cell = ws.find(note_id)
    if cell:
        ws.delete_rows(cell.row)


def append_transaction(date: str, category: str, amount: float, original_text: str, author: str = "", company: str = "") -> None:
    type_ = get_category_type(category)
    client = _get_client()
    sheet = client.open_by_key(config.SPREADSHEET_ID)
    ws = sheet.worksheet("raw")
    ws.append_row([date, category, type_, amount, original_text, author, company])
