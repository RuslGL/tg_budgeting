import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "/data/dashboard.db")


def get_months() -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
            SELECT DISTINCT
                CAST(strftime('%Y', date) AS INTEGER) AS year,
                CAST(strftime('%m', date) AS INTEGER) AS month
            FROM transactions
            ORDER BY year DESC, month DESC
        """).fetchall()
    return [{"year": r[0], "month": r[1]} for r in rows]


def get_year_data(year: int) -> list[dict]:
    year_str = f"{year:04d}"
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
            SELECT category, type, SUM(amount) AS total
            FROM transactions
            WHERE strftime('%Y', date) = ?
            GROUP BY category, type
            ORDER BY total DESC
        """, (year_str,)).fetchall()
    return [{"category": r[0], "type": r[1], "total": r[2]} for r in rows]


def get_month_data(year: int, month: int) -> list[dict]:
    month_str = f"{year:04d}-{month:02d}"
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
            SELECT category, type, SUM(amount) AS total
            FROM transactions
            WHERE strftime('%Y-%m', date) = ?
            GROUP BY category, type
            ORDER BY total DESC
        """, (month_str,)).fetchall()
    return [{"category": r[0], "type": r[1], "total": r[2]} for r in rows]
