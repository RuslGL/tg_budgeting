import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "food.db")


def _get_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def search_food(query: str) -> list[dict]:
    """Search food by name using FTS5. Falls back to LIKE if no FTS results."""
    if not os.path.exists(DB_PATH):
        return []
    conn = _get_conn()
    try:
        # FTS5: each word in query must appear in name
        fts_query = " ".join(f'"{w}"' for w in query.split() if w)
        rows = conn.execute(
            "SELECT name, calories, protein, fat, carbs FROM foods_fts WHERE foods_fts MATCH ? ORDER BY rank LIMIT 5",
            [fts_query],
        ).fetchall()
        if not rows:
            # Fallback: LIKE on each word
            conditions = " AND ".join(["name LIKE ?" for _ in query.split() if _])
            params = [f"%{w}%" for w in query.split() if w]
            if conditions:
                rows = conn.execute(
                    f"SELECT name, calories, protein, fat, carbs FROM foods_fts WHERE {conditions} LIMIT 5",
                    params,
                ).fetchall()
        return [
            {"name": r[0], "calories": r[1], "protein": r[2], "fat": r[3], "carbs": r[4]}
            for r in rows
        ]
    finally:
        conn.close()
