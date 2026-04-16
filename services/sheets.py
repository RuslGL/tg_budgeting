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
_projects_cache: Optional[list[str]] = None
_projects_cached_at: float = 0
CACHE_TTL = 60  # 1 minute


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


def invalidate_cache() -> None:
    global _categories_cache, _categories_cached_at, _projects_cache, _projects_cached_at
    _categories_cache = None
    _categories_cached_at = 0
    _projects_cache = None
    _projects_cached_at = 0


def get_categories() -> list[str]:
    _ensure_cache()
    return _categories_cache


def get_projects() -> list[str]:
    global _projects_cache, _projects_cached_at
    if _projects_cache is not None and time.time() - _projects_cached_at < CACHE_TTL:
        return _projects_cache
    try:
        client = _get_client()
        ws = client.open_by_key(config.SPREADSHEET_ID).worksheet("business_type")
        rows = ws.get_all_values()
        _projects_cache = [r[0].strip() for r in rows if r and r[0].strip()]
        _projects_cached_at = time.time()
    except Exception as e:
        logger.warning("get_projects failed: %s", e)
        _projects_cache = _projects_cache or []
    return _projects_cache


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
        "start": {"dateTime": f"{event_date}T07:00:00", "timeZone": "Europe/Moscow"},
        "end": {"dateTime": f"{event_date}T07:30:00", "timeZone": "Europe/Moscow"},
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 0}],
        },
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
    ws.append_row([note_id, date, text, category, calendar_event_id, event_date or ""])
    return note_id


def delete_note(note_id: str) -> None:
    client = _get_client()
    sheet = client.open_by_key(config.SPREADSHEET_ID)
    ws = sheet.worksheet("notes")
    cell = ws.find(note_id)
    if cell:
        ws.delete_rows(cell.row)


def append_transaction(date: str, category: str, amount: float, original_text: str, author: str = "", company: str = "", project: str = "unknown") -> None:
    type_ = get_category_type(category)
    client = _get_client()
    sheet = client.open_by_key(config.SPREADSHEET_ID)
    ws = sheet.worksheet("raw")
    ws.append_row([date, category, type_, amount, original_text, author, company, project])


# --- Calorie tracking ---

def append_meal(date: str, time_str: str, food_name: str, grams: float,
                calories: float, protein: float, fat: float, carbs: float) -> None:
    meal_id = str(uuid.uuid4())
    client = _get_client()
    ws = client.open_by_key(config.SPREADSHEET_ID).worksheet("cal_meals")
    ws.append_row([meal_id, date, time_str, food_name, int(grams), int(calories), float(round(protein, 1)), float(round(fat, 1)), float(round(carbs, 1))],
                  value_input_option="RAW")


def get_recent_meals(limit: int = 15) -> list[dict]:
    client = _get_client()
    ws = client.open_by_key(config.SPREADSHEET_ID).worksheet("cal_meals")
    rows = ws.get_all_values()
    # Skip header row, take last N rows
    data = [r for r in rows[1:] if len(r) >= 6 and r[0].strip()]
    recent = data[-limit:][::-1]
    result = []
    for row in recent:
        try:
            result.append({
                "id": row[0],
                "date": row[1],
                "time": row[2],
                "food_name": row[3],
                "grams": float(row[4]),
                "calories": float(row[5]),
            })
        except (ValueError, IndexError):
            continue
    return result


def get_last_meal(date: str) -> dict | None:
    client = _get_client()
    ws = client.open_by_key(config.SPREADSHEET_ID).worksheet("cal_meals")
    rows = ws.get_all_values()
    for row in reversed(rows):
        if len(row) >= 6 and row[1] == date and row[0].strip():
            try:
                return {
                    "id": row[0],
                    "date": row[1],
                    "time": row[2],
                    "food_name": row[3],
                    "grams": float(row[4]),
                    "calories": float(row[5]),
                }
            except (ValueError, IndexError):
                continue
    return None


def delete_cal_meal(meal_id: str) -> None:
    client = _get_client()
    ws = client.open_by_key(config.SPREADSHEET_ID).worksheet("cal_meals")
    cell = ws.find(meal_id)
    if cell:
        ws.delete_rows(cell.row)


def log_weight(date: str, weight: float) -> None:
    client = _get_client()
    ws = client.open_by_key(config.SPREADSHEET_ID).worksheet("cal_weight")
    rows = ws.get_all_values()
    for i, row in enumerate(rows, start=1):
        if row and row[0] == date:
            ws.update(f"A{i}:B{i}", [[date, weight]])
            return
    ws.append_row([date, weight])


def get_cal_limits() -> dict:
    client = _get_client()
    ws = client.open_by_key(config.SPREADSHEET_ID).worksheet("cal_limits")
    rows = ws.get_all_values()
    return {row[0]: row[1] for row in rows if len(row) >= 2 and row[0]}


def set_cal_limit(field: str, value: str) -> None:
    client = _get_client()
    ws = client.open_by_key(config.SPREADSHEET_ID).worksheet("cal_limits")
    rows = ws.get_all_values()
    for i, row in enumerate(rows, start=1):
        if row and row[0] == field:
            ws.update(f"A{i}:B{i}", [[field, value]])
            return
    ws.append_row([field, value])


def get_today_cal_total(date: str) -> dict:
    client = _get_client()
    ws = client.open_by_key(config.SPREADSHEET_ID).worksheet("cal_meals")
    rows = ws.get_all_values()
    totals = {"calories": 0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    for row in rows[1:]:  # skip header
        if not row or row[1] != date:  # col 1 = date (after id)
            continue
        try:
            totals["calories"] += int(float(row[5]))
            totals["protein"] += float(row[6])
            totals["fat"] += float(row[7])
            totals["carbs"] += float(row[8])
        except (IndexError, ValueError):
            pass
    return totals


