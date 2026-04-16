"""
One-time script to build food database from OpenFoodFacts API.
Searches common Russian food keywords and stores results in SQLite with FTS5.

Run from project root:
    python scripts/build_food_db.py
"""
import logging
import os
import sqlite3
import time

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = os.getenv(
    "FOOD_DB_PATH",
    os.path.join(os.path.dirname(__file__), "..", "dashboard", "api", "food.db"),
)
API_URL = "https://world.openfoodfacts.org/cgi/search.pl"

SEARCH_QUERIES = [
    "куриная грудка", "говядина", "свинина", "индейка", "лосось", "треска", "тунец", "минтай",
    "яйцо", "молоко", "кефир", "йогурт", "творог", "сыр", "сметана", "масло сливочное",
    "хлеб", "макароны", "рис", "гречка", "овсянка", "геркулес", "перловка", "пшено",
    "картофель", "морковь", "капуста", "огурец", "помидор", "лук", "свекла", "кабачок",
    "яблоко", "банан", "апельсин", "виноград", "груша", "слива",
    "подсолнечное масло", "оливковое масло", "сахар", "мука пшеничная",
    "грецкий орех", "миндаль", "арахис", "фундук",
    "колбаса", "сосиски", "ветчина",
    "шоколад", "мёд", "варенье",
]


def create_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS foods_fts USING fts5(
            name,
            calories UNINDEXED,
            protein UNINDEXED,
            fat UNINDEXED,
            carbs UNINDEXED
        )
    """)
    conn.commit()


HEADERS = {
    "User-Agent": "CalorieBot/1.0 (personal calorie tracker; ruslanglotov@gmail.com)",
    "Accept": "application/json",
}


def fetch_products(query: str, retries: int = 3) -> list[dict]:
    params = {
        "search_terms": query,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": 50,
        "fields": "product_name,product_name_ru,nutriments",
        "lc": "ru",
    }
    for attempt in range(retries):
        try:
            r = requests.get(API_URL, params=params, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return r.json().get("products", [])
        except Exception as e:
            wait = 2 ** attempt * 2
            logger.warning("Failed to fetch '%s' (attempt %d): %s — retrying in %ds", query, attempt + 1, e, wait)
            time.sleep(wait)
    return []


def parse_product(p: dict) -> tuple | None:
    name = (p.get("product_name_ru") or p.get("product_name") or "").strip()
    if not name or len(name) > 120:
        return None
    n = p.get("nutriments", {})
    calories = n.get("energy-kcal_100g")
    if calories is None:
        energy = n.get("energy_100g")
        if energy and n.get("energy_unit", "").lower() == "kj":
            calories = energy / 4.184
        elif energy:
            calories = energy
    protein = n.get("proteins_100g")
    fat = n.get("fat_100g")
    carbs = n.get("carbohydrates_100g")
    if any(v is None for v in [calories, protein, fat, carbs]):
        return None
    calories, protein, fat, carbs = float(calories), float(protein), float(fat), float(carbs)
    if not (5 < calories < 950):
        return None
    if not (0 <= protein <= 100) or not (0 <= fat <= 100) or not (0 <= carbs <= 100):
        return None
    return (name, round(calories, 1), round(protein, 1), round(fat, 1), round(carbs, 1))


def main() -> None:
    db_dir = os.path.dirname(DB_PATH)
    os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    create_db(conn)

    seen_names: set[str] = set()
    total = 0

    for query in SEARCH_QUERIES:
        logger.info("Fetching: %s", query)
        products = fetch_products(query)
        batch = []
        for p in products:
            parsed = parse_product(p)
            if parsed and parsed[0].lower() not in seen_names:
                seen_names.add(parsed[0].lower())
                batch.append(parsed)
        if batch:
            conn.executemany(
                "INSERT INTO foods_fts (name, calories, protein, fat, carbs) VALUES (?, ?, ?, ?, ?)",
                batch,
            )
            conn.commit()
            total += len(batch)
            logger.info("  Added %d products (total: %d)", len(batch), total)
        else:
            logger.info("  No new products")
        time.sleep(1.5)

    conn.close()
    logger.info("Done. Total unique products in DB: %d", total)


if __name__ == "__main__":
    main()
