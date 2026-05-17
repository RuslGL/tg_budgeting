import logging
import re
from datetime import date
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

import config

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

SHEET_NAME = "friends"

# Column indices (0-based)
COL_NAME = 0        # A — Имя
COL_BIRTHDAY = 1    # B — ДР
COL_COMMENT = 2     # C — Комментарий
COL_PLANNED = 3     # D — Запланировано
COL_DATE = 4        # E — Дата события
COL_RESULT = 5      # F — Итог

HEADERS = ["Имя", "ДР", "Комментарий", "Запланировано", "Дата события", "Итог"]

# Colors for column A (relationship status)
COLOR_RED = {"red": 1.0, "green": 0.0, "blue": 0.0}        # нет контакта
COLOR_YELLOW = {"red": 1.0, "green": 1.0, "blue": 0.0}     # увял
COLOR_GREEN = {"red": 0.0, "green": 1.0, "blue": 0.0}      # периодический

# Colors for column D (meeting type)
COLOR_BLUE = {"red": 0.678, "green": 0.847, "blue": 0.902}  # живая встреча (#ADD8E6)
COLOR_FUCHSIA = {"red": 1.0, "green": 0.467, "blue": 1.0}   # онлайн (#FF77FF)

COLOR_NONE = {"red": 1.0, "green": 1.0, "blue": 1.0}        # сброс цвета

_gc: Optional[gspread.Client] = None
_creds: Optional[Credentials] = None


def _get_creds() -> Credentials:
    global _creds
    if _creds is None:
        _creds = Credentials.from_service_account_info(config.GOOGLE_CREDENTIALS, scopes=SCOPES)
    return _creds


def _get_client() -> gspread.Client:
    global _gc
    if _gc is None:
        _gc = gspread.authorize(_get_creds())
    return _gc


def _get_sheet() -> gspread.Worksheet:
    client = _get_client()
    spreadsheet = client.open_by_key(config.ASSISTANT_SPREADSHEET_ID)
    return spreadsheet.worksheet(SHEET_NAME)


def _get_sheet_id() -> int:
    client = _get_client()
    spreadsheet = client.open_by_key(config.ASSISTANT_SPREADSHEET_ID)
    ws = spreadsheet.worksheet(SHEET_NAME)
    return ws.id


def update_headers() -> None:
    ws = _get_sheet()
    ws.update("A1:F1", [HEADERS])


def get_all_contacts() -> list[dict]:
    ws = _get_sheet()
    rows = ws.get_all_values()
    contacts = []
    for i, row in enumerate(rows[1:], start=2):  # skip header, row index from 2
        while len(row) < 6:
            row.append("")
        if row[COL_NAME].strip():
            contacts.append({
                "row": i,
                "name": row[COL_NAME].strip(),
                "birthday": row[COL_BIRTHDAY].strip(),
                "comment": row[COL_COMMENT].strip(),
                "planned": row[COL_PLANNED].strip(),
                "event_date": row[COL_DATE].strip(),
                "result": row[COL_RESULT].strip(),
            })
    return contacts


def find_contact(name: str) -> list[dict]:
    """Return contacts whose name contains query (case-insensitive)."""
    contacts = get_all_contacts()
    name_lower = name.lower().strip()
    matches = [c for c in contacts if name_lower in c["name"].lower()]
    return matches


def update_cell(row: int, col: int, value: str) -> None:
    ws = _get_sheet()
    ws.update_cell(row, col + 1, value)  # gspread is 1-based


def append_to_cell(row: int, col: int, text: str) -> None:
    """Append dated text to cell, preserving existing content."""
    ws = _get_sheet()
    existing = ws.cell(row, col + 1).value or ""
    today = date.today().strftime("%d.%m")
    new_entry = f"{today}: {text}"
    if existing.strip():
        combined = existing.strip() + "\n" + new_entry
    else:
        combined = new_entry
    ws.update_cell(row, col + 1, combined)


def set_cell_color(row: int, col: int, color: dict) -> None:
    """Set background color of a cell using Sheets API v4."""
    creds = _get_creds()
    service = build("sheets", "v4", credentials=creds)
    sheet_id = _get_sheet_id()
    body = {
        "requests": [{
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": row - 1,
                    "endRowIndex": row,
                    "startColumnIndex": col,
                    "endColumnIndex": col + 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": color
                    }
                },
                "fields": "userEnteredFormat.backgroundColor"
            }
        }]
    }
    service.spreadsheets().batchUpdate(
        spreadsheetId=config.ASSISTANT_SPREADSHEET_ID,
        body=body
    ).execute()


def parse_deadline_date(event_date_str: str) -> Optional[date]:
    """Parse deadline string like 'до 26.04', '26.04.2026', '26.04' into a date."""
    if not event_date_str:
        return None
    s = event_date_str.strip().lower().replace("до ", "").strip()
    # Try dd.mm.yyyy
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    # Try dd.mm (assume current year)
    m = re.match(r"(\d{1,2})\.(\d{1,2})$", s)
    if m:
        try:
            today = date.today()
            d = date(today.year, int(m.group(2)), int(m.group(1)))
            # If date already passed this year, assume next year
            if d < today:
                d = date(today.year + 1, int(m.group(2)), int(m.group(1)))
            return d
        except ValueError:
            pass
    return None
