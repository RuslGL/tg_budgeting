import json
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.environ["BOT_TOKEN"]

_allowed_list = [int(uid.strip()) for uid in os.environ["ALLOWED_USERS"].split(",") if uid.strip()]
_names_list = [n.strip() for n in os.getenv("USERS_NAME", "").split(",") if n.strip()]

ALLOWED_USERS: set[int] = set(_allowed_list)
USER_NAMES: dict[int, str] = dict(zip(_allowed_list, _names_list))

OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]

SPREADSHEET_ID: str = os.environ["SPREADSHEET_ID"]

GOOGLE_CREDENTIALS: dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

COMPANY: str = os.getenv("COMPANY", "family")
CATEGORIES_SHEET: str = os.getenv("CATEGORIES_SHEET", "categories")

GOOGLE_CALENDAR_ID: str = os.getenv("GOOGLE_CALENDAR_ID", "")
CALENDAR_CATEGORIES: list[str] = [c.strip().lower() for c in os.getenv("CALENDAR_CATEGORIES", "Календарь").split(",") if c.strip()]

BOT_TOKEN_CALORIES: str = os.getenv("BOT_TOKEN_CALORIES", "")
CALORIES_SECRET: str = os.getenv("CALORIES_SECRET", "")
DASHBOARD_URL: str = os.getenv("DASHBOARD_URL", "http://dashboard:8080")
FATSECRET_CLIENT_ID: str = os.getenv("FATSECRET_CLIENT_ID", "")
FATSECRET_CLIENT_SECRET: str = os.getenv("FATSECRET_CLIENT_SECRET", "")

BOT_TOKEN_MAX: str = os.getenv("BOT_TOKEN_MAX", "")
_max_allowed_list = [uid.strip() for uid in os.getenv("MAX_ALLOWED_USERS", "").split(",") if uid.strip()]
_max_names_list = [n.strip() for n in os.getenv("MAX_USERS_NAME", "").split(",") if n.strip()]
MAX_ALLOWED_USERS: set[str] = set(_max_allowed_list)
MAX_USER_NAMES: dict[str, str] = dict(zip(_max_allowed_list, _max_names_list))

BOT_TOKEN_ASSISTANT: str = os.getenv("BOT_TOKEN_ASSISTANT", "")
ASSISTANT_SPREADSHEET_ID: str = os.getenv("ASSISTANT_SPREADSHEET_ID", "")
ASSISTANT_USER_ID: int = int(os.getenv("ASSISTANT_USER_ID", "666038149"))

PROXY_URL: str = os.getenv("PROXY_URL", "")
