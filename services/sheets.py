import time
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

import config

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_client: Optional[gspread.Client] = None
_categories_cache: Optional[list[str]] = None
_categories_cached_at: float = 0
CACHE_TTL = 600  # 10 minutes


def _get_client() -> gspread.Client:
    global _client
    if _client is None:
        creds = Credentials.from_service_account_info(config.GOOGLE_CREDENTIALS, scopes=SCOPES)
        _client = gspread.authorize(creds)
    return _client


def get_categories() -> list[str]:
    global _categories_cache, _categories_cached_at
    now = time.time()
    if _categories_cache is not None and now - _categories_cached_at < CACHE_TTL:
        return _categories_cache

    client = _get_client()
    sheet = client.open_by_key(config.SPREADSHEET_ID)
    ws = sheet.worksheet("categories")
    rows = ws.get_all_values()
    # First row is header: categorie, type
    _categories_cache = [row[0] for row in rows[1:] if row and row[0].strip()]
    _categories_cached_at = now
    return _categories_cache


def append_transaction(date: str, category: str, amount: float, original_text: str) -> None:
    client = _get_client()
    sheet = client.open_by_key(config.SPREADSHEET_ID)
    ws = sheet.worksheet("raw")
    ws.append_row([date, category, amount, original_text])
