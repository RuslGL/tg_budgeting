import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

import db
import notes_db
import notes_sync
import sync

load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

DASHBOARD_SECRET = os.environ["DASHBOARD_SECRET"]
NOTES_SECRET = os.environ["NOTES_SECRET"]
STATIC_DIR = Path(__file__).parent / "frontend" / "dist"


async def _sync_loop() -> None:
    sync.init_db()
    while True:
        try:
            count = sync.run_sync()
            logger.info("Sync complete: %d rows", count)
        except Exception as e:
            logger.error("Sync error: %s", e)
        await asyncio.sleep(3600)


async def _notes_sync_loop() -> None:
    notes_db.init_notes_table()
    while True:
        try:
            count = notes_sync.run_notes_sync()
            logger.debug("Notes sync complete: %d rows", count)
        except Exception as e:
            logger.error("Notes sync error: %s", e)
        await asyncio.sleep(10)


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(_sync_loop())
    asyncio.create_task(_notes_sync_loop())
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


def _check(secret: str) -> None:
    if secret != DASHBOARD_SECRET:
        raise HTTPException(status_code=404)


def _check_notes(secret: str) -> None:
    if secret != NOTES_SECRET:
        raise HTTPException(status_code=404)


@app.get("/favicon.png")
async def favicon():
    return FileResponse(STATIC_DIR / "favicon.png")


@app.get("/favicon-notes.svg")
async def favicon_notes():
    return FileResponse(STATIC_DIR / "favicon-notes.svg", media_type="image/svg+xml")


@app.get("/favicon-budget.svg")
async def favicon_budget():
    return FileResponse(STATIC_DIR / "favicon-budget.svg", media_type="image/svg+xml")


@app.get("/d/{secret}")
async def index(secret: str):
    _check(secret)
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/d/{secret}/api/months")
async def months(secret: str, company: str = "family"):
    _check(secret)
    return db.get_months(company)


@app.get("/d/{secret}/api/month")
async def month(secret: str, year: int, month: int, company: str = "family"):
    _check(secret)
    return db.get_month_data(year, month, company)


@app.get("/d/{secret}/api/year")
async def year(secret: str, year: int, company: str = "family"):
    _check(secret)
    return db.get_year_data(year, company)


@app.get("/d/{secret}/api/month/by-author")
async def month_by_author(secret: str, year: int, month: int, company: str = "family"):
    _check(secret)
    return db.get_month_by_author(year, month, company)


@app.get("/d/{secret}/api/year/by-author")
async def year_by_author(secret: str, year: int, company: str = "family"):
    _check(secret)
    return db.get_year_by_author(year, company)


@app.get("/n/{secret}")
async def notes_index(secret: str):
    _check_notes(secret)
    svg_path = STATIC_DIR / "favicon-notes.svg"
    logger.info("favicon-notes.svg exists: %s, path: %s", svg_path.exists(), svg_path)
    html = (STATIC_DIR / "index.html").read_text()
    patched = html.replace(
        "</head>",
        '<link rel="icon" type="image/svg+xml" href="/favicon-notes.svg" /></head>',
    )
    logger.info("head patched: %s", "</head>" not in patched or "favicon-notes" in patched)
    return HTMLResponse(patched)


@app.get("/n/{secret}/api/categories")
async def note_categories(secret: str):
    _check_notes(secret)
    return notes_db.get_note_categories()


@app.get("/n/{secret}/api/notes")
async def notes_list(
    secret: str,
    category: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
):
    _check_notes(secret)
    return notes_db.get_notes(category, date_from, date_to)


@app.delete("/n/{secret}/api/note/{note_id}")
async def delete_note(secret: str, note_id: str):
    _check_notes(secret)
    try:
        notes_sync.delete_note_from_sheets(note_id)
    except Exception as e:
        logger.error("Sheets delete error: %s", e)
    notes_db.delete_note_local(note_id)
    return {"ok": True}
