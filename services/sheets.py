import time
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

import config

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_client: Optional[gspread.Client] = None
_categories_cache: Optional[list[str]] = None
_category_types: dict[str, str] = {}
_categories_cached_at: float = 0
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
    ws = sheet.worksheet("categories")
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


def append_transaction(date: str, category: str, amount: float, original_text: str) -> None:
    type_ = get_category_type(category)
    client = _get_client()
    sheet = client.open_by_key(config.SPREADSHEET_ID)
    ws = sheet.worksheet("raw")
    ws.append_row([date, category, type_, amount, original_text])
