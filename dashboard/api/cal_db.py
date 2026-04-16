import os
import sqlite3
from datetime import date, timedelta

DB_PATH = os.getenv("DB_PATH", "/data/dashboard.db")


def init_cal_tables() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        # Migrate: drop cal_meals if it has old schema (integer id instead of meal_id text)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(cal_meals)").fetchall()]
        if cols and "meal_id" not in cols:
            conn.execute("DROP TABLE cal_meals")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cal_meals (
                meal_id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                time TEXT NOT NULL DEFAULT '',
                food_name TEXT NOT NULL,
                grams REAL NOT NULL,
                calories REAL NOT NULL,
                protein REAL NOT NULL DEFAULT 0,
                fat REAL NOT NULL DEFAULT 0,
                carbs REAL NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cal_weight (
                date TEXT PRIMARY KEY,
                weight REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cal_profile (
                field TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            )
        """)
        conn.commit()


def get_today_meals(today: str) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT meal_id, date, time, food_name, grams, calories, protein, fat, carbs FROM cal_meals WHERE date = ? ORDER BY time, rowid",
            (today,),
        ).fetchall()
    return [
        {
            "id": r[0], "date": r[1], "time": r[2], "food_name": r[3],
            "grams": r[4], "calories": r[5], "protein": r[6], "fat": r[7], "carbs": r[8],
        }
        for r in rows
    ]


def get_today_macros(today: str) -> dict:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(calories),0), COALESCE(SUM(protein),0), COALESCE(SUM(fat),0), COALESCE(SUM(carbs),0) FROM cal_meals WHERE date = ?",
            (today,),
        ).fetchone()
    return {
        "calories": round(row[0]),
        "protein": round(row[1], 1),
        "fat": round(row[2], 1),
        "carbs": round(row[3], 1),
    }


def get_weight_history(days: int = 14) -> list[dict]:
    date_from = (date.today() - timedelta(days=days)).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT date, weight FROM cal_weight WHERE date >= ? ORDER BY date",
            (date_from,),
        ).fetchall()
    return [{"date": r[0], "weight": r[1]} for r in rows]


def get_calorie_history(days: int = 14) -> list[dict]:
    date_from = (date.today() - timedelta(days=days)).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT date, SUM(calories) FROM cal_meals WHERE date >= ? GROUP BY date ORDER BY date",
            (date_from,),
        ).fetchall()
    return [{"date": r[0], "calories": round(r[1])} for r in rows]


def get_cal_profile() -> dict:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT field, value FROM cal_profile").fetchall()
    return {r[0]: r[1] for r in rows}
