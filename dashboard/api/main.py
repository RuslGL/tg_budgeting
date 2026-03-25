import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import db
import sync

load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

DASHBOARD_SECRET = os.environ["DASHBOARD_SECRET"]
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(_sync_loop())
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


def _check(secret: str) -> None:
    if secret != DASHBOARD_SECRET:
        raise HTTPException(status_code=404)


@app.get("/favicon.png")
async def favicon():
    return FileResponse(STATIC_DIR / "favicon.png")


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
