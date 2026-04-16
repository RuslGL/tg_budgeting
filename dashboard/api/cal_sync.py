import json
import logging
import os
import sqlite3

import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
DB_PATH = os.getenv("DB_PATH", "/data/dashboard.db")
SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
GOOGLE_CREDENTIALS = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])

logger = logging.getLogger(__name__)


def _f(v: str) -> float:
    return float(v.replace(",", "."))


def run_cal_sync() -> None:
    logger.info("cal_sync: starting")
    creds = Credentials.from_service_account_info(GOOGLE_CREDENTIALS, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(SPREADSHEET_ID)

    _sync_meals(sheet)
    _sync_weight(sheet)
    _sync_limits(sheet)
    logger.info("cal_sync: done")


def _sync_meals(sheet) -> None:
    rows = sheet.worksheet("cal_meals").get_all_values()
    records = []
    for row in rows[1:]:  # skip header
        if len(row) < 6 or not row[0].strip():
            continue
        try:
            records.append((
                row[0].strip(),        # id
                row[1].strip(),        # date
                row[2].strip(),        # time
                row[3].strip(),        # food_name
                _f(row[4]),            # grams
                _f(row[5]),            # calories
                _f(row[6]) if len(row) > 6 else 0.0,  # protein
                _f(row[7]) if len(row) > 7 else 0.0,  # fat
                _f(row[8]) if len(row) > 8 else 0.0,  # carbs
            ))
        except (ValueError, IndexError):
            continue
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM cal_meals")
        conn.executemany(
            "INSERT INTO cal_meals (meal_id, date, time, food_name, grams, calories, protein, fat, carbs) VALUES (?,?,?,?,?,?,?,?,?)",
            records,
        )
        conn.commit()
    logger.info("cal_meals sync: %d rows", len(records))


def _sync_weight(sheet) -> None:
    rows = sheet.worksheet("cal_weight").get_all_values()
    records = []
    for row in rows:
        if len(row) < 2 or not row[0].strip():
            continue
        try:
            records.append((row[0].strip(), float(row[1].replace(",", "."))))
        except ValueError:
            continue
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM cal_weight")
        conn.executemany("INSERT INTO cal_weight (date, weight) VALUES (?, ?)", records)
        conn.commit()
    logger.info("cal_weight sync: %d rows", len(records))


def _sync_limits(sheet) -> None:
    rows = sheet.worksheet("cal_limits").get_all_values()
    records = [(row[0].strip(), row[1].strip()) for row in rows if len(row) >= 2 and row[0].strip()]
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM cal_profile")
        conn.executemany("INSERT INTO cal_profile (field, value) VALUES (?, ?)", records)
        conn.commit()
    logger.info("cal_limits sync: %d rows", len(records))
