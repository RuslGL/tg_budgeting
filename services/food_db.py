"""Food KBJU lookup with three-tier fallback:
1. Local cache (food_cache) — exact/partial match, populated from FatSecret + GPT
2. FatSecret API — search by translated English name, store result in cache
3. GPT estimate — last resort, also stored in cache
"""
import logging
import os
import re
import sqlite3
import time

import requests

logger = logging.getLogger(__name__)

DB_PATH = os.getenv(
    "FOOD_DB_PATH",
    os.path.join(os.path.dirname(__file__), "..", "dashboard", "api", "food.db"),
)

_fs_token: str = ""
_fs_token_expires: float = 0.0


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS food_cache (
            name TEXT PRIMARY KEY,
            english_name TEXT NOT NULL DEFAULT '',
            calories REAL NOT NULL,
            protein REAL NOT NULL,
            fat REAL NOT NULL,
            carbs REAL NOT NULL,
            source TEXT NOT NULL DEFAULT 'gpt'
        )
    """)
    # Migrate: add english_name and source columns if missing
    cols = [r[1] for r in conn.execute("PRAGMA table_info(food_cache)").fetchall()]
    if "english_name" not in cols:
        conn.execute("ALTER TABLE food_cache ADD COLUMN english_name TEXT NOT NULL DEFAULT ''")
    if "source" not in cols:
        conn.execute("ALTER TABLE food_cache ADD COLUMN source TEXT NOT NULL DEFAULT 'gpt'")
    conn.commit()
    return conn


def _row_to_dict(row: tuple) -> dict:
    return {
        "name": row[0], "english_name": row[1],
        "calories": row[2], "protein": row[3], "fat": row[4], "carbs": row[5],
        "source": row[6],
    }


def _normalize(s: str) -> str:
    return " ".join(s.strip().lower().split())


def search_cache(query: str) -> dict | None:
    """Search local cache only."""
    if not os.path.exists(DB_PATH):
        return None
    conn = _get_conn()
    query = _normalize(query)
    try:
        row = conn.execute(
            "SELECT name, english_name, calories, protein, fat, carbs, source FROM food_cache WHERE LOWER(name) = ?",
            (query,),
        ).fetchone()
        if row:
            return _row_to_dict(row)

        words = [w for w in query.lower().split() if len(w) > 2]
        if words:
            conditions = " AND ".join(["LOWER(name) LIKE ?" for _ in words])
            params = [f"%{w}%" for w in words]
            row = conn.execute(
                f"SELECT name, english_name, calories, protein, fat, carbs, source FROM food_cache WHERE {conditions} LIMIT 1",
                params,
            ).fetchone()
            if row:
                return _row_to_dict(row)
        return None
    finally:
        conn.close()


def save_food(name: str, english_name: str, calories: float, protein: float, fat: float, carbs: float, source: str = "gpt") -> None:
    """Save food to cache (per 100g values)."""
    name = _normalize(name)
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO food_cache (name, english_name, calories, protein, fat, carbs, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, english_name, calories, protein, fat, carbs, source),
        )
        conn.commit()
    finally:
        conn.close()


def _get_fatsecret_token() -> str:
    global _fs_token, _fs_token_expires
    if _fs_token and time.time() < _fs_token_expires - 60:
        return _fs_token
    client_id = os.getenv("FATSECRET_CLIENT_ID", "")
    client_secret = os.getenv("FATSECRET_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return ""
    try:
        r = requests.post(
            "https://oauth.fatsecret.com/connect/token",
            data={"grant_type": "client_credentials", "scope": "basic"},
            auth=(client_id, client_secret),
            timeout=10,
        )
        data = r.json()
        _fs_token = data.get("access_token", "")
        _fs_token_expires = time.time() + data.get("expires_in", 86400)
        return _fs_token
    except Exception as e:
        logger.warning("FatSecret token error: %s", e)
        return ""


def _parse_per100g(serving: dict) -> dict | None:
    """Extract per-100g nutrition from a serving dict."""
    try:
        amount = float(serving.get("metric_serving_amount", 0))
        unit = serving.get("metric_serving_unit", "")
        if unit != "g" or amount <= 0:
            return None
        ratio = 100.0 / amount
        return {
            "calories": round(float(serving["calories"]) * ratio, 1),
            "protein": round(float(serving["protein"]) * ratio, 1),
            "fat": round(float(serving["fat"]) * ratio, 1),
            "carbs": round(float(serving["carbohydrate"]) * ratio, 1),
        }
    except (KeyError, ValueError, ZeroDivisionError):
        return None


def _fs_search_raw(token: str, query: str) -> list:
    """Raw FatSecret search, returns list of food dicts."""
    r = requests.get(
        "https://platform.fatsecret.com/rest/server.api",
        headers={"Authorization": f"Bearer {token}"},
        params={"method": "foods.search", "search_expression": query, "max_results": 5, "format": "json"},
        timeout=10,
    )
    foods = r.json().get("foods", {}).get("food", [])
    if isinstance(foods, dict):
        foods = [foods]
    return foods or []


def _make_query_variants(english_name: str) -> list[str]:
    """Generate query variants to improve FatSecret hit rate."""
    variants = [english_name]
    words = english_name.split()
    # Try reversed word order (e.g. "boiled chicken breast" -> "chicken breast boiled")
    if len(words) >= 2 and words[0] in ("boiled", "fried", "steamed", "baked", "grilled", "stewed", "smoked", "raw", "cooked"):
        variants.append(" ".join(words[1:] + [words[0]]))
    # Replace cooking synonyms
    replacements = {"boiled": "cooked", "steamed": "cooked", "stewed": "cooked"}
    for old, new in replacements.items():
        if old in english_name:
            variants.append(english_name.replace(old, new))
    return variants


def search_fatsecret(english_name: str) -> dict | None:
    """Search FatSecret by English name. Returns per-100g dict or None."""
    token = _get_fatsecret_token()
    if not token:
        return None
    try:
        foods = []
        for query in _make_query_variants(english_name):
            foods = _fs_search_raw(token, query)
            if foods:
                logger.info("FatSecret found %d results for query: %s", len(foods), query)
                break
        if not foods:
            return None

        # Prefer Generic type, exclude heavily processed variants
        EXCLUDE = ("coated", "breaded", "stuffed", "battered", "nugget", "patty", "sandwich", "burger")
        generic = [f for f in foods if f.get("food_type") == "Generic"]
        if not generic:
            generic = foods
        clean = [f for f in generic if not any(w in f.get("food_name", "").lower() for w in EXCLUDE)]
        candidate = clean[0] if clean else generic[0]
        food_id = candidate["food_id"]

        # Get full nutrition
        r2 = requests.get(
            "https://platform.fatsecret.com/rest/server.api",
            headers={"Authorization": f"Bearer {token}"},
            params={"method": "food.get.v4", "food_id": food_id, "format": "json"},
            timeout=10,
        )
        servings = r2.json().get("food", {}).get("servings", {}).get("serving", [])
        if isinstance(servings, dict):
            servings = [servings]

        # Find 100g serving first, then normalize any other
        for s in servings:
            if s.get("serving_description", "").strip() == "100 g":
                result = _parse_per100g(s)
                if result:
                    return result

        for s in servings:
            result = _parse_per100g(s)
            if result:
                return result

        return None
    except Exception as e:
        logger.warning("FatSecret search error for '%s': %s", english_name, e)
        return None


def get_cache_stats() -> dict:
    """Return cache statistics."""
    if not os.path.exists(DB_PATH):
        return {"total": 0, "fatsecret": 0, "gpt": 0}
    conn = _get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM food_cache").fetchone()[0]
        fatsecret = conn.execute("SELECT COUNT(*) FROM food_cache WHERE source = 'fatsecret'").fetchone()[0]
        gpt = conn.execute("SELECT COUNT(*) FROM food_cache WHERE source = 'gpt'").fetchone()[0]
        return {"total": total, "fatsecret": fatsecret, "gpt": gpt}
    finally:
        conn.close()
