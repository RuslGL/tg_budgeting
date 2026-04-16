import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "/data/dashboard.db")


def _project_clause(project: str | None) -> tuple[str, list]:
    if project and project != "all":
        return "AND project = ?", [project]
    return "", []


def get_months(company: str) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
            SELECT DISTINCT
                CAST(strftime('%Y', date) AS INTEGER) AS year,
                CAST(strftime('%m', date) AS INTEGER) AS month
            FROM transactions
            WHERE company = ?
            ORDER BY year DESC, month DESC
        """, (company,)).fetchall()
    return [{"year": r[0], "month": r[1]} for r in rows]


def get_projects(company: str) -> list[str]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
            SELECT DISTINCT project FROM transactions
            WHERE company = ? AND project != 'unknown' AND project != ''
            ORDER BY project
        """, (company,)).fetchall()
    return [r[0] for r in rows]


def get_month_by_author(year: int, month: int, company: str, project: str | None = None) -> list[dict]:
    month_str = f"{year:04d}-{month:02d}"
    pc, pp = _project_clause(project)
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(f"""
            SELECT category, author, SUM(amount) AS total
            FROM transactions
            WHERE strftime('%Y-%m', date) = ? AND type != 'Доход' AND company = ? {pc}
            GROUP BY category, author
        """, (month_str, company, *pp)).fetchall()
    return [{"category": r[0], "author": r[1], "total": r[2]} for r in rows]


def get_year_by_author(year: int, company: str, project: str | None = None) -> list[dict]:
    year_str = f"{year:04d}"
    pc, pp = _project_clause(project)
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(f"""
            SELECT category, author, SUM(amount) AS total
            FROM transactions
            WHERE strftime('%Y', date) = ? AND type != 'Доход' AND company = ? {pc}
            GROUP BY category, author
        """, (year_str, company, *pp)).fetchall()
    return [{"category": r[0], "author": r[1], "total": r[2]} for r in rows]


def get_year_data(year: int, company: str, project: str | None = None) -> list[dict]:
    year_str = f"{year:04d}"
    pc, pp = _project_clause(project)
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(f"""
            SELECT category, type, SUM(amount) AS total
            FROM transactions
            WHERE strftime('%Y', date) = ? AND company = ? {pc}
            GROUP BY category, type
            ORDER BY total DESC
        """, (year_str, company, *pp)).fetchall()
    return [{"category": r[0], "type": r[1], "total": r[2]} for r in rows]


def get_month_data(year: int, month: int, company: str, project: str | None = None) -> list[dict]:
    month_str = f"{year:04d}-{month:02d}"
    pc, pp = _project_clause(project)
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(f"""
            SELECT category, type, SUM(amount) AS total
            FROM transactions
            WHERE strftime('%Y-%m', date) = ? AND company = ? {pc}
            GROUP BY category, type
            ORDER BY total DESC
        """, (month_str, company, *pp)).fetchall()
    return [{"category": r[0], "type": r[1], "total": r[2]} for r in rows]
